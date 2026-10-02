"""
Structural checks on the table source itself, not on what it evaluates to.

``register/tables/`` is thousands of lines of hand-written data, and a
duplicate key in a dict literal is silently legal Python: the later entry wins
and the earlier one vanishes. That is invisible at runtime, so no test that
imports the module can see it — by then the evidence is gone. These read the
source, every module of it.

It has bitten twice. Both times a verb was given new tenses, both times a
second entry for the same verb further down the dict quietly discarded them,
and both times the symptom was a rule that simply never fired: "तू नहीं जानता?"
would not agree its participle, and "तू कितनी देर रुकेगा?" would not conjugate
at all. Nothing failed loudly; the rules were just absent.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterator, List, Tuple

#: Every module the tables are written across. Reading the package rather than
#: one file, so splitting it up again cannot quietly take a language out of
#: this check's reach.
TABLE_SOURCES = sorted(
    (Path(__file__).resolve().parent.parent / "register" / "tables").glob("*.py")
)


def _dict_literals(tree: ast.AST) -> Iterator[Tuple[str, ast.Dict]]:
    """Every dict literal assigned to a module-level name."""
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if not isinstance(value, ast.Dict):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name):
                yield target.id, value


def _duplicate_keys(node: ast.Dict) -> List[Tuple[str, int]]:
    seen: dict = {}
    duplicates = []
    for key in node.keys:
        if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
            continue
        if key.value in seen:
            duplicates.append((key.value, key.lineno))
        seen[key.value] = key.lineno
    return duplicates


def test_no_duplicate_keys_in_table_dicts():
    assert TABLE_SOURCES, "no table modules found — has the package moved?"
    problems = []
    for source in TABLE_SOURCES:
        tree = ast.parse(source.read_text(encoding="utf-8"))
        for name, node in _dict_literals(tree):
            for key, line in _duplicate_keys(node):
                problems.append(f"{name}[{key!r}] redefined at {source.name}:{line}")
            # Paradigms are dicts of dicts; the inner ones hold the tenses, and
            # a repeated tense loses forms the same way a repeated verb does.
            for outer_key, value in zip(node.keys, node.values):
                if not isinstance(value, ast.Dict):
                    continue
                label = getattr(outer_key, "value", "?")
                for key, line in _duplicate_keys(value):
                    problems.append(
                        f"{name}[{label!r}][{key!r}] redefined at {source.name}:{line}"
                    )
    assert not problems, "duplicate keys silently discard entries:\n  " + \
        "\n  ".join(problems)


def test_no_duplicate_rule_names_within_a_table():
    """
    Two rules with one name are not fatal, but they are always a mistake —
    either a copy-paste, or two rules that will disagree about a word's level.
    """
    from register import TABLES as LANGUAGE_TABLES

    problems = []
    for code, table in LANGUAGE_TABLES.items():
        seen = set()
        for rule in table.rules:
            if rule.name in seen:
                problems.append(f"{code}: {rule.name}")
            seen.add(rule.name)
    assert not problems, "duplicate rule names:\n  " + "\n  ".join(problems)
