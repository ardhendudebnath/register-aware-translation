"""
The dataset release: does it describe itself honestly?

A release is a set of claims about data made to people who cannot see the data
being made. Most of these assert the unflattering ones — that nothing has been
reviewed, that the baselines are not an accuracy claim, that no licence has
been chosen — because those are exactly the claims that rot quietly. A datasheet
whose counts no longer match its data is worse than no datasheet, since it is
now a confident statement about something else.

The honesty here is meant to be automatic: ``status`` follows the ``status``
field in the rows, so the day speakers finish reviewing, the release stops
calling itself a draft without anybody editing a document.
"""

from __future__ import annotations

import json

import pytest

from evaluation import release
from evaluation.gold_sets import GOLD_DIR


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """One release, built without baselines — they are tested separately."""
    out = tmp_path_factory.mktemp("releases")
    return release.build(out, "9.9.9", with_baselines=False)


# ------------------------------------------------------------------ shape


def test_a_release_carries_the_data_and_its_documentation(built):
    for name in ("MANIFEST.json", "README.md", "SCHEMA.md", "DATASHEET.md"):
        assert (built / name).exists(), name
    shipped = {p.stem for p in (built / "data").glob("*.jsonl")}
    assert shipped == {p.stem for p in GOLD_DIR.glob("*.jsonl")}


def test_the_data_is_copied_byte_for_byte(built):
    for source in GOLD_DIR.glob("*.jsonl"):
        assert (built / "data" / source.name).read_bytes() == source.read_bytes()


def test_checksums_match_what_was_shipped(built):
    import hashlib

    manifest = json.loads((built / "MANIFEST.json").read_text(encoding="utf-8"))
    for entry in manifest["languages"]:
        shipped = (built / "data" / f"{entry['language']}.jsonl").read_bytes()
        assert hashlib.sha256(shipped).hexdigest() == entry["sha256"]


def test_counts_in_the_manifest_match_the_rows(built):
    manifest = json.loads((built / "MANIFEST.json").read_text(encoding="utf-8"))
    for entry in manifest["languages"]:
        lines = [
            line for line in
            (built / "data" / f"{entry['language']}.jsonl")
            .read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("//")
        ]
        assert entry["rows"] == len(lines), entry["language"]
    assert manifest["totals"]["rows"] == sum(
        e["rows"] for e in manifest["languages"]
    )


# --------------------------------------------------------------- honesty


def test_it_calls_itself_a_draft_while_rows_are_unverified(built):
    manifest = json.loads((built / "MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "draft"
    assert manifest["totals"]["verified_rows"] == 0
    assert built.name.endswith("-draft")
    assert "checked by a native speaker" in (built / "README.md").read_text(
        encoding="utf-8"
    )


def test_the_word_benchmark_is_not_claimed_while_it_is_a_draft(built):
    """
    A benchmark whose labels nobody has verified is one person's opinion with
    a leaderboard attached.
    """
    readme = (built / "README.md").read_text(encoding="utf-8").lower()
    assert "benchmark" not in readme.replace("not a benchmark", "")


def test_status_follows_the_data_rather_than_a_constant(tmp_path, monkeypatch):
    """The day every row is verified, the release says so on its own."""
    gold = tmp_path / "gold"
    gold.mkdir()
    row = {
        "text": "আপনি কেমন আছেন?", "level": 2, "language": "bn",
        "id": "bn-0001", "group": "pronouns", "construction": "pron.nom",
        "domain": "greeting", "context": "stranger", "note": "",
        "status": "verified",
    }
    (gold / "bn.jsonl").write_text(
        json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    monkeypatch.setattr(release, "GOLD_DIR", gold)

    built = release.build(tmp_path / "out", "1.0.0", with_baselines=False)
    manifest = json.loads((built / "MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "verified"
    assert not built.name.endswith("-draft")
    assert "has been checked by a native speaker" in (built / "README.md").read_text(
        encoding="utf-8"
    )


def test_the_release_carries_the_data_licence_and_how_to_credit_it(built):
    """
    Data and code are licensed separately — CC BY 4.0 and MIT — because
    conflating them is how a dataset ends up unusable. A release is data, so
    it ships the data licence.
    """
    manifest = json.loads((built / "MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["licence"]["id"] == "CC-BY-4.0"
    assert "Ardhendu Debnath" in manifest["licence"]["attribution"]

    shipped = (built / "LICENSE").read_text(encoding="utf-8")
    assert shipped == (release.GOLD_DIR / "LICENSE").read_text(encoding="utf-8")
    assert "CC-BY-4.0" in shipped
    assert manifest["licence"]["attribution"] in (
        built / "README.md"
    ).read_text(encoding="utf-8")


def test_a_release_refuses_to_ship_data_with_no_licence(tmp_path, monkeypatch):
    """Data nobody may legally use is worse than data nobody has."""
    monkeypatch.setattr(release, "LICENCE_FILE", tmp_path / "nowhere" / "LICENSE")
    with pytest.raises(FileNotFoundError, match="must carry one"):
        release.build(tmp_path / "out", "1.0.0", with_baselines=False)


def test_the_repository_licenses_code_and_data_separately():
    code = (release.PROJECT_ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "MIT License" in code
    assert "data/gold/LICENSE" in code, "the code licence should point at the data one"
    data = (release.GOLD_DIR / "LICENSE").read_text(encoding="utf-8")
    assert "SPDX-License-Identifier: CC-BY-4.0" in data
    assert "MIT" in data, "the data licence should point back at the code one"


def test_baselines_are_labelled_as_a_consistency_check(tmp_path):
    built = release.build(tmp_path / "out", "1.0.0", codes=["en"])
    payload = json.loads((built / "baselines.json").read_text(encoding="utf-8"))
    assert "internal consistency, not correctness" in payload["caveat"]
    assert payload["internal"]["en"]["detection_accuracy"]["total"] > 0
    # Failure lists are for debugging this engine, not for a release.
    assert "failures" not in payload["internal"]["en"]["detection_accuracy"]
    assert "not an accuracy claim" in (built / "baselines.md").read_text(
        encoding="utf-8"
    )


# ------------------------------------------------------------- datasheet


def test_the_datasheet_counts_are_current():
    """
    Generated, so they cannot drift. If this fails, run:

        python -m evaluation.release --refresh-datasheet
    """
    assert release.refresh_datasheet() is False, (
        "the datasheet's counts no longer match the data"
    )


def test_the_datasheet_leads_with_the_thing_that_matters():
    text = (GOLD_DIR / "DATASHEET.md").read_text(encoding="utf-8")
    # Markdown wraps and quotes the sentence, so match on the words alone.
    head = " ".join(text[:1200].replace(">", " ").split())
    assert "checked by a native speaker" in head
    for section in ("## Motivation", "## Composition", "## Collection process",
                    "## Uses", "## Distribution", "## Maintenance"):
        assert section in text, section


def test_the_schema_documents_every_field_the_data_uses():
    schema = (GOLD_DIR / "SCHEMA.md").read_text(encoding="utf-8")
    fields = set()
    for path in GOLD_DIR.glob("*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.startswith("//"):
                fields.update(json.loads(line))
    for field in fields:
        assert f"`{field}`" in schema, f"{field} is in the data but not the schema"
