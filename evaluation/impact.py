"""
What a change to the rules actually did.

Every idea in this project is checked the same way: run the four metrics over
the gold sets, run the agreement against FAME-MT, run the misfire sweep, and
compare the numbers to what they were before. Done by hand that is four
commands and a lot of squinting, and the squinting is where a regression hides
— the honorific nouns moved Bengali exactness by two tenths of a point, which
is invisible unless you are looking straight at it.

So this takes the snapshot, and the diff:

    python -m evaluation.impact --save     # before the change
    python -m evaluation.impact            # after it

and prints only what moved. Nothing moved is the most common and most useful
answer, which is why it says so in one line rather than reprinting the table.

The gold metrics always run; they need nothing but the repository. The corpus
sections are skipped when the 2.3 GB splits are absent, and a snapshot taken
without them compares cleanly against one taken with them — the sections that
are missing are simply not compared, rather than counting as changes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from utils.helpers import PROJECT_ROOT

from .gold_sets import available_gold_sets, load_gold_set
from .metrics import evaluate

__all__ = ["snapshot", "compare", "BASELINE_PATH", "main"]

#: Committed on purpose. A rule change that moves a number then shows up as a
#: change to this file, where somebody reviewing the commit will see it.
BASELINE_PATH = PROJECT_ROOT / "evaluation" / "baseline.json"

#: Below this a difference is noise from a similarity model, not a change.
EPSILON = 0.0005


def _gold_metrics() -> Dict[str, Dict[str, float]]:
    out: Dict[str, Dict[str, float]] = {}
    for code in available_gold_sets():
        cases = load_gold_set(code)
        if not cases:
            continue
        report = evaluate(cases, code)
        scores = {
            "register": round(report.register.score, 4),
            "detection": round(report.detection.score, 4),
            "semantic": round(report.semantic.score, 4),
            "rows": report.detection.total,
        }
        if report.exactness and report.exactness.total:
            scores["exactness"] = round(report.exactness.score, 4)
        out[code] = scores
    return out


def _external() -> Optional[Dict[str, Dict[str, float]]]:
    # The same row limit the documented command uses, so a number here and a
    # number in the README cannot disagree about the method behind them.
    from .external import DEFAULT_SPLIT, ROW_LIMIT, SPLIT_DIR, score_language

    if not (SPLIT_DIR / DEFAULT_SPLIT).exists():
        return None
    scored = score_language(limit=ROW_LIMIT)
    return {
        code: {
            "agreement": round(tally.accuracy, 4),
            "coverage": round(tally.coverage, 4),
            "read": tally.read,
        }
        for code, tally in sorted(scored.items())
    }


def _sweep() -> Optional[Dict[str, Dict[str, int]]]:
    from .external import DEFAULT_SPLIT, SPLIT_DIR
    from .misfires import sweep

    if not (SPLIT_DIR / DEFAULT_SPLIT).exists():
        return None
    return {
        code: {
            "touched": tally.damaged,
            "unstable": tally.unstable,
            "unaddressed": tally.unaddressed,
        }
        for code, tally in sorted(sweep().items())
    }


def snapshot(with_corpus: bool = True) -> dict:
    """Every number this project checks itself against."""
    out: dict = {"gold": _gold_metrics()}
    if with_corpus:
        external = _external()
        if external is not None:
            out["external"] = external
        misfires = _sweep()
        if misfires is not None:
            out["misfires"] = misfires
    return out


def _walk(section: dict, prefix: str = "") -> Dict[str, float]:
    """Flatten {lang: {metric: value}} into {"lang.metric": value}."""
    flat: Dict[str, float] = {}
    for key, value in section.items():
        if isinstance(value, dict):
            flat.update(_walk(value, f"{prefix}{key}."))
        else:
            flat[f"{prefix}{key}"] = value
    return flat


def compare(before: dict, after: dict) -> List[str]:
    """
    Lines describing what moved. Empty when nothing did.

    A section missing from either side is not compared: a snapshot taken
    without the corpus is a smaller claim, not a contradicting one.
    """
    lines: List[str] = []
    for section in ("gold", "external", "misfires"):
        if section not in before or section not in after:
            continue
        old, new = _walk(before[section]), _walk(after[section])

        for key in sorted(set(old) | set(new)):
            if key not in old:
                lines.append(f"  + {section}.{key} = {new[key]} (new)")
            elif key not in new:
                lines.append(f"  - {section}.{key} was {old[key]} (gone)")
            elif isinstance(old[key], float) or isinstance(new[key], float):
                if abs(new[key] - old[key]) > EPSILON:
                    lines.append(
                        f"  {'↑' if new[key] > old[key] else '↓'} "
                        f"{section}.{key}  {old[key]:.4f} → {new[key]:.4f}"
                    )
            elif old[key] != new[key]:
                lines.append(
                    f"  {'↑' if new[key] > old[key] else '↓'} "
                    f"{section}.{key}  {old[key]:,} → {new[key]:,}"
                )
    return lines


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="What a rule change did.")
    parser.add_argument("--save", action="store_true",
                        help="write the current numbers as the baseline")
    parser.add_argument("--no-corpus", action="store_true",
                        help="gold metrics only — seconds instead of minutes")
    parser.add_argument("--baseline", type=Path, default=BASELINE_PATH)
    parser.add_argument("--strict", action="store_true",
                        help="exit non-zero when anything moved, for CI")
    args = parser.parse_args(argv)

    current = snapshot(with_corpus=not args.no_corpus)

    if args.save:
        args.baseline.write_text(
            json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        sections = ", ".join(sorted(current))
        print(f"baseline written to {args.baseline} ({sections})")
        return 0

    if not args.baseline.exists():
        print(f"no baseline at {args.baseline} — take one with --save")
        return 1

    before = json.loads(args.baseline.read_text(encoding="utf-8"))
    changes = compare(before, current)

    compared = [s for s in ("gold", "external", "misfires")
                if s in before and s in current]
    print()
    if not changes:
        print(f"  nothing moved ({', '.join(compared)})")
        return 0

    print(f"  {len(changes)} changes ({', '.join(compared)})")
    print()
    for line in changes:
        print(line)
    print()
    print("  If these are the change you meant, record them:")
    print("      python -m evaluation.impact --save")
    return 1 if args.strict else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
