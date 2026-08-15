"""Utility helpers for Setu."""

from . import helpers, slang_detection
from .helpers import (
    DATA_DIR,
    PROJECT_ROOT,
    load_json,
    load_slang_dictionary,
    normalise_text,
    project_path,
    split_sentences,
)
from .slang_detection import (
    SlangMatch,
    detect_slang,
    flatten_slang_dictionary,
    informality_score,
    slang_words_for,
)

__all__ = [
    "helpers",
    "slang_detection",
    "PROJECT_ROOT",
    "DATA_DIR",
    "project_path",
    "load_json",
    "load_slang_dictionary",
    "normalise_text",
    "split_sentences",
    "SlangMatch",
    "detect_slang",
    "flatten_slang_dictionary",
    "slang_words_for",
    "informality_score",
]
