"""
Slang detection tests.

The first class of test here is the regression net for the bug that corrupted
the training data: ``slang_dictionary.json`` is nested ``{lang: {term: gloss}}``
and every call site read ``.keys()`` off the outer level, so the "slang terms"
were the language codes ``en, de, fr, it, es, pl...`` — matched as bare
substrings. "Could you please send the report?" was labelled informal because
"en" is inside "send" and "pl" is inside "please".
"""

from __future__ import annotations

import pytest

from utils.helpers import load_slang_dictionary
from utils.slang_detection import (
    detect_slang,
    flatten_slang_dictionary,
    informality_score,
    slang_words_for,
)


@pytest.fixture(scope="module")
def slang():
    return load_slang_dictionary()


# ------------------------------------------------- the corruption regression


@pytest.mark.parametrize(
    "text",
    [
        "Could you please send the report?",              # 'en' in send, 'pl' in please
        "Regardless of the negative aspects, there are positive aspects.",
        "I would like to schedule a meeting.",
        "Please confirm receipt.",
        "The application process is complete.",
        "Kindly review the attached document.",
    ],
)
def test_formal_sentences_have_no_slang(slang, text):
    assert detect_slang(text, slang, "en") == []


def test_language_codes_are_not_treated_as_slang_terms(slang):
    """The outer keys are languages. None of them may become a search term."""
    terms = set(slang_words_for(slang, "en"))
    assert not (terms & set(slang.keys()))


def test_flatten_resolves_the_nested_shape(slang):
    flat = flatten_slang_dictionary(slang, "en")
    assert "lol" in flat
    assert flat["lol"][0] == "laughing out loud"
    assert flat["lol"][1] == "en"
    assert "en" not in flat
    assert "de" not in flat


# ------------------------------------------------------- boundary behaviour


@pytest.mark.parametrize(
    "text",
    [
        "supper was nice",         # 'sup' inside 'supper'
        "your afternoon plans",    # 'ya' / 'af' inside words
        "nothing to declare",
        "a synopsis of the novel", # 'np' inside 'synopsis'
        "the thoroughfare",        # 'tho' inside 'thoroughfare'
    ],
)
def test_no_substring_matches(slang, text):
    assert detect_slang(text, slang, "en") == []


def test_matches_at_word_boundaries(slang):
    found = {m.term for m in detect_slang("lol brb ttyl", slang, "en")}
    assert found == {"lol", "brb", "ttyl"}


def test_punctuation_delimits(slang):
    found = {m.term for m in detect_slang("idk, tbh... nvm!", slang, "en")}
    assert found == {"idk", "tbh", "nvm"}


def test_case_insensitive(slang):
    assert {m.term for m in detect_slang("LOL OMG", slang, "en")} == {"lol", "omg"}


def test_multiword_terms_win_over_their_parts(slang):
    found = [m.term for m in detect_slang("Ich hab kein bock heute", slang, "de")]
    assert "kein bock" in found


# ------------------------------------------------------- language isolation


def test_language_argument_is_honoured(slang):
    """It used to be accepted and ignored, mixing every language together."""
    assert [m.term for m in detect_slang("q", slang, "pt")] == ["q"]
    assert detect_slang("q", slang, "en") == []


def test_unknown_language_yields_nothing(slang):
    assert detect_slang("lol", slang, "xx") == []


def test_none_language_searches_everything(slang):
    assert [m.term for m in detect_slang("lol", slang, None)] == ["lol"]


# ------------------------------------------------------------- input shapes


def test_tolerates_flat_dictionary():
    flat = {"yeet": "throw", "sus": "suspicious"}
    found = {m.term for m in detect_slang("that is sus", flat)}
    assert found == {"sus"}


def test_tolerates_list_of_terms():
    found = {m.term for m in detect_slang("that is sus", ["sus", "yeet"])}
    assert found == {"sus"}


@pytest.mark.parametrize("bad", [None, "", 123, [], {}])
def test_empty_and_bad_inputs(bad, slang):
    assert detect_slang(bad, slang, "en") == []
    assert detect_slang("lol", bad, "en") == []


def test_matches_are_ordered_by_position(slang):
    matches = detect_slang("btw idk lol", slang, "en")
    assert [m.start for m in matches] == sorted(m.start for m in matches)


# ----------------------------------------------------------------- scoring


def test_informality_score_rises_with_density():
    from utils.slang_detection import SlangMatch

    one = [SlangMatch("lol", "lol", "", "en", 0)]
    three = one * 3
    short = "lol"
    long_text = " ".join(["word"] * 40)
    assert informality_score(long_text, []) == 0.0
    assert informality_score(short, one) > 0
    assert informality_score(short, three) >= informality_score(long_text, three)
    assert informality_score(short, three) <= 1.0
