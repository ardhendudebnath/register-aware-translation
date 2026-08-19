"""
The README's coverage table has to match the tables it describes.

It was hand-maintained and it drifted, quietly and in the direction that
undersells the work: the README claimed 399 rules when there were 1,369, and
said Bengali had 39 when it had 118. Every figure in it was wrong, and nothing
anywhere would have said so — a stale number in prose fails no test and throws
no exception, it just misleads whoever reads it next.

So the table is generated, and this fails when it goes out of date. If it does:

    python -m docs.make_coverage_table --write
"""

from __future__ import annotations

from docs.make_coverage_table import BEGIN, END, build_table, current_block
from register import TABLES
from utils.helpers import PROJECT_ROOT

README = PROJECT_ROOT / "README.md"


def test_the_readme_has_somewhere_to_put_the_table():
    text = README.read_text(encoding="utf-8")
    assert BEGIN in text and END in text, (
        "the generated-block markers are gone from README.md"
    )


def test_the_table_matches_the_tables():
    block = current_block(README.read_text(encoding="utf-8"))
    assert block is not None
    assert block.strip() == build_table().strip(), (
        "README.md coverage table is stale — run:\n"
        "    python -m docs.make_coverage_table --write"
    )


def test_every_language_appears():
    """A language added to the engine but missing from the README is invisible."""
    block = current_block(README.read_text(encoding="utf-8")) or ""
    for code in TABLES:
        assert f"| `{code}` |" in block, f"{code} is not in the README table"


def test_the_rule_total_is_not_asserted_by_hand_anywhere_else():
    """
    One number, one source. A second copy of the total in the prose is exactly
    how the first one went stale.
    """
    text = README.read_text(encoding="utf-8")
    block = current_block(text) or ""
    outside = text.replace(block, "")
    total = f"{sum(len(t.rules) for t in TABLES.values()):,}"
    assert total not in outside, (
        f"the rule total {total} is repeated outside the generated block; "
        f"it will drift"
    )
