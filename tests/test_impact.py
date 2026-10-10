"""
The before-and-after check every rule change in this project gets.

Four separate commands used to produce these numbers and a person compared
them by eye, which is where a small regression hides: the honorific nouns
moved Bengali exactness by two tenths of a point, and that is invisible unless
you are looking straight at it.

What matters about this tool is that it is *quiet*. "Nothing moved" has to be
one line, or nobody runs it twice; and a difference has to be impossible to
miss, or running it is theatre.
"""

from __future__ import annotations

import json

import pytest

from evaluation.impact import EPSILON, compare, main, snapshot


@pytest.fixture()
def baseline() -> dict:
    return {
        "gold": {
            "bn": {"register": 1.0, "detection": 1.0, "exactness": 0.9846, "rows": 494},
            "hi": {"register": 1.0, "detection": 1.0, "exactness": 1.0, "rows": 249},
        },
        "external": {"pt": {"agreement": 0.928, "coverage": 0.761, "read": 18980}},
    }


def test_nothing_moved_is_silence(baseline):
    assert compare(baseline, json.loads(json.dumps(baseline))) == []


def test_a_drop_is_reported_with_both_numbers(baseline):
    after = json.loads(json.dumps(baseline))
    after["gold"]["bn"]["exactness"] = 0.9829

    lines = compare(baseline, after)
    assert len(lines) == 1
    assert "gold.bn.exactness" in lines[0]
    assert "0.9846" in lines[0] and "0.9829" in lines[0]
    assert "↓" in lines[0], "the direction is the first thing to read"


def test_an_improvement_is_reported_too(baseline):
    """A change you did not intend is worth seeing even when it is upward."""
    after = json.loads(json.dumps(baseline))
    after["external"]["pt"]["agreement"] = 0.935
    assert "↑" in compare(baseline, after)[0]


def test_noise_below_the_threshold_is_not_a_change(baseline):
    """The similarity model wobbles; a tool that cries wolf gets muted."""
    after = json.loads(json.dumps(baseline))
    after["gold"]["bn"]["register"] = 1.0 - (EPSILON / 2)
    assert compare(baseline, after) == []


def test_counts_are_compared_as_counts(baseline):
    after = json.loads(json.dumps(baseline))
    after["external"]["pt"]["read"] = 18000
    line = compare(baseline, after)[0]
    assert "18,980" in line and "18,000" in line


def test_a_new_or_departed_language_is_called_out(baseline):
    after = json.loads(json.dumps(baseline))
    after["gold"]["ta"] = {"register": 1.0, "detection": 1.0, "rows": 51}
    del after["gold"]["hi"]

    lines = "\n".join(compare(baseline, after))
    assert "+ gold.ta.register" in lines and "(new)" in lines
    assert "- gold.hi.register" in lines and "(gone)" in lines


def test_a_snapshot_without_the_corpus_is_a_smaller_claim(baseline):
    """
    Not a contradicting one. Somebody without the 2.3 GB splits still gets a
    useful answer about the gold sets rather than three false alarms.
    """
    without = {"gold": json.loads(json.dumps(baseline["gold"]))}
    assert compare(baseline, without) == []
    assert compare(without, baseline) == []


# --------------------------------------------------------------- the real run


def test_the_gold_snapshot_covers_every_language():
    current = snapshot(with_corpus=False)
    assert set(current) == {"gold"}
    assert len(current["gold"]) == 20
    for code, scores in current["gold"].items():
        assert scores["rows"] > 0, code
        assert 0.0 <= scores["register"] <= 1.0


def test_the_cli_says_so_when_there_is_no_baseline(tmp_path, capsys):
    code = main(["--no-corpus", "--baseline", str(tmp_path / "none.json")])
    assert code == 1
    assert "no baseline" in capsys.readouterr().out


def test_save_then_compare_is_quiet(tmp_path, capsys):
    path = str(tmp_path / "baseline.json")
    assert main(["--save", "--no-corpus", "--baseline", path]) == 0
    capsys.readouterr()

    assert main(["--no-corpus", "--baseline", path]) == 0
    assert "nothing moved" in capsys.readouterr().out
