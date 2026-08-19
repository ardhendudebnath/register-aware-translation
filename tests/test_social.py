"""
The two-axis register model (blueprint 13.2 #1).

The claim being tested is narrow and specific: a stranger and a family elder
are owed the *same* deference and differ only in closeness, so any model with
one dial puts them in the same place and reaches for the distant pronoun with
your grandmother. These tests fail if the second axis stops doing anything.
"""

from __future__ import annotations

import pytest

from register import CASUAL, CLOSE, FORMAL, POLITE, get_table, rewrite
from register.social import (
    CORNERS,
    LANGUAGE_OVERRIDES,
    RELATIONSHIPS,
    describe,
    expected_in,
    level_for,
    level_in,
    nearest,
)


@pytest.mark.parametrize("language", ["bn", "hi", "de", "ja", "es", "ur", "ta"])
def test_stranger_and_family_elder_are_not_the_same_place(language):
    """
    The whole reason for the second axis.

    Both are people you owe respect. One gets the distant pronoun and one does
    not, and no amount of sliding a single dial expresses that.
    """
    stranger = level_in(language, *RELATIONSHIPS["stranger"].coordinates)
    elder = level_in(language, *RELATIONSHIPS["elder_family"].coordinates)
    assert stranger != elder, (
        f"{language}: a stranger and a grandmother landed on the same register"
    )


def test_the_elder_is_closer_not_more_distant():
    """Specifically: closeness wins over deference, it does not merely soften."""
    assert level_for(*RELATIONSHIPS["elder_family"].coordinates) == CASUAL
    assert level_for(*RELATIONSHIPS["stranger"].coordinates) == POLITE


def test_power_and_solidarity_move_independently():
    """Hold one axis, move the other, and the answer changes. Twice."""
    # Same closeness, rising power.
    assert level_for(0, 0) == CLOSE
    assert level_for(1, 0) == POLITE
    assert level_for(3, 0) == FORMAL
    # Same power, rising closeness.
    assert level_for(2, 0) == POLITE
    assert level_for(2, 2) == CASUAL


@pytest.mark.parametrize("language", ["de", "fr", "ta", "te", "en"])
def test_two_pronoun_languages_need_no_data_of_their_own(language):
    """
    The canon already says which levels a language realises, so pointing at a
    child in German lands on du without German declaring anything. This is what
    keeps the amount of unreviewed linguistic claim small.
    """
    assert language not in LANGUAGE_OVERRIDES or (0, 2) not in LANGUAGE_OVERRIDES[language]
    child = level_in(language, *RELATIONSHIPS["child"].coordinates)
    assert child == get_table(language).fold(CLOSE)


def test_service_encounters_differ_by_culture():
    """A shopkeeper you know takes तुम in Delhi and Sie in Munich."""
    shop = RELATIONSHIPS["shopkeeper"].coordinates
    assert level_in("hi", *shop) == CASUAL
    assert level_in("de", *shop) == POLITE
    assert level_in("fr", *shop) == POLITE


@pytest.mark.parametrize("key", CORNERS)
def test_every_corner_is_reachable_and_named(key):
    relationship = RELATIONSHIPS[key]
    assert nearest(*relationship.coordinates).key == key


@pytest.mark.parametrize("point", [(2, 1), (1, 0), (3, 2), (0, 0), (2, 2)])
def test_dragging_between_corners_lands_on_something_sayable(point):
    """The pad is continuous and the labels are not."""
    assert nearest(*point).key in RELATIONSHIPS


def test_a_two_level_language_stops_offering_a_distinction_it_lacks():
    """
    German has one informal pronoun, so Close and Casual are one thing. The
    tutor used to offer a correction between two identical forms.
    """
    assert expected_in("de", "child") == (CASUAL,)
    assert expected_in("bn", "child") == (CLOSE, CASUAL)


def test_the_model_reaches_three_different_pronouns_in_bengali():
    """End to end: one sentence, three relationships, three pronouns."""
    source = "আপনি কেমন আছেন?"
    said = {
        key: rewrite(source, "bn", level_in("bn", *RELATIONSHIPS[key].coordinates)).text
        for key in ("stranger", "elder_family", "child")
    }
    assert said["stranger"].startswith("আপনি")
    assert said["elder_family"].startswith("তুমি")
    assert said["child"].startswith("তুই")
    assert len(set(said.values())) == 3


def test_describe_gives_the_ui_everything_it_needs():
    out = describe("bn", *RELATIONSHIPS["elder_family"].coordinates)
    assert out["relationship"] == "elder_family"
    assert out["level_name"] == "Casual"
    assert out["address"]          # the vocative slot, joined from the tables
    assert out["why"]


def test_relationships_join_the_address_term_vocabulary():
    """
    The third of the three vocabularies. Every relationship names a slot the
    tables actually have, or the vocative silently never fires.
    """
    slots = set(get_table("bn").address_terms)
    for relationship in RELATIONSHIPS.values():
        assert relationship.address in slots, (
            f"{relationship.key} points at {relationship.address!r}, "
            f"which no table declares"
        )
