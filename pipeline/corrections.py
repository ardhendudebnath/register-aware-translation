"""
What the app got wrong, written down while you still remember.

The blueprint's advice for the week after this ships is to use it for real and
note every time it gets the register wrong, because that list is the actual
roadmap. The trouble with advice like that is the noting: the mistake happens
mid-conversation, and by the evening it is gone.

So the app records it. One press while the wrong answer is still on screen
captures the sentence, the level it chose, the level you expected, and the
rules that fired to get there — which is most of a gold row already, and the
rule names are what turn "this feels wrong" into something fixable.

These are **not** gold rows yet, and the file is deliberately not in
``data/gold/``. A correction is one person's opinion written in a hurry; a
gold row is a claim the project stands behind. Promoting one means looking at
it again, which is what ``python -m pipeline.corrections`` is for.

On a shared server this is off, for the same reason relationship memory is:
other people's sentences are not yours to collect.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from register import LEVELS, coerce_level, has_table, level_name
from utils.helpers import PROJECT_ROOT

__all__ = ["Correction", "CorrectionLog", "CORRECTIONS_PATH"]

CORRECTIONS_PATH = PROJECT_ROOT / "data" / "corrections.jsonl"


@dataclass(frozen=True)
class Correction:
    """One sentence the engine placed wrongly, as the user saw it."""

    text: str
    language: str
    #: What the engine said. None when it read no register at all, which is
    #: its own kind of mistake — the sentence had a marker and it missed it.
    detected: Optional[int]
    #: What the user says it should have been.
    expected: int
    #: The engine's own account of how it got there, so a fix has somewhere
    #: to start: ["pron.2sg.nom", "v.hona.pres"].
    rules: List[str] = field(default_factory=list)
    note: str = ""
    at: float = field(default_factory=time.time)

    def as_dict(self) -> dict:
        return {
            "text": self.text,
            "language": self.language,
            "detected": self.detected,
            "detected_name": level_name(self.detected) if self.detected is not None else None,
            "expected": self.expected,
            "expected_name": level_name(self.expected),
            "rules": list(self.rules),
            "note": self.note,
            "at": round(self.at, 3),
            # Marks these as the raw material they are. A gold row carries
            # "draft"; this is a step before that.
            "status": "reported",
        }


class CorrectionLog:
    """Append-only, one JSON object per line, like the gold sets themselves."""

    def __init__(self, path: Optional[Path] = CORRECTIONS_PATH):
        self.path = Path(path) if path is not None else None
        self._lock = threading.Lock()
        self._memory: List[Correction] = []

    def record(
        self,
        text: str,
        language: str,
        expected,
        detected=None,
        rules: Optional[List[str]] = None,
        note: str = "",
    ) -> Correction:
        """
        Write one down. Raises ValueError on anything it cannot make sense of,
        because a correction nobody can read later is worse than none.
        """
        text = (text or "").strip()
        if not text:
            raise ValueError("a correction needs the sentence that was wrong")
        language = (language or "").strip().lower()
        if not has_table(language):
            raise ValueError(f"no register table for {language!r}")

        expected_level = coerce_level(expected)
        detected_level = None if detected is None else coerce_level(detected)
        if detected_level == expected_level:
            raise ValueError(
                "the engine already agrees with that — nothing to correct"
            )

        correction = Correction(
            text=text,
            language=language,
            detected=detected_level,
            expected=expected_level,
            rules=[str(r) for r in (rules or [])][:20],
            note=(note or "").strip()[:500],
        )

        with self._lock:
            self._memory.append(correction)
            if self.path is not None:
                try:
                    self.path.parent.mkdir(parents=True, exist_ok=True)
                    with self.path.open("a", encoding="utf-8") as handle:
                        handle.write(
                            json.dumps(correction.as_dict(), ensure_ascii=False) + "\n"
                        )
                except OSError:
                    # A read-only data directory must not take down the app in
                    # the middle of somebody's conversation. The correction
                    # stays in memory for this session and says so in /api.
                    pass
        return correction

    def all(self) -> List[Correction]:
        if self.path is None or not self.path.exists():
            return list(self._memory)
        out: List[Correction] = []
        with self.path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                out.append(
                    Correction(
                        text=row.get("text", ""),
                        language=row.get("language", ""),
                        detected=row.get("detected"),
                        expected=row.get("expected", 0),
                        rules=row.get("rules", []),
                        note=row.get("note", ""),
                        at=row.get("at", 0.0),
                    )
                )
        return out

    def summary(self) -> Dict[str, object]:
        """Enough for the UI to say "3 noted" without reading the file twice."""
        rows = self.all()
        by_language: Dict[str, int] = {}
        for row in rows:
            by_language[row.language] = by_language.get(row.language, 0) + 1
        return {
            "count": len(rows),
            "by_language": dict(sorted(by_language.items())),
            "path": str(self.path) if self.path else None,
        }


def main(argv: Optional[List[str]] = None) -> int:
    """Print what has been reported, worst-served language first."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--path", type=Path, default=CORRECTIONS_PATH)
    args = parser.parse_args(argv)

    log = CorrectionLog(args.path)
    rows = log.all()
    if not rows:
        print(f"nothing reported yet ({args.path})")
        return 0

    counts = log.summary()["by_language"]
    print()
    print(f"  {len(rows)} corrections — the list the blueprint says is the roadmap")
    print()
    for code, count in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {code}  {count}")
    print()
    for row in rows:
        got = level_name(row.detected) if row.detected is not None else "nothing"
        print(f"  {row.language}  {row.text}")
        print(f"      read as {got}, should have been {level_name(row.expected)}")
        if row.rules:
            print(f"      rules: {', '.join(row.rules)}")
        if row.note:
            print(f"      note: {row.note}")
    print()
    print("  These are reports, not gold rows. A gold row is a claim the")
    print("  project stands behind; read these again before promoting any.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
