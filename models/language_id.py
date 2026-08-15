"""
Language identification.

Two stages, cheapest first:

1. **Script detection.** Most of the languages this project cares about have a
   Unicode block to themselves — Bengali, Tamil, Telugu, Kannada, Malayalam,
   Gujarati and Gurmukhi are each unambiguous from a single character. This is
   free, needs no model, and is *more* reliable than a statistical detector on
   the short utterances speech produces.

2. **Statistical detection.** Only for the ambiguous cases: Latin script (a
   dozen candidates) and Devanagari (Hindi vs Marathi vs Nepali vs Sanskrit).
   Uses ``langdetect`` when installed; falls back to a stop-word vote otherwise
   so the pipeline degrades rather than breaks.

The previous implementation returned the string ``"en"`` unconditionally.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from typing import Dict, Optional, Tuple

__all__ = ["detect_language", "detect_script", "SCRIPT_TO_LANGUAGE"]

# Unicode ranges that identify a language outright.
_SCRIPT_RANGES: Tuple[Tuple[int, int, str], ...] = (
    (0x0980, 0x09FF, "Bengali"),
    (0x0A00, 0x0A7F, "Gurmukhi"),
    (0x0A80, 0x0AFF, "Gujarati"),
    (0x0B00, 0x0B7F, "Oriya"),
    (0x0B80, 0x0BFF, "Tamil"),
    (0x0C00, 0x0C7F, "Telugu"),
    (0x0C80, 0x0CFF, "Kannada"),
    (0x0D00, 0x0D7F, "Malayalam"),
    (0x0D80, 0x0DFF, "Sinhala"),
    (0x0900, 0x097F, "Devanagari"),
    (0x0600, 0x06FF, "Arabic"),
    (0x0400, 0x04FF, "Cyrillic"),
    (0x0370, 0x03FF, "Greek"),
    (0x3040, 0x309F, "Hiragana"),
    (0x30A0, 0x30FF, "Katakana"),
    (0x4E00, 0x9FFF, "Han"),
    (0xAC00, 0xD7AF, "Hangul"),
    (0x0E00, 0x0E7F, "Thai"),
    (0x0590, 0x05FF, "Hebrew"),
)

#: Scripts used by exactly one language we support.
SCRIPT_TO_LANGUAGE: Dict[str, str] = {
    "Bengali": "bn",
    "Gurmukhi": "pa",
    "Gujarati": "gu",
    "Oriya": "or",
    "Tamil": "ta",
    "Telugu": "te",
    "Kannada": "kn",
    "Malayalam": "ml",
    "Sinhala": "si",
    "Hiragana": "ja",
    "Katakana": "ja",
    "Hangul": "ko",
    "Thai": "th",
    "Hebrew": "he",
    "Greek": "el",
}

# Ambiguous scripts, with the candidates the statistical stage must choose from.
_AMBIGUOUS = {
    "Devanagari": ("hi", "mr", "ne", "sa"),
    "Cyrillic": ("ru", "uk", "bg", "sr"),
    "Arabic": ("ar", "ur", "fa"),
    "Han": ("zh", "ja"),
    "Latin": (
        "en", "de", "fr", "es", "it", "nl", "pl", "pt", "cs", "da",
        "nb", "sk", "sv", "ro", "tr", "id", "vi",
    ),
}

# Cheap stop-word vote, used when langdetect is unavailable. Deliberately small
# — this is a fallback, not a competitor to a real detector.
_STOPWORDS: Dict[str, Tuple[str, ...]] = {
    "en": ("the", "and", "is", "you", "to", "of", "that", "have", "with", "this"),
    "de": ("der", "die", "das", "und", "ist", "nicht", "sie", "ich", "mit", "ein"),
    "fr": ("le", "la", "les", "et", "est", "vous", "je", "que", "pas", "une"),
    "es": ("el", "la", "los", "que", "de", "y", "es", "un", "por", "con"),
    "it": ("il", "la", "che", "di", "e", "un", "per", "non", "sono", "con"),
    "nl": ("de", "het", "een", "en", "is", "van", "je", "niet", "dat", "met"),
    "pl": ("nie", "jest", "sie", "to", "na", "w", "z", "do", "ze", "jak"),
    "pt": ("o", "a", "de", "que", "e", "do", "da", "em", "para", "com"),
    "cs": ("je", "na", "se", "ne", "to", "v", "a", "ze", "pro", "jak"),
    "sk": ("je", "na", "sa", "nie", "to", "v", "a", "zo", "pre", "ako"),
    "da": ("og", "er", "det", "en", "til", "af", "for", "ikke", "med", "har"),
    "nb": ("og", "er", "det", "en", "til", "av", "for", "ikke", "med", "har"),
    "sv": ("och", "är", "det", "en", "till", "av", "för", "inte", "med", "har"),
    "hi": ("है", "और", "में", "की", "को", "नहीं", "यह", "से", "का", "पर"),
    "mr": ("आहे", "आणि", "मध्ये", "ची", "ला", "नाही", "हे", "पासून", "चा", "वर"),
    "ru": ("и", "не", "что", "это", "на", "в", "с", "как", "по", "но"),
    "uk": ("і", "не", "що", "це", "на", "в", "з", "як", "по", "але"),
}

_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


def detect_script(text: str) -> str:
    """
    The dominant script in ``text``.

    Counts only letters, so punctuation and digits in an otherwise Bengali
    sentence do not drag the answer toward Latin. Returns "Latin" when nothing
    else dominates and "Unknown" for text with no letters at all.
    """
    if not isinstance(text, str) or not text:
        return "Unknown"

    counts: Counter = Counter()
    for ch in text:
        if not ch.isalpha():
            continue
        code = ord(ch)
        for lo, hi, name in _SCRIPT_RANGES:
            if lo <= code <= hi:
                counts[name] += 1
                break
        else:
            if code < 0x0250 or 0x1E00 <= code <= 0x1EFF:
                counts["Latin"] += 1

    if not counts:
        return "Unknown"
    return counts.most_common(1)[0][0]


def detect_language(text: str, default: str = "en") -> str:
    """
    Best-guess ISO 639-1 code for ``text``.

    Returns ``default`` for empty or unidentifiable input rather than raising —
    a translator that stops working because someone coughed into the mic is
    worse than one that guesses.
    """
    if not isinstance(text, str) or not text.strip():
        return default

    script = detect_script(text)

    direct = SCRIPT_TO_LANGUAGE.get(script)
    if direct:
        return direct

    candidates = _AMBIGUOUS.get(script)
    if not candidates:
        return default

    guess = _statistical_guess(text, candidates)
    if guess:
        return guess
    return _stopword_vote(text, candidates) or candidates[0]


def _statistical_guess(text: str, candidates: Tuple[str, ...]) -> Optional[str]:
    """Ask langdetect, constrained to the candidates the script allows."""
    try:
        from langdetect import DetectorFactory, detect_langs
    except ImportError:
        return None

    # Without this, langdetect is nondeterministic across runs on short input.
    DetectorFactory.seed = 0

    try:
        ranked = detect_langs(text)
    except Exception:
        return None

    allowed = set(candidates)
    for item in ranked:
        code = str(item.lang).split("-")[0].lower()
        if code in allowed:
            return code
    return None


def _stopword_vote(text: str, candidates: Tuple[str, ...]) -> Optional[str]:
    """Count stop-word hits per candidate language and take the winner."""
    words = {w.lower() for w in _WORD_RE.findall(text)}
    if not words:
        return None

    scores: Counter = Counter()
    for code in candidates:
        stops = _STOPWORDS.get(code)
        if not stops:
            continue
        scores[code] = len(words & set(stops))

    if not scores:
        return None
    best, hits = scores.most_common(1)[0]
    return best if hits else None
