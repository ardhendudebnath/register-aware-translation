"""
Run the register evaluation.

    python -m evaluation.run
    python -m evaluation.run --lang bn --verbose
    python -m evaluation.run --json results/eval.json
    python -m evaluation.run --write-template bn

Run this on every rule-table change. It is the regression suite that keeps a
new rule from quietly breaking an old one — and the numbers it prints are the
thing that turns "we have rule tables" into a claim you can defend.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from register import TABLES, supported_languages

from .gold_sets import GOLD_DIR, SEED_CASES, available_gold_sets, load_gold_set, write_template
from .metrics import evaluate


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate the register layer")
    parser.add_argument("--lang", action="append", default=None,
                        help="Language code. Repeatable. Default: every language "
                             "that has cases.")
    parser.add_argument("--json", dest="json_path", default=None,
                        help="Write the full report, including failures, here.")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Print individual failures.")
    parser.add_argument("--write-template", metavar="LANG", default=None,
                        help="Create data/gold/<LANG>.jsonl from the seed cases "
                             "so a native speaker has the right shape to fill in.")
    parser.add_argument("--fail-under", type=float, default=None,
                        help="Exit non-zero if any metric falls below this "
                             "(0-1). Use it in CI.")
    args = parser.parse_args(argv)

    if args.write_template:
        path = write_template(args.write_template, overwrite=False)
        print(f"Template at {path}")
        print("Add one JSON object per line: "
              '{"text": "...", "level": 0-3, "note": "..."}')
        return 0

    languages = args.lang or _languages_with_cases()
    if not languages:
        print("No gold sets found and no seed cases matched.", file=sys.stderr)
        return 1

    reports = []
    print()
    print(f"{'lang':<5} {'register':>18} {'detection':>19} {'semantic':>18}")
    print("-" * 64)

    for code in languages:
        cases = load_gold_set(code)
        if not cases:
            print(f"{code:<5}  (no cases)")
            continue
        report = evaluate(cases, code)
        reports.append(report)
        print(report.summary())

        if args.verbose:
            _print_failures(report)

    print()
    _print_coverage(languages)

    if args.json_path:
        out = Path(args.json_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps([r.as_dict() for r in reports], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"Full report written to {out}")

    if args.fail_under is not None:
        worst = min(
            (m.score for r in reports for m in (r.register, r.detection, r.semantic)),
            default=0.0,
        )
        if worst < args.fail_under:
            print(f"\nFAIL: lowest metric {worst:.1%} is below {args.fail_under:.1%}")
            return 1
        print(f"\nPASS: lowest metric {worst:.1%}")

    return 0


def _languages_with_cases() -> List[str]:
    from_disk = available_gold_sets()
    from_seed = sorted({c.language for c in SEED_CASES})
    return sorted(set(from_disk) | set(from_seed))


def _print_failures(report) -> None:
    # Exactness was missing from this list, which meant --verbose silently
    # printed nothing for the one metric that was failing. Nepali sat at 59.1%
    # exact for several rounds with no way to see why.
    metrics = [report.register, report.detection, report.semantic]
    if report.exactness is not None:
        metrics.append(report.exactness)
    for metric in metrics:
        if not metric.failures:
            continue
        print(f"    {metric.name}: {len(metric.failures)} failure(s)")
        for failure in metric.failures[:10]:
            bits = "  ".join(f"{k}={v!r}" for k, v in failure.items())
            print(f"      {bits}")


def _print_coverage(evaluated: List[str]) -> None:
    """Say plainly which languages have no gold data — an unmeasured table is
    an unverified claim."""
    missing = [c for c in supported_languages() if c not in evaluated]
    on_disk = set(available_gold_sets())
    seeded = [c for c in evaluated if c not in on_disk]

    if seeded:
        print(f"Using built-in seed cases (not a benchmark): {', '.join(seeded)}")
        print(f"  Write real sets to {GOLD_DIR}/<lang>.jsonl — "
              f"`--write-template <lang>` starts one.")
    if missing:
        print(f"No cases at all for: {', '.join(missing)} "
              f"({len(missing)} of {len(TABLES)} tables unmeasured)")


if __name__ == "__main__":
    sys.exit(main())
