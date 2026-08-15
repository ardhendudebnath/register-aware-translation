"""
Shared helpers: project paths, JSON loading, text normalisation.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from register.boundaries import DELIMITER_CLASS as _DELIMITER_CLASS

__all__ = [
    "PROJECT_ROOT",
    "DATA_DIR",
    "DELIMITER_CLASS",
    "project_path",
    "load_json",
    "load_slang_dictionary",
    "normalise_text",
    "split_sentences",
]

#: Re-exported from the register package, which owns the single definition.
#: See ``register/boundaries.py`` for why `\b` is not usable on Indic scripts.
DELIMITER_CLASS = _DELIMITER_CLASS

#: Resolved from this file rather than the working directory, so scripts run
#: from anywhere still find data/. The previous relative "data/..." lookups
#: silently returned {} whenever the app was started from another directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


def project_path(*parts: str) -> Path:
    """Absolute path to something inside the project."""
    return PROJECT_ROOT.joinpath(*parts)


def load_json(file_path, default: Optional[Any] = None) -> Any:
    """
    Load JSON, returning ``default`` (``{}`` unless given) when the file is
    missing or malformed.

    Relative paths are resolved against the project root, not the process
    working directory.
    """
    if default is None:
        default = {}

    path = Path(file_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path

    if not path.exists():
        return default

    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return default


@lru_cache(maxsize=1)
def load_slang_dictionary() -> dict:
    """The slang dictionary, loaded once and cached."""
    return load_json(DATA_DIR / "slang_dictionary.json", default={})


def normalise_text(text: str) -> str:
    """
    Light normalisation for comparison and cache keys.

    NFC composition matters for Indic scripts, where the same visible word can
    arrive in more than one code point sequence depending on the keyboard or
    ASR engine — without this, two identical-looking Bengali strings miss each
    other in the phrasebook cache.
    """
    if not isinstance(text, str):
        return ""
    text = unicodedata.normalize("NFC", text)
    return re.sub(r"\s+", " ", text).strip()


def split_sentences(text: str) -> list:
    """
    Split on sentence-final punctuation, including the Devanagari danda and
    CJK full stop. Deliberately simple — this feeds streaming TTS chunking,
    where an occasional bad split costs a pause, not a wrong translation.
    """
    if not isinstance(text, str) or not text.strip():
        return []
    parts = re.split(r"(?<=[.!?।॥。！？])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]
