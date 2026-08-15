"""
Deprecated. Preprocessing now lives in :mod:`data_preprocessing.build_splits`.

See ``src/preprocessing/__init__.py`` for why. This file can be deleted.
"""

from __future__ import annotations

from data_preprocessing.build_splits import build, main
from src.preprocessing import preprocess_data

__all__ = ["preprocess_data", "build", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
