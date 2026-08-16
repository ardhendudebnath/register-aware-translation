"""
Tests for the features that do not exist in any other translation product:
gender-aware downgrade, speaker gender, asymmetric conversations, relationship
memory and learner mode.
"""

from __future__ import annotations

import pytest

from pipeline import (
    Conversation,
    Participant,
    Phrasebook,
    RelationshipBook,
    assess,
)
from register import AUTO, CASUAL, CLOSE, FORMAL, POLITE, rewrite
from register.gender import french_gender, french_possessive
from register.speaker import (
    FEMININE,
    MASCULINE,
    apply_speaker_gender,
    supports_speaker_gender,
)


# --------------------------------------------------------------- fr gender


@pytest.mark.parametrize(
    "source,expected",
    [
        ("votre maison", "ta maison"),        # feminine
        ("votre livre", "ton livre"),         # masculine
        ("votre voiture", "ta voiture"),
        ("votre question", "ta question"),    # -tion suffix rule
        ("votre travail", "ton travail"),
        ("votre amie", "ton amie"),           # feminine but vowel-initial
        ("votre adresse", "ton adresse"),
        ("Votre réponse", "Ta réponse"),      # capital preserved
    ],
)
def test_french_downgrade_respects_gender(source, expected):
    """
    "votre" carries no gender, so the old behaviour always guessed masculine
    and produced the wrong "ton maison" (blueprint 3.4).
    """
    assert rewrite(source, "fr", CASUAL).text == expected


@pytest.mark.parametrize(
    "source", ["ta maison", "ton livre", "tes amis"]
)
def test_french_upgrade_still_collapses(source):
    """Going up, every singular possessive becomes votre/vos."""
    result = rewrite(source, "fr", POLITE).text
    assert result.startswith(("votre", "vos"))


def test_french_gender_lexicon_beats_suffix():
    """Common irregulars must win over the suffix rules."""
    assert french_gender("page") == "f"      # despite masculine -age
    assert french_gender("musée") == "m"     # despite feminine -ée
    assert french_gender("maison") == "f"
    assert french_gender("livre") == "m"


def test_french_gender_suffix_generalises():
    """Words outside the lexicon still resolve from morphology."""
    assert french_gender("administration") == "f"
    assert french_gender("gouvernement") == "m"
    assert french_gender("liberté") == "f"


def test_french_gender_unknown_is_none():
    assert french_gender("") is None
    assert french_gender(None) is None


def test_french_possessive_vowel_rule():
    """"ta amie" is unpronounceable, so French uses the masculine form."""
    assert french_possessive("amie") == "ton"
    assert french_possessive("maison") == "ta"
    assert french_possessive("livre") == "ton"


# ------------------------------------------------------------ speaker gender


@pytest.mark.parametrize(
    "lang,source,gender,expected",
    [
        ("hi", "मैं करता हूँ", FEMININE, "मैं करती हूँ"),
        ("hi", "मैं करती हूँ", MASCULINE, "मैं करता हूँ"),
        ("hi", "मैं जा रहा हूँ", FEMININE, "मैं जा रही हूँ"),
        ("hi", "मैं कल जाऊँगा", FEMININE, "मैं कल जाऊँगी"),
        ("mr", "मी करतो", FEMININE, "मी करते"),
        ("pa", "ਮੈਂ ਕਰਦਾ ਹਾਂ", FEMININE, "ਮੈਂ ਕਰਦੀ ਹਾਂ"),
        ("gu", "હું ગયો", FEMININE, "હું ગઈ"),
    ],
)
def test_speaker_gender(lang, source, gender, expected):
    """
    Hindi, Marathi, Punjabi and Gujarati agree the verb with the *speaker*.
    MT defaults to masculine and so misgenders half its users.
    """
    result, edits = apply_speaker_gender(source, lang, gender)
    assert result == expected
    assert edits


@pytest.mark.parametrize(
    "source", ["वह करता है", "राम करता है", "पिता जी आते हैं"]
)
def test_third_person_is_not_regendered(source):
    """
    Only first-person sentences may be touched. Hindi has ordinary nouns
    ending in ता — पिता, माता, नेता — and rewriting those would be far worse
    than leaving a verb masculine.
    """
    result, edits = apply_speaker_gender(source, "hi", FEMININE)
    assert result == source
    assert edits == []


def test_speaker_gender_noop_cases():
    assert apply_speaker_gender("मैं करता हूँ", "hi", None)[0] == "मैं करता हूँ"
    assert apply_speaker_gender("মৈ করি", "bn", FEMININE)[1] == []   # bn has no marking
    assert apply_speaker_gender("", "hi", FEMININE)[1] == []


def test_supports_speaker_gender():
    assert supports_speaker_gender("hi")
    assert supports_speaker_gender("mr")
    assert not supports_speaker_gender("bn")   # Bengali does not mark it
    assert not supports_speaker_gender("de")


def test_speaker_gender_through_rewrite():
    result = rewrite("मैं काम करता हूँ", "hi", CASUAL, speaker_gender=FEMININE)
    assert "करती" in result.text
    assert any(e.rule == "speaker.gender" for e in result.edits)


# ----------------------------------------------------- asymmetric conversation


def _conversation(tmp_path):
    return Phrasebook(tmp_path / "pb.sqlite3")


def test_conversation_holds_a_register_per_direction(tmp_path):
    """
    Your uncle says তুই to you; you say আপনি back. Every other product applies
    one register to the whole session and gets this exactly wrong.
    """
    uncle = Participant("uncle", "bn", register=AUTO)
    you = Participant("you", "bn", register=POLITE)
    convo = Conversation(uncle, you, phrasebook=_conversation(tmp_path))

    convo.say("uncle", "তুই কোথায় যাস?")
    result = convo.say("you", "তুমি কেমন আছ?")

    # The uncle's own words stay Close; yours are rendered Polite.
    assert convo.observed_registers()["uncle"] == CLOSE
    assert result.register_level == POLITE
    assert result.translated_text == "আপনি কেমন আছেন?"


def test_conversation_detects_asymmetry(tmp_path):
    uncle = Participant("uncle", "bn", register=AUTO)
    you = Participant("you", "bn", register=AUTO)
    convo = Conversation(uncle, you, phrasebook=_conversation(tmp_path))
    convo.say("uncle", "তুই কোথায় যাস?")
    convo.say("you", "আপনি কেমন আছেন?")
    assert convo.is_asymmetric()


def test_conversation_addressee_inserts_vocative(tmp_path):
    you = Participant("you", "bn", register=POLITE, addressee="elder_man")
    elder = Participant("elder", "bn", register=AUTO)
    convo = Conversation(you, elder, phrasebook=_conversation(tmp_path))
    result = convo.say("you", "আপনি কেমন আছেন?")
    assert result.translated_text.startswith("কাকু,")


def test_conversation_rejects_unknown_speaker(tmp_path):
    convo = Conversation(
        Participant("a", "bn"), Participant("b", "bn"),
        phrasebook=_conversation(tmp_path),
    )
    with pytest.raises(KeyError):
        convo.say("nobody", "hello")


def test_conversation_mirror(tmp_path):
    uncle = Participant("uncle", "bn", register=AUTO)
    you = Participant("you", "bn", register=POLITE)
    convo = Conversation(uncle, you, phrasebook=_conversation(tmp_path))
    convo.say("uncle", "তুই কোথায় যাস?")
    convo.mirror("uncle")
    assert uncle.register == CLOSE


# --------------------------------------------------------- relationship memory


def test_relationship_round_trip(tmp_path):
    book = RelationshipBook(tmp_path / "r.sqlite3")
    book.remember("Rahul's father", language="bn", register=POLITE,
                  addressee="elder_man")
    found = book.recall("rahul's father")          # name is normalised
    assert found is not None
    assert found.register == POLITE
    assert found.addressee == "elder_man"


def test_relationship_merge_preserves_fields(tmp_path):
    book = RelationshipBook(tmp_path / "r.sqlite3")
    book.remember("Priya", language="hi", register=CASUAL)
    book.remember("Priya", note="college friend")
    found = book.recall("Priya")
    assert found.register == CASUAL       # not wiped by the note update
    assert found.note == "college friend"


def test_relationship_forget(tmp_path):
    book = RelationshipBook(tmp_path / "r.sqlite3")
    book.remember("Someone", register=POLITE)
    assert book.forget("Someone") is True
    assert book.recall("Someone") is None
    assert book.forget("Someone") is False


def test_relationship_survives_unwritable_path(tmp_path):
    book = RelationshipBook(tmp_path / "no" / "\0bad" / "r.sqlite3")
    assert book.remember("x", register=POLITE) is None
    assert book.recall("x") is None
    assert book.all() == []


# ------------------------------------------------------------- learner mode


@pytest.mark.parametrize(
    "text,relationship,verdict",
    [
        ("তুই কেমন আছিস?", "stranger", "too_familiar"),
        ("আপনি কেমন আছেন?", "stranger", "good"),
        ("আপনি কেমন আছেন?", "close_friend", "too_formal"),
        ("তুমি কেমন আছ?", "close_friend", "good"),
        ("তুই কেমন আছিস?", "child", "good"),
    ],
)
def test_learner_verdicts(text, relationship, verdict):
    assert assess(text, "bn", relationship).verdict == verdict


def test_learner_offers_a_correction():
    feedback = assess("তুই কেমন আছিস?", "bn", "stranger")
    assert feedback.suggestion == "আপনি কেমন আছেন?"
    assert not feedback.is_appropriate


def test_learner_no_correction_when_correct():
    feedback = assess("আপনি কেমন আছেন?", "bn", "stranger")
    assert feedback.suggestion is None
    assert feedback.is_appropriate


def test_learner_handles_unmarked_sentence():
    """A sentence with no register marker cannot be judged."""
    assert assess("ভাত", "bn", "stranger").verdict == "unknown"


def test_learner_handles_unknown_inputs():
    assert assess("hello", "bn", "not-a-relationship").verdict == "unknown"
    assert assess("hello", "xx", "stranger").verdict == "unknown"


def test_learner_elder_family_accepts_both():
    """
    Register is culturally contested and family elders are the contested case:
    high respect but high closeness. Insisting on one answer would teach
    something false.
    """
    assert assess("তুমি কেমন আছ?", "bn", "elder_family").verdict == "good"
    assert assess("আপনি কেমন আছেন?", "bn", "elder_family").verdict == "good"


def test_learner_serialises():
    payload = assess("তুই কেমন আছিস?", "bn", "stranger").as_dict()
    for key in ("verdict", "message", "suggestion", "expected", "appropriate"):
        assert key in payload
