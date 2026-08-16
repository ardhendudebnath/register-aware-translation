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

__all__ = ["RELATIONSHIPS", "Feedback", "assess"]

#: Social situations, and the register a native speaker would expect. Values
#: are the levels considered acceptable, best first.
#:
#: More than one is acceptable in most situations, because register is
#: genuinely contested — two native speakers will disagree about whether a
#: sentence is Polite or Formal, and regional variation is real. A tutor that
#: insists on one answer would be teaching something false.
RELATIONSHIPS: Dict[str, Dict[str, object]] = {
    "stranger": {
        "label": "Someone you have just met",
        "expected": (POLITE, FORMAL),
        "why": "Strangers get the polite form until invited otherwise.",
    },
    "elder_family": {
        "label": "An older relative",
        "expected": (CASUAL, POLITE),
        "why": (
            "Family elders are the interesting case: high respect but high "
            "closeness, so the polite pronoun can sound cold. Many families use "
            "the casual form with grandparents and mean no disrespect by it."
        ),
    },
    "close_friend": {
        "label": "A close friend",
        "expected": (CASUAL, CLOSE),
        "why": "The polite form with a close friend reads as distancing.",
    },
    "child": {
        "label": "A child",
        "expected": (CLOSE, CASUAL),
        "why": "Children take the close form; the polite form sounds like a joke.",
    },
    "teacher": {
        "label": "A teacher or senior colleague",
        "expected": (POLITE, FORMAL),
        "why": "Institutional seniority takes the polite form regardless of age.",
    },
    "official": {
        "label": "An official or someone in authority",
        "expected": (FORMAL, POLITE),
        "why": "Formal register, and usually a title with it.",
    },
    "shopkeeper": {
        "label": "A shopkeeper you know",
        "expected": (CASUAL, POLITE),
        "why": "Familiar but transactional — casual is normal, polite is safe.",
    },
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
    expected = tuple(table.fold(lvl) for lvl in situation["expected"])
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
