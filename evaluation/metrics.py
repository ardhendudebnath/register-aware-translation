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
    get_table,
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
    "rewrite_exactness",
    "evaluate",
]


@dataclass(frozen=True)
class Case:
    """One annotated example from a gold set."""

    language: str
    text: str
    #: The register a native speaker says this sentence is in. None means the
    #: sentence carries no second-person marker, and detection must abstain.
    level: Optional[int]
    #: Optional: the expected surface form at each level, when the gold set has
    #: it. Contrastive triads supply this, which is what makes it possible to
    #: grade the rewriter against a gold rendering instead of against the
    #: engine's own detector.
    expected: Dict[int, str] = field(default_factory=dict)
    note: str = ""
    domain: str = ""
    construction: str = ""
    #: "draft" until a native speaker has checked it. The harness refuses to
    #: describe a set as a benchmark while any row is still draft.
    status: str = "draft"
    case_id: str = ""


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
    exactness: Optional[MetricResult] = None
    #: True only when every case has been checked by a native speaker.
    verified: bool = False
    draft_count: int = 0

    def as_dict(self) -> dict:
        out = {
            "language": self.language,
            "verified": self.verified,
            "draft_rows": self.draft_count,
            "register_accuracy": self.register.as_dict(),
            "detection_accuracy": self.detection.as_dict(),
            "semantic_preservation": self.semantic.as_dict(),
        }
        if self.exactness is not None:
            out["rewrite_exactness"] = self.exactness.as_dict()
        return out

    def summary(self) -> str:
        line = (
            f"{self.language:<4} "
            f"register {self.register.score:6.1%} ({self.register.total:>4})  "
            f"detection {self.detection.score:6.1%} ({self.detection.total:>4})  "
            f"semantic {self.semantic.score:6.1%} ({self.semantic.total:>4})"
        )
        if self.exactness is not None and self.exactness.total:
            line += f"  exact {self.exactness.score:6.1%} ({self.exactness.total:>4})"
        if self.draft_count:
            line += "  [draft]"
        return line


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
                # No marker survived. That is correct in two situations, and a
                # failure otherwise.
                #
                # First, if the source had no marker either — nothing was lost.
                #
                # Second, if the rewrite *deleted* a marker because the target
                # level has no equivalent for it. English has no casual form of
                # "please", so downgrading "Please send it over." to
                # "Send it over." is exactly right, and the result is correctly
                # unmarked. Scoring that as a miss penalised the engine for
                # doing the only sensible thing.
                deleted_a_marker = any(not e.after for e in out.edits)
                if deleted_a_marker or detect(case.text, case.language).level is None:
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
    """
    Does Auto mode read the register the annotator says is there?

    Cases annotated with level None carry no second-person marker at all, and
    the correct answer is to abstain. Scoring those is not pedantry: Auto mode
    mirrors whatever the detector reports, so a detector that invents a level
    for an unmarked sentence makes the product confidently wrong.
    """
    from register import get_table

    result = MetricResult("detection_accuracy")
    for case in cases:
        if not has_table(case.language):
            continue
        result.total += 1
        reading = detect(case.text, case.language)

        if case.level is None:
            if reading.level is None:
                result.correct += 1
            else:
                result.failures.append({
                    "id": case.case_id,
                    "text": case.text,
                    "expected": "no marker",
                    "got": level_name(reading.level),
                    "confidence": round(reading.confidence, 3),
                })
            continue

        expected = get_table(case.language).fold(case.level)
        if reading.level == expected:
            result.correct += 1
        else:
            result.failures.append({
                "id": case.case_id,
                "text": case.text,
                "expected": level_name(expected),
                "got": level_name(reading.level) if reading.level is not None else None,
                "confidence": round(reading.confidence, 3),
            })
    return result


def rewrite_exactness(cases: Sequence[Case]) -> MetricResult:
    """
    Of cases that carry a gold rendering, how many does the rewriter reproduce
    exactly?

    This is the strictest and most useful metric available, and it only works
    because the gold set is contrastive: each row knows what the same sentence
    should look like at every level. The other metrics grade the rewriter with
    the engine's own detector, which cannot catch a rewrite that is
    self-consistent but not what a Bengali speaker would say — for instance
    changing the pronoun and leaving the verb behind.
    """
    result = MetricResult("rewrite_exactness")
    for case in cases:
        if not has_table(case.language) or not case.expected:
            continue
        table = get_table(case.language)
        for level, gold in sorted(case.expected.items()):
            # Skip levels this language folds away — asking for Formal in a
            # language that does not distinguish it is not a fair test.
            if table.fold(level) != level:
                continue
            result.total += 1
            got = rewrite(case.text, case.language, level).text
            if got == gold:
                result.correct += 1
            else:
                result.failures.append({
                    "id": case.case_id,
                    "from": case.text,
                    "level": level_name(level),
                    "got": got,
                    "want": gold,
                    "construction": case.construction,
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
    """Run every metric over one language's cases."""
    lang = language or (cases[0].language if cases else "")
    subset = [c for c in cases if not language or c.language == language]
    drafts = sum(1 for c in subset if c.status != "verified")
    return EvaluationReport(
        language=lang,
        register=register_accuracy(subset),
        detection=detection_accuracy(subset),
        semantic=semantic_preservation(subset),
        exactness=rewrite_exactness(subset),
        verified=bool(subset) and drafts == 0,
        draft_count=drafts,
    )


# --------------------------------------------------------------------------
# Similarity
# --------------------------------------------------------------------------


def _mask(text: str, spans: Iterable[str]) -> str:
    """
    Remove the substrings the engine claims to have edited.

    Case-insensitively, because an edit records the replacement *before*
    sentence-initial capitalisation is restored: rewriting "Scusa." reports
    ``Scusa -> scusi`` while the output reads "Scusi.". Matching case-sensitively
    left the whole word unmasked and scored an otherwise perfect one-word
    rewrite at 0.29.
    """
    out = text
    for span in sorted(set(s for s in spans if s), key=len, reverse=True):
        out = re.sub(re.escape(span), " ", out, flags=re.IGNORECASE)
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
