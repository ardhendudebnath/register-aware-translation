"""
Formality classification.

Returns a 0-100 formality percentage plus the evidence behind it. Three sources
are combined, in decreasing order of authority:

1. **The register engine.** If the text is in a language with a rule table and
   the engine can read a level off it, that is the strongest signal available —
   it is grounded in actual grammar rather than correlation.
2. **A fine-tuned classifier**, if one has been trained and saved.
3. **Lexical cues** — slang density, contractions, politeness markers,
   punctuation. Always available, never wrong in an interesting way.

The previous implementation returned 30 when any "slang" was found and 70
otherwise, driven by a slang detector that matched language codes as
substrings — so it returned 30 for almost everything.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from register import (
    CASUAL,
    FORMAL,
    LEVELS,
    detect as detect_register,
    formality_percent,
    has_table,
    level_from_percent,
    level_name,
)
from utils.helpers import PROJECT_ROOT, load_slang_dictionary
from utils.slang_detection import SlangMatch, detect_slang, informality_score

from .language_id import detect_language  # re-exported for API compatibility

__all__ = [
    "FormalityResult",
    "classify_formality",
    "detect_language",
    "load_trained_classifier",
]

MODEL_DIR = PROJECT_ROOT / "models" / "formality-classifier"

# Surface cues that are cheap and language-agnostic enough to be worth checking.
_CONTRACTION_RE = re.compile(r"\b\w+'(?:s|t|re|ve|ll|d|m)\b", re.IGNORECASE)
_MULTI_PUNCT_RE = re.compile(r"[!?]{2,}|\.{3,}")
_EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF]"
)
_ALLCAPS_RE = re.compile(r"\b[A-Z]{3,}\b")

_FORMAL_MARKERS = (
    "please", "kindly", "sincerely", "regards", "furthermore", "however",
    "therefore", "would you", "could you", "i would like", "with respect to",
    "bitte", "sehr geehrte", "hochachtungsvoll",
    "veuillez", "cordialement", "je vous prie",
    "por favor", "atentamente", "le agradezco",
    "per favore", "cordiali saluti", "la ringrazio",
    "कृपया", "धन्यवाद", "दयवितः",
    "দয়া করে", "ধন্যবাদ", "অনুগ্রহ করে",
)


@dataclass
class FormalityResult:
    """A formality reading, with the reasoning attached."""

    percent: int
    level: int
    source: str
    language: str = ""
    confidence: float = 0.0
    slang: List[SlangMatch] = field(default_factory=list)
    markers: List[str] = field(default_factory=list)

    @property
    def level_name(self) -> str:
        return level_name(self.level)

    def as_dict(self) -> dict:
        return {
            "percent": self.percent,
            "level": self.level,
            "level_name": self.level_name,
            "source": self.source,
            "language": self.language,
            "confidence": round(self.confidence, 3),
            "slang": [s.as_dict() for s in self.slang],
            "markers": self.markers,
        }


def classify_formality(
    text: str,
    slang_matches: Optional[Sequence[SlangMatch]] = None,
    language: Optional[str] = None,
    use_model: bool = True,
) -> FormalityResult:
    """
    Score how formal ``text`` is, 0-100.

    ``slang_matches`` may be passed in when the caller has already run the
    detector, to avoid doing the work twice. ``language`` should be supplied
    whenever it is known — the slang dictionary and the register tables are
    both per-language, and guessing wastes both.
    """
    if not isinstance(text, str) or not text.strip():
        return FormalityResult(percent=50, level=CASUAL, source="empty",
                               language=language or "")

    lang = language or detect_language(text)

    # 1. Grammar beats correlation. If the language marks register explicitly
    #    and we can read it, use that.
    if has_table(lang):
        reading = detect_register(text, lang)
        if reading.level is not None and reading.confidence >= 0.5:
            return FormalityResult(
                percent=formality_percent(reading.level),
                level=reading.level,
                source="register-engine",
                language=lang,
                confidence=reading.confidence,
                markers=[surface for surface, _ in reading.evidence],
            )

    # 2. A trained classifier, if there is one on disk.
    if use_model:
        model = load_trained_classifier()
        if model is not None:
            scored = model(text)
            if scored is not None:
                percent, confidence = scored
                return FormalityResult(
                    percent=percent,
                    level=level_from_percent(percent),
                    source="trained-model",
                    language=lang,
                    confidence=confidence,
                )

    # 3. Lexical fallback.
    return _lexical_formality(text, lang, slang_matches)


def _lexical_formality(
    text: str,
    lang: str,
    slang_matches: Optional[Sequence[SlangMatch]],
) -> FormalityResult:
    """
    Surface-cue scoring. Starts neutral and moves for each piece of evidence,
    so a sentence with no signal at all lands at 50 rather than being forced
    into a class it has no support for.
    """
    if slang_matches is None:
        slang_matches = detect_slang(text, load_slang_dictionary(), lang)

    score = 50.0
    markers: List[str] = []
    lowered = text.lower()

    slang_pressure = informality_score(text, slang_matches)
    if slang_pressure:
        score -= 30.0 * slang_pressure
        markers.extend(m.term for m in slang_matches)

    formal_hits = [m for m in _FORMAL_MARKERS if m in lowered]
    if formal_hits:
        score += min(25.0, 9.0 * len(formal_hits))
        markers.extend(formal_hits)

    contractions = _CONTRACTION_RE.findall(text)
    if contractions:
        score -= min(12.0, 4.0 * len(contractions))

    if _MULTI_PUNCT_RE.search(text):
        score -= 8.0
        markers.append("!!/??/...")
    if _EMOJI_RE.search(text):
        score -= 15.0
        markers.append("emoji")
    if _ALLCAPS_RE.search(text):
        score -= 6.0

    words = text.split()
    if len(words) >= 12:
        # Long, well-punctuated sentences skew formal; clipped ones do not.
        score += 6.0
    if text.strip().endswith((".", "।", "。")) and len(words) >= 5:
        score += 4.0

    percent = int(max(0, min(100, round(score))))
    evidence_count = len(markers) + len(contractions)
    return FormalityResult(
        percent=percent,
        level=level_from_percent(percent),
        source="lexical",
        language=lang,
        confidence=min(0.9, 0.25 + 0.15 * evidence_count),
        slang=list(slang_matches),
        markers=markers,
    )


@lru_cache(maxsize=1)
def load_trained_classifier():
    """
    Load the fine-tuned classifier if one exists.

    Returns a callable ``text -> (percent, confidence)`` or None. Missing model,
    missing transformers, or a corrupt checkpoint all return None rather than
    raising: the caller has two working fallbacks and the app must not die
    because an optional artefact is absent.
    """
    if not MODEL_DIR.exists():
        return None

    try:
        import json

        import torch
        from transformers import (
            AutoModelForSequenceClassification,
            AutoTokenizer,
        )
    except ImportError:
        return None

    try:
        tokenizer = AutoTokenizer.from_pretrained(str(MODEL_DIR))
        model = AutoModelForSequenceClassification.from_pretrained(str(MODEL_DIR))
        model.eval()
    except Exception:
        return None

    label_map_path = MODEL_DIR / "label_map.json"
    if label_map_path.exists():
        label_map = json.loads(label_map_path.read_text(encoding="utf-8"))
    else:
        label_map = {v: int(k) for k, v in (model.config.id2label or {}).items()}
    inv = {v: k for k, v in label_map.items()}

    # Where each class sits on the 0-100 scale.
    anchors = {"informal": 20, "neutral": 50, "formal": 85}

    def predict(text: str):
        try:
            with torch.no_grad():
                inputs = tokenizer(
                    text, return_tensors="pt", truncation=True, max_length=128
                )
                probs = torch.softmax(model(**inputs).logits, dim=-1)[0]
        except Exception:
            return None

        # Expected value over the class anchors, so a 51/49 split lands in the
        # middle instead of snapping to whichever side won.
        percent = 0.0
        for idx, prob in enumerate(probs.tolist()):
            percent += anchors.get(inv.get(idx, ""), 50) * prob
        return int(round(percent)), float(probs.max())

    return predict
