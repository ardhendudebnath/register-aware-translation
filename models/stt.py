"""
Speech-to-text.

Tries three backends in order of quality, and reports honestly when none is
available rather than returning a placeholder string:

1. ``faster-whisper`` — CTranslate2 build, several times quicker than the
   reference implementation on CPU, which matters because the blueprint's
   latency budget gives ASR 200-400 ms.
2. ``openai-whisper`` — the reference implementation.
3. Nothing — :func:`transcribe_audio_chunk` returns a result with
   ``ok=False`` and a message the UI can show.

Browser-side ``SpeechRecognition`` remains the zero-cost default for the web
client (blueprint 4, Tier B); this module is the server-side path used when the
browser cannot do it, which per blueprint 8 is the common case on iOS.

The previous implementation returned the literal string "Hello world".
"""

from __future__ import annotations

import base64
import binascii
import io
import os
import tempfile
import wave
from dataclasses import dataclass, field
from functools import lru_cache
from typing import List, Optional, Tuple

__all__ = ["Transcript", "transcribe_audio_chunk", "transcribe_file", "available_backend"]

#: Whisper model size. Small enough to run on a laptop; override with
#: SETU_WHISPER_MODEL=small for better accuracy on Indic languages.
MODEL_SIZE = os.environ.get("SETU_WHISPER_MODEL", "base")

_NO_BACKEND_MESSAGE = (
    "No speech-to-text backend is installed. Either use the browser's built-in "
    "speech recognition, or install one:\n"
    "    pip install faster-whisper"
)


@dataclass
class Transcript:
    text: str = ""
    language: Optional[str] = None
    ok: bool = True
    message: str = ""
    duration_s: float = 0.0
    segments: List[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "text": self.text,
            "language": self.language,
            "ok": self.ok,
            "message": self.message,
            "duration_s": round(self.duration_s, 3),
            "segments": self.segments,
        }


def available_backend() -> Optional[str]:
    """Which STT backend is installed, if any."""
    try:
        import faster_whisper  # noqa: F401
        return "faster-whisper"
    except ImportError:
        pass
    try:
        import whisper  # noqa: F401
        return "openai-whisper"
    except ImportError:
        return None


def transcribe_audio_chunk(audio_data, language: Optional[str] = None) -> Transcript:
    """
    Transcribe one chunk of audio.

    ``audio_data`` may be raw bytes, a base64 string, or a data URL — the
    browser sends whichever is convenient and the caller should not have to
    care. Anything unreadable comes back as ``ok=False`` with a reason.
    """
    try:
        payload = _coerce_audio(audio_data)
    except ValueError as exc:
        return Transcript(ok=False, message=str(exc))

    if not payload:
        return Transcript(ok=False, message="Empty audio payload.")

    backend = available_backend()
    if backend is None:
        return Transcript(ok=False, message=_NO_BACKEND_MESSAGE)

    suffix = _guess_suffix(payload)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(payload)
            tmp_path = tmp.name
        return transcribe_file(tmp_path, language=language)
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def transcribe_file(path: str, language: Optional[str] = None) -> Transcript:
    """Transcribe an audio file already on disk."""
    backend = available_backend()
    if backend is None:
        return Transcript(ok=False, message=_NO_BACKEND_MESSAGE)

    try:
        if backend == "faster-whisper":
            return _transcribe_faster_whisper(path, language)
        return _transcribe_openai_whisper(path, language)
    except Exception as exc:  # noqa: BLE001 - surface, never crash the socket
        return Transcript(ok=False, message=f"Transcription failed: {exc}")


def _transcribe_faster_whisper(path: str, language: Optional[str]) -> Transcript:
    model = _load_faster_whisper()
    segments, info = model.transcribe(
        path,
        language=language,
        beam_size=1,            # greedy: the latency budget does not allow beams
        vad_filter=True,        # endpointing, per blueprint 5.2
        condition_on_previous_text=False,
    )
    collected = []
    parts = []
    for seg in segments:
        parts.append(seg.text)
        collected.append({"start": seg.start, "end": seg.end, "text": seg.text.strip()})
    return Transcript(
        text="".join(parts).strip(),
        language=getattr(info, "language", None) or language,
        duration_s=float(getattr(info, "duration", 0.0) or 0.0),
        segments=collected,
    )


def _transcribe_openai_whisper(path: str, language: Optional[str]) -> Transcript:
    model = _load_openai_whisper()
    result = model.transcribe(path, language=language, fp16=False)
    segments = [
        {"start": s.get("start"), "end": s.get("end"), "text": (s.get("text") or "").strip()}
        for s in result.get("segments", [])
    ]
    return Transcript(
        text=(result.get("text") or "").strip(),
        language=result.get("language") or language,
        segments=segments,
    )


@lru_cache(maxsize=1)
def _load_faster_whisper():
    from faster_whisper import WhisperModel

    return WhisperModel(MODEL_SIZE, device="auto", compute_type="int8")


@lru_cache(maxsize=1)
def _load_openai_whisper():
    import whisper

    return whisper.load_model(MODEL_SIZE)


def _coerce_audio(audio_data) -> bytes:
    """Accept bytes, base64, or a data: URL and return raw bytes."""
    if audio_data is None:
        return b""
    if isinstance(audio_data, (bytes, bytearray, memoryview)):
        return bytes(audio_data)
    if isinstance(audio_data, str):
        payload = audio_data
        if payload.startswith("data:"):
            _, _, payload = payload.partition(",")
        payload = payload.strip()
        if not payload:
            return b""
        try:
            return base64.b64decode(payload, validate=False)
        except (binascii.Error, ValueError) as exc:
            raise ValueError(f"Audio payload is not valid base64: {exc}") from None
    raise ValueError(f"Unsupported audio payload type: {type(audio_data).__name__}")


def _guess_suffix(payload: bytes) -> str:
    """
    Sniff the container so ffmpeg is handed a sensibly named file. Browsers
    send WebM/Opus from MediaRecorder; files may be WAV, MP3 or OGG.
    """
    if payload[:4] == b"RIFF":
        return ".wav"
    if payload[:4] == b"\x1aE\xdf\xa3":
        return ".webm"
    if payload[:4] == b"OggS":
        return ".ogg"
    if payload[:3] == b"ID3" or payload[:2] in (b"\xff\xfb", b"\xff\xf3"):
        return ".mp3"
    if payload[4:8] == b"ftyp":
        return ".m4a"
    return ".webm"
