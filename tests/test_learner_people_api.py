"""
The contract between the Practise and People panels and the server.

Same reason as the conversation contract test: the browser reads specific keys,
and renaming one server-side breaks nothing that raises. The screen just goes
quietly wrong.

Relationship memory writes to a real SQLite file on the user's device, so every
test here swaps in a book backed by a temporary directory. A test suite that
leaves strangers in somebody's contact memory would be a strange bug to find.
"""

from __future__ import annotations

import pytest

import app as app_module
from app import app
from pipeline import RelationshipBook


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(app_module, "ALLOW_NETWORK", False)
    monkeypatch.setattr(
        app_module, "_relationships", RelationshipBook(tmp_path / "people.sqlite3")
    )


@pytest.fixture()
def client():
    return app.test_client()


# ------------------------------------------------------------------ learner


def test_the_practise_panel_can_list_who_to_practise_with(client):
    rels = client.get("/api/learner/relationships").get_json()["relationships"]
    assert rels
    for r in rels:
        for key in ("key", "label", "why", "expected"):
            assert key in r, f"the chips render {key!r}"


@pytest.mark.parametrize("text,relationship,verdict,suggests", [
    ("তুই কেমন আছিস?", "stranger", "too_familiar", True),
    ("আপনি কেমন আছেন?", "stranger", "good", False),
    ("আপনি কেমন আছেন?", "child", "too_formal", True),
    ("আজ আবহাওয়া ভালো।", "stranger", "unknown", False),
])
def test_every_verdict_the_panel_styles(client, text, relationship, verdict, suggests):
    fb = client.post("/api/learner/assess", json={
        "text": text, "language": "bn", "relationship": relationship,
    }).get_json()
    assert fb["verdict"] == verdict
    assert bool(fb["suggestion"]) is suggests
    for key in ("message", "evidence", "suggestion"):
        assert key in fb, f"the feedback renders {key!r}"


def test_the_evidence_names_the_words_that_carried_the_register(client):
    """A verdict with no reason is a ruling; one that points at তুই is a lesson."""
    fb = client.post("/api/learner/assess", json={
        "text": "তুই কেমন আছিস?", "language": "bn", "relationship": "stranger",
    }).get_json()
    assert "তুই" in fb["evidence"]


def test_empty_text_is_refused(client):
    assert client.post("/api/learner/assess", json={"text": "  "}).status_code == 400


# ------------------------------------------------------------------- people


def test_remember_then_use_round_trips_what_the_panel_applies(client):
    saved = client.post("/api/relationships", json={
        "name": "Rahul's father", "language": "bn",
        "register": "polite", "addressee": "elder_man",
    }).get_json()
    # "Use" reads exactly these to set the language, the chip and the vocative.
    for key in ("name", "language", "register_name", "register_slug", "addressee"):
        assert key in saved, f"the Use button needs {key!r}"
    assert saved["register_slug"] == "polite"

    people = client.get("/api/relationships").get_json()["relationships"]
    assert [p["name"] for p in people] == [saved["name"]]


def test_auto_is_saved_as_no_register_which_the_panel_explains(client):
    saved = client.post("/api/relationships", json={
        "name": "Somebody", "language": "bn", "register": "auto",
    }).get_json()
    assert saved["register_name"] is None
    assert saved["register_slug"] is None


def test_forget_really_removes_it(client):
    """There must always be a way to remove this data."""
    client.post("/api/relationships", json={"name": "Temp", "register": "casual"})
    res = client.delete("/api/relationships/temp").get_json()
    assert res["deleted"] is True
    assert client.get("/api/relationships").get_json()["relationships"] == []


def test_a_name_is_required(client):
    assert client.post("/api/relationships", json={"name": ""}).status_code == 400


def test_there_is_still_no_export_endpoint(client):
    """
    Who you are deferential to is as sensitive as a contact list gets. The
    panel says the data never leaves the device; this keeps that true.
    """
    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert not any("export" in r or "download" in r for r in rules)
