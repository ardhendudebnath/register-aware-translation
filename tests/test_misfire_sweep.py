"""
The misfire sweep, run over a slice of the corpus.

:mod:`evaluation.misfires` checks two properties that need no labels, which is
what makes them runnable over 150,000 sentences nobody annotated for register:
a sentence with no second-person marker must not be changed by a rule that
votes, and rewriting twice must not move again.

Skipped when the corpus is absent, which it is on a fresh clone — the splits
are 2.3 GB and gitignored. The full run is a command, not a test:

    python -m evaluation.misfires
"""

from __future__ import annotations

import pytest

from evaluation.external import SPLIT_DIR
from evaluation.misfires import _voting_rules, sweep
from register import TABLES

SPLIT = SPLIT_DIR / "test.tsv"

#: Rows read per test. Lower than the external harness reads, because this
#: rewrites each sentence at four levels — and twice again for the idempotence
#: check — where that one only detects. Enough for a real regression to show
#: without giving the suite a tail of its own.
CORPUS_ROWS = 6_000

needs_corpus = pytest.mark.skipif(
    not SPLIT.exists(), reason="FAME-MT splits not built"
)


@pytest.fixture(scope="module")
def tallies():
    return sweep(split=SPLIT, limit=CORPUS_ROWS)


@needs_corpus
def test_no_voting_rule_fires_on_a_sentence_with_nobody_in_it(tallies):
    """
    The property every misfire fixed in this project violated. It held over
    the whole corpus when it was last run: 0 of 49,828 unaddressed sentences
    in six languages.
    """
    damage = []
    for code, tally in sorted(tallies.items()):
        if tally.damaged:
            worst = tally.examples[0] if tally.examples else None
            damage.append(
                f"{code}: {tally.damaged} of {tally.unaddressed}"
                + (f"\n{worst.describe()}" if worst else "")
            )
    assert not damage, "\n".join(damage)


@needs_corpus
def test_the_sweep_actually_read_something(tallies):
    """A sweep that silently matched nothing would pass every other test here."""
    assert sum(t.seen for t in tallies.values()) > 1_000
    assert sum(t.unaddressed for t in tallies.values()) > 100


def test_lexical_rules_are_exempt_by_design():
    """
    English register is lexical — "However" for "But" is a real register
    change on a sentence about nothing in particular. Those rules are marked
    ``rewrite_only`` and never vote, so they are not held to the invariant.
    Before that distinction was drawn the sweep flagged 463 English sentences,
    every one of them a lexical rule doing its job.
    """
    voting = _voting_rules("en")
    lexical = {r.name for r in TABLES["en"].rules if r.rewrite_only}
    assert lexical, "English should still have lexical-only rules"
    assert not (voting & lexical)
    assert "word.but" in lexical
