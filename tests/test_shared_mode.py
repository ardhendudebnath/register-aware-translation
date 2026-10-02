"""
What changes when more than one person shares the server.

Two features here are device-local by design, and both quietly stop being so
the moment the app has a public URL. There is no login, so "device-local" is
enforced by nothing but the fact that only you can reach localhost.

*Relationship memory* is who you are deferential to — about as sensitive as a
contact list gets. Shared, one visitor's "Rahul's father — আপনি" is readable
by the next, and the API hands over the whole list to anyone who asks.

*The phrasebook* is a durable record of every sentence anybody typed, written
to a file on a machine they do not own.

``SETU_SHARED=1`` closes the first and makes the second ephemeral. It is not
authentication and does not pretend to be: it is the difference between a demo
that cannot leak these and one that does.
"""

from __future__ import annotations

import importlib

import pytest


@pytest.fixture()
def shared_app(monkeypatch):
    """The app as it comes up with SETU_SHARED=1."""
    monkeypatch.setenv("SETU_SHARED", "1")
    import app as app_module

    importlib.reload(app_module)
    yield app_module
    monkeypatch.delenv("SETU_SHARED", raising=False)
    importlib.reload(app_module)        # leave the module as the others expect


@pytest.fixture()
def private_app(monkeypatch):
    monkeypatch.delenv("SETU_SHARED", raising=False)
    import app as app_module

    importlib.reload(app_module)
    return app_module


# ------------------------------------------------------- the shared server


@pytest.mark.parametrize("method, path", [
    ("get", "/api/relationships"),
    ("post", "/api/relationships"),
    ("delete", "/api/relationships/anybody"),
])
def test_relationship_memory_is_closed(shared_app, method, path):
    client = shared_app.app.test_client()
    response = getattr(client, method)(path, json={"name": "Rahul's father"})
    assert response.status_code == 403
    body = response.get_json()
    # The refusal has to say why, or it reads as a bug in the app.
    assert "shared server" in body["error"]
    assert "locally" in body["why"]


def test_nothing_anybody_types_is_written_to_disk(shared_app, monkeypatch, tmp_path):
    """
    The durable cache must not see a visitor's sentence — which means every
    entry point has to pass this server's own phrasebook rather than falling
    back to the module-level default. Asserted through the API, because that
    fallback is exactly the kind of thing a refactor reintroduces by accident.
    """
    from pipeline.core import Phrasebook

    assert shared_app._phrasebook.ephemeral
    assert shared_app._phrasebook.path is None

    durable = Phrasebook(tmp_path / "pb.sqlite3")
    monkeypatch.setattr(shared_app.core, "_phrasebook", durable)
    monkeypatch.setattr(shared_app, "ALLOW_NETWORK", False)
    before = shared_app._phrasebook.stats()["phrases"]

    shared_app.app.test_client().post("/api/translate", json={
        "text": "আপনি কেমন আছেন?", "source_lang": "bn",
        "target_lang": "bn", "register": "close",
    })

    assert durable.stats()["phrases"] == 0, "a visitor's sentence reached the file"
    assert shared_app._phrasebook.stats()["phrases"] > before


def test_the_cache_still_works_in_memory(shared_app):
    book = shared_app._phrasebook
    book.put("en", "bn", "hello there", "হ্যালো")
    assert book.get("en", "bn", "hello there") == "হ্যালো"
    assert book.stats()["phrases"] >= 1


def test_the_page_is_told_so_it_can_hide_the_panel(shared_app):
    body = shared_app.app.test_client().get("/api/health").get_json()
    assert body["shared"] is True
    assert body["phrasebook"]["ephemeral"] is True


# ------------------------------------------------------ one person's laptop


def test_nothing_changes_for_a_local_run(private_app):
    body = private_app.app.test_client().get("/api/health").get_json()
    assert body["shared"] is False
    assert body["phrasebook"]["ephemeral"] is False
    assert private_app.app.test_client().get("/api/relationships").status_code == 200
