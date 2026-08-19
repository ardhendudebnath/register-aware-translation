"""
Learner mode — the pipeline run backwards.

Duolingo and every other language app teach vocabulary and grammar. None of
them teach *register*, which is the thing that actually determines whether a
learner sounds rude (blueprint 13.2 #9).

So: the learner speaks, and instead of translating, the app tells them which
register they just used and whether it fits the person they said they were
talking to. "You used তুই with someone you have met once. A native speaker
would use আপনি here."

This is a separate product on the same engine. It needs no new linguistics —
the detector already exists, and the ladder already shows the alternative.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from register import (
    CASUAL,
    CLOSE,
    FORMAL,
    POLITE,
    coerce_level,
    detect as detect_register,
    get_table,
    has_table,
    ladder as register_ladder,
    level_name,
    rewrite as register_rewrite,
)
from register.social import RELATIONSHIPS as SOCIAL_RELATIONSHIPS, expected_in

__all__ = ["RELATIONSHIPS", "Feedback", "assess"]

#: The situations, in the shape this module and the HTTP API have always used.
#:
#: The list itself now lives in :mod:`register.social`, as points on the power
#: and solidarity axes rather than as a flat set of labels. It was authored
#: here first and the prose already described two dimensions — "high respect
#: but high closeness" — with nowhere to put them as data. This is a view onto
#: that, kept so nothing downstream has to change.
RELATIONSHIPS: Dict[str, Dict[str, object]] = {
    key: {
        "label": relationship.label,
        "expected": relationship.expected,
        "why": relationship.why,
        "power": relationship.power,
        "solidarity": relationship.solidarity,
    }
    for key, relationship in SOCIAL_RELATIONSHIPS.items()
}


@dataclass
class Feedback:
    """What the learner said, and how it landed."""

    text: str
    language: str
    detected_level: Optional[int]
    relationship: str
    verdict: str                    # "good" | "too_familiar" | "too_formal" | "unknown"
    message: str
    suggestion: Optional[str] = None
    expected_levels: tuple = ()
    confidence: float = 0.0
    evidence: List[str] = field(default_factory=list)

    @property
    def is_appropriate(self) -> bool:
        return self.verdict == "good"

    def as_dict(self) -> dict:
        return {
            "text": self.text,
            "language": self.language,
            "detected_level": self.detected_level,
            "detected_name": (
                level_name(self.detected_level) if self.detected_level is not None else None
            ),
            "relationship": self.relationship,
            "verdict": self.verdict,
            "message": self.message,
            "suggestion": self.suggestion,
            "expected": [level_name(lvl) for lvl in self.expected_levels],
            "confidence": round(self.confidence, 3),
            "evidence": self.evidence,
            "appropriate": self.is_appropriate,
        }


def assess(text: str, language: str, relationship: str) -> Feedback:
    """
    Judge a learner's sentence against who they said they were talking to.

    Returns a :class:`Feedback` rather than raising, including for unsupported
    languages and unknown relationships — a tutor that errors out mid-lesson is
    worse than one that says it does not know.
    """
    situation = RELATIONSHIPS.get(relationship)
    if situation is None:
        return Feedback(
            text=text, language=language, detected_level=None,
            relationship=relationship, verdict="unknown",
            message=f"I do not have guidance for {relationship!r}.",
        )

    if not has_table(language):
        return Feedback(
            text=text, language=language, detected_level=None,
            relationship=relationship, verdict="unknown",
            message=f"No register table for {language!r} yet.",
            expected_levels=situation["expected"],
        )

    table = get_table(language)
    reading = detect_register(text, language)
    # Folded onto what this language actually realises, with the two-axis
    # reading first. A two-pronoun language stops being told it has a Close
    # level distinct from Casual, so the tutor no longer offers a correction
    # between two identical forms.
    expected = expected_in(language, relationship)
    evidence = [surface for surface, _ in reading.evidence]

    if reading.level is None:
        return Feedback(
            text=text, language=language, detected_level=None,
            relationship=relationship, verdict="unknown",
            message=(
                "I could not find a register marker in that sentence — no "
                "pronoun or verb ending that shows how you are addressing them. "
                "Try a sentence with 'you' in it."
            ),
            expected_levels=expected,
            confidence=reading.confidence,
        )

    detected = reading.level
    best = expected[0]

    if detected in expected:
        return Feedback(
            text=text, language=language, detected_level=detected,
            relationship=relationship, verdict="good",
            message=(
                f"That is {level_name(detected)}, which fits "
                f"{situation['label'].lower()}. {situation['why']}"
            ),
            expected_levels=expected, confidence=reading.confidence,
            evidence=evidence,
        )

    corrected = register_rewrite(text, language, best).text
    if detected < min(expected):
        verdict = "too_familiar"
        message = (
            f"You used {level_name(detected)} with {situation['label'].lower()}. "
            f"That will sound too familiar — native speakers would use "
            f"{level_name(best)} here. {situation['why']}"
        )
    else:
        verdict = "too_formal"
        message = (
            f"You used {level_name(detected)} with {situation['label'].lower()}. "
            f"That is not rude, but it will sound distant — "
            f"{level_name(best)} is more natural. {situation['why']}"
        )

    return Feedback(
        text=text, language=language, detected_level=detected,
        relationship=relationship, verdict=verdict, message=message,
        suggestion=corrected if corrected != text else None,
        expected_levels=expected, confidence=reading.confidence,
        evidence=evidence,
    )
