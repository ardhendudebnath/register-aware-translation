"""
Package the gold sets as a dataset somebody else can use.

Blueprint 13.2 #7 wants a publicly released multi-level register benchmark for
Indian languages, on the grounds that Bengali — 228 million speakers, three
grammatical registers — has nothing, and neither does Tamil, Telugu, Kannada,
Malayalam, Gujarati, Marathi, Punjabi, Odia or Assamese.

The data exists. What was missing is everything that turns a directory of
JSONL into something a stranger can pick up: a schema, a datasheet, stable
checksums, and baseline numbers produced by a stated method. This builds that,
in one command, into a versioned directory.

It will not call the result a benchmark. Every row is still ``status: draft``,
meaning it was written by its drafter and checked by nobody, and a benchmark
whose labels nobody has verified is a way of publishing one person's opinion
with a leaderboard attached. So the release carries ``status: "draft"``, the
directory name says ``-draft``, and the baselines are labelled for what they
are: a consistency check between two halves of the same engine, not an
accuracy claim. When rows start coming back verified from the review pages,
all three change on their own — nothing here needs editing.

Usage::

    python -m evaluation.release                    # build releases/
    python -m evaluation.release --version 0.2.0
    python -m evaluation.release --external         # add FAME-MT agreement
    python -m evaluation.release --refresh-datasheet
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from register import LEVEL_NAMES, get_table, has_table
from utils.helpers import PROJECT_ROOT

from .gold_sets import GOLD_DIR, load_gold_set
from .metrics import evaluate

__all__ = [
    "VERSION",
    "LanguageSummary",
    "summarise",
    "build",
    "counts_table",
    "refresh_datasheet",
    "main",
]

#: Bump by hand. The suffix is decided by the data, not by this number.
VERSION = "0.1.0"

DATASET_NAME = "setu-register"
DEFAULT_OUT = PROJECT_ROOT / "releases"
DOCS = (GOLD_DIR / "SCHEMA.md", GOLD_DIR / "DATASHEET.md")

#: Matches ``python -m evaluation.external``'s own default.
EXTERNAL_ROW_LIMIT = 200_000

#: The datasheet's counts are generated, so they cannot drift from the data.
COUNTS_BEGIN = "<!-- counts:begin -->"
COUNTS_END = "<!-- counts:end -->"


@dataclass
class LanguageSummary:
    """One language's contribution to a release."""

    code: str
    name: str
    rows: int
    verified: int
    levels: Dict[str, int] = field(default_factory=dict)
    groups: Dict[str, int] = field(default_factory=dict)
    ladders: int = 0
    unmarked: int = 0
    hard: int = 0
    confidence: str = "unrated"
    sha256: str = ""

    @property
    def status(self) -> str:
        return "verified" if self.rows and self.verified == self.rows else "draft"

    def as_dict(self) -> dict:
        return {
            "language": self.code,
            "name": self.name,
            "rows": self.rows,
            "verified_rows": self.verified,
            "status": self.status,
            "drafter_confidence": self.confidence,
            "ladders": self.ladders,
            "unmarked_rows": self.unmarked,
            "hard_rows": self.hard,
            "rows_per_level": self.levels,
            "rows_per_group": self.groups,
            "sha256": self.sha256,
        }


def _rows(code: str) -> List[dict]:
    path = GOLD_DIR / f"{code}.jsonl"
    with path.open(encoding="utf-8") as fh:
        return [
            json.loads(line)
            for line in fh
            if line.strip() and not line.startswith("//")
        ]


def available() -> List[str]:
    """Languages with a gold set, in the order the release lists them."""
    return sorted(p.stem for p in GOLD_DIR.glob("*.jsonl"))


def summarise(code: str) -> LanguageSummary:
    """Count one language's rows without interpreting them."""
    rows = _rows(code)
    path = GOLD_DIR / f"{code}.jsonl"

    levels: Dict[str, int] = {}
    groups: Dict[str, int] = {}
    ladders = set()
    for row in rows:
        key = (
            LEVEL_NAMES[row["level"]] if isinstance(row.get("level"), int)
            else "unmarked"
        )
        levels[key] = levels.get(key, 0) + 1
        group = row.get("group") or "ungrouped"
        groups[group] = groups.get(group, 0) + 1
        expected = row.get("expected")
        if expected:
            # Rows sharing an expected map are one contrast set.
            ladders.add(json.dumps(expected, sort_keys=True, ensure_ascii=False))

    return LanguageSummary(
        code=code,
        name=get_table(code).name if has_table(code) else code,
        rows=len(rows),
        verified=sum(1 for r in rows if r.get("status") == "verified"),
        levels=dict(sorted(levels.items())),
        groups=dict(sorted(groups.items(), key=lambda kv: (-kv[1], kv[0]))),
        ladders=len(ladders),
        unmarked=levels.get("unmarked", 0),
        hard=groups.get("hard", 0),
        confidence=next(
            (r["confidence"] for r in rows if r.get("confidence")), "unrated"
        ),
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    )


def baselines(codes: Sequence[str]) -> Dict[str, dict]:
    """The four internal metrics, per language."""
    out: Dict[str, dict] = {}
    for code in codes:
        cases = load_gold_set(code)
        if not cases:
            continue
        out[code] = evaluate(cases, code).as_dict()
        # The failure lists are for debugging this engine, not for a release.
        for key, value in out[code].items():
            if isinstance(value, dict):
                value.pop("failures", None)
    return out


def external_agreement() -> Optional[Dict[str, dict]]:
    """
    Agreement with FAME-MT's own formality labels, when the corpus is present.

    This is the one number here that is not self-referential: somebody else's
    labels, on somebody else's sentences. It covers six European languages and
    none of the Indian ones, which is the entire reason the rest of this
    release needs to exist.
    """
    from .external import DEFAULT_SPLIT, SPLIT_DIR, score_language

    if not (SPLIT_DIR / DEFAULT_SPLIT).exists():
        return None
    # The same 200,000-row default the documented command uses, so a number in
    # a release and a number in the README cannot disagree about the method.
    scored = score_language(limit=EXTERNAL_ROW_LIMIT)
    return {
        code: {
            "agreement": round(agreement.accuracy, 4),
            "coverage": round(agreement.coverage, 4),
            "sentences_read": agreement.read,
            "sentences_seen": agreement.seen,
        }
        for code, agreement in sorted(scored.items())
    }


# --------------------------------------------------------------------------
# The datasheet's generated counts
# --------------------------------------------------------------------------


def counts_table(summaries: Optional[Sequence[LanguageSummary]] = None) -> str:
    """The per-language table in the datasheet, generated from the data."""
    summaries = summaries or [summarise(code) for code in available()]
    lines = [
        "| Language | Rows | Ladders | Unmarked | Hard | Drafter confidence | Reviewed |",
        "|---|---:|---:|---:|---:|---|---:|",
    ]
    for s in sorted(summaries, key=lambda s: s.name):
        lines.append(
            f"| {s.name} (`{s.code}`) | {s.rows} | {s.ladders} | {s.unmarked} | "
            f"{s.hard} | {s.confidence} | {s.verified} |"
        )
    total_rows = sum(s.rows for s in summaries)
    total_ladders = sum(s.ladders for s in summaries)
    total_unmarked = sum(s.unmarked for s in summaries)
    total_hard = sum(s.hard for s in summaries)
    total_verified = sum(s.verified for s in summaries)
    lines.append(
        f"| **{len(summaries)} languages** | **{total_rows}** | **{total_ladders}** | "
        f"**{total_unmarked}** | **{total_hard}** | | **{total_verified}** |"
    )
    return "\n".join(lines)


def refresh_datasheet(path: Optional[Path] = None) -> bool:
    """
    Rewrite the datasheet's generated block. True when it changed.

    Counts in a datasheet go stale the moment anyone adds a row, and a stale
    datasheet is worse than none — it is a claim about data that is no longer
    the data. So they are generated, and a test fails if the file on disk is
    not what this produces.
    """
    path = path or (GOLD_DIR / "DATASHEET.md")
    text = path.read_text(encoding="utf-8")
    start, end = text.find(COUNTS_BEGIN), text.find(COUNTS_END)
    if start < 0 or end < 0:
        raise ValueError(f"{path} has no {COUNTS_BEGIN} … {COUNTS_END} block")

    block = f"{COUNTS_BEGIN}\n{counts_table()}\n{COUNTS_END}"
    updated = text[:start] + block + text[end + len(COUNTS_END):]
    if updated == text:
        return False
    path.write_text(updated, encoding="utf-8")
    return True


# --------------------------------------------------------------------------
# Building a release
# --------------------------------------------------------------------------


def _release_readme(manifest: dict) -> str:
    draft = manifest["status"] == "draft"
    warning = (
        "> **Nothing in here has been checked by a native speaker.**\n"
        "> Every row was written by its drafter and verified by nobody, which\n"
        "> is why this is a draft dataset and not a benchmark. Treat the\n"
        "> sentences as a starting point to correct, not as ground truth.\n"
        if draft else
        "> Every row in this release has been checked by a native speaker.\n"
    )
    counts = manifest["totals"]
    return f"""# {manifest['name']} {manifest['version']}{'  (draft)' if draft else ''}

A multi-level register dataset for {counts['languages']} languages:
{counts['rows']} sentences annotated with **four** levels of politeness rather
than the usual formal/informal binary, across {counts['ladders']} contrast sets.

{warning}
## Why it exists

Bengali has 228 million speakers and three grammatical registers, and no
register dataset at all. Neither do Tamil, Telugu, Kannada, Malayalam,
Gujarati, Marathi, Punjabi, Odia or Assamese. The existing work — CoCoA-MT
(2022) and FAME-MT — is binary and, where it covers Indian languages at all,
covers Hindi only.

## What is here

    data/<lang>.jsonl    the sentences, one JSON object per line
    SCHEMA.md            every field, and what null means
    DATASHEET.md         who made it, how, and what it must not be used for
    MANIFEST.json        per-language counts and SHA-256 checksums
    baselines.json       what this project's own engine scores, and the method

Start with `DATASHEET.md`. It is more use than this file.

## Corrections

Corrections are the point. The review pages put one language on one page with
the ladders laid out and a box per row:

    {manifest['review_url']}

Or open an issue: {manifest['repository']}
"""


def _baselines_markdown(scores: Dict[str, dict], external: Optional[dict]) -> str:
    lines = [
        "# Baselines",
        "",
        "What this project's own rule engine scores on the data in this release.",
        "",
        "**These are a consistency check, not an accuracy claim.** Register",
        "accuracy and semantic preservation grade the engine against itself: a",
        "rewrite is read back by the same tables that produced it. Detection and",
        "exactness grade it against the drafter's own labels and strings, which",
        "is better — but the drafter is the person nobody has checked. A row that",
        "is wrong in the same direction as the rules scores a confident 100%.",
        "",
        "None of the four is external. The FAME-MT table, when the corpus is",
        "present, is the only number here that is.",
        "",
        "| Language | Register | Detection | Semantic | Exactness | Rows |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for code, report in sorted(scores.items()):
        exact = report.get("rewrite_exactness")
        exact_cell = f"{exact['score']:.1%}" if exact and exact["total"] else "—"
        lines.append(
            f"| `{code}` | {report['register_accuracy']['score']:.1%} "
            f"| {report['detection_accuracy']['score']:.1%} "
            f"| {report['semantic_preservation']['score']:.1%} "
            f"| {exact_cell} | {report['detection_accuracy']['total']} |"
        )

    if external:
        lines += [
            "",
            "## Agreement with FAME-MT",
            "",
            "Somebody else's labels, on somebody else's sentences — the one",
            "number here that is not self-referential. FAME-MT is binary, so",
            "the four levels are cut into formal/informal to compare. It covers",
            "six European languages and none of the Indian ones, which is the",
            "reason this dataset exists.",
            "",
            "| Language | Agreement | Coverage | Sentences read |",
            "|---|---:|---:|---:|",
        ]
        for code, row in external.items():
            lines.append(
                f"| `{code}` | {row['agreement']:.1%} | {row['coverage']:.1%} "
                f"| {row['sentences_read']:,} |"
            )
    return "\n".join(lines) + "\n"


def build(
    out_dir: Path = DEFAULT_OUT,
    version: str = VERSION,
    *,
    codes: Optional[Sequence[str]] = None,
    with_baselines: bool = True,
    with_external: bool = False,
) -> Path:
    """Assemble a release directory and return its path."""
    codes = list(codes or available())
    summaries = [summarise(code) for code in codes]
    status = (
        "verified"
        if summaries and all(s.status == "verified" for s in summaries)
        else "draft"
    )

    name = f"{DATASET_NAME}-{version}" + ("-draft" if status == "draft" else "")
    target = Path(out_dir) / name
    if target.exists():
        shutil.rmtree(target)
    (target / "data").mkdir(parents=True)

    for code in codes:
        shutil.copy2(GOLD_DIR / f"{code}.jsonl", target / "data" / f"{code}.jsonl")
    for doc in DOCS:
        shutil.copy2(doc, target / doc.name)

    manifest = {
        "name": DATASET_NAME,
        "version": version,
        "status": status,
        "built": date.today().isoformat(),
        "repository": "https://github.com/ardhendudebnath/register-aware-translation",
        "review_url": "https://ardhendudebnath.github.io/register-aware-translation/",
        "licence": _licence_state(),
        "levels": {str(k): v for k, v in sorted(LEVEL_NAMES.items())},
        "totals": {
            "languages": len(summaries),
            "rows": sum(s.rows for s in summaries),
            "ladders": sum(s.ladders for s in summaries),
            "verified_rows": sum(s.verified for s in summaries),
        },
        "languages": [s.as_dict() for s in summaries],
    }
    _write_json(target / "MANIFEST.json", manifest)
    (target / "README.md").write_text(_release_readme(manifest), encoding="utf-8")

    if with_baselines:
        scores = baselines(codes)
        external = external_agreement() if with_external else None
        _write_json(target / "baselines.json", {
            "engine": "setu register layer",
            "measured": date.today().isoformat(),
            "caveat": (
                "Register accuracy and semantic preservation grade the engine "
                "against itself; detection and exactness grade it against the "
                "drafter's own labels, and no drafter has been checked by a "
                "native speaker. These show internal consistency, not correctness."
            ),
            "internal": scores,
            "external_fame_mt": external,
        })
        (target / "baselines.md").write_text(
            _baselines_markdown(scores, external), encoding="utf-8"
        )

    licence = PROJECT_ROOT / "LICENSE"
    if licence.exists():
        shutil.copy2(licence, target / "LICENSE")
    else:
        (target / "LICENCE-NOT-CHOSEN.md").write_text(_LICENCE_NOTE, encoding="utf-8")

    return target


def _licence_state() -> str:
    return "see LICENSE" if (PROJECT_ROOT / "LICENSE").exists() else "not yet chosen"


_LICENCE_NOTE = """# No licence has been chosen yet

This repository carries no licence file, so by default nobody has permission to
use, copy or redistribute these files — which defeats the purpose of releasing
them. That decision belongs to the maintainer and has not been made.

For a dataset, the usual choices are **CC BY 4.0** (use it, credit us) or
**CC0** (use it, no conditions). For the code, a permissive software licence
such as MIT or Apache-2.0. Datasets and code are normally licensed separately.

Until a `LICENSE` file exists in the repository, treat this directory as
shared for review and correction only.
"""


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


# --------------------------------------------------------------------------


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("codes", nargs="*", help="languages (default: all)")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--version", default=VERSION)
    parser.add_argument("--no-baselines", action="store_true")
    parser.add_argument("--external", action="store_true",
                        help="also score against FAME-MT (needs the corpus)")
    parser.add_argument("--refresh-datasheet", action="store_true",
                        help="regenerate the datasheet's counts and stop")
    args = parser.parse_args(argv)

    if args.refresh_datasheet:
        changed = refresh_datasheet()
        print("datasheet updated" if changed else "datasheet already current")
        return 0

    target = build(
        args.out_dir,
        args.version,
        codes=args.codes or None,
        with_baselines=not args.no_baselines,
        with_external=args.external,
    )
    manifest = json.loads((target / "MANIFEST.json").read_text(encoding="utf-8"))
    totals = manifest["totals"]

    print(f"wrote {target}")
    print(f"  {totals['languages']} languages, {totals['rows']} rows, "
          f"{totals['ladders']} ladders")
    print(f"  status: {manifest['status']}  "
          f"({totals['verified_rows']} rows verified by a speaker)")
    print(f"  licence: {manifest['licence']}")
    if manifest["status"] == "draft":
        print()
        print("  This is not a benchmark yet. Rows become verified as speakers")
        print("  check them on the review pages; the status follows the data.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
