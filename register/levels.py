"""
Register levels — the single scale everything else is expressed in.

Setu models politeness as four ordered levels (blueprint 3.1). Not every
language fills all four slots: German and Tamil genuinely have two, Japanese
three. Each language table carries a ``canon`` map that folds a nominal level
onto the nearest level that language actually distinguishes, so German ``du``
reports as *Casual* rather than *Close*.
"""

from __future__ import annotations

CLOSE = 0
CASUAL = 1
POLITE = 2
FORMAL = 3

LEVELS = (CLOSE, CASUAL, POLITE, FORMAL)

LEVEL_NAMES = {
    CLOSE: "Close",
    CASUAL: "Casual",
    POLITE: "Polite",
    FORMAL: "Formal",
}

LEVEL_SLUGS = {
    CLOSE: "close",
    CASUAL: "casual",
    POLITE: "polite",
    FORMAL: "formal",
}

_SLUG_TO_LEVEL = {slug: level for level, slug in LEVEL_SLUGS.items()}
_NAME_TO_LEVEL = {name.lower(): level for level, name in LEVEL_NAMES.items()}

#: Sentinel meaning "detect the speaker's register and mirror it".
AUTO = "auto"


def level_name(level: int) -> str:
    """Human-readable name for a level."""
    return LEVEL_NAMES[coerce_level(level)]


def level_slug(level: int) -> str:
    """Lowercase machine-friendly name for a level."""
    return LEVEL_SLUGS[coerce_level(level)]


def coerce_level(value) -> int:
    """
    Accept an int, a slug ("polite"), or a display name ("Polite") and return
    the canonical integer level. Raises ValueError on anything else.
    """
    if isinstance(value, bool):
        raise ValueError(f"invalid register level: {value!r}")
    if isinstance(value, int):
        if value in LEVEL_NAMES:
            return value
        raise ValueError(f"register level out of range 0..3: {value!r}")
    if isinstance(value, str):
        key = value.strip().lower()
        if key in _SLUG_TO_LEVEL:
            return _SLUG_TO_LEVEL[key]
        if key in _NAME_TO_LEVEL:
            return _NAME_TO_LEVEL[key]
        if key.isdigit():
            return coerce_level(int(key))
    raise ValueError(f"invalid register level: {value!r}")


def formality_percent(level: int) -> int:
    """
    Map a register level onto the 0-100 formality scale the rest of the app
    (and the UI) speaks in.
    """
    return {CLOSE: 10, CASUAL: 35, POLITE: 70, FORMAL: 95}[coerce_level(level)]


def level_from_percent(percent: float) -> int:
    """Inverse of :func:`formality_percent`, for the classifier hand-off."""
    try:
        value = float(percent)
    except (TypeError, ValueError):
        return CASUAL
    if value < 22:
        return CLOSE
    if value < 52:
        return CASUAL
    if value < 82:
        return POLITE
    return FORMAL
