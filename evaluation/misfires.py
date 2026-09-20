"""
Find rules that fire where they should not, on 150,000 real sentences.

The four gold metrics cannot see this class of bug. They compare the engine
against gold rows, and gold rows are single-clause sentences addressed to
somebody — so a rule that misbehaves in a compound verb, on a third-person
subject, or in a construction nobody thought to write down collides with
nothing and scores 100%. Every bug found this way so far was found by hand,
one probe at a time, in a language somebody happened to think about.

This does it at scale, against the FAME-MT corpus, using two invariants that
need no labels and no native speaker — which is what makes them runnable over
a corpus nobody annotated for register:

**Nobody in it, nothing for a voting rule to change.** If ``detect`` finds no
second-person marker in a sentence, no rule that *votes* may change it. A
change means such a rule matched something carrying no register at all: a
third-person verb, a noun that looks like a term of address, half of a
compound. Every misfire fixed in this project violated exactly this.

The exception is written into the engine already. A ``rewrite_only`` rule
rewrites and never votes, which is how lexical register works in a language
with no second-person grammar: English "However" → "But" is a real register
change on a sentence about nothing in particular, and it should not be
reported here. Only voting rules are held to the invariant — the first run of
this sweep flagged 463 English sentences before that distinction was drawn,
and every one of them was a lexical rule doing its job.

**Rewriting twice changes nothing.** ``rewrite(rewrite(s, L), L)`` must equal
``rewrite(s, L)``. The engine resolves overlaps in a single pass precisely so
a rewrite cannot feed its own output back into another rule; this checks that
the property survives contact with real text.

Neither says the engine is *right* — a sentence can be left alone and still be
read wrongly. They say it is not doing something indefensible, and they do it
on sentences people actually wrote rather than on sentences this project wrote
about itself.

Covers the six European languages FAME-MT contains. The Indian languages have
no corpus, which is the reason the gold sets and the review pages exist.

Usage::

    python -m evaluation.misfires
    python -m evaluation.misfires --lang pt --show 5
    python -m evaluation.misfires --limit 20000
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from register import LEVELS, detect, get_table, has_table, level_name, rewrite

from .external import DEFAULT_SPLIT, SPLIT_DIR, rows

__all__ = ["Misfire", "Tally", "sweep", "main"]


@dataclass(frozen=True)
class Misfire:
    """One sentence the engine should not have touched, and what touched it."""

    language: str
    text: str
    level: int
    after: str
    rules: Tuple[str, ...]
    kind: str = "unaddressed"      # or "unstable"

    def describe(self) -> str:
        return (
            f"  {self.text}\n"
            f"    -> {self.after}   (at {level_name(self.level)})\n"
            f"       {', '.join(self.rules) or '—'}"
        )


@dataclass
class Tally:
    language: str
    seen: int = 0
    #: Sentences carrying no second-person marker — the ones under test.
    unaddressed: int = 0
    damaged: int = 0
    unstable: int = 0
    by_rule: Counter = field(default_factory=Counter)
    examples: List[Misfire] = field(default_factory=list)

    @property
    def rate(self) -> float:
        return self.damaged / self.unaddressed if self.unaddressed else 0.0

    def row(self) -> str:
        return (
            f"{self.language:<4} "
            f"touched {self.damaged:>5,} of {self.unaddressed:>6,} unaddressed "
            f"({self.rate:6.2%})   unstable {self.unstable:>4,}   "
            f"of {self.seen:,} seen"
        )


def sweep(
    codes: Optional[Sequence[str]] = None,
    split: Path = SPLIT_DIR / DEFAULT_SPLIT,
    limit: Optional[int] = None,
    per_language: Optional[int] = None,
    keep_examples: int = 3,
) -> Dict[str, Tally]:
    """Run both invariants over the corpus, tallying per language."""
    wanted = set(codes) if codes else None
    out: Dict[str, Tally] = {}
    seen_text: Dict[str, set] = {}

    for row in rows(split, limit):
        code = (row.get("tgt_lang") or "").strip().lower()
        text = (row.get("target_text") or "").strip()
        if not code or not text or not has_table(code):
            continue
        if wanted is not None and code not in wanted:
            continue

        tally = out.setdefault(code, Tally(code))
        already = seen_text.setdefault(code, set())
        if text in already:
            continue            # the corpus repeats itself; count each once
        already.add(text)
        if per_language is not None and tally.seen >= per_language:
            continue
        tally.seen += 1

        reading = detect(text, code)
        if reading.level is None:
            tally.unaddressed += 1
            found = _first_change(code, text)
            if found is not None:
                tally.damaged += 1
                tally.by_rule.update(found.rules or ("(no rule recorded)",))
                if len(tally.examples) < keep_examples * 4:
                    tally.examples.append(found)
            continue

        unstable = _unstable(code, text)
        if unstable is not None:
            tally.unstable += 1
            tally.by_rule.update(unstable.rules or ("(no rule recorded)",))
            if len(tally.examples) < keep_examples * 4:
                tally.examples.append(unstable)

    return out


@lru_cache(maxsize=32)
def _voting_rules(code: str) -> frozenset:
    """
    Rules that read register as well as write it.

    A ``rewrite_only`` rule is excluded by design: it never votes, so a
    sentence it changes was never claimed to carry a register in the first
    place.
    """
    return frozenset(
        rule.name for rule in get_table(code).rules if not rule.rewrite_only
    )


def _first_change(code: str, text: str) -> Optional[Misfire]:
    """The first level at which a voting rule alters a sentence with nobody in it."""
    voting = _voting_rules(code)
    for level in LEVELS:
        out = rewrite(text, code, level)
        fired = sorted({e.rule for e in out.edits if e.rule in voting})
        if out.text != text and fired:
            return Misfire(
                language=code, text=text, level=level, after=out.text,
                rules=tuple(fired),
            )
    return None


def _unstable(code: str, text: str) -> Optional[Misfire]:
    """A rewrite that is not a fixed point: doing it twice moves again."""
    for level in LEVELS:
        once = rewrite(text, code, level)
        twice = rewrite(once.text, code, level)
        if twice.text != once.text:
            return Misfire(
                language=code, text=once.text, level=level, after=twice.text,
                rules=tuple(sorted({e.rule for e in twice.edits})),
                kind="unstable",
            )
    return None


# --------------------------------------------------------------------------


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Find rules firing on sentences that address nobody."
    )
    parser.add_argument("--lang", action="append", dest="langs",
                        help="restrict to a language (repeatable)")
    parser.add_argument("--split", default=DEFAULT_SPLIT)
    parser.add_argument("--limit", type=int, default=200_000,
                        help="rows to read from the file; 0 for all")
    parser.add_argument("--per-language", type=int, default=None)
    parser.add_argument("--show", type=int, default=3,
                        help="examples to print per offending rule")
    args = parser.parse_args(argv)

    split = SPLIT_DIR / args.split
    if not split.exists():
        print(f"no corpus at {split}")
        print("Build the splits first:  python -m data_preprocessing.build_splits")
        return 1

    tallies = sweep(
        codes=args.langs,
        split=split,
        limit=args.limit or None,
        per_language=args.per_language,
        keep_examples=args.show,
    )
    if not tallies:
        print("no rows matched a language with a register table")
        return 1

    print()
    print(f"  FAME-MT {split.name} — sentences nobody is addressed in")
    print()
    for code in sorted(tallies):
        print("  " + tallies[code].row())

    offenders = Counter()
    for tally in tallies.values():
        offenders.update(tally.by_rule)

    if not offenders:
        print()
        print("  No rule fired on a sentence with nobody in it, and no rewrite")
        print("  moved twice. That is the property, not a score.")
        return 0

    print()
    print("  Rules that fired where nothing should have:")
    for rule, count in offenders.most_common(12):
        print(f"    {rule:<28} {count:>5,}")

    for code in sorted(tallies):
        shown = tallies[code].examples[: args.show]
        if not shown:
            continue
        print()
        print(f"  {code}:")
        for example in shown:
            print(example.describe())
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
