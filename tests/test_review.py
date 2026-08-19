"""
The review pages are a promise the build scripts already make.

``build_bn.py`` has been printing "Review with: python -m evaluation.review bn"
since before the module existed. These tests keep that command working, and
keep the one piece of logic in it honest: a triad emits one row per level, and
collapsing them back into a single ladder is what turns Bengali's 1976 rows
into 198 things a person can actually be asked about.
"""

from __future__ import annotations

import json

from evaluation.review import build_pages, build_sections, load_rows, main


def test_the_advertised_command_runs(tmp_path):
    assert main(["bn", "--out-dir", str(tmp_path)]) == 0
    assert (tmp_path / "bn.html").exists()
    assert (tmp_path / "index.html").exists()


def test_a_triad_collapses_into_one_ladder(tmp_path):
    """Three rows sharing an `expected` map are one question, not three."""
    expected = {"0": "low", "1": "mid", "2": "high"}
    rows = [
        {"text": text, "level": level, "expected": expected,
         "group": "pronouns", "construction": "pron.nom", "id": f"x-{level}"}
        for level, text in enumerate(("low", "mid", "high"))
    ]
    sections = build_sections(rows)
    ladders = [ladder for section in sections for ladder in section.ladders]
    assert len(ladders) == 1
    assert [text for _, text in ladders[0].rungs] == ["low", "mid", "high"]


def test_hard_rows_come_first():
    """The flagged ambiguities are the highest-value question on the page."""
    rows = load_rows("ml")
    assert rows, "Malayalam gold set is missing"
    titles = [section.title for section in build_sections(rows)]
    assert titles[0].startswith("Questions we already know are hard")


def test_pages_are_self_contained_and_escaped(tmp_path):
    build_pages(["ur"], out_dir=tmp_path)
    page = (tmp_path / "ur.html").read_text(encoding="utf-8")
    # No network: a reviewer may well be offline, and a page that silently
    # loses its fonts or styling is a page that does not get filled in.
    assert "http://" not in page and "https://" not in page
    # Right-to-left has to reach the cell, not just the font.
    assert "card rtl" in page
    assert page.count("<script>") == 1


def test_every_gold_set_renders(tmp_path):
    """A set that cannot be reviewed is a set that stays a draft forever."""
    written = build_pages(out_dir=tmp_path)
    codes = {path.stem for path in written} - {"index"}
    from evaluation.gold_sets import GOLD_DIR
    assert codes == {path.stem for path in GOLD_DIR.glob("*.jsonl")}
