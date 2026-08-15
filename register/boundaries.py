"""
Word-boundary matching for scripts that ``\\b`` gets wrong.

Python's ``\\b`` is defined in terms of ``\\w``, which does not include Indic
combining vowel marks (Unicode category Mn/Mc). So ``\\bকরো\\b`` fails on a
perfectly ordinary Bengali word: the trailing ``ো`` is not a word character, so
there is no word/non-word transition after it for ``\\b`` to find. The same
applies to Devanagari, Gujarati, Gurmukhi, Tamil, Telugu, Kannada and Malayalam
— which is to say, to most of the languages this project exists for.

We therefore define a boundary positively, as "the neighbouring character is a
delimiter or there is no neighbouring character", using lookarounds that are
zero-width at the string edges.
"""

from __future__ import annotations

__all__ = ["DELIMITER_CLASS", "LEFT", "RIGHT", "delimited"]

#: Body of a regex character class listing every character allowed to sit
#: beside a matched word.
#:
#: Written with explicit escapes on purpose. An earlier version spelled this out
#: with literal characters and left a bare ``-`` sitting between two invisible
#: space code points, which ``re`` read as a *range* — quietly promoting a large
#: block of Unicode to "delimiter" and letting "sup" match inside "supper".
#: Keep the hyphen escaped and last.
DELIMITER_CLASS = (
    r"\s"                                       # whitespace, incl. NBSP
    r"\.,!\?;:"                                 # sentence punctuation
    "\"'“”‘’«»"   # quotes
    "…—–"                        # ellipsis, em dash, en dash
    r"/\\\(\)\[\]\{\}"                          # slashes and brackets
    "।॥"                              # Devanagari danda, double danda
    "¿¡"                              # Spanish inverted ? and !
    "、。！？「」"      # CJK punctuation
    "​‌‍"                        # zero-width space / non-joiner / joiner
    r"\-"                                       # hyphen — escaped, and last
)

#: Zero-width assertions. At the start or end of the string the lookaround has
#: nothing to inspect and therefore succeeds, which is what we want.
LEFT = f"(?<![^{DELIMITER_CLASS}])"
RIGHT = f"(?![^{DELIMITER_CLASS}])"


def delimited(pattern: str) -> str:
    """Wrap an already-escaped pattern in boundary assertions."""
    return f"{LEFT}{pattern}{RIGHT}"
