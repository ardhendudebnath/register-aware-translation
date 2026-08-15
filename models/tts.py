"""
Text-to-speech, with prosody driven by register.

Formal speech is not only different words — it is slower, lower and more evenly
paced, with longer pauses. Nobody makes prosody follow the *register*
(blueprint 13.2 #4), so this module wires the register level straight into the
synthesis parameters: a Formal rendering comes out about 10% slower than a
Casual one, which makes formal output *sound* formal rather than merely read as
formal.

Returns base64 audio plus the prosody actually applied, so the browser can use
its own on-device voices — which are already installed, cost nothing, and are
the offline path from blueprint 6 — and still honour the register.

The previous implementation returned b"dummy_audio_data".
"""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass, field
from typing import Dict, Optional

from register import CASUAL, coerce_level, level_name, prosody

__all__ = ["Speech", "generate_speech", "available_backend"]

#: gTTS language codes differ from ISO 639-1 in a few places.
_GTTS_ALIASES = {
    "nb": "no",
    "he": "iw",
    "zh": "zh-CN",
    "pt": "pt",
}


@dataclass
class Speech:
    audio_b64: str = ""
    mime_type: str = "audio/mpeg"
    engine: str = "none"
    ok: bool = True
    message: str = ""
    language: str = ""
    prosody: Dict[str, float] = field(default_factory=dict)

    @property
    def audio_bytes(self) -> bytes:
        return base64.b64decode(self.audio_b64) if self.audio_b64 else b""

    def as_dict(self) -> dict:
        return {
            "audio_b64": self.audio_b64,
            "mime_type": self.mime_type,
            "engine": self.engine,
            "ok": self.ok,
            "message": self.message,
            "language": self.language,
            "prosody": self.prosody,
        }


def available_backend() -> Optional[str]:
    try:
        import gtts  # noqa: F401
        return "gtts"
    except ImportError:
        return None


def generate_speech(
    text: str,
    target_lang: str = "en",
    register_level=CASUAL,
    *,
    allow_network: bool = True,
) -> Speech:
    """
    Synthesise ``text``.

    ``register_level`` sets rate, pitch floor and inter-clause pause length.
    Even when no server-side engine is available the prosody is still returned,
    because the browser's own `speechSynthesis` can apply it — that path is
    free, works offline, and is the default for the web client.
    """
    level = coerce_level(register_level)
    voice = prosody(level)
    lang = _norm(target_lang)

    if not isinstance(text, str) or not text.strip():
        return Speech(ok=False, message="Nothing to speak.", language=lang, prosody=voice)

    backend = available_backend()
    if backend is None:
        return Speech(
            ok=False,
            engine="client-side",
            message=(
                "No server-side TTS installed; use the browser's speech synthesis. "
                "To enable server-side audio: pip install gTTS"
            ),
            language=lang,
            prosody=voice,
        )

    if not allow_network:
        return Speech(
            ok=False,
            engine="client-side",
            message="gTTS needs network; falling back to browser speech synthesis.",
            language=lang,
            prosody=voice,
        )

    try:
        from gtts import gTTS

        buffer = io.BytesIO()
        # gTTS exposes one speed switch rather than a rate multiplier, so the
        # polite/formal half of the scale gets the slow setting and the browser
        # applies the finer-grained rate from `prosody` on top.
        gTTS(
            text=text,
            lang=_GTTS_ALIASES.get(lang, lang) or "en",
            slow=voice["rate"] < 1.0,
        ).write_to_fp(buffer)
        payload = buffer.getvalue()
    except Exception as exc:  # noqa: BLE001
        return Speech(
            ok=False,
            engine="client-side",
            message=f"TTS failed ({exc}); falling back to browser speech synthesis.",
            language=lang,
            prosody=voice,
        )

    if not payload:
        return Speech(ok=False, engine="client-side", message="TTS produced no audio.",
                      language=lang, prosody=voice)

    return Speech(
        audio_b64=base64.b64encode(payload).decode("ascii"),
        mime_type="audio/mpeg",
        engine="gtts",
        language=lang,
        prosody=voice,
    )


def _norm(code) -> str:
    if not isinstance(code, str):
        return "en"
    return code.strip().lower().replace("_", "-").split("-")[0] or "en"
