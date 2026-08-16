"""
Context-sensitive replacements.

Most rules are a straight lookup: match a form, emit the form at the requested
level. A few cannot be, because the target language needs information the source
form does not carry. French ``votre`` is the clear case — it is gender-neutral,
so downgrading it to ``ton`` or ``ta`` requires knowing the gender of the noun
that comes next.

A selector receives the matched span and its surroundings and returns the
replacement, or None to fall back to the table's own answer. Selectors are
looked up by name so the rule tables stay plain data.
"""

from __future__ import annotations

import re
from typing import Callable, Dict, Optional

from .gender import french_possessive
from .levels import CASUAL, CLOSE

__all__ = ["SELECTORS", "get_selector"]

_NEXT_WORD = re.compile(r"^\s*([^\s.,!?;:\"'()\[\]{}«»]+)")


def _following_word(text: str, end: int) -> str:
    match = _NEXT_WORD.match(text[end:])
    return match.group(1) if match else ""


def french_possessive_selector(surface: str, level: int, text: str,
                               start: int, end: int) -> Optional[str]:
    """
    Pick ``ton`` / ``ta`` when downgrading French ``votre``.

    Only fires on the way down. Going up, every singular possessive collapses
    to ``votre`` and the table already says so.
    """
    if level > CASUAL:
        return None
    if surface.lower() not in ("votre", "vôtre"):
        return None

    chosen = french_possessive(_following_word(text, end))
    # Preserve a sentence-initial capital.
    return chosen.capitalize() if surface[:1].isupper() else chosen


SELECTORS: Dict[str, Callable[..., Optional[str]]] = {
    "fr_possessive": french_possessive_selector,
}


def get_selector(name: str):
    """Look up a selector by name, or None when the name is unknown."""
    return SELECTORS.get(name)
