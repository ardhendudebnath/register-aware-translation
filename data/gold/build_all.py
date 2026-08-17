"""
Build every draft register set.

    python -m data.gold.build_all              # write all of them
    python -m data.gold.build_all --stats      # coverage report only
    python -m data.gold.build_all --lang hi ta # just these

Bengali is built by its own script (``build_bn.py``) and is not rebuilt here;
it is the hand-written reference the others are modelled on.

Everything written by this script is ``status: "draft"``. The evaluation
harness will not describe a language as verified while any of its rows are
drafts, and ``--stats`` prints the review queue worst-confidence-first so it is
obvious where a native speaker's time is worth most.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

# Allow running as a plain script as well as with -m.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from data.gold.common import CONFIDENCE, HERE, report, write
from data.gold.sets import ALL, BY_CODE

_ORDER = {"low": 0, "medium": 1, "high": 2}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().split("\n")[0])
    parser.add_argument("--lang", action="append", default=None,
                        help="Language code. Repeatable. Default: all.")
    parser.add_argument("--stats", action="store_true",
                        help="Report coverage without writing files.")
    parser.add_argument("--out-dir", default=str(HERE))
    args = parser.parse_args(argv)

    if args.lang:
        unknown = [code for code in args.lang if code not in BY_CODE]
        if unknown:
            parser.error(
                f"no draft set for {', '.join(unknown)}. "
                f"Available: {', '.join(sorted(BY_CODE))}"
            )
        languages = [BY_CODE[code] for code in args.lang]
    else:
        languages = list(ALL)

    languages.sort(key=lambda lang: (_ORDER[lang.confidence], lang.code))

    total = 0
    for language in languages:
        report(language)
        rows = language.rows()
        total += len(rows)
        if not args.stats:
            path = write(language, Path(args.out_dir))
            print(f"  wrote {path.name}")
        print()

    print(f"{len(languages)} languages, {total:,} rows — every row status=draft.")
    print()
    print("Review queue, least confident first:")
    for level in ("low", "medium", "high"):
        codes = [lang.code for lang in languages if lang.confidence == level]
        if codes:
            print(f"  {level:<7} {', '.join(codes)}")
            print(f"          {CONFIDENCE[level]}")
    print()
    print("A draft set is a scaffold, not a benchmark. It turns 'write 300")
    print("sentences' into 'check 300 sentences' — which is the useful part,")
    print("and is not the same as having checked them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
