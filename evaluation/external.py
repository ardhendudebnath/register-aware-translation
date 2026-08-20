"""
Check the register detector against somebody else's labels.

Every number this project reports is self-referential: the engine is measured
against gold sets written alongside it, and a sentence wrong in the same
direction as the table scores a confident 100%. That has been said in the
README and in a dozen commit messages, always with the same conclusion — that
only a native speaker can break the circle.

That conclusion was too quick. FAME-MT is sitting in ``data/splits/``: a
formality-annotated parallel corpus, labelled by other people, for reasons
that have nothing to do with this engine. For the languages it covers it is a
genuinely independent test, and it is large enough that no amount of
overfitting to a hand-written gold set can flatter it.

It covers German, English, Spanish, French, Italian and Portuguese. It does
not cover Bengali, Hindi, Marathi, Gujarati, Punjabi, Urdu, Odia, Assamese,
Nepali, Tamil, Telugu, Kannada, Malayalam or Japanese — which is not a gap in
this module, it is the thesis of the project restated as a missing file. There
is no external corpus to check those against, because nobody has built one.

Two numbers, and the second one is the honest one:

**Coverage** — how often a sentence carries a register marker the engine can
read at all. Abstaining is correct when a sentence has no second-person
reference; FAME-MT labels every row formal or informal regardless, so a low
coverage number is a fact about the corpus as much as about the engine.

**Agreement** — of the sentences it does read, how often it agrees with the
human label. This is the number that cannot be gamed from inside the project.

The engine has four levels and the corpus has two, so they meet at a cut point
— which is not in the same place in every language. See ``FORMAL_FROM``, and
be careful with it: a wrong cut looks exactly like a broken rule table.

    python -m evaluation.external
    python -m evaluation.external --lang de --limit 20000 --show-disagreements 15
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Sequence, Tuple

from register import CASUAL, CLOSE, POLITE, detect, has_table, level_name
from utils.helpers import PROJECT_ROOT

__all__ = ["Agreement", "score_language", "main"]

SPLIT_DIR = PROJECT_ROOT / "data" / "splits"
DEFAULT_SPLIT = "test.tsv"

# --------------------------------------------------------------------------
# Where the T/V line falls, per language.
#
# The corpus is binary and the engine has four levels, so the comparison needs
# a cut point — and it is not the same cut in every language. This started as
# a constant, and Portuguese scored 69.9% against 96–99% for its neighbours,
# which looked like a broken table. It was the constant that was broken.
#
# Asking the corpus where its own line falls settles it:
#
#     we say Casual -> corpus says formal      we say Polite -> formal
#     de    0.2%                                99.2%
#     es    2.7%                                96.6%
#     fr    0.8%                                99.0%
#     it    4.8%                                85.5%
#     pt   96.6%   <-- não                      80.5%
#
# Portuguese has three second-person pronouns and its familiar one, tu, sits
# at Close. você is already a V-form — historically *vossa mercê*, "your
# grace" — so the line falls between Close and Casual, one level below
# everyone else. The engine had it right the whole time and this module was
# reading it wrong.
#
# Declared rather than derived: the shape of the table cannot tell you this.
# Bengali's তুই and তুমি sit at the same two levels as tu and você and are
# both familiar, so the same arithmetic would give the wrong answer there.
# --------------------------------------------------------------------------

#: First level counted as formal. Two — the T/V boundary — unless stated.
FORMAL_FROM: Dict[str, int] = {
    "pt": CASUAL,
}
DEFAULT_FORMAL_FROM = POLITE


def _binary(level: int, language: str) -> str:
    cut = FORMAL_FROM.get(language, DEFAULT_FORMAL_FROM)
    return "formal" if level >= cut else "informal"


@dataclass
class Agreement:
    language: str
    seen: int = 0
    read: int = 0                 # carried a marker the engine could read
    agreed: int = 0
    confusion: Counter = field(default_factory=Counter)
    disagreements: List[Tuple[str, str, str, float]] = field(default_factory=list)

    @property
    def coverage(self) -> float:
        return self.read / self.seen if self.seen else 0.0

    @property
    def accuracy(self) -> float:
        return self.agreed / self.read if self.read else 0.0

    def row(self) -> str:
        return (
            f"{self.language:<4} "
            f"agreement {self.accuracy:6.1%} ({self.read:>6,} read)   "
            f"coverage {self.coverage:6.1%} of {self.seen:,}"
        )


def rows(split: Path, limit: Optional[int] = None) -> Iterator[dict]:
    csv.field_size_limit(10_000_000)
    with split.open(encoding="utf-8", newline="") as fh:
        for index, row in enumerate(csv.DictReader(fh, delimiter="\t")):
            if limit is not None and index >= limit:
                return
            yield row


def score_language(
    codes: Optional[Sequence[str]] = None,
    split: Path = SPLIT_DIR / DEFAULT_SPLIT,
    limit: Optional[int] = None,
    per_language: Optional[int] = None,
    keep_disagreements: int = 0,
) -> Dict[str, Agreement]:
    """Run the detector over the corpus and tally agreement per language."""
    wanted = set(codes) if codes else None
    out: Dict[str, Agreement] = {}

    for row in rows(split, limit):
        code = (row.get("tgt_lang") or "").strip().lower()
        if not code or not has_table(code):
            continue
        if wanted is not None and code not in wanted:
            continue

        tally = out.setdefault(code, Agreement(language=code))
        if per_language is not None and tally.seen >= per_language:
            if all(t.seen >= per_language for t in out.values()) and (
                wanted is None or len(out) >= len(wanted)
            ):
                break
            continue

        text = (row.get("target_text") or "").strip()
        gold = (row.get("formality_label") or "").strip().lower()
        if not text or gold not in ("formal", "informal"):
            continue

        tally.seen += 1
        reading = detect(text, code)
        if reading.level is None:
            continue

        tally.read += 1
        ours = _binary(reading.level, code)
        tally.confusion[(gold, ours)] += 1
        if ours == gold:
            tally.agreed += 1
        elif len(tally.disagreements) < keep_disagreements:
            tally.disagreements.append(
                (text[:110], gold, level_name(reading.level), reading.confidence)
            )

    return out


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Score the register detector against FAME-MT's own labels."
    )
    parser.add_argument("--lang", action="append", dest="langs",
                        help="restrict to a language (repeatable)")
    parser.add_argument("--split", default=DEFAULT_SPLIT,
                        help="test.tsv (default), val.tsv or train.tsv")
    parser.add_argument("--limit", type=int, default=200_000,
                        help="rows to read from the file; 0 for all")
    parser.add_argument("--per-language", type=int, default=None,
                        help="stop after this many scored rows per language")
    parser.add_argument("--show-disagreements", type=int, default=0,
                        help="print this many sentences we got wrong")
    args = parser.parse_args(argv)

    split = SPLIT_DIR / args.split
    if not split.exists():
        print(f"no corpus at {split}")
        print("Build the splits first:  python -m data_preprocessing.build_splits")
        return 1

    scores = score_language(
        codes=args.langs,
        split=split,
        limit=args.limit or None,
        per_language=args.per_language,
        keep_disagreements=args.show_disagreements,
    )
    if not scores:
        print("no rows matched a language with a register table")
        return 1

    print()
    print(f"  FAME-MT {split.name} — labels by other people, for other reasons")
    print()
    for code in sorted(scores):
        print("  " + scores[code].row())

    read = sum(t.read for t in scores.values())
    agreed = sum(t.agreed for t in scores.values())
    seen = sum(t.seen for t in scores.values())
    print()
    print(f"  overall  agreement {agreed / read:.1%} over {read:,} sentences "
          f"({seen:,} seen, {1 - read / seen:.0%} carried no marker)")

    print()
    print("  Not in this corpus, and not in any other: Assamese, Bengali,")
    print("  Gujarati, Hindi, Japanese, Kannada, Malayalam, Marathi, Nepali,")
    print("  Odia, Punjabi, Tamil, Telugu, Urdu. Those still need speakers —")
    print("  see REVIEWING.md.")

    if args.show_disagreements:
        for code in sorted(scores):
            rows_ = scores[code].disagreements
            if not rows_:
                continue
            print()
            print(f"  {code} — where we disagreed with the corpus")
            for text, gold, ours, conf in rows_:
                print(f"    corpus={gold:<8} ours={ours:<7} ({conf:.2f})  {text}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
