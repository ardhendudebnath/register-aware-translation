"""
Code-switching (blueprint 13.2 #8): measure the English, keep the everyday words.

Nothing here can check that ऑफिस is what people say — there is no native-script
code-mixing corpus to check it against, and the word lists wait on a speaker.
What these check is everything around that judgement: that a swap keeps the
sentence grammatical (case endings, gender), that it never damages a word it
was not aimed at (compounds, names, verb forms), that it never fights the
register tables, and that English is never read as a register.
"""

from __future__ import annotations

import pytest

import app as app_module
import pipeline.core as core
from app import app
from pipeline import Conversation, Participant
from pipeline.core import Phrasebook, translate_text
from register import CASUAL, CLOSE, FORMAL, LEVELS, POLITE, TABLES, detect
from register.codeswitch import LOANS, REJECTED, keep_english, measure


# ---------------------------------------------------------------- keeping


@pytest.mark.parametrize("level", [CLOSE, CASUAL])
def test_casual_keeps_the_english_word(level):
    out = keep_english("मैं कार्यालय जा रहा हूँ।", "hi", level)
    assert out.text == "मैं ऑफिस जा रहा हूँ।"
    assert [e.rule for e in out.edits] == ["english.office"]


@pytest.mark.parametrize("level", [POLITE, FORMAL])
def test_polite_and_formal_are_left_alone(level):
    text = "मैं कार्यालय जा रहा हूँ।"
    assert keep_english(text, "hi", level).text == text


def test_it_never_purifies():
    """The reverse swap does not exist: English in a formal sentence stays."""
    text = "आप ऑफिस कब जाएँगे?"
    for level in LEVELS:
        assert keep_english(text, "hi", level).text == text


def test_what_the_speaker_said_in_english_survives_every_level():
    out = keep_english("आप कार्यालय कब जाएँगे?", "hi", FORMAL, keep={"office"})
    assert out.text == "आप ऑफिस कब जाएँगे?"
    assert "you said this in English" in out.edits[0].gloss


def test_keeping_one_word_does_not_license_the_others():
    out = keep_english("कार्यालय में बैठक है।", "hi", FORMAL, keep={"office"})
    assert out.text == "ऑफिस में बैठक है।"


def test_idempotent():
    once = keep_english("कार्यालयों में बैठक और संदेश", "hi", CASUAL).text
    assert keep_english(once, "hi", CASUAL).text == once


def test_languages_without_a_list_are_untouched():
    text = "நான் அலுவலகம் போகிறேன்"
    assert keep_english(text, "ta", CASUAL).text == text


# ----------------------------------------------------- grammar of the swap


@pytest.mark.parametrize("native, loan", [
    ("কার্যালয়ে", "অফিসে"),        # locative, consonant → consonant
    ("বৈঠকের", "মিটিংয়ের"),         # genitive, consonant → anusvara
    ("বৈঠকে", "মিটিংয়ে"),           # locative, consonant → anusvara
    ("বার্তায়", "মেসেজে"),          # locative, vowel → consonant
    ("বার্তার", "মেসেজের"),         # genitive, vowel → consonant
    ("বার্তাটা", "মেসেজটা"),        # classifiers attach the same way
    ("চিকিৎসককে", "ডাক্তারকে"),     # object ending
    ("বৈঠকেও", "মিটিংয়েও"),         # emphatic after a case ending
    ("সপ্তাহান্তে", "উইকেন্ডে"),
])
def test_bengali_case_endings_are_reshaped_for_the_loan(native, loan):
    assert keep_english(f"{native} কী হল?", "bn", CASUAL).text == f"{loan} কী হল?"


def test_hindi_oblique_plural_carries_over():
    assert keep_english("कार्यालयों में", "hi", CASUAL).text == "ऑफिसों में"


def test_hindi_vowel_final_plurals_are_not_guessed_at():
    text = "समस्याओं पर बात करो"
    assert keep_english(text, "hi", CASUAL).text == text


def test_every_hindi_noun_keeps_its_gender():
    """
    A swap that changes gender breaks agreement elsewhere in the sentence:
    मेरा तनाव → *मेरा टेंशन. Every Hindi noun records the gender its native and
    loan forms share, and the pairs that do not share one are rejected.
    """
    for loan in LOANS["hi"]:
        if loan.english == "busy":
            assert loan.gender == "", "adjectives do not inflect for gender here"
        else:
            assert loan.gender in {"m", "f"}, loan.english
    for language, rejected in REJECTED.items():
        listed = {loan.english for loan in LOANS[language]}
        assert not listed & set(rejected), "a rejected word crept back in"


# ------------------------------------------------ words it must not touch


@pytest.mark.parametrize("language, text", [
    ("hi", "कमरा अस्त-व्यस्त है"),             # compound: "in a mess"
    ("hi", "कमरा अस्त व्यस्त है"),             # the same, written apart
    ("hi", "बैठकर बात करो"),                   # a verb, not बैठक
    ("hi", "संदेशवाहक आया"),                   # messenger
    ("hi", "वह केंद्रीय विद्यालय में पढ़ता है"),  # a school's name
    ("bn", "বার্তা সংস্থা জানিয়েছে"),          # news agency
    ("bn", "সে উচ্চ বিদ্যালয়ে পড়ে"),          # a school's name
])
def test_compounds_names_and_lookalikes_are_left_alone(language, text):
    assert keep_english(text, language, CASUAL).text == text


def test_a_word_inside_a_longer_word_is_not_matched():
    out = keep_english("वह महाविद्यालय जाता है", "hi", CASUAL).text
    assert out == "वह कॉलेज जाता है", "not *महास्कूल"


def test_either_encoding_of_a_nukta_letter_matches():
    # য় as one code point (U+09DF), which NFC splits into য + ়.
    precomposed = "আমি কার্যালয়ে যাচ্ছি"
    assert keep_english(precomposed, "bn", CASUAL).text == "আমি অফিসে যাচ্ছি"


# ------------------------------------------- it stays out of register's way


def test_no_loan_or_native_form_appears_in_any_register_rule():
    """
    If a register rule mentioned one of these words, a swap could hide a
    marker from detection or undo a rewrite. None does, and this keeps it so.
    """
    for language, loans in LOANS.items():
        words = {w for loan in loans for w in (loan.loan, *loan.also, *loan.native)}
        for rule in TABLES[language].rules:
            for form in rule.forms:
                assert not words & set(form.split()), (language, rule.name, form)


@pytest.mark.parametrize("language, text", [
    ("hi", "तू कार्यालय कब जाएगा?"),
    ("hi", "तुम कार्यालय कब जाओगे?"),
    ("hi", "आप कार्यालय कब जाएँगे?"),
    ("hi", "क्या तुम व्यस्त हो?"),
    ("bn", "তুই কার্যালয়ে কখন যাবি?"),
    ("bn", "তুমি কার্যালয়ে কখন যাবে?"),
    ("bn", "আপনি কার্যালয়ে কখন যাবেন?"),
])
def test_the_swap_does_not_change_the_register_read(language, text):
    before = detect(text, language)
    after = detect(keep_english(text, language, CASUAL).text, language)
    assert after.level == before.level


# ---------------------------------------------------------------- measuring


def test_latin_words_in_a_bengali_sentence_are_counted():
    reading = measure("আমি office যাচ্ছি", "bn")
    assert reading.words == 3
    assert [(i.english, i.kind) for i in reading.insertions] == [("office", "latin")]
    assert reading.rate == pytest.approx(1 / 3)


def test_loans_in_the_native_script_are_counted_with_their_endings():
    reading = measure("আমি অফিসে যাচ্ছি, meeting-এর পরে", "bn")
    assert reading.english_words == ("office", "meeting")
    assert [i.kind for i in reading.insertions] == ["loan", "latin"]
    assert reading.words == 5, "meeting-এর is one word, not two"


def test_english_plurals_find_their_headword():
    assert measure("कल मेरी meetings हैं", "hi").english_words == ("meeting",)


@pytest.mark.parametrize("language, text", [
    ("en", "I am going to the office"),
    ("hi", "kal office jaana hai"),      # romanised Hindi: not visible here
    ("hi", "   "),
])
def test_nothing_to_measure_says_so(language, text):
    assert measure(text, language) is None


def test_a_measurement_carries_no_register():
    """English marks formality for some speakers and casualness for others."""
    payload = measure("আমি office যাচ্ছি", "bn").as_dict()
    assert not {"level", "register", "level_name"} & set(payload)


# ---------------------------------------------------------------- pipeline


@pytest.fixture()
def book(tmp_path):
    return Phrasebook(tmp_path / "pb.sqlite3")


def test_pipeline_keeps_english_at_casual_only(book):
    result = translate_text(
        "मैं कार्यालय जा रहा हूँ, तुम कब आओगे?", "hi", "hi", CASUAL,
        allow_network=False, phrasebook=book,
    )
    assert result.translated_text == "मैं ऑफिस जा रहा हूँ, तुम कब आओगे?"
    assert "english.office" in [e["rule"] for e in result.edits]
    assert "ऑफिस" in result.ladder["Close"] and "ऑफिस" in result.ladder["Casual"]
    assert "कार्यालय" in result.ladder["Polite"] and "कार्यालय" in result.ladder["Formal"]
    assert result.mt_text == "मैं कार्यालय जा रहा हूँ, तुम कब आओगे?"


def test_pipeline_can_be_told_not_to(book):
    result = translate_text(
        "मैं कार्यालय जा रहा हूँ।", "hi", "hi", CASUAL,
        keep_english=False, allow_network=False, phrasebook=book,
    )
    assert result.translated_text == "मैं कार्यालय जा रहा हूँ।"


def test_pipeline_preserves_the_speakers_own_english_across_languages(book):
    # A Bengali speaker says "office" in English; MT renders it bookishly.
    book.put("bn", "hi", "আমি office যাচ্ছি", "मैं कार्यालय जा रहा हूँ", "test")
    result = translate_text(
        "আমি office যাচ্ছি", "hi", "bn", FORMAL,
        allow_network=False, phrasebook=book,
    )
    assert result.engine == "phrasebook"
    assert result.translated_text == "मैं ऑफिस जा रहा हूँ"
    assert result.ladder["Formal"] == "मैं ऑफिस जा रहा हूँ"
    assert result.code_switch["english_words"] == ["office"]


def test_conversation_reports_each_sides_english_mix(book):
    talk = Conversation(
        Participant("Riya", "bn"), Participant("Dadu", "bn"), phrasebook=book,
    )
    talk.say("Riya","আমি office যাচ্ছি", allow_network=False)
    talk.say("Dadu", "তুমি কখন ফিরবে?", allow_network=False)
    mix = talk.as_dict()["english_mix"]
    assert mix["Riya"] == pytest.approx(1 / 3, abs=1e-3)
    assert mix["Dadu"] == 0.0


# --------------------------------------------------------------------- API


@pytest.fixture()
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(app_module, "ALLOW_NETWORK", False)
    # Never write test sentences into the real phrasebook.
    monkeypatch.setattr(core, "_phrasebook", Phrasebook(tmp_path / "pb.sqlite3"))
    return app.test_client()


def test_api_translate_honours_the_toggle(client):
    body = {"text": "मैं कार्यालय जा रहा हूँ।", "source_lang": "hi",
            "target_lang": "hi", "register": "casual"}
    on = client.post("/api/translate", json=body).get_json()
    off = client.post("/api/translate", json={**body, "keep_english": False}).get_json()
    assert on["translated_text"] == "मैं ऑफिस जा रहा हूँ।"
    assert off["translated_text"] == "मैं कार्यालय जा रहा हूँ।"
    # The client re-levels from these, so their names are part of the contract.
    assert on["mt_text"] == "मैं कार्यालय जा रहा हूँ।"
    assert set(on["code_switch"]) >= {"words", "english", "rate", "english_words"}


def test_api_relevel_applies_the_same_stage(client):
    text = "आप कार्यालय कब जाएँगे?"
    casual = client.post("/api/relevel", json={
        "text": text, "language": "hi", "register": "casual",
    }).get_json()
    formal = client.post("/api/relevel", json={
        "text": text, "language": "hi", "register": "formal",
    }).get_json()
    kept = client.post("/api/relevel", json={
        "text": text, "language": "hi", "register": "formal", "keep": ["office"],
    }).get_json()
    assert "ऑफिस" in casual["text"]
    assert "कार्यालय" in formal["text"]
    assert "ऑफिस" in kept["text"]
    assert any(e["rule"] == "english.office" for e in casual["edits"])
