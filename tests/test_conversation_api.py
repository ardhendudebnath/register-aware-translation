"""
The contract between the conversation UI and the server.

The client reads specific keys out of these payloads to draw the transcript,
the per-side register readout and the shift notices. If a key is renamed the
server keeps working, every Python test keeps passing, and the screen quietly
goes blank — nothing raises, because JavaScript reading an absent property
gets `undefined` and carries on.

So this asserts the shape the browser actually depends on, and nothing more.
"""

from __future__ import annotations

import pytest

import app as app_module
from app import app

CASUAL_BN = "তুমি কেমন আছ?"
POLITE_BN = "আপনি কেমন আছেন?"


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    """
    Keep the network out of it.

    These test a payload shape, not a translation engine, and left online each
    turn made a real call — seven tests took two and a half minutes, more than
    the rest of the suite put together. Offline the register layer still runs,
    which is the part being asserted.
    """
    monkeypatch.setattr(app_module, "ALLOW_NETWORK", False)


@pytest.fixture()
def client():
    return app.test_client()


@pytest.fixture()
def conversation(client):
    res = client.post("/api/conversation", json={
        "a": {"name": "Priya", "language": "bn", "register": "auto"},
        "b": {"name": "You", "language": "en", "register": "auto"},
    })
    assert res.status_code == 201
    return res.get_json()


def _say(client, cid, speaker, text):
    res = client.post(f"/api/conversation/{cid}/say",
                      json={"speaker": speaker, "text": text})
    assert res.status_code == 200, res.get_data(as_text=True)
    return res.get_json()


def test_create_returns_what_the_client_needs_to_start(conversation):
    assert conversation["id"]
    assert set(conversation["participants"]) == {"Priya", "You"}
    for key in ("observed_registers", "asymmetric", "shifts", "turns"):
        assert key in conversation, f"the client reads {key!r}"


def test_a_turn_returns_both_the_result_and_the_conversation(client, conversation):
    payload = _say(client, conversation["id"], "Priya", CASUAL_BN)
    assert "result" in payload and "conversation" in payload
    turns = payload["conversation"]["turns"]
    assert len(turns) == 1
    # Every field the transcript renders.
    for key in ("speaker", "text", "translated", "register_name", "detected_name"):
        assert key in turns[0], f"the transcript renders {key!r}"


def test_the_transcript_can_tell_the_two_sides_apart(client, conversation):
    cid = conversation["id"]
    _say(client, cid, "Priya", CASUAL_BN)
    payload = _say(client, cid, "You", "How are you?")
    speakers = [t["speaker"] for t in payload["conversation"]["turns"]]
    assert speakers == ["Priya", "You"]
    # The client maps speaker -> side off participants, so the names have to
    # agree between the two.
    assert set(speakers) <= set(payload["conversation"]["participants"])


def test_a_shift_carries_a_turn_index_the_client_can_anchor_to(client, conversation):
    """
    The notice is placed *in* the transcript, after the turn that confirmed it,
    so at_turn has to be a usable index into turns.
    """
    cid = conversation["id"]
    for text in (CASUAL_BN, CASUAL_BN, POLITE_BN, POLITE_BN):
        payload = _say(client, cid, "Priya", text)

    convo = payload["conversation"]
    assert convo["shifts"], "four turns across a register change and no shift"
    shift = convo["shifts"][0]
    assert 0 <= shift["at_turn"] < len(convo["turns"])
    assert shift["message"]
    assert shift["direction"] in ("warmer", "cooler")


def test_observed_registers_is_keyed_by_name(client, conversation):
    cid = conversation["id"]
    _say(client, cid, "Priya", POLITE_BN)
    payload = _say(client, cid, "Priya", POLITE_BN)
    observed = payload["conversation"]["observed_registers"]
    assert set(observed) == {"Priya", "You"}
    # Rendered straight into the readout, so it is a name or nothing.
    assert observed["Priya"] in ("Close", "Casual", "Polite", "Formal")
    assert observed["You"] is None


def test_an_unknown_speaker_is_refused_rather_than_silently_dropped(client, conversation):
    res = client.post(f"/api/conversation/{conversation['id']}/say",
                      json={"speaker": "Nobody", "text": "hello"})
    assert res.status_code == 400
    assert "error" in res.get_json()


def test_an_unknown_conversation_is_a_404(client):
    assert client.get("/api/conversation/nope").status_code == 404
