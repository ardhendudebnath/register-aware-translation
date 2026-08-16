"""
Speaker gender — the axis that is not register, but rides along with it.

In Hindi, Marathi and Punjabi the verb agrees with the *speaker's* gender, not
the listener's: a man says मैं करता हूँ and a woman says मैं करती हूँ for the
same sentence. Machine translation has no way to know which, so it picks one —
in practice almost always the masculine, because that is what dominates the
training data. Half of all users are therefore misgendered by default
(blueprint 3.4, last row).

This is orthogonal to register: it does not change how polite you sound, it
changes whether the sentence is about a man or a woman. So it is applied as a
separate pass rather than folded into the rule tables, which would otherwise
need doubling.

Bengali does not mark speaker gender at all, which is why it has no entry here.

Patterns are anchored on the first-person auxiliary rather than the participle
alone. Hindi has ordinary nouns ending in ता — माता (mother), पिता (father),
नेता (leader) — and rewriting those would be considerably worse than leaving
the verb masculine.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .boundaries import LEFT, RIGHT

__all__ = ["MASCULINE", "FEMININE", "NEUTRAL", "apply_speaker_gender",
           "supports_speaker_gender", "GENDERED_LANGUAGES"]

MASCULINE = "male"
FEMININE = "female"
NEUTRAL = "neutral"

# Word endings are matched with the project's delimiter-based boundary, never
# `\b`. Indic vowel signs are Unicode category Mn/Mc, which `\w` excludes — so
# `\bगा\b` does not match "जाऊँगा" and `\bमैं\b` does not match "मैं", because
# both end in a combining mark. Using `\b` here silently disabled the whole
# feature for Marathi and Punjabi.
_E = RIGHT   # end-of-word assertion that understands combining marks


#: (masculine pattern, masculine template, feminine pattern, feminine template)
#: Each entry is reversible: it can move a sentence in either direction.
_PATTERNS: Dict[str, Tuple[Tuple[str, str, str, str], ...]] = {
    "hi": (
        # मैं करता हूँ  <->  मैं करती हूँ
        (r"ता(\s+हूँ)", r"ती\1", r"ती(\s+हूँ)", r"ता\1"),
        (r"ता(\s+हूं)", r"ती\1", r"ती(\s+हूं)", r"ता\1"),
        # मैं कर रहा हूँ  <->  मैं कर रही हूँ
        (r"रहा(\s+हूँ)", r"रही\1", r"रही(\s+हूँ)", r"रहा\1"),
        (r"रहा(\s+हूं)", r"रही\1", r"रही(\s+हूं)", r"रहा\1"),
        # मैं करूँगा  <->  मैं करूँगी
        (rf"गा{_E}", r"गी", rf"गी{_E}", r"गा"),
        # मैं था  <->  मैं थी
        (rf"{LEFT}था{_E}", r"थी", rf"{LEFT}थी{_E}", r"था"),
    ),
    "mr": (
        # मी करतो  <->  मी करते
        (rf"तो{_E}", r"ते", rf"(?<!क)ते{_E}", r"तो"),
        (rf"{LEFT}होतो{_E}", r"होते", rf"{LEFT}होते{_E}", r"होतो"),
    ),
    "pa": (
        # ਮੈਂ ਕਰਦਾ ਹਾਂ  <->  ਮੈਂ ਕਰਦੀ ਹਾਂ
        (r"ਦਾ(\s+ਹਾਂ)", r"ਦੀ\1", r"ਦੀ(\s+ਹਾਂ)", r"ਦਾ\1"),
        (r"ਰਿਹਾ(\s+ਹਾਂ)", r"ਰਹੀ\1", r"ਰਹੀ(\s+ਹਾਂ)", r"ਰਿਹਾ\1"),
        (rf"ਗਾ{_E}", r"ਗੀ", rf"ਗੀ{_E}", r"ਗਾ"),
    ),
    "gu": (
        # હું ગયો  <->  હું ગઈ
        (rf"યો{_E}", r"ઈ", rf"ઈ{_E}", r"યો"),
        (r"તો(\s+હતો)", r"તી\1", r"તી(\s+હતી)", r"તો\1"),
    ),
}

#: First-person markers. A gender rewrite only fires when the sentence is
#: actually about the speaker — "वह करता है" (he does) must not become "करती".
_FIRST_PERSON = {
    "hi": re.compile(rf"{LEFT}(?:मैं|मैंने|मुझे|मेरा|मेरी|मेरे)"),
    "mr": re.compile(rf"{LEFT}(?:मी|मला|माझा|माझी|माझे)"),
    "pa": re.compile(rf"{LEFT}(?:ਮੈਂ|ਮੈਨੂੰ|ਮੇਰਾ|ਮੇਰੀ|ਮੇਰੇ)"),
    "gu": re.compile(rf"{LEFT}(?:હું|મને|મારો|મારી|મારું)"),
}

GENDERED_LANGUAGES = tuple(sorted(_PATTERNS))


@dataclass(frozen=True)
class GenderEdit:
    before: str
    after: str
    start: int

    def describe(self) -> str:
        return f"{self.before} → {self.after}  (speaker.gender)"


def supports_speaker_gender(language: str) -> bool:
    """True when this language marks the speaker's gender on the verb."""
    return _norm(language) in _PATTERNS


def apply_speaker_gender(
    text: str,
    language: str,
    gender: Optional[str],
) -> Tuple[str, List[GenderEdit]]:
    """
    Rewrite first-person verb forms to agree with the speaker's gender.

    Returns ``(text, edits)``. A gender of None or ``NEUTRAL`` is a no-op, as is
    any language that does not mark it — the caller does not have to check
    first.

    Only fires on sentences carrying a first-person marker, so third-person
    verbs with the same ending are left alone.
    """
    lang = _norm(language)
    if (
        not isinstance(text, str)
        or not text.strip()
        or gender not in (MASCULINE, FEMININE)
        or lang not in _PATTERNS
    ):
        return text, []

    marker = _FIRST_PERSON.get(lang)
    if marker is not None and not marker.search(text):
        return text, []

    original = text
    for masc_pat, masc_repl, fem_pat, fem_repl in _PATTERNS[lang]:
        if gender == FEMININE:
            text = re.sub(masc_pat, masc_repl, text)
        else:
            text = re.sub(fem_pat, fem_repl, text)

    if text == original:
        return original, []

    return text, [GenderEdit(before=original, after=text, start=0)]


def _norm(code) -> str:
    if not isinstance(code, str):
        return ""
    return code.strip().lower().replace("_", "-").split("-")[0]
