"""
Rules firing outside the construction they belong to.

The four metrics cannot see this class of bug. They compare the engine against
gold rows, and gold rows are single-clause sentences addressed to somebody —
so a rule that misbehaves in a compound verb, or on a noun that happens to look
like a term of address, collides with nothing and scores 100%.

Every case here was found by probing outside the gold sets, and each one was
live when it was written:

    तुम सो जाओ।          -> आप सोइए जाइए।      (should be आप सो जाइए।)
    मेरा भाई डॉक्टर है।  -> मेरा साहब डॉक्टर है।
    ਮੈਂ ਜਾ ਰਿਹਾ ਹਾਂ।      -> ਮੈਂ ਜਾਓ ਰਿਹਾ ਹਾਂ।   read as Casual, confidence 1.00

The last is the worst of the three. It is a sentence about the speaker,
addressed to nobody, reported as confident evidence of how the listener is
being spoken to — which in Auto mode is a wrong mirror rather than a clumsy
rewrite.
"""

from __future__ import annotations

import glob
import json
from pathlib import Path

import pytest

from register import (
    CASUAL,
    FORMAL,
    LEVELS,
    POLITE,
    TABLES,
    detect,
    has_table,
    rewrite,
)

GOLD = Path(__file__).resolve().parents[1] / "data" / "gold"


# ------------------------------------------------- compound verbs: one command


@pytest.mark.parametrize("language, source, level, expected", [
    # Hindi and Urdu build a compound from a bare stem plus a light verb, and
    # only the light verb carries the politeness.
    ("hi", "तुम सो जाओ।", POLITE, "आप सो जाइए।"),
    ("hi", "तुम बैठ जाओ।", POLITE, "आप बैठ जाइए।"),
    ("hi", "ले आओ।", POLITE, "ले आइए।"),
    ("hi", "खा लो।", POLITE, "खा लीजिए।"),
    ("hi", "कर दो।", POLITE, "कर दीजिए।"),
    # …and back down again, which is where the compound has to survive being
    # matched from the other end.
    ("hi", "आप सो जाइए।", CASUAL, "तुम सो जाओ।"),
    ("ur", "سو جاؤ۔", POLITE, "سو جائیے۔"),
    ("ur", "کھا لو۔", POLITE, "کھا لیجیے۔"),
    ("pa", "ਬੈਠ ਜਾ।", POLITE, "ਬੈਠ ਜਾਓ।"),
    ("pa", "ਲੈ ਆ।", POLITE, "ਲੈ ਆਓ।"),
])
def test_only_the_light_verb_moves(language, source, level, expected):
    assert rewrite(source, language, level).text == expected


@pytest.mark.parametrize("language, source, level, expected", [
    ("hi", "तुम यहाँ आओ।", POLITE, "आप यहाँ आइए।"),
    ("hi", "खाना खाओ।", POLITE, "खाना खाइए।"),
    ("pa", "ਇੱਥੇ ਆ।", POLITE, "ਇੱਥੇ ਆਓ।"),
    ("ur", "یہاں آؤ۔", POLITE, "یہاں آئیے۔"),
])
def test_an_ordinary_imperative_still_moves(language, source, level, expected):
    """The guard must not cost the thing it is guarding."""
    assert rewrite(source, language, level).text == expected


@pytest.mark.parametrize("language, source", [
    # These languages build the first half of a compound as a participle, not
    # a bare stem, so they never had the collision. Locked in so a future
    # paradigm edit cannot introduce it.
    ("bn", "শুয়ে পড়ো।"),
    ("bn", "নিয়ে এসো।"),
    ("mr", "बसून घे।"),
    ("gu", "બેસી જા।"),
    ("or", "ବସି ଯାଅ।"),
    ("as", "বহি যোৱা।"),
])
def test_a_participle_first_half_is_never_touched(language, source):
    first = source.split()[0]
    assert first in rewrite(source, language, POLITE).text


# ------------------------------------------- a bare stem before an auxiliary


@pytest.mark.parametrize("language, sentence", [
    # Nobody is addressed in any of these. Punjabi rewrote all four and read
    # them as Casual at full confidence.
    ("pa", "ਮੈਂ ਜਾ ਰਿਹਾ ਹਾਂ।"),
    ("pa", "ਉਹ ਕੰਮ ਕਰ ਸਕਦਾ ਹੈ।"),
    ("pa", "ਗੱਡੀ ਆ ਰਹੀ ਹੈ।"),
    ("pa", "ਉਹ ਖਾ ਰਿਹਾ ਹੈ।"),
    ("hi", "वह काम कर सकता है।"),
    ("hi", "गाड़ी आ रही है।"),
    ("ur", "وہ کام کر سکتا ہے۔"),
])
def test_a_sentence_addressed_to_nobody_is_left_alone(language, sentence):
    for level in LEVELS:
        assert rewrite(sentence, language, level).text == sentence
    reading = detect(sentence, language)
    assert reading.level is None, (
        f"{sentence!r} has no second person in it but was read as "
        f"{reading.level} at {reading.confidence:.0%}"
    )


@pytest.mark.parametrize("language", ["hi", "ur", "pa"])
def test_every_imperative_in_these_languages_is_guarded(language):
    """
    Hindi, Urdu and Punjabi spell the तू/ਤੂੰ imperative exactly like the stem
    their progressives, modals and compounds are built on. Any imperative rule
    without a guard is the next instance of this bug.
    """
    for rule in TABLES[language].rules:
        if rule.name.endswith(".imp"):
            assert rule.guard_after, f"{language} {rule.name} has no guard"


# --------------------------------------------- a vocative needs a vocative


@pytest.mark.parametrize("language, sentence", [
    ("hi", "मेरा भाई डॉक्टर है।"),
    ("hi", "उसका भाई कहाँ है?"),
    ("ur", "میرا بھائی ڈاکٹر ہے۔"),
])
def test_a_kinship_term_is_not_a_term_of_address(language, sentence):
    """
    भाई is "brother" as often as it is "mate". Raising the second to साहब
    rewrote the first, turning "my brother is a doctor" into "my sir is a
    doctor" — not a politeness change but a different sentence.
    """
    for level in LEVELS:
        assert rewrite(sentence, language, level).text == sentence


@pytest.mark.parametrize("language, source, expected", [
    ("hi", "भाई, ज़रा सुनो।", "साहब, ज़रा सुनिए।"),
    ("hi", "सुनो, भाई।", "सुनिए, साहब।"),
    ("ur", "بھائی، ذرا سنو۔", "صاحب، ذرا سنیے۔"),
])
def test_an_actual_vocative_still_rises(language, source, expected):
    assert rewrite(source, language, POLITE).text == expected


# ------------------------------------- Romance: the imperative and the third
#
# Portuguese, Spanish and Italian spell the tu imperative exactly like some
# third-person present, so the same collision as Hindi's bare stem turns up in
# three more languages. Agreement with FAME-MT, on somebody else's labels,
# moved pt 91.3% -> 92.2% and it 92.0% -> 92.1% when these were fixed, while
# coverage fell — which is the shape of a system that has stopped claiming to
# read sentences nobody is addressed in.


@pytest.mark.parametrize("language, sentence", [
    ("pt", "Ele fala português."),
    ("pt", "Ela come pão."),
    ("pt", "O trem vai para o centro."),      # a named subject, not a pronoun
    ("pt", "Ele tem um carro."),
    ("pt", "A loja está aberta."),
    ("es", "Él habla español."),
    # Italian rules are `cased`, because Lei and lei are you and she — which
    # made their guards case-sensitive too, so the lower-case blocklist
    # exempted the one position a subject actually occupies: the start of a
    # sentence. Every one of these was mangled while its lower-case twin
    # was handled correctly.
    ("it", "Lui è italiano."),
    ("it", "Lui parla italiano."),
    ("it", "Lui ha tempo."),
    ("it", "lui è italiano."),
    ("it", "Il treno parte adesso."),
])
def test_a_third_person_sentence_is_not_addressed_to_anybody(language, sentence):
    for level in LEVELS:
        assert rewrite(sentence, language, level).text == sentence
    reading = detect(sentence, language)
    assert reading.level is None, (
        f"{sentence!r} is about somebody else but was read as "
        f"{reading.level} at {reading.confidence:.0%}"
    )


@pytest.mark.parametrize("language, source, level, expected", [
    ("es", "Espera un momento.", POLITE, "Espere un momento."),
    ("es", "Habla más despacio.", POLITE, "Hable más despacio."),
    ("it", "Aspetta un momento.", POLITE, "Aspetti un momento."),
    ("it", "Come sta?", CASUAL, "Come stai?"),
])
def test_romance_imperatives_still_rise(language, source, level, expected):
    assert rewrite(source, language, level).text == expected


def test_capitalised_lei_is_still_the_polite_pronoun():
    """
    The one word on the Italian blocklist that stays case-sensitive. "Lei" is
    the polite you and "lei" is she, and that distinction is the reason the
    whole table is cased — so it must survive the fix to the rest of the list.
    """
    assert rewrite("Lei parla inglese?", "it", CASUAL).text != "Lei parla inglese?"
    assert rewrite("lei parla inglese.", "it", CASUAL).text == "lei parla inglese."


# ------------------------------------------------------ the systematic sweep


def _no_marker_rows():
    for path in sorted(glob.glob(str(GOLD / "*.jsonl"))):
        code = Path(path).stem
        if not has_table(code):
            continue
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if not line.strip() or line.startswith("//"):
                    continue
                row = json.loads(line)
                if row.get("level") is None:
                    yield code, row["text"]


def test_no_rule_fires_on_a_sentence_with_nobody_in_it():
    """
    Every gold row that carries no second-person marker, rewritten at all four
    levels. A change to any of them is a rule reaching outside its construction.

    The detection half of this is already a metric; the rewriting half was not
    checked anywhere, and rewriting is where the damage shows.
    """
    damage = []
    for code, text in _no_marker_rows():
        for level in LEVELS:
            out = rewrite(text, code, level)
            if out.text != text:
                damage.append(f"{code}: {text!r} -> {out.text!r}")
                break
    assert not damage, "\n".join(damage)
