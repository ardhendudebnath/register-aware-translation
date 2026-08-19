"""
The three-stage pipeline: pre-edit, translate, post-edit.

    speech -> ASR -> PRE-EDIT -> [MT] -> REGISTER POST-EDIT -> TTS -> speech

The middle box is swappable and knows nothing about register. The stage either
side is Setu's actual product (blueprint 3.3), and being deterministic string
processing it costs about nothing and keeps working with no network.

Two properties fall out of arranging it this way, and both are things a system
that treats register as part of translation cannot do:

*Offline re-levelling.* A phrase cached at Polite can be re-rendered at Formal
with no round trip, because the register layer never left the client.

*Asymmetric conversations.* Your uncle says তুই to you and you say আপনি back.
:func:`translate_text` takes one register per direction, so the elder speaks
down and you speak up without anyone touching a control (blueprint 13.2 #2).
"""

from __future__ import annotations

import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from models import classifier, stt, translator, tts
from register import (
    AUTO,
    CASUAL,
    Detection,
    LEVELS,
    RewriteResult,
    address_term,
    coerce_level,
    detect as detect_register,
    formality_percent,
    has_table,
    ladder as register_ladder,
    level_name,
    politeness_warning,
    pre_edit,
    prosody,
    rewrite as register_rewrite,
)
from utils.helpers import PROJECT_ROOT, load_slang_dictionary, normalise_text
from utils.slang_detection import detect_slang

__all__ = ["ExchangeResult", "Phrasebook", "translate_text", "translate_audio"]

PHRASEBOOK_PATH = PROJECT_ROOT / "data" / "phrasebook.sqlite3"


@dataclass
class ExchangeResult:
    """Everything one utterance produced, ready to serialise to the client."""

    original_text: str = ""
    translated_text: str = ""
    source_language: str = ""
    target_language: str = ""
    register_level: int = CASUAL
    detected_level: Optional[int] = None
    #: How sure the reading was. Kept because a claim about how someone is
    #: speaking to you has to be able to say how firm the evidence is —
    #: see :class:`~pipeline.conversation.RegisterShift`.
    detected_confidence: float = 0.0
    formality_percent: int = 50
    engine: str = ""
    cached: bool = False
    ok: bool = True
    message: str = ""
    edits: List[dict] = field(default_factory=list)
    detected_slang: List[dict] = field(default_factory=list)
    ladder: Dict[str, str] = field(default_factory=dict)
    warning: Optional[str] = None
    audio: Optional[dict] = None
    prosody: Dict[str, float] = field(default_factory=dict)
    timings_ms: Dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "original_text": self.original_text,
            "translated_text": self.translated_text,
            "source_language": self.source_language,
            "target_language": self.target_language,
            "register_level": self.register_level,
            "register_name": level_name(self.register_level),
            "detected_level": self.detected_level,
            "detected_register_name": (
                level_name(self.detected_level) if self.detected_level is not None else None
            ),
            "detected_confidence": round(self.detected_confidence, 3),
            "formality_percentage": self.formality_percent,
            "engine": self.engine,
            "cached": self.cached,
            "ok": self.ok,
            "message": self.message,
            "edits": self.edits,
            "detected_slang": self.detected_slang,
            "ladder": self.ladder,
            "warning": self.warning,
            "audio": self.audio,
            "prosody": self.prosody,
            "timings_ms": self.timings_ms,
        }


class Phrasebook:
    """
    Every translation is written here, keyed by source/target/text.

    Repeats are then free — which matters twice over. Offline it is the only
    thing that works, and online it makes the app feel faster, because in real
    conversations people repeat themselves constantly (blueprint 6, 7).

    Crucially the key does *not* include the register: one cached MT output can
    be re-levelled to any of the four registers with no network at all.
    """

    def __init__(self, path: Path = PHRASEBOOK_PATH):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        #: Set once the path proves unusable, so we stop retrying on every call.
        self._broken = False

    def _connect(self) -> Optional[sqlite3.Connection]:
        if self._conn is not None:
            return self._conn
        if self._broken:
            return None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.path, check_same_thread=False)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS phrases (
                    source_lang TEXT NOT NULL,
                    target_lang TEXT NOT NULL,
                    source_text TEXT NOT NULL,
                    translated  TEXT NOT NULL,
                    engine      TEXT NOT NULL DEFAULT '',
                    created_at  REAL NOT NULL,
                    hits        INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (source_lang, target_lang, source_text)
                )
                """
            )
            conn.commit()
            self._conn = conn
            return conn
        except (sqlite3.Error, OSError, ValueError):
            # A read-only, missing or invalid data directory must not take the
            # app down — the cache is an optimisation, not a dependency.
            # OSError/ValueError matter as much as sqlite3.Error here: mkdir is
            # what fails first on a bad path.
            self._broken = True
            return None

    def get(self, source_lang: str, target_lang: str, text: str) -> Optional[str]:
        conn = self._connect()
        if conn is None:
            return None
        key = (source_lang, target_lang, normalise_text(text))
        try:
            with self._lock:
                row = conn.execute(
                    "SELECT translated FROM phrases "
                    "WHERE source_lang=? AND target_lang=? AND source_text=?",
                    key,
                ).fetchone()
                if row:
                    conn.execute(
                        "UPDATE phrases SET hits = hits + 1 "
                        "WHERE source_lang=? AND target_lang=? AND source_text=?",
                        key,
                    )
                    conn.commit()
                    return row[0]
        except sqlite3.Error:
            return None
        return None

    def put(self, source_lang: str, target_lang: str, text: str,
            translated: str, engine: str = "") -> None:
        conn = self._connect()
        if conn is None or not translated.strip():
            return
        try:
            with self._lock:
                conn.execute(
                    "INSERT OR REPLACE INTO phrases "
                    "(source_lang, target_lang, source_text, translated, engine, created_at, hits) "
                    "VALUES (?,?,?,?,?,?,COALESCE("
                    "  (SELECT hits FROM phrases WHERE source_lang=? AND target_lang=? AND source_text=?), 0))",
                    (source_lang, target_lang, normalise_text(text), translated, engine,
                     time.time(), source_lang, target_lang, normalise_text(text)),
                )
                conn.commit()
        except sqlite3.Error:
            pass

    def stats(self) -> Dict[str, int]:
        conn = self._connect()
        if conn is None:
            return {"phrases": 0, "hits": 0}
        try:
            with self._lock:
                row = conn.execute(
                    "SELECT COUNT(*), COALESCE(SUM(hits), 0) FROM phrases"
                ).fetchone()
            return {"phrases": int(row[0]), "hits": int(row[1])}
        except sqlite3.Error:
            return {"phrases": 0, "hits": 0}


_phrasebook = Phrasebook()


def translate_text(
    text: str,
    target_lang: str,
    source_lang: Optional[str] = None,
    register_level=AUTO,
    *,
    addressee: Optional[str] = None,
    speaker_gender: Optional[str] = None,
    soften: bool = False,
    with_ladder: bool = True,
    with_audio: bool = False,
    allow_network: bool = True,
    phrasebook: Optional[Phrasebook] = None,
) -> ExchangeResult:
    """
    Run one utterance end to end.

    ``register_level`` accepts a level, a name ("polite"), or ``AUTO`` to detect
    the speaker's own register and mirror it into the target.
    """
    book = phrasebook if phrasebook is not None else _phrasebook
    timings: Dict[str, float] = {}
    result = ExchangeResult(original_text=text or "")

    if not isinstance(text, str) or not text.strip():
        result.ok = False
        result.message = "Nothing to translate."
        return result

    # --- language identification -----------------------------------------
    t0 = time.perf_counter()
    src = _norm(source_lang) or classifier.detect_language(text)
    tgt = _norm(target_lang)
    result.source_language, result.target_language = src, tgt
    timings["language_id"] = _ms(t0)

    # --- read the speaker's own register ---------------------------------
    t0 = time.perf_counter()
    source_reading: Detection = detect_register(text, src) if has_table(src) else Detection(
        level=None, confidence=0.0, language=src
    )
    result.detected_level = source_reading.level
    result.detected_confidence = source_reading.confidence

    slang = detect_slang(text, load_slang_dictionary(), src)
    result.detected_slang = [m.as_dict() for m in slang]

    if register_level == AUTO:
        if source_reading.level is not None:
            target_level = source_reading.level
        else:
            # No grammatical register in the source (English, say) — fall back
            # to the formality classifier so Auto still means something.
            reading = classifier.classify_formality(text, slang, src)
            target_level = reading.level
    else:
        target_level = coerce_level(register_level)
    timings["register_detect"] = _ms(t0)

    # --- stage 1: pre-edit the source ------------------------------------
    t0 = time.perf_counter()
    steered = pre_edit(text, src, target_level)
    timings["pre_edit"] = _ms(t0)

    # --- stage 2: translate ----------------------------------------------
    t0 = time.perf_counter()
    cached = book.get(src, tgt, steered)
    if cached is not None:
        mt_text, engine, was_cached, mt_ok, mt_msg = cached, "phrasebook", True, True, ""
    else:
        mt = translator.translate(steered, src, tgt, allow_network=allow_network)
        mt_text, engine, was_cached = mt.text, mt.engine, False
        mt_ok, mt_msg = mt.ok, mt.message
        if mt.ok:
            book.put(src, tgt, steered, mt.text, mt.engine)
    timings["translate"] = _ms(t0)

    result.engine = engine
    result.cached = was_cached
    result.ok = mt_ok
    result.message = mt_msg

    # --- stage 3: post-edit into the requested register -------------------
    t0 = time.perf_counter()
    rewritten: RewriteResult = register_rewrite(
        mt_text, tgt, target_level, soften=soften, addressee=addressee,
        speaker_gender=speaker_gender,
    )
    timings["register_post_edit"] = _ms(t0)

    result.translated_text = rewritten.text
    result.register_level = rewritten.level
    result.formality_percent = formality_percent(rewritten.level)
    result.edits = [
        {"rule": e.rule, "gloss": e.gloss, "before": e.before, "after": e.after}
        for e in rewritten.edits
    ]

    # --- the ladder: same sentence at every level -------------------------
    if with_ladder and mt_text:
        t0 = time.perf_counter()
        rungs = register_ladder(mt_text, tgt, soften=soften, addressee=addressee,
                                speaker_gender=speaker_gender)
        result.ladder = {level_name(lvl): res.text for lvl, res in rungs.items()}
        timings["ladder"] = _ms(t0)

    # --- rudeness warning -------------------------------------------------
    result.warning = politeness_warning(mt_text, tgt, target_level)

    # --- prosody and optional audio ---------------------------------------
    result.prosody = prosody(rewritten.level)
    if with_audio:
        t0 = time.perf_counter()
        speech = tts.generate_speech(
            rewritten.text, tgt, rewritten.level, allow_network=allow_network
        )
        result.audio = speech.as_dict()
        timings["tts"] = _ms(t0)

    timings["total"] = round(sum(timings.values()), 2)
    result.timings_ms = timings
    return result


def translate_audio(
    audio_data,
    target_lang: str,
    source_lang: Optional[str] = None,
    register_level=AUTO,
    **kwargs,
) -> ExchangeResult:
    """Transcribe, then run :func:`translate_text` over the transcript."""
    t0 = time.perf_counter()
    transcript = stt.transcribe_audio_chunk(audio_data, language=_norm(source_lang) or None)
    asr_ms = _ms(t0)

    if not transcript.ok or not transcript.text.strip():
        return ExchangeResult(
            ok=False,
            message=transcript.message or "Could not hear anything.",
            source_language=_norm(source_lang),
            target_language=_norm(target_lang),
            timings_ms={"asr": asr_ms},
        )

    result = translate_text(
        transcript.text,
        target_lang,
        source_lang or transcript.language,
        register_level,
        **kwargs,
    )
    result.timings_ms["asr"] = asr_ms
    result.timings_ms["total"] = round(result.timings_ms.get("total", 0) + asr_ms, 2)
    return result


def _ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 2)


def _norm(code) -> str:
    if not isinstance(code, str):
        return ""
    return code.strip().lower().replace("_", "-").split("-")[0]
