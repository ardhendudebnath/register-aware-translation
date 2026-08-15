"""
Pipeline and model-wrapper tests.

Everything here runs with ``allow_network=False``. The pipeline must be
exercisable without reaching an undocumented public endpoint — both because
tests should not depend on someone else's rate limit, and because "works with
no network" is a product requirement, not an accident.
"""

from __future__ import annotations

import pytest

from models import backend_report
from models.classifier import classify_formality
from models.language_id import detect_language, detect_script
from models.translator import translate as mt_translate
from models.tts import generate_speech
from pipeline import Phrasebook, translate_text
from register import CASUAL, CLOSE, FORMAL, POLITE


# --------------------------------------------------------------- language id


@pytest.mark.parametrize(
    "text,expected",
    [
        ("আপনি কেমন আছেন?", "bn"),
        ("আমি ভালো আছি", "bn"),
        ("आप कैसे हैं?", "hi"),
        ("நீங்கள் எப்படி இருக்கிறீர்கள்?", "ta"),
        ("మీరు ఎలా ఉన్నారు?", "te"),
        ("ನೀವು ಹೇಗಿದ್ದೀರಿ?", "kn"),
        ("നിങ്ങൾ എങ്ങനെ ഉണ്ട്?", "ml"),
        ("તમે કેમ છો?", "gu"),
        ("ਤੁਸੀਂ ਕਿਵੇਂ ਹੋ?", "pa"),
        ("こんにちは", "ja"),
    ],
)
def test_detect_language_by_script(text, expected):
    """Unique scripts are decided without a statistical model at all."""
    assert detect_language(text) == expected


def test_detect_language_latin():
    assert detect_language("The quick brown fox jumps over the lazy dog") == "en"
    assert detect_language("Der schnelle braune Fuchs springt über den Hund") == "de"


def test_detect_script():
    assert detect_script("আপনি") == "Bengali"
    assert detect_script("hello") == "Latin"
    assert detect_script("123 !?") == "Unknown"


def test_detect_language_defaults_gracefully():
    """Empty or unidentifiable input must not raise; a translator that dies
    because someone coughed into the mic is worse than one that guesses."""
    assert detect_language("") == "en"
    assert detect_language("   ") == "en"
    assert detect_language(None) == "en"
    assert detect_language("!!!", default="bn") == "bn"


# -------------------------------------------------------------- formality


@pytest.mark.parametrize(
    "text,lang,expected_level",
    [
        ("তুই কোথায় যাস?", "bn", CLOSE),
        ("তুমি কি করছ?", "bn", CASUAL),
        ("আপনি কেমন আছেন?", "bn", POLITE),
        ("आप कैसे हैं?", "hi", POLITE),
    ],
)
def test_formality_uses_the_register_engine(text, lang, expected_level):
    """Grammar beats correlation: an explicit register marker wins outright."""
    result = classify_formality(text, language=lang)
    assert result.level == expected_level
    assert result.source == "register-engine"


def test_formality_lexical_fallback():
    informal = classify_formality("yo lol idk tbh", language="en")
    formal = classify_formality(
        "I am writing to enquire about the position advertised.", language="en"
    )
    assert informal.percent < formal.percent


def test_formality_neutral_when_no_evidence():
    result = classify_formality("The table is brown.", language="en")
    assert 35 <= result.percent <= 75


def test_formality_handles_empty():
    result = classify_formality("")
    assert result.source == "empty"


def test_formality_serialises():
    payload = classify_formality("তুমি কি করছ?", language="bn").as_dict()
    assert payload["level_name"] == "Casual"
    assert "percent" in payload


# ------------------------------------------------------------------ engines


def test_backend_report_shape():
    report = backend_report()
    assert set(report) == {"stt", "mt", "tts", "formality_model"}
    assert isinstance(report["mt"], list)


def test_mt_identity_for_same_language():
    result = mt_translate("hello", "en", "en")
    assert result.text == "hello"
    assert result.engine == "identity"


def test_mt_offline_fails_soft():
    """
    With no network and no local model, MT must hand back the source flagged as
    untranslated rather than raising or returning an empty string. The UI shows
    "here's what I heard" instead of a blank box.
    """
    result = mt_translate("hello there", "en", "bn", allow_network=False)
    assert result.ok is False
    assert result.text == "hello there"
    assert result.engine == "none"
    assert result.message


def test_mt_empty_input():
    assert mt_translate("", "en", "bn").text == ""


def test_tts_returns_prosody_even_without_a_backend():
    """
    The browser can apply the prosody itself, so it is returned regardless of
    whether server-side synthesis is available.
    """
    formal = generate_speech("হ্যালো", "bn", FORMAL, allow_network=False)
    casual = generate_speech("হ্যালো", "bn", CASUAL, allow_network=False)
    assert formal.prosody["rate"] < casual.prosody["rate"]
    assert formal.prosody["pause_ms"] > casual.prosody["pause_ms"]


def test_tts_empty_text():
    assert generate_speech("", "en").ok is False


# ----------------------------------------------------------------- pipeline


def test_pipeline_offline_still_applies_register(tmp_path):
    """
    The whole point of the layering: MT can fail completely and the register
    layer still runs over whatever text there is.
    """
    book = Phrasebook(tmp_path / "pb.sqlite3")
    result = translate_text(
        "আপনি কেমন আছেন?",
        target_lang="bn",
        source_lang="bn",
        register_level=CLOSE,
        allow_network=False,
        phrasebook=book,
    )
    # Same language in and out, so MT is the identity and the post-edit is the
    # only thing that acts.
    assert result.translated_text == "তুই কেমন আছিস?"
    assert result.register_level == CLOSE
    assert len(result.edits) == 2


def test_pipeline_ladder(tmp_path):
    book = Phrasebook(tmp_path / "pb.sqlite3")
    result = translate_text(
        "তুমি কি করছ?", "bn", "bn", POLITE,
        allow_network=False, phrasebook=book,
    )
    assert result.ladder["Close"] == "তুই কি করছিস?"
    assert result.ladder["Polite"] == "আপনি কি করছেন?"


def test_pipeline_auto_mirrors(tmp_path):
    book = Phrasebook(tmp_path / "pb.sqlite3")
    result = translate_text(
        "তুই কোথায় যাস?", "bn", "bn", "auto",
        allow_network=False, phrasebook=book,
    )
    assert result.register_level == CLOSE
    assert result.detected_level == CLOSE


def test_pipeline_reports_timings(tmp_path):
    book = Phrasebook(tmp_path / "pb.sqlite3")
    result = translate_text(
        "তুমি কি করছ?", "bn", "bn", POLITE,
        allow_network=False, phrasebook=book,
    )
    assert "register_post_edit" in result.timings_ms
    # The register layer is a string pass and must never show up in the
    # latency budget (blueprint 7).
    assert result.timings_ms["register_post_edit"] < 50


def test_pipeline_rejects_empty():
    result = translate_text("", "bn", "en", POLITE, allow_network=False)
    assert result.ok is False


def test_pipeline_serialises(tmp_path):
    book = Phrasebook(tmp_path / "pb.sqlite3")
    payload = translate_text(
        "তুমি কি করছ?", "bn", "bn", POLITE,
        allow_network=False, phrasebook=book,
    ).as_dict()
    for key in ("original_text", "translated_text", "register_name",
                "formality_percentage", "edits", "ladder", "timings_ms"):
        assert key in payload


# --------------------------------------------------------------- phrasebook


def test_phrasebook_round_trip(tmp_path):
    book = Phrasebook(tmp_path / "pb.sqlite3")
    assert book.get("en", "bn", "hello") is None
    book.put("en", "bn", "hello", "হ্যালো", "test")
    assert book.get("en", "bn", "hello") == "হ্যালো"
    assert book.stats()["phrases"] == 1


def test_phrasebook_normalises_whitespace(tmp_path):
    book = Phrasebook(tmp_path / "pb.sqlite3")
    book.put("en", "bn", "hello  there", "হ্যালো")
    assert book.get("en", "bn", "  hello there  ") == "হ্যালো"


def test_phrasebook_survives_unwritable_path(tmp_path):
    """A read-only data directory must degrade, not crash the app."""
    book = Phrasebook(tmp_path / "nope" / "\0bad" / "pb.sqlite3")
    book.put("en", "bn", "hello", "হ্যালো")
    assert book.get("en", "bn", "hello") is None
    assert book.stats() == {"phrases": 0, "hits": 0}
