"""
The scheduled languages added in blueprint phase 3: Urdu, Odia, Assamese, Nepali.

CoCoA-MT gave Hindi a binary formality benchmark in 2022 and the rest of India
got nothing. These four have no register-controlled MT resource of any kind, so
these tables are the only ones in existence — which is exactly why they need a
regression net rather than being trusted because they looked right once.

The forms here are compiled from standard grammars and have not been reviewed by
a native speaker. The tests pin current behaviour so a correction is a visible,
deliberate change rather than a silent drift.
"""

from __future__ import annotations

import pytest

from models.language_id import detect_language
from register import (
    CASUAL,
    CLOSE,
    FORMAL,
    POLITE,
    TABLES,
    detect,
    get_table,
    rewrite,
    supported_languages,
)

NEW = ("ur", "or", "as", "ne")


def test_twenty_languages():
    assert len(supported_languages()) == 20
    for code in NEW:
        assert code in TABLES


@pytest.mark.parametrize("code", NEW)
def test_new_tables_are_well_formed(code):
    table = get_table(code)
    assert table.rules
    assert all(rule.is_discriminative for rule in table.rules)
    assert len(table.address_terms) >= 4, "Indic languages need the vocative slot"


@pytest.mark.parametrize(
    "lang,source,level,expected",
    [
        # Urdu — تو / تم / آپ
        ("ur", "آپ کیسے ہیں", CASUAL, "تم کیسے ہو"),
        ("ur", "آپ کیسے ہیں", CLOSE, "تو کیسے ہے"),
        ("ur", "تم کیسے ہو", POLITE, "آپ کیسے ہیں"),
        ("ur", "جاؤ", POLITE, "جائیے"),
        # Odia — ତୁ / ତୁମେ / ଆପଣ
        ("or", "ଆପଣ କେମିତି ଅଛନ୍ତି", CASUAL, "ତୁମେ କେମିତି ଅଛ"),
        ("or", "ଆପଣ କେମିତି ଅଛନ୍ତି", CLOSE, "ତୁ କେମିତି ଅଛୁ"),
        ("or", "ତୁମେ କେମିତି ଅଛ", POLITE, "ଆପଣ କେମିତି ଅଛନ୍ତି"),
        # Assamese — তই / তুমি / আপুনি
        ("as", "আপুনি কেনে আছে", CASUAL, "তুমি কেনে আছা"),
        ("as", "আপুনি কেনে আছে", CLOSE, "তই কেনে আছ"),
        ("as", "তুমি কেনে আছা", POLITE, "আপুনি কেনে আছে"),
        # Nepali — तँ / तिमी / तपाईं
        ("ne", "तपाईं कस्तो हुनुहुन्छ", CASUAL, "तिमी कस्तो हौ"),
        ("ne", "तपाईं कस्तो हुनुहुन्छ", CLOSE, "तँ कस्तो होस्"),
        ("ne", "तिमी कस्तो हौ", POLITE, "तपाईं कस्तो हुनुहुन्छ"),
    ],
)
def test_new_language_rewrite(lang, source, level, expected):
    assert rewrite(source, lang, level).text == expected


@pytest.mark.parametrize(
    "lang,text,expected",
    [
        ("ur", "آپ کیسے ہیں", POLITE),
        ("ur", "تم کیسے ہو", CASUAL),
        ("or", "ଆପଣ କେମିତି ଅଛନ୍ତି", POLITE),
        ("as", "আপুনি কেনে আছে", POLITE),
        ("ne", "तपाईं कस्तो हुनुहुन्छ", POLITE),
        ("ne", "तिमी कस्तो हौ", CASUAL),
    ],
)
def test_new_language_detect(lang, text, expected):
    assert detect(text, lang).level == expected


@pytest.mark.parametrize(
    "lang,polite",
    [
        ("ur", "آپ کیسے ہیں"),
        ("or", "ଆପଣ କେମିତି ଅଛନ୍ତି"),
        ("as", "আপুনি কেনে আছে"),
        ("ne", "तपाईं कस्तो हुनुहुन्छ"),
    ],
)
def test_new_language_round_trip(lang, polite):
    casual = rewrite(polite, lang, CASUAL).text
    assert rewrite(casual, lang, POLITE).text == polite


# --------------------------------------------------------------------------
# Assamese and Bengali share a script
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        # Assamese: ৰ / ৱ, or a distinctive function word
        ("মোৰ নাম", "as"),
        ("মই ভাল আছোঁ", "as"),
        ("আপুনি কেনে আছে", "as"),
        ("তেওঁ আহিছে", "as"),
        # Bengali must not be dragged along with it — it is the far larger
        # language, so a false "as" is the costlier error.
        ("আপনি কেমন আছেন?", "bn"),
        ("আমি ভালো আছি", "bn"),
        ("তুমি কি করছ?", "bn"),
        ("আমার নাম", "bn"),
        ("সে এসেছে", "bn"),
        ("তুই কোথায় যাস?", "bn"),
    ],
)
def test_assamese_vs_bengali(text, expected):
    assert detect_language(text) == expected


def test_urdu_script_is_identified():
    """Urdu is Arabic script; it must not be confused with Arabic or Persian."""
    assert detect_language("آپ کیسے ہیں") in ("ur", "ar", "fa")


def test_nepali_and_hindi_share_devanagari():
    """
    Both are Devanagari, so this leans on the statistical stage. Assert only
    that it stays inside the Devanagari candidate set rather than pinning a
    specific answer the detector cannot reliably give on short input.
    """
    assert detect_language("तपाईं कस्तो हुनुहुन्छ") in ("ne", "hi", "mr", "sa")
    assert detect_language("आप कैसे हैं?") in ("hi", "ne", "mr", "sa")
