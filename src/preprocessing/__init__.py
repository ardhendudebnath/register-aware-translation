"""
Deprecated. Preprocessing now lives in :mod:`data_preprocessing.build_splits`.

This module and its sibling ``preprocess.py`` were two of three near-identical
copies of the split builder. All three shared the slang-dictionary bug that
mislabelled most of the corpus, and fixing one never fixed the others. The
logic now has a single home; these files remain only so existing imports and
scripts do not break, and can be deleted.
"""

from __future__ import annotations

import warnings

from data_preprocessing.build_splits import build, main

__all__ = ["preprocess_data", "build", "main"]


def preprocess_data(*args, **kwargs):
    """Deprecated alias for :func:`data_preprocessing.build_splits.build`."""
    warnings.warn(
        "src.preprocessing.preprocess_data is deprecated; "
        "use `python -m data_preprocessing.build_splits` instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return build(*args, **kwargs)


if __name__ == "__main__":
    raise SystemExit(main())
