"""
The three metrics from blueprint 9, measured separately.

    register accuracy      of translations requested at level N, what fraction
                           actually land at level N?
    detection accuracy     when the speaker used আপনি, does Auto report Polite?
    semantic preservation  did the register rewrite break the meaning?

The third is the one that will bite you. A rule that makes something more polite
but subtly wrong is worse than no rule, and it is invisible to the first two
metrics — a sentence can be perfectly Polite and also nonsense. It is tracked
from day one here, with a similarity model when one is installed and a
character-level fallback when not, so it is never silently skipped.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from register import (
    LEVELS,
    coerce_level,
    detect,
    has_table,
    level_name,
    rewrite,
)

__all__ = [
    "Case",
    "MetricResult",
    "EvaluationReport",
    "register_accuracy",
    "detection_accuracy",
    "semantic_preservation",
    "evaluate",
]


@dataclass(frozen=True)
class Case:
    """One annotated example from a gold set."""

    language: str
    text: str
    #: The register a native speaker says this sentence is in.
    level: int
    #: Optional: the expected surface form at each level, when the gold set has it.
    expected: Dict[int, str] = field(default_factory=dict)
    note: str = ""


@dataclass
class MetricResult:
    name: str
    correct: int = 0
    total: int = 0
    failures: List[dict] = field(default_factory=list)

    @property
    def score(self) -> float:
        return (self.correct / self.total) if self.total else 0.0

    def as_dict(self) -> dict:
        return {
            "metric": self.name,
            "score": round(self.score, 4),
            "correct": self.correct,
            "total": self.total,
            "failures": self.failures[:50],
        }


@dataclass
class EvaluationReport:
    language: str
    register: MetricResult
    detection: MetricResult
    semantic: MetricResult

    def as_dict(self) -> dict:
        return {
            "language": self.language,
            "register_accuracy": self.register.as_dict(),
            "detection_accuracy": self.detection.as_dict(),
            "semantic_preservation": self.semantic.as_dict(),
        }

    def summary(self) -> str:
        return (
            f"{self.language:<4} "
            f"register {self.register.score:6.1%} ({self.register.total:>4})  "
            f"detection {self.detection.score:6.1%} ({self.detection.total:>4})  "
            f"semantic {self.semantic.score:6.1%} ({self.semantic.total:>4})"
        )


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------


def register_accuracy(cases: Sequence[Case]) -> MetricResult:
    """
    Ask for level N, then read the result back and check it *is* level N.

    Using the detector to grade the rewriter is meaningful because the two read
    the same table from opposite directions — a rewrite the detector cannot
    place is a genuine failure either way.

    Two levels count as agreeing when they are indistinguishable *for this
    sentence*. Bengali আপনি is the correct form at both Polite and Formal, and
    the detector breaks that tie toward Polite by design; scoring "requested
    Formal, read back Polite" as an error would measure the tie-break rule
    rather than the rewriter. The distinction is only real when the two levels
    actually produce different text.
    """
    result = MetricResult("register_accuracy")
    for case in cases:
        if not has_table(case.language):
            continue
        for level in LEVELS:
            target = coerce_level(level)
            out = rewrite(case.text, case.language, target)
            reading = detect(out.text, case.language)
            result.total += 1

            expected = out.level  # canon-folded, so two-level languages are fair
            if reading.level is None:
                # No marker survived. Only a failure if the source had one.
                if detect(case.text, case.language).level is None:
                    result.correct += 1
                    continue
                result.failures.append({
                    "text": case.text, "requested": level_name(target),
                    "output": out.text, "got": None,
                })
                continue

            if reading.level == expected or _indistinguishable(
                case.text, case.language, expected, reading.level
            ):
                result.correct += 1
            else:
                result.failures.append({
                    "text": case.text,
                    "requested": level_name(target),
                    "output": out.text,
                    "got": level_name(reading.level),
                })
    return result


def _indistinguishable(text: str, language: str, a: int, b: int) -> bool:
    """True when levels ``a`` and ``b`` render this sentence identically."""
    return rewrite(text, language, a).text == rewrite(text, language, b).text


def detection_accuracy(cases: Sequence[Case]) -> MetricResult:
    """Does Auto mode read the register the annotator says is there?"""
    result = MetricResult("detection_accuracy")
    for case in cases:
        if not has_table(case.language):
            continue
        result.total += 1
        reading = detect(case.text, case.language)
        from register import get_table

        expected = get_table(case.language).fold(case.level)
        if reading.level == expected:
            result.correct += 1
        else:
            result.failures.append({
                "text": case.text,
                "expected": level_name(expected),
                "got": level_name(reading.level) if reading.level is not None else None,
                "confidence": round(reading.confidence, 3),
            })
    return result


def semantic_preservation(
    cases: Sequence[Case],
    threshold: float = 0.60,
) -> MetricResult:
    """
    Did the rewrite change more than the register?

    Compares each rewrite against the untouched source. Register changes are
    *supposed* to alter the string, so the comparison is on the parts that
    should have survived: everything the rule table did not explicitly rewrite.
    A low score means the engine reached beyond its own rules.
    """
    result = MetricResult("semantic_preservation")
    for case in cases:
        if not has_table(case.language):
            continue
        for level in LEVELS:
            out = rewrite(case.text, case.language, level)
            result.total += 1

            # Mask out every span the engine says it edited. What remains must
            # be untouched, or the rewrite damaged something it never claimed.
            masked_source = _mask(case.text, [e.before for e in out.edits])
            masked_output = _mask(out.text, [e.after for e in out.edits])
            score = _similarity(masked_source, masked_output)

            if score >= threshold:
                result.correct += 1
            else:
                result.failures.append({
                    "text": case.text,
                    "level": level_name(level),
                    "output": out.text,
                    "similarity": round(score, 3),
                    "claimed_edits": [f"{e.before}->{e.after}" for e in out.edits],
                })
    return result


def evaluate(cases: Sequence[Case], language: Optional[str] = None) -> EvaluationReport:
    """Run all three metrics over one language's cases."""
    lang = language or (cases[0].language if cases else "")
    subset = [c for c in cases if not language or c.language == language]
    return EvaluationReport(
        language=lang,
        register=register_accuracy(subset),
        detection=detection_accuracy(subset),
        semantic=semantic_preservation(subset),
    )


# --------------------------------------------------------------------------
# Similarity
# --------------------------------------------------------------------------


def _mask(text: str, spans: Iterable[str]) -> str:
    """Remove the substrings the engine claims to have edited."""
    out = text
    for span in sorted(set(s for s in spans if s), key=len, reverse=True):
        out = out.replace(span, " ")
    return re.sub(r"\s+", " ", out).strip()


def _similarity(a: str, b: str) -> float:
    """
    Semantic similarity, using the best model available.

    sentence-transformers when installed, because character overlap cannot see
    a meaning change that preserves the letters. Falls back to a character
    ratio so the metric is always reported rather than silently skipped —
    blueprint 9 is explicit that this is the one to track from day one.
    """
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0

    model = _load_similarity_model()
    if model is not None:
        try:
            from sentence_transformers import util

            embeddings = model.encode([a, b], convert_to_tensor=True,
                                      show_progress_bar=False)
            return float(util.cos_sim(embeddings[0], embeddings[1]).item())
        except Exception:
            pass

    return difflib.SequenceMatcher(None, a, b).ratio()


@lru_cache(maxsize=1)
def _load_similarity_model():
    try:
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    except Exception:
        return None
