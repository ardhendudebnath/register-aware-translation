"""
Register is not one dial. It is two axes (blueprint 13.2 #1).

Every system that touches formality — this one included, until now — treats it
as a single line from casual to formal. Brown & Gilman showed in 1960 that it
is at least two independent dimensions:

* **power** — how much deference the listener is owed relative to the speaker
* **solidarity** — how close the two of them are

Independent, and that is the whole point. Your boss is high power and low
solidarity. Your grandmother is high power and *high* solidarity. On one line
those two collapse together, and the system reaches for the distant pronoun
with your grandmother — আপনি to the person who raised you — which is wrong in
the most emotionally loaded case the language has.

The Hindi gold set already carries the observation, in a note written long
before this module existed: *"the family elder is high power AND high
solidarity. Hindi families commonly use तुम with grandparents, where a stranger
of the same age would get आप."* That sentence is a two-axis claim with nowhere
to put itself. This is the place.

What this module is *not*: a new set of rule tables. The levels already exist
and the languages already declare which of them they realise, through ``canon``
and :meth:`LanguageTable.fold`. A binary-pronoun language folds Close onto
Casual by itself, so pointing at "a child" in German lands on *du* without
German having to say anything. Only where a language genuinely departs from the
common pattern does it need an entry in :data:`LANGUAGE_OVERRIDES` — which
keeps the amount of unreviewed linguistic claim small, and every one of those
entries carries its reason.

Three vocabularies existed for "who am I talking to" before this — the learner
mode's relationships, the tables' ``address_terms``, and the conversation
participant's ``addressee`` — and none of them knew about the others. They meet
here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from .levels import CASUAL, CLOSE, FORMAL, POLITE
from .tables import get_table, has_table

__all__ = [
    "Relationship",
    "RELATIONSHIPS",
    "CORNERS",
    "POWER_LABELS",
    "SOLIDARITY_LABELS",
    "level_for",
    "level_in",
    "expected_in",
    "nearest",
    "describe",
]


#: What each step of the power axis means. The listener is the reference: 0 is
#: someone you have authority over, 3 someone whose authority is institutional
#: rather than personal.
POWER_LABELS = {
    0: "you are the senior one",
    1: "equals",
    2: "they are senior to you",
    3: "they hold an office",
}

#: And the solidarity axis. This is closeness, not liking — a sibling you are
#: not speaking to is still high solidarity.
SOLIDARITY_LABELS = {
    0: "strangers",
    1: "acquainted",
    2: "close",
}


@dataclass(frozen=True)
class Relationship:
    """A named point on the two axes."""

    key: str
    label: str
    power: int
    solidarity: int
    why: str
    #: Which ``address_terms`` slot fits this person, where the language has
    #: one. This is the join between the two vocabularies.
    address: str = ""
    #: Levels a speaker would accept here, best first, before folding onto
    #: what a particular language realises. More than one, because register is
    #: genuinely contested and a tutor insisting on a single answer would be
    #: teaching something false.
    expected: Tuple[int, ...] = ()

    @property
    def coordinates(self) -> Tuple[int, int]:
        return (self.power, self.solidarity)


#: The named situations. Coordinates first, everything else derived from them.
RELATIONSHIPS: Dict[str, Relationship] = {
    r.key: r for r in (
        Relationship(
            "child", "A child", power=0, solidarity=2,
            address="peer", expected=(CLOSE, CASUAL),
            why="Children take the close form; the polite form sounds like a joke.",
        ),
        Relationship(
            "close_friend", "A close friend", power=1, solidarity=2,
            address="peer", expected=(CASUAL, CLOSE),
            why="The polite form with a close friend reads as distancing.",
        ),
        Relationship(
            "shopkeeper", "A shopkeeper you know", power=1, solidarity=1,
            address="older_man", expected=(CASUAL, POLITE),
            why="Familiar but transactional — casual is normal, polite is safe.",
        ),
        Relationship(
            # A peer, not a superior. What you owe a stranger is distance, not
            # deference — the blueprint's own example is "a stranger your own
            # age: low power, low solidarity". Filed at power 2 the pad read a
            # stranger as a kind of teacher, and a point midway between the two
            # corners came back labelled "shopkeeper".
            "stranger", "Someone you have just met", power=1, solidarity=0,
            address="older_man", expected=(POLITE, FORMAL),
            why="Strangers get the polite form until invited otherwise.",
        ),
        Relationship(
            "elder_family", "An older relative", power=2, solidarity=2,
            address="elder_man", expected=(CASUAL, POLITE),
            why=(
                "The case that makes the second axis necessary: high power and "
                "high solidarity at once. The polite pronoun is not wrong here "
                "so much as cold, and many families use the casual form with "
                "grandparents meaning no disrespect whatever."
            ),
        ),
        Relationship(
            "teacher", "A teacher or senior colleague", power=2, solidarity=1,
            address="elder_man", expected=(POLITE, FORMAL),
            why="Institutional seniority takes the polite form regardless of age.",
        ),
        Relationship(
            "official", "An official or someone in authority", power=3, solidarity=0,
            address="official", expected=(FORMAL, POLITE),
            why="Formal register, and usually a title with it.",
        ),
    )
}

#: The four the blueprint names for the 2D pad, one per quadrant. Stranger and
#: elder share a row — same deference, opposite closeness — which is the
#: contrast the pad exists to make visible.
CORNERS: Tuple[str, ...] = ("stranger", "elder_family", "close_friend", "child")


def level_for(power: int, solidarity: int) -> int:
    """
    The register the two axes point at, before any language sees it.

    Read it as a shape rather than a table: deference rises with power, and
    solidarity pulls back down against it. The one place they cross is the
    family elder, where closeness wins outright.
    """
    if power >= 3:
        return FORMAL
    if power >= 2:
        # Senior to you — polite, unless they are also family, and then the
        # closeness governs and the polite form would read as distance.
        return CASUAL if solidarity >= 2 else POLITE
    if power <= 0:
        return CLOSE
    return POLITE if solidarity <= 0 else CASUAL


#: Where a language departs from the shape above.
#:
#: Kept deliberately short. Every entry is a claim nobody has reviewed yet, and
#: the default already produces the right answer for most of these languages
#: because ``canon`` does the work — a binary-pronoun table folds Close onto
#: Casual on its own.
LANGUAGE_OVERRIDES: Dict[str, Dict[Tuple[int, int], int]] = {
    # Service encounters are where western European usage parts company with
    # South Asian. A Delhi shopkeeper you know takes तुम; a Munich one takes
    # Sie however long you have been going there, and the same holds in France
    # and for Japanese shop staff.
    "de": {(1, 1): POLITE},
    "fr": {(1, 1): POLITE},
    "ja": {(1, 1): POLITE},
}


def level_in(language: str, power: int, solidarity: int) -> int:
    """
    The same point, as the given language actually realises it.

    Two steps, and the second is the reason this needs so little new data:
    take the override if the language declares one, then fold the result onto
    the levels the language has. A language with one informal pronoun collapses
    Close and Casual by itself.
    """
    override = LANGUAGE_OVERRIDES.get(language, {}).get((power, solidarity))
    level = override if override is not None else level_for(power, solidarity)
    if has_table(language):
        return get_table(language).fold(level)
    return level


def expected_in(language: str, key: str) -> Tuple[int, ...]:
    """
    The levels acceptable for a relationship in one language, best first.

    The authored list folded onto what the language realises, deduplicated and
    with the two-axis reading in front. For a three-level language this changes
    nothing; for a two-level one it stops the tutor offering a distinction the
    language does not draw.
    """
    relationship = RELATIONSHIPS.get(key)
    if relationship is None:
        return ()
    fold = get_table(language).fold if has_table(language) else (lambda lvl: lvl)
    ordered = [level_in(language, *relationship.coordinates)]
    ordered += [fold(level) for level in relationship.expected]
    out: list = []
    for level in ordered:
        if level not in out:
            out.append(level)
    return tuple(out)


def nearest(power: int, solidarity: int) -> Relationship:
    """
    The named relationship closest to a point on the pad.

    The pad is continuous and the labels are not, so dragging between corners
    has to land on something sayable. Manhattan distance, with power weighted
    slightly heavier because getting the deference wrong is the more visible
    mistake.
    """
    return min(
        RELATIONSHIPS.values(),
        key=lambda r: 2 * abs(r.power - power) + abs(r.solidarity - solidarity),
    )


def describe(language: str, power: int, solidarity: int) -> Dict[str, object]:
    """Everything the UI needs for one point on the pad."""
    from .levels import level_name  # local: avoid a cycle at import time

    relationship = nearest(power, solidarity)
    level = level_in(language, power, solidarity)
    return {
        "power": power,
        "solidarity": solidarity,
        "power_label": POWER_LABELS.get(power, ""),
        "solidarity_label": SOLIDARITY_LABELS.get(solidarity, ""),
        "relationship": relationship.key,
        "label": relationship.label,
        "why": relationship.why,
        "level": level,
        "level_name": level_name(level),
        "address": relationship.address,
    }
