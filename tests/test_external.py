"""
The one check on this engine that comes from outside it.

Skipped when the corpus is absent, which it is on a fresh clone — the splits
are 2.3 GB and gitignored. Build them with:

    python -m data_preprocessing.build_splits
"""

from __future__ import annotations

import pytest

from evaluation.external import (
    DEFAULT_FORMAL_FROM,
    FORMAL_FROM,
    SPLIT_DIR,
    _binary,
    score_language,
)
from register import CASUAL, CLOSE, FORMAL, POLITE, TABLES

SPLIT = SPLIT_DIR / "test.tsv"
needs_corpus = pytest.mark.skipif(
    not SPLIT.exists(), reason="FAME-MT splits not built"
)


def test_the_cut_point_is_a_level_the_language_has():
    """A cut above every level the language realises would mark nothing formal."""
    for code, cut in FORMAL_FROM.items():
        assert code in TABLES, f"{code} has a cut point but no table"
        realised = {TABLES[code].fold(level) for level in (CLOSE, CASUAL, POLITE, FORMAL)}
        assert cut in realised, f"{code}: cut at {cut}, which it never realises"


def test_portuguese_cuts_lower_than_its_neighbours():
    """
    tu sits at Close in Portuguese and você is already a V-form, so the
    boundary is one level below French or German. Getting this wrong scored
    Portuguese at 69.9% and looked exactly like a broken rule table.
    """
    assert FORMAL_FROM["pt"] == CASUAL
    assert DEFAULT_FORMAL_FROM == POLITE
    assert _binary(CASUAL, "pt") == "formal"
    assert _binary(CASUAL, "fr") == "informal"
    assert _binary(CLOSE, "pt") == "informal"


@needs_corpus
@pytest.mark.parametrize("code,floor", [
    ("de", 0.95), ("fr", 0.95), ("es", 0.90), ("it", 0.85), ("pt", 0.85),
])
def test_agreement_with_somebody_elses_labels(code, floor):
    """
    A floor, not a target. These are set below the measured values so a real
    regression trips them without the numbers needing an edit every time a
    table improves.
    """
    scores = score_language(codes=[code], split=SPLIT, limit=40_000)
    tally = scores[code]
    assert tally.read > 1_000, f"only {tally.read} readable sentences for {code}"
    assert tally.accuracy >= floor, (
        f"{code}: {tally.accuracy:.1%} agreement with FAME-MT, expected >= {floor:.0%}"
    )


@needs_corpus
def test_english_is_the_weak_one_and_we_say_so():
    """
    English has no T/V distinction, so register lives entirely in lexis and
    hedging. It reads about a tenth of what it is given and agrees about two
    thirds of the time — near enough to chance that the number belongs in the
    README rather than being quietly averaged away.
    """
    tally = score_language(codes=["en"], split=SPLIT, limit=40_000)["en"]
    assert tally.coverage < 0.25, "English coverage jumped — recheck the claim"
    assert tally.accuracy < 0.85, "English got good; update the README"


@needs_corpus
def test_abstaining_is_counted_apart_from_being_wrong():
    """
    A sentence with no second-person reference carries no register, and the
    corpus labels it anyway. Folding those into the accuracy would punish the
    engine for the one thing it should do.
    """
    tally = score_language(codes=["de"], split=SPLIT, limit=20_000)["de"]
    assert tally.read < tally.seen
    assert tally.agreed <= tally.read
