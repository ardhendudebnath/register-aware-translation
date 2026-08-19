"""
Generate the coverage table in the README from the tables themselves.

It was hand-maintained, and it drifted the way hand-maintained tables do: the
README claimed 399 rules across 20 languages when there were 1,369, and said
Bengali had 39 when it had 118. Every number in it was wrong, in the direction
that undersells the work, and nothing anywhere would have said so.

So it is generated now, and ``tests/test_readme_coverage.py`` fails when the
README no longer matches the tables. That test failing means run this:

    python -m docs.make_coverage_table --write

Confidence comes from the gold sets rather than being asserted here, so a
language stops being marked unreviewed at the moment somebody reviews it.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from register import LEVELS, TABLES, get_table
from utils.helpers import PROJECT_ROOT

README = PROJECT_ROOT / "README.md"
GOLD_DIR = PROJECT_ROOT / "data" / "gold"

BEGIN = "<!-- coverage:begin -->"
END = "<!-- coverage:end -->"

#: Reading order: Indian languages first, because that is the point of the
#: project, then the rest.
ORDER = (
    "bn", "hi", "mr", "gu", "pa", "ur", "or", "as", "ne",
    "ta", "te", "kn", "ml",
    "de", "fr", "es", "it", "pt", "ja", "en",
)

#: The second-person system, which no table stores because the engine never
#: needs it spelled out — it is documentation, not data.
PRONOUNS: Dict[str, str] = {
    "bn": "তুই / তুমি / আপনি",
    "hi": "तू / तुम / आप",
    "mr": "तू / तुम्ही / आपण",
    "gu": "તું / તમે / આપ",
    "pa": "ਤੂੰ / ਤੁਸੀਂ",
    "ur": "تو / تم / آپ",
    "or": "ତୁ / ତୁମେ / ଆପଣ",
    "as": "তই / তুমি / আপুনি",
    "ne": "तँ / तिमी / तपाईं / हजुर",
    "ta": "நீ / நீங்கள்",
    "te": "నువ్వు / మీరు",
    "kn": "ನೀನು / ನೀವು",
    "ml": "നീ / നിങ്ങൾ / താങ്കൾ",
    "de": "du / Sie",
    "fr": "tu / vous",
    "es": "tú / usted",
    "it": "tu / Lei",
    "pt": "tu / você / o senhor",
    "ja": "plain / です・ます / 敬語",
    "en": "*(no grammatical T/V)*",
}

#: How the gold set behind a language was made. "drafted" carries the
#: confidence the set declares about itself; a set with no confidence field is
#: the Bengali one, which was written by a speaker rather than compiled.
CONFIDENCE_MARK = {
    "low": "drafted · low",
    "medium": "drafted · medium",
    "high": "drafted · high",
    "unrated": "speaker",
    "none": "—",
}


def _gold_confidence(code: str) -> str:
    path = GOLD_DIR / f"{code}.jsonl"
    if not path.exists():
        return "none"
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                return json.loads(line).get("confidence") or "unrated"
    return "unrated"


def _levels_realised(code: str) -> int:
    """How many of the four the language actually distinguishes."""
    return len({get_table(code).fold(level) for level in LEVELS})


def build_table() -> str:
    rows: List[str] = [
        "| Code | Language | Levels | Rules | Vocatives | Gold | Second person |",
        "|---|---|:-:|:-:|:-:|:-:|---|",
    ]
    total = 0
    codes = [c for c in ORDER if c in TABLES] + sorted(set(TABLES) - set(ORDER))
    for code in codes:
        table = get_table(code)
        count = len(table.rules)
        total += count
        confidence = _gold_confidence(code)
        rows.append(
            "| `{code}` | {name} | {levels} | {rules} | {voc} | {conf} | {pron} |".format(
                code=code,
                name=table.name,
                levels=_levels_realised(code),
                rules=count,
                voc="✓" if table.address_terms else "—",
                conf=CONFIDENCE_MARK.get(confidence, confidence),
                pron=PRONOUNS.get(code, ""),
            )
        )

    header = (
        f"**{len(codes)} languages, {total:,} rules.** Thirteen of them are "
        "Indian, which is the point: CoCoA-MT gave Hindi a *binary* formality "
        "benchmark in 2022 and every other Indian language got nothing at all."
    )
    footer = (
        "**Levels** is how many of the four the language actually realises — "
        "the rest fold onto the nearest real one. **Vocatives** marks the "
        "languages that require an address term (দাদা, भैया, அண்ணா), which "
        "English leaves empty. **Gold** is how much the sentence set behind "
        "the numbers has been checked: `speaker` means written by one, and "
        "everything marked `drafted` was compiled from reference grammars and "
        "is waiting for one — see [REVIEWING.md](REVIEWING.md).\n\n"
        "This table is generated. Run `python -m docs.make_coverage_table "
        "--write` after changing a table."
    )
    return f"{header}\n\n" + "\n".join(rows) + f"\n\n{footer}"


def current_block(readme: str) -> Optional[str]:
    match = re.search(
        re.escape(BEGIN) + r"\n(.*?)\n" + re.escape(END), readme, re.DOTALL
    )
    return match.group(1) if match else None


def write(readme_path: Path = README) -> bool:
    text = readme_path.read_text(encoding="utf-8")
    block = build_table()
    if BEGIN not in text:
        raise SystemExit(
            f"{readme_path.name} has no {BEGIN} marker — add it and the "
            f"matching {END} around the coverage table."
        )
    updated = re.sub(
        re.escape(BEGIN) + r"\n.*?\n" + re.escape(END),
        f"{BEGIN}\n{block}\n{END}",
        text,
        flags=re.DOTALL,
    )
    if updated == text:
        return False
    readme_path.write_text(updated, encoding="utf-8")
    return True


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true",
                        help="update README.md in place")
    args = parser.parse_args(argv)

    if not args.write:
        print(build_table())
        return 0

    changed = write()
    print("README.md updated" if changed else "README.md already up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
