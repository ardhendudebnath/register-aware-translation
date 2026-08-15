"""
Evaluation harness for the register layer.

    python -m evaluation.run            # all languages with a gold set
    python -m evaluation.run --lang bn  # one language
    python -m evaluation.run --json results.json
"""

from .gold_sets import GOLD_DIR, SEED_CASES, available_gold_sets, load_gold_set
from .metrics import (
    Case,
    EvaluationReport,
    MetricResult,
    detection_accuracy,
    evaluate,
    register_accuracy,
    semantic_preservation,
)

__all__ = [
    "Case",
    "MetricResult",
    "EvaluationReport",
    "register_accuracy",
    "detection_accuracy",
    "semantic_preservation",
    "evaluate",
    "load_gold_set",
    "available_gold_sets",
    "SEED_CASES",
    "GOLD_DIR",
]
