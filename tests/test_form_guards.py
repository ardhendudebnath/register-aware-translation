"""
How a form's constraints combine with its rule's.

Most rules constrain every form the same way. Some cannot: Portuguese "estás"
is unmistakably second person while "está" is equally "he/she/it is", so the
ambiguous form needs a guard the unambiguous one must not have. That is what
``form_guards`` is for, and the question this file pins down is what happens
to the rule's own guard when a form adds one.

**Blocking guards accumulate. Requirements replace.**

The asymmetry is not arbitrary. A blocker says "never here" and two blockers
are both still true. A requirement says "only here", and a form's own is the
precise one; demanding the rule's as well would ask for two licences at once.

The arrangement before this had form guards replacing the rule's blocker, and
it cost a real bug: giving one Portuguese form a positional guard silently
dropped its third-person guard, and "Ele fala português" came back as "Ele
falas português". The repair was to paste the rule's guard into thirty form
guards, each a copy free to drift from its original.
"""

from __future__ import annotations

import pytest

from register import TABLES, detect, rewrite
from register.engine import _Matcher
from register.levels import CASUAL, CLOSE, POLITE
from register.tables import FormGuard, LanguageTable, Rule


def _matcher(rule: Rule) -> _Matcher:
    """A matcher over one rule, with nothing else to interfere."""
    return _Matcher(LanguageTable(code="xx", name="Test", canon=(0, 1, 2, 3),
                                  rules=(rule,)))


def _allows(rule: Rule, form: str, text: str) -> bool:
    """Whether ``form`` is allowed to match where it appears in ``text``."""
    start = text.index(form)
    patterns = [p for p in _matcher(rule).patterns if p.form == form]
    assert patterns, f"no pattern compiled for {form!r}"
    return patterns[0].guards.allows(text, start, start + len(form))


# ------------------------------------------------------------- accumulation


def test_a_blocking_guard_adds_to_the_rules_own():
    rule = Rule("t.block", ("lo", "lo", "hi", "hi"), "test",
                guard_before=r"\bred\s+",
                form_guards=((("hi"), r"\bblue\s+", "", "", ""),))
    assert not _allows(rule, "hi", "red hi")    # the rule's guard still bites
    assert not _allows(rule, "hi", "blue hi")   # and so does the form's
    assert _allows(rule, "hi", "green hi")


def test_the_unguarded_form_keeps_only_the_rules_guard():
    rule = Rule("t.block", ("lo", "lo", "hi", "hi"), "test",
                guard_before=r"\bred\s+",
                form_guards=((("hi"), r"\bblue\s+", "", "", ""),))
    assert not _allows(rule, "lo", "red lo")
    assert _allows(rule, "lo", "blue lo"), "the other form's guard is not its own"


def test_a_requirement_replaces_rather_than_accumulates():
    """Two licences at once is not what a caller means by a second one."""
    rule = Rule("t.req", ("lo", "lo", "hi", "hi"), "test",
                require_before=r"\bred\s+",
                form_guards=((("hi"), "", "", r"\bblue\s+", ""),))
    assert _allows(rule, "hi", "blue hi")
    assert not _allows(rule, "hi", "red hi"), "the form's requirement is the one that counts"
    assert _allows(rule, "lo", "red lo"), "and the other form keeps the rule's"


def test_a_form_can_ask_for_a_weaker_guard_but_has_to_say_so():
    rule = Rule("t.replace", ("lo", "lo", "hi", "hi"), "test",
                guard_before=r"\bred\s+|\bblue\s+",
                form_guards=(FormGuard("hi", guard_before=r"\bred\s+",
                                       replace=True),))
    assert not _allows(rule, "hi", "red hi")
    assert _allows(rule, "hi", "blue hi"), "replace=True drops the rest of the rule's"
    assert not _allows(rule, "lo", "blue hi".replace("hi", "lo"))


def test_the_tuple_form_still_works():
    """Every table but one still writes these as plain tuples."""
    rule = Rule("t.tuple", ("lo", "lo", "hi", "hi"), "test",
                form_guards=((("hi"), r"\bred\s+", "", "", ""),))
    assert not _allows(rule, "hi", "red hi")
    assert _allows(rule, "hi", "green hi")


# ----------------------------------------------------------------- hygiene


def test_no_form_guard_restates_its_rules_guard():
    """
    Thirty of these existed to work around the old semantics. They are a
    liability now rather than a fix: two copies of a pattern, one of which
    will eventually be edited alone.
    """
    offenders = []
    slots = ("guard_before", "guard_after")
    for code, table in TABLES.items():
        for rule in table.rules:
            for guard in rule.form_guards:
                spec = guard.as_spec() if isinstance(guard, FormGuard) else guard
                if isinstance(guard, FormGuard) and guard.replace:
                    continue            # deliberately its own, see FormGuard
                for index, slot in enumerate(slots, start=1):
                    form_pattern = spec[index] if len(spec) > index else ""
                    rule_pattern = getattr(rule, slot)
                    if form_pattern and rule_pattern and rule_pattern in form_pattern:
                        offenders.append(f"{code} {rule.name} {spec[0]} {slot}")
    assert not offenders, (
        "these repeat the rule's own guard, which now applies anyway:\n"
        + "\n".join(offenders)
    )


# ------------------------------------------------- the bugs this came from


def test_the_portuguese_form_keeps_its_third_person_guard():
    """
    The bug that prompted all of this: a positional guard on the ambiguous
    form dropped the rule's third-person guard, and the sentence about him
    was conjugated as though it were about the listener.
    """
    assert rewrite("Ele fala português.", "pt", CLOSE).text == "Ele fala português."
    assert detect("Ele fala português.", "pt").level is None


def test_the_french_verb_keeps_its_weaker_guard():
    """And the one case that genuinely needs the old behaviour."""
    assert rewrite("Je vous vois demain.", "fr", POLITE).text == "Je vous vois demain."
    assert rewrite("ni sur qui vous êtes,", "fr", CASUAL).text == "ni sur qui tu es,"
