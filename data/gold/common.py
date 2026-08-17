"""
Shared machinery for building register gold sets.

``build_bn.py`` established the shape: contrastive triads, an ``expected`` map
per row, negatives with no marker at all, and a set of deliberately hard
ambiguities. This module lifts that out so nineteen more languages do not each
carry a copy of it.

Two rules the sets are built under, both of which matter more than volume:

**Write the sentences independently of the rule tables.** If the gold data is
derived from the same tables the engine rewrites with, the evaluation is
circular and will report 100% no matter how bad the engine is. The Bengali set
scores 99.2%, and the 0.8% is the whole point — those are real gaps that only
showed up because the sentences were written from the language rather than from
the code.

**Everything is a draft until a native speaker says otherwise.** Every row is
written with ``status: "draft"``, and each language declares a ``confidence``
saying how much review it needs. A machine-drafted set is a scaffold that turns
"write 300 sentences" into "check 300 sentences" — valuable, and not the same
thing as a benchmark.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Sequence, Tuple

HERE = Path(__file__).resolve().parent

#: (close/low form, mid form, high form, domain, context, construction)
#: The three columns are whatever levels the language actually distinguishes;
#: :class:`LanguageSet` says which levels they map onto.
Triad = Tuple[str, str, str, str, str, str]

#: (text, domain, context)
Formal = Tuple[str, str, str]

#: (text, domain)
NoMarker = Tuple[str, str]

#: (text, level or None, construction, note)
Hard = Tuple[str, Optional[int], str, str]


#: How much a native speaker needs to look at this, worst first. This is an
#: honest self-assessment, not a quality score — it drives the review queue.
CONFIDENCE = {
    "high": "Common constructions, widely documented. Spot-check.",
    "medium": "Plausible but review every row before trusting a number.",
    "low": "Structurally sound, wording uncertain. Assume errors.",
}


@dataclass
class LanguageSet:
    """One language's draft data, plus how its columns map onto levels."""

    code: str
    name: str
    #: Which register level each triad column represents. Bengali is
    #: (0, 1, 2) — তুই / তুমি / আপনি. German is (1, 1, 2): the first two
    #: columns are the same form, because the language has one informal
    #: pronoun and duplicating it would fake a distinction it does not make.
    columns: Tuple[int, int, int]
    confidence: str
    triads: List[Tuple[str, List[Triad]]] = field(default_factory=list)
    formal: List[Formal] = field(default_factory=list)
    no_marker: List[NoMarker] = field(default_factory=list)
    hard: List[Hard] = field(default_factory=list)
    #: Anything a reviewer needs to know before starting.
    note: str = ""
    #: True when the language has a Formal level the triads do not cover.
    #:
    #: Triads carry three columns. For most languages that is enough, because
    #: Formal reuses the top column's form and differs only lexically. Nepali
    #: does not: हजुर is a fourth pronoun above तपाईं, so filling in
    #: ``expected["3"]`` from the तपाईं column invents a gold rendering the
    #: language disagrees with, and then marks the engine wrong for producing
    #: the right one. Formal rows for these languages live in ``formal``.
    formal_distinct: bool = False
    #: Triad groups whose Formal rendering *is* lexically distinct, in a
    #: language where most groups' is not.
    #:
    #: Tamil, Telugu and Kannada share one honorific pronoun across Polite and
    #: Formal, so for nearly every triad the Formal fallback is right. Courtesy
    #: is the exception: நன்றி → மிக்க நன்றி, ధన్యవాదాలు → చాలా ధన్యవాదాలు,
    #: ಧನ್ಯವಾದ → ಅನಂತ ಧನ್ಯವಾದಗಳು. Left to the fallback these sets assert two
    #: contradictory things about one sentence — the triad says Formal keeps
    #: the plain thanks, while ``formal`` lists the upgraded thanks as a Formal
    #: row. Naming the group here drops the invented expectation and leaves the
    #: real one standing.
    formal_lexical_groups: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.confidence not in CONFIDENCE:
            raise ValueError(
                f"{self.code}: confidence must be one of {sorted(CONFIDENCE)}"
            )
        if len(self.columns) != 3:
            raise ValueError(f"{self.code}: columns must name three levels")

    # ------------------------------------------------------------------

    def triad_rows(self) -> Iterator[dict]:
        """
        Expand each triad into one row per *distinct* level.

        A language whose first two columns are the same level emits two rows,
        not three. Emitting a duplicate would inflate the row count and, worse,
        tell the harness that a distinction exists where it does not.
        """
        for group, triads in self.triads:
            for low, mid, high, domain, context, construction in triads:
                by_level: Dict[int, str] = {}
                for level, text in zip(self.columns, (low, mid, high)):
                    by_level.setdefault(level, text)

                expected = {str(level): text for level, text in by_level.items()}
                # Formal falls back to the highest level the triad supplies,
                # unless the language has a distinct Formal the triads do not
                # reach — see `formal_distinct` and `formal_lexical_groups`.
                if not self.formal_distinct and group not in self.formal_lexical_groups:
                    top = max(by_level)
                    expected.setdefault("3", by_level[top])

                for level, text in sorted(by_level.items()):
                    yield {
                        "text": text,
                        "level": level,
                        "expected": expected,
                        "domain": domain,
                        "context": context,
                        "construction": construction,
                        "group": group,
                        "status": "draft",
                        "note": f"{construction} · {context}",
                    }

    def formal_rows(self) -> Iterator[dict]:
        for text, domain, context in self.formal:
            yield {
                "text": text, "level": 3, "domain": domain, "context": context,
                "construction": "lexical formality", "group": "formal",
                "status": "draft",
                "note": "Formal is lexical here, not a separate pronoun",
            }

    def no_marker_rows(self) -> Iterator[dict]:
        for text, domain in self.no_marker:
            yield {
                "text": text, "level": None, "domain": domain, "context": "n/a",
                "construction": "no second-person marker", "group": "negative",
                "status": "draft",
                "note": "detection must return None; abstaining beats guessing",
            }

    def hard_rows(self) -> Iterator[dict]:
        for text, level, construction, note in self.hard:
            yield {
                "text": text, "level": level, "domain": "ambiguity",
                "context": "n/a", "construction": construction, "group": "hard",
                "status": "draft", "note": note,
            }

    def rows(self) -> List[dict]:
        out = (
            list(self.triad_rows())
            + list(self.formal_rows())
            + list(self.no_marker_rows())
            + list(self.hard_rows())
        )
        for index, row in enumerate(out, 1):
            row["id"] = f"{self.code}-{index:04d}"
            row["language"] = self.code
            row["confidence"] = self.confidence
        return out


# --------------------------------------------------------------------------


def write(language: LanguageSet, out_dir: Path = HERE) -> Path:
    rows = language.rows()
    path = out_dir / f"{language.code}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def report(language: LanguageSet) -> None:
    rows = language.rows()
    levels = Counter(str(r["level"]) for r in rows)
    groups = Counter(r["group"] for r in rows)

    names = {"0": "Close", "1": "Casual", "2": "Polite", "3": "Formal",
             "None": "no marker"}
    print(f"{language.name} ({language.code}) — {len(rows)} rows, "
          f"confidence={language.confidence}")
    print(f"  {CONFIDENCE[language.confidence]}")
    if language.note:
        print(f"  {language.note}")
    print("  levels: " + "  ".join(
        f"{names[k]}={levels[k]}" for k in ("0", "1", "2", "3", "None") if k in levels
    ))
    print("  groups: " + "  ".join(
        f"{name}={count}" for name, count in groups.most_common()
    ))


def cli(language: LanguageSet, argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=f"Build the {language.name} register gold set draft"
    )
    parser.add_argument("--stats", action="store_true", help="report coverage only")
    parser.add_argument("--out-dir", default=str(HERE))
    args = parser.parse_args(argv)

    report(language)
    if args.stats:
        return 0

    path = write(language, Path(args.out_dir))
    print(f"  wrote {path.name}  (all rows status=draft)")
    return 0
