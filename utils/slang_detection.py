"""
Slang detection.

``data/slang_dictionary.json`` is nested two levels deep::

    {"en": {"lol": "laughing out loud", ...}, "de": {...}, ...}

The obvious-looking ``slang_dict.keys()`` therefore yields *language codes*,
not slang words — and matching those as bare substrings tags almost every
sentence in the corpus as informal, because "en" is inside "s**en**d" and "pl"
is inside "**pl**ease". That single mistake is what skewed the training splits
to roughly 3:1 informal. Two rules keep it fixed:

1. Always resolve the per-language sub-dictionary before reading words from it.
2. Match on word boundaries, never on substrings.

Boundaries are computed against an explicit delimiter class rather than ``\\b``,
for the same reason the register engine does it: ``\\w`` does not include Indic
combining vowel marks, so ``\\b`` misfires on any script that uses them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

__all__ = [
    "SlangMatch",
    "detect_slang",
    "flatten_slang_dictionary",
    "slang_words_for",
    "informality_score",
]

from .helpers import DELIMITER_CLASS as _DELIMS

_LEFT = f"(?<![^{_DELIMS}])"
_RIGHT = f"(?![^{_DELIMS}])"


@dataclass(frozen=True)
class SlangMatch:
    """One slang hit: what matched, what it means, and where it came from."""

    surface: str
    term: str
    expansion: str
    language: str
    start: int

    def as_dict(self) -> dict:
        return {
            "surface": self.surface,
            "term": self.term,
            "expansion": self.expansion,
            "language": self.language,
            "start": self.start,
        }


def flatten_slang_dictionary(
    slang_dict: Mapping,
    language: Optional[str] = None,
) -> Dict[str, Tuple[str, str]]:
    """
    Normalise whatever shape the dictionary is in into ``{term: (expansion,
    language)}``.

    Accepts the real nested form, and also tolerates a flat ``{term:
    expansion}`` mapping or a bare list of terms, so callers that build small
    dictionaries inline keep working.

    ``language`` restricts the result to one language plus the shared entries.
    Passing None means "every language", which is what you want when the input
    language is not yet known.
    """
    if not slang_dict:
        return {}

    if isinstance(slang_dict, (list, tuple, set)):
        return {
            str(term).lower(): (str(term), language or "")
            for term in slang_dict
            if isinstance(term, str) and term.strip()
        }

    if not isinstance(slang_dict, Mapping):
        return {}

    nested = _looks_nested(slang_dict)
    out: Dict[str, Tuple[str, str]] = {}

    if not nested:
        # Flat {term: expansion}.
        for term, expansion in slang_dict.items():
            if isinstance(term, str) and term.strip():
                out[term.lower()] = (str(expansion), language or "")
        return out

    wanted = _normalise_code(language) if language else None
    for code, entries in slang_dict.items():
        if not isinstance(entries, Mapping):
            continue
        code_norm = _normalise_code(code)
        if wanted is not None and code_norm != wanted:
            continue
        for term, expansion in entries.items():
            if not isinstance(term, str) or not term.strip():
                continue
            # First writer wins, so a language-specific entry is not clobbered
            # by an identical term from another language.
            out.setdefault(term.lower(), (str(expansion), code_norm))
    return out


def detect_slang(
    text: str,
    slang_dict: Mapping,
    lang: Optional[str] = None,
) -> List[SlangMatch]:
    """
    Find slang terms in ``text``.

    ``lang`` selects the sub-dictionary. It used to be accepted and then
    ignored, which meant Portuguese "tb" fired on Spanish text and vice versa.
    Pass None only when the language is genuinely unknown.

    Longer terms are matched first so multi-word entries ("kein bock",
    "v pohodě") win over the single words inside them.
    """
    if not isinstance(text, str) or not text.strip():
        return []

    terms = flatten_slang_dictionary(slang_dict, lang)
    if not terms:
        return []

    matcher = _compile_terms(tuple(sorted(terms)))
    matches: List[SlangMatch] = []
    taken: List[Tuple[int, int]] = []

    for term, pattern in matcher:
        for m in pattern.finditer(text):
            span = (m.start(), m.end())
            if any(span[0] < end and start < span[1] for start, end in taken):
                continue
            taken.append(span)
            expansion, code = terms[term]
            matches.append(
                SlangMatch(
                    surface=m.group(0),
                    term=term,
                    expansion=expansion,
                    language=code,
                    start=m.start(),
                )
            )

    matches.sort(key=lambda s: s.start)
    return matches


def slang_words_for(slang_dict: Mapping, language: Optional[str] = None) -> List[str]:
    """The slang terms for a language — handy for tests and data pipelines."""
    return sorted(flatten_slang_dictionary(slang_dict, language))


def informality_score(text: str, matches: Sequence[SlangMatch]) -> float:
    """
    How strongly the slang evidence points at informal speech, 0.0-1.0.

    Density matters, not just presence: one "ok" in a long formal paragraph is
    weak evidence, whereas three markers in a six-word utterance is decisive.
    """
    if not matches:
        return 0.0
    tokens = max(len(text.split()), 1)
    density = len(matches) / tokens
    # Saturates around three markers in ten words.
    return min(1.0, 0.35 + min(density, 0.3) * 2.2)


# --------------------------------------------------------------------------
# Internals
# --------------------------------------------------------------------------


def _looks_nested(mapping: Mapping) -> bool:
    """True when the mapping is {lang: {term: expansion}} rather than flat."""
    for value in mapping.values():
        if isinstance(value, Mapping):
            return True
    return False


@lru_cache(maxsize=64)
def _compile_terms(terms: Tuple[str, ...]) -> Tuple[Tuple[str, re.Pattern], ...]:
    """Compile once per distinct term set; longest term first."""
    ordered = sorted(terms, key=len, reverse=True)
    return tuple(
        (term, re.compile(f"{_LEFT}{re.escape(term)}{_RIGHT}", re.IGNORECASE))
        for term in ordered
    )


def _normalise_code(code) -> str:
    if not isinstance(code, str):
        return ""
    return code.strip().lower().replace("_", "-").split("-")[0]
