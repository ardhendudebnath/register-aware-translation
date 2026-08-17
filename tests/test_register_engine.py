"""
Register engine tests.

Blueprint 9 is emphatic that measurement is what turns this from a demo into a
product, and that the metric which will bite you is *semantic preservation*: a
rule that makes something more polite but subtly wrong is worse than no rule.
These tests are the regression net for exactly that — every case here is a
sentence the engine used to get wrong, or a property that must not regress.
"""

from __future__ import annotations

import pytest

from register import (
    AUTO,
    CASUAL,
    CLOSE,
    FORMAL,
    LEVELS,
    POLITE,
    TABLES,
    address_term,
    coerce_level,
    detect,
    formality_percent,
    get_table,
    has_table,
    ladder,
    level_name,
    politeness_warning,
    pre_edit,
    prosody,
    rewrite,
    supported_languages,
)


# ---------------------------------------------------------------- structure


def test_all_tables_load():
    assert len(TABLES) == 20
    for code in supported_languages():
        assert has_table(code)


@pytest.mark.parametrize("code", sorted(TABLES))
def test_every_rule_is_discriminative(code):
    """A rule whose four forms are identical carries no register information."""
    for rule in get_table(code).rules:
        assert rule.is_discriminative, f"{code}:{rule.name} has four identical forms"


@pytest.mark.parametrize("code", sorted(TABLES))
def test_rule_names_unique(code):
    names = [r.name for r in get_table(code).rules]
    assert len(names) == len(set(names))


@pytest.mark.parametrize("code", sorted(TABLES))
def test_canon_is_idempotent(code):
    """Folding an already-folded level must not move it again."""
    table = get_table(code)
    for level in LEVELS:
        once = table.fold(level)
        assert table.fold(once) == once


def test_language_code_normalisation():
    assert has_table("BN")
    assert has_table("bn-IN")
    assert has_table("bn_IN")
    assert not has_table("xx")


# ------------------------------------------------------------------ rewrite


@pytest.mark.parametrize(
    "lang,source,level,expected",
    [
        # Bengali — three genuine registers plus honorific verb agreement
        ("bn", "তুমি কি করছ?", CLOSE, "তুই কি করছিস?"),
        ("bn", "তুমি কি করছ?", POLITE, "আপনি কি করছেন?"),
        ("bn", "আপনি কেমন আছেন?", CASUAL, "তুমি কেমন আছ?"),
        ("bn", "তুই কোথায় যাস?", POLITE, "আপনি কোথায় যান?"),
        ("bn", "আপনি কি আমাকে আপনার বই দিতে পারেন?", CLOSE,
         "তুই কি আমাকে তোর বই দিতে পারিস?"),
        # Hindi
        ("hi", "तुम क्या करते हो?", POLITE, "आप क्या करते हैं?"),
        ("hi", "आप कैसे हैं?", CASUAL, "तुम कैसे हो?"),
        ("hi", "जाओ", POLITE, "जाइए"),
        # German — pronoun and verb must move together
        ("de", "Kannst du mir dein Buch geben?", POLITE,
         "Können Sie mir Ihr Buch geben?"),
        ("de", "Sie sind sehr nett.", CASUAL, "Du bist sehr nett."),
        ("de", "Sie haben Ihr Buch vergessen.", CASUAL,
         "Du hast dein Buch vergessen."),
        ("de", "Wo wohnen Sie?", CASUAL, "Wo wohnst du?"),
        # French — subject, clitic and tonic are three different targets
        ("fr", "Vous êtes très gentil.", CASUAL, "Tu es très gentil."),
        ("fr", "Je vous vois demain.", CASUAL, "Je te vois demain."),
        ("fr", "C'est pour vous.", CASUAL, "C'est pour toi."),
        ("fr", "Il vous attend.", CASUAL, "Il t'attend."),
        ("fr", "Tu es très gentil.", POLITE, "Vous êtes très gentil."),
        # Spanish / Italian
        ("es", "¿Puedes darme tu libro?", POLITE, "¿Puede darme su libro?"),
        ("it", "Puoi darmi il tuo libro?", POLITE, "Può darmi il Suo libro?"),
        # Japanese — no word boundaries, so matching is substring-ordered
        ("ja", "これをする。", POLITE, "これをします。"),
        ("ja", "これをする。", FORMAL, "これをいたします。"),
        # Tamil
        ("ta", "நீ எப்படி இருக்கிறாய்?", POLITE, "நீங்கள் எப்படி இருக்கிறீர்கள்?"),
    ],
)
def test_rewrite(lang, source, level, expected):
    assert rewrite(source, lang, level).text == expected


@pytest.mark.parametrize(
    "lang,text",
    [
        # German "sie/Sie/ihr" is she/you/her. Only the verb disambiguates, and
        # getting this wrong turns "she is nice" into "you is nice".
        ("de", "Sie ist nett und sie hat ihr Buch."),
        ("de", "Sie kommt morgen."),
        ("de", "Sie hat ihr Auto verkauft."),
        # Italian lowercase "lei" (she), "le" (the/to her), "sua" (her) are not
        # the polite pronoun, and case is what distinguishes them.
        ("it", "Ho visto lei e le sue amiche."),
        ("it", "Anche lei ha la sua ragione."),
    ],
)
def test_third_person_is_not_rewritten(lang, text):
    """Downgrading must leave third-person pronouns completely alone."""
    assert rewrite(text, lang, CASUAL).text == text
    assert rewrite(text, lang, CLOSE).text == text


def test_italian_sentence_initial_lei_is_read_as_polite():
    """
    Documents a known limitation rather than asserting a fix.

    Italian polite "Lei" is capitalised by convention even mid-sentence, which
    is how the engine tells it from "lei" (she). At the start of a sentence both
    capitalise, and polite Lei takes the same third-person verb as she, so the
    two are not separable by any local rule. The engine resolves the tie toward
    the polite reading; mid-sentence casing is handled correctly either way.
    """
    assert rewrite("Lei è molto gentile.", "it", CASUAL).text == "Tu sei molto gentile."
    # Mid-sentence, the distinction survives and lowercase 'lei' is untouched.
    assert rewrite("Ho visto lei.", "it", CASUAL).text == "Ho visto lei."


def test_unknown_language_passes_through():
    """An unsupported language returns the text untouched, not an exception."""
    result = rewrite("hello there", "xx", POLITE)
    assert result.text == "hello there"
    assert result.edits == ()


def test_empty_and_whitespace():
    for text in ("", "   ", "\n"):
        assert rewrite(text, "bn", POLITE).text == text


def test_rewrite_rejects_non_string():
    with pytest.raises(TypeError):
        rewrite(None, "bn", POLITE)


def test_no_double_application():
    """
    A clause rule's output must not be re-matched by the bare pronoun rule
    nested inside it: "kannst du" -> "können Sie" must not then become
    "können Sie" -> something else.
    """
    result = rewrite("Kannst du kommen?", "de", POLITE)
    assert result.text == "Können Sie kommen?"
    assert result.text.count("Sie") == 1


# ------------------------------------------------------------- round trips


@pytest.mark.parametrize(
    "lang,formal",
    [
        ("bn", "আপনি কি করছেন?"),
        ("bn", "আপনি কোথায় যান?"),
        ("hi", "आप क्या करते हैं?"),
        ("de", "Können Sie mir Ihr Buch geben?"),
        ("de", "Sie sind sehr nett."),
        ("fr", "Pouvez-vous me donner votre livre ?"),
        ("fr", "Vous êtes très gentil."),
        ("es", "¿Puede darme su libro?"),
        ("it", "Può darmi il Suo libro?"),
        ("ja", "これをします。"),
        ("ta", "நீங்கள் எப்படி இருக்கிறீர்கள்?"),
    ],
)
def test_round_trip_is_stable(lang, formal):
    """polite -> casual -> polite must land exactly back where it started."""
    casual = rewrite(formal, lang, CASUAL).text
    back = rewrite(casual, lang, POLITE).text
    assert back == formal


@pytest.mark.parametrize("code", sorted(TABLES))
def test_rewriting_to_own_level_is_a_noop(code):
    """
    Text already at level N must be unchanged when asked for level N.

    Homographs are excluded: Gujarati આપ is the formal pronoun *you* in one rule
    and the imperative *give!* in another, so "its own level" is not a single
    well-defined thing for that surface. Those are covered by their own guards
    and cases instead.
    """
    table = get_table(code)

    seen = {}
    for rule in table.rules:
        for surface in rule.forms:
            if surface:
                seen.setdefault(surface, set()).add(rule.name)
    homographs = {s for s, rules in seen.items() if len(rules) > 1}

    for rule in table.rules:
        for level in table.distinct_levels:
            surface = rule.forms[level]
            if not surface or surface in homographs:
                continue
            result = rewrite(surface, code, level)
            assert result.text == surface, (
                f"{code}:{rule.name} at {level_name(level)} changed {surface!r} "
                f"to {result.text!r}"
            )


# -------------------------------------------------------------- detection


@pytest.mark.parametrize(
    "lang,text,expected",
    [
        ("bn", "তুই কোথায় যাস?", CLOSE),
        ("bn", "তুমি কি করছ?", CASUAL),
        ("bn", "আপনি কেমন আছেন?", POLITE),
        ("hi", "तुम क्या करते हो?", CASUAL),
        ("hi", "आप कैसे हैं?", POLITE),
        ("de", "Kannst du mir helfen?", CASUAL),
        ("de", "Können Sie mir helfen?", POLITE),
        ("fr", "Tu es gentil.", CASUAL),
        ("fr", "Vous êtes gentil.", POLITE),
        ("ja", "これをします。", POLITE),
    ],
)
def test_detect(lang, text, expected):
    assert detect(text, lang).level == expected


def test_detect_returns_none_without_evidence():
    reading = detect("Das Wetter ist gut.", "de")
    assert reading.level is None
    assert reading.confidence == 0.0


def test_detect_ties_break_toward_polite():
    """
    Bengali আপনি spans Polite and Formal equally. A native speaker calls that
    Polite; Formal is reserved for sentences that also carry দয়া করে.
    """
    assert detect("আপনি কেমন আছেন?", "bn").level == POLITE


def test_detect_on_unsupported_language():
    assert detect("hello", "xx").level is None


# ------------------------------------------------------------------ ladder


def test_ladder_covers_every_level():
    rungs = ladder("তুমি কি করছ?", "bn")
    assert set(rungs) == set(LEVELS)
    assert rungs[CLOSE].text == "তুই কি করছিস?"
    assert rungs[POLITE].text == "আপনি কি করছেন?"


def test_ladder_folds_two_level_languages():
    """German Close and Casual are the same form; the ladder must say so."""
    rungs = ladder("Können Sie mir helfen?", "de")
    assert rungs[CLOSE].text == rungs[CASUAL].text


# -------------------------------------------------------------------- auto


def test_auto_mirrors_the_speaker():
    for text, expected in [
        ("তুই কোথায় যাস?", CLOSE),
        ("তুমি কি করছ?", CASUAL),
        ("আপনি কেমন আছেন?", POLITE),
    ]:
        result = rewrite(text, "bn", AUTO)
        assert result.level == expected
        assert result.text == text


# ------------------------------------------------------------------- edits


def test_edits_are_reported():
    result = rewrite("তুমি কি করছ?", "bn", POLITE)
    assert len(result.edits) == 2
    pairs = {(e.before, e.after) for e in result.edits}
    assert ("তুমি", "আপনি") in pairs
    assert ("করছ", "করছেন") in pairs
    assert all(e.rule for e in result.edits)


def test_no_edits_when_nothing_changes():
    assert rewrite("আপনি কেমন আছেন?", "bn", POLITE).edits == ()


def test_result_serialises():
    payload = rewrite("তুমি কি করছ?", "bn", POLITE).as_dict()
    assert payload["level_name"] == "Polite"
    assert payload["formality_percent"] == 70
    assert isinstance(payload["edits"], list)


# ------------------------------------------------------- levels and prosody


def test_coerce_level_accepts_several_spellings():
    assert coerce_level(2) == POLITE
    assert coerce_level("polite") == POLITE
    assert coerce_level("Polite") == POLITE
    assert coerce_level("2") == POLITE
    for bad in (-1, 4, "nope", None, True):
        with pytest.raises(ValueError):
            coerce_level(bad)


def test_formality_percent_is_monotonic():
    values = [formality_percent(level) for level in LEVELS]
    assert values == sorted(values)


def test_prosody_tracks_register():
    """Formal must be slower and lower than Close, or it will not sound formal."""
    close, formal = prosody(CLOSE), prosody(FORMAL)
    assert formal["rate"] < close["rate"]
    assert formal["pitch"] < close["pitch"]
    assert formal["pause_ms"] > close["pause_ms"]


# ---------------------------------------------------- address and warnings


def test_address_terms():
    assert address_term("bn", CASUAL, "older_man") == "দাদা"
    assert address_term("hi", CASUAL, "older_woman") == "दीदी"
    assert address_term("ta", CASUAL, "older_man") == "அண்ணா"
    assert address_term("de", CASUAL, "older_man") == ""      # no vocative slot
    assert address_term("bn", CASUAL, "nonexistent") == ""


def test_address_term_is_inserted():
    result = rewrite("আপনি কেমন আছেন?", "bn", POLITE, addressee="older_man")
    assert result.text.startswith("দাদা,")


def test_softener_is_added_once():
    once = rewrite("করুন", "bn", FORMAL, soften=True).text
    twice = rewrite(once, "bn", FORMAL, soften=True).text
    assert once.startswith("দয়া করে")
    assert twice == once


def test_politeness_warning_fires_on_close_register():
    warning = politeness_warning("আপনি কেমন আছেন?", "bn", CLOSE)
    assert warning and "আপনি" in warning


def test_no_warning_for_polite_register():
    assert politeness_warning("আপনি কেমন আছেন?", "bn", POLITE) is None


# ----------------------------------------------------------------- pre-edit


def test_pre_edit_adds_please_for_formal_targets():
    assert pre_edit("Give me the book.", "en", FORMAL).startswith("Please give")


def test_pre_edit_strips_scaffolding_for_casual_targets():
    assert "kindly" not in pre_edit("Could you kindly help me?", "en", CASUAL).lower()


def test_pre_edit_leaves_existing_politeness_alone():
    text = "Please give me the book."
    assert pre_edit(text, "en", FORMAL) == text


# ------------------------------------------------------------ script safety


def test_indic_boundaries_do_not_match_inside_words():
    """
    Python's \\b is defined on \\w, which excludes Indic combining vowel marks.
    A naive boundary therefore misfires on ordinary Bengali words — this is the
    regression test for the delimiter-class approach that replaced it.
    """
    # করছেন contains করছ but must not be rewritten as if it were the bare form.
    assert rewrite("আপনি করছেন", "bn", POLITE).text == "আপনি করছেন"
    # তুমিও ("you too") must not have তুমি swapped out of it.
    assert "আপনিও" not in rewrite("তুমিও", "bn", POLITE).text


@pytest.mark.parametrize(
    "lang,text,expected",
    [
        # U+06D4, the Urdu full stop. Leaving it out of the delimiter class
        # silently disabled register detection for every sentence-final word in
        # the language — "یہاں بیٹھو۔" read as no register at all.
        ("ur", "یہاں بیٹھو۔", CASUAL),
        ("ur", "یہاں بیٹھیے۔", POLITE),
        ("ur", "یہاں آ۔", CLOSE),
        # Devanagari danda, the same class of bug.
        ("hi", "यहाँ बैठो।", CASUAL),
        ("bn", "এখানে বসো।", CASUAL),
    ],
)
def test_script_terminators_do_not_break_boundaries(lang, text, expected):
    """
    A script's own sentence terminator must count as a word boundary.

    Each script brings its own punctuation, and forgetting one does not fail
    loudly — it just makes every sentence-final word invisible to the matcher.
    """
    assert detect(text, lang).level == expected


def test_japanese_matches_without_spaces():
    result = rewrite("わたしはこれをする。", "ja", POLITE)
    assert result.text == "わたしはこれをします。"
