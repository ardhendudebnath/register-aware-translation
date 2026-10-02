"""
Register rule tables — the linguistic asset.

Every rule is a 4-tuple of equivalent surface forms, one per level
(Close, Casual, Polite, Formal). Because the tuple is symmetric, one dataset
drives all three jobs the engine needs:

    upgrading   casual surface form -> formal surface form
    downgrading formal surface form -> casual surface form
    detection   read the speaker's level from which column their words sit in

Adding a language means adding a table here, not writing code.

Conventions
-----------
* A slot may repeat across levels when the language does not distinguish them
  (Bengali uses আপনি for both Polite and Formal). Repeats are fine and are
  handled by the detector, which splits its vote across matching levels.
* A rule whose four forms are all identical carries no register information.
  ``LanguageTable`` rejects those at construction time rather than letting them
  silently pollute detection.
* ``canon`` folds a nominal level onto the nearest level the language actually
  realises, so German ``du`` reports as Casual rather than Close.
* ``boundary`` is ``"delimited"`` for scripts that separate words with spaces
  and ``"none"`` for scripts that do not (Japanese).
"""

from __future__ import annotations

from typing import Dict, Tuple

from .model import FormGuard, LanguageTable, Rule
from .dravidian import KANNADA, MALAYALAM, TAMIL, TELUGU
from .east_asian import JAPANESE
from .european import ENGLISH, FRENCH, GERMAN, ITALIAN, PORTUGUESE, SPANISH
from .indo_aryan import (
    ASSAMESE,
    BENGALI,
    GUJARATI,
    HINDI,
    MARATHI,
    NEPALI,
    ODIA,
    PUNJABI,
    URDU,
)

__all__ = [
    "FormGuard",
    "Rule",
    "LanguageTable",
    "TABLES",
    "supported_languages",
    "get_table",
    "has_table",
]


TABLES: Dict[str, LanguageTable] = {
    t.code: t
    for t in (
        BENGALI,
        HINDI,
        MARATHI,
        GUJARATI,
        PUNJABI,
        URDU,
        ODIA,
        ASSAMESE,
        NEPALI,
        TAMIL,
        TELUGU,
        KANNADA,
        MALAYALAM,
        GERMAN,
        FRENCH,
        SPANISH,
        ITALIAN,
        PORTUGUESE,
        JAPANESE,
        ENGLISH,
    )
}


def supported_languages() -> Tuple[str, ...]:
    """Language codes that have a register table, in table order."""
    return tuple(TABLES.keys())


def has_table(code: str) -> bool:
    return _normalise(code) in TABLES


def get_table(code: str) -> LanguageTable:
    key = _normalise(code)
    try:
        return TABLES[key]
    except KeyError:
        raise KeyError(
            f"no register table for language {code!r}; "
            f"available: {', '.join(sorted(TABLES))}"
        ) from None


def _normalise(code: str) -> str:
    """Accept 'bn', 'BN', 'bn-IN', 'bn_IN' and land on 'bn'."""
    if not isinstance(code, str):
        return ""
    return code.strip().lower().replace("_", "-").split("-")[0]
