"""
Dataset preparation for the FAME-MT formality corpus.

The build script lives in :mod:`data_preprocessing.build_splits`. It is not
imported here on purpose: this module used to *be* the script, so merely
importing the package created directories and printed to stdout.

    python -m data_preprocessing.build_splits
"""

__all__ = ["build_splits"]
