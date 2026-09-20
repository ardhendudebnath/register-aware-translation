"""
Speculative translation: answering before the speaker has finished (5.2).

The browser produces interim transcripts within a few hundred milliseconds and
this project used to throw them away. Translating them instead is cheap, but it
puts three things at risk, and that is what these cover:

*The phrasebook.* It is a durable record of things people actually said. Half
a sentence is not one, and filling the cache with fragments would both mislead
its statistics and keep them forever.

*The engine.* Interim results arrive several times a second. Without a floor
between calls and a rule for dropping stale ones, a single speaker becomes a
flood of requests for answers nobody will see.

*The user.* A guess must never be mistaken for the answer — not shown as
settled, and never spoken aloud, since a sentence that is about to be corrected
is worse than silence.
"""

from __future__ import annotations

import time

import pytest

import app as app_module
from app import PARTIAL_MIN_CHARS, app, socketio
from pipeline import Phrasebook, SpeculativeCache, translate_partial, translate_text
from pipeline.core import _speculative
from register import CASUAL, POLITE


@pytest.fixture()
def book(tmp_path):
    return Phrasebook(tmp_path / "pb.sqlite3")


@pytest.fixture(autouse=True)
def _clean_cache():
    _speculative.clear()
    yield
    _speculative.clear()


# ------------------------------------------------------------------- cache


def test_the_cache_keeps_the_newest_and_forgets_the_oldest():
    cache = SpeculativeCache(size=2)
    cache.put("en", "bn", "one", "এক")
    cache.put("en", "bn", "two", "দুই")
    assert cache.get("en", "bn", "one") is not None
    cache.put("en", "bn", "three", "তিন")     # evicts the least recently used
    assert cache.get("en", "bn", "two") is None
    assert cache.get("en", "bn", "three")[0] == "তিন"


def test_the_cache_ignores_an_empty_translation():
    cache = SpeculativeCache()
    cache.put("en", "bn", "hello", "   ")
    assert cache.get("en", "bn", "hello") is None


# ----------------------------------------------------------------- partials


def test_a_partial_is_marked_and_stripped_of_what_it_cannot_use(book):
    result = translate_partial(
        "तुम कार्यालय जा", "hi", "hi", CASUAL,
        allow_network=False, phrasebook=book,
    )
    assert result.partial is True
    assert result.ladder == {}, "a half-sentence does not need four renderings"
    assert result.audio is None


def test_a_partial_is_still_put_into_the_right_register(book):
    """
    The register layer is a string pass, so the preview is at the right
    politeness level from the start rather than changing tone when it settles.
    """
    result = translate_partial(
        "तुम कहाँ जा", "hi", "hi", POLITE, allow_network=False, phrasebook=book,
    )
    assert "आप" in result.translated_text


def test_a_partial_never_reaches_the_phrasebook(book):
    translate_partial(
        "मैं कार्यालय जा", "hi", "hi", CASUAL,
        allow_network=False, phrasebook=book,
    )
    assert book.stats()["phrases"] == 0


def test_the_final_sentence_is_free_when_a_guess_already_covered_it(book):
    """
    The last partial is usually identical to the final transcript. When it is,
    the wait disappears — which is the entire point of guessing.
    """
    spoken = "मैं कार्यालय जा रहा हूँ"
    _speculative.put("hi", "hi", spoken, "मैं कार्यालय जा रहा हूँ", "public-endpoint")

    result = translate_text(
        spoken, "hi", "hi", CASUAL, allow_network=False, phrasebook=book,
    )
    assert result.engine == "speculative"
    assert result.cached is True
    # Said in full now, so it earns its place in the durable cache.
    assert book.stats()["phrases"] == 1


def test_a_guess_that_was_never_said_in_full_stays_out_of_the_phrasebook(book):
    _speculative.put("hi", "hi", "मैं कार्यालय जा", "मैं कार्यालय जा", "public-endpoint")
    translate_partial(
        "मैं कार्यालय जा", "hi", "hi", CASUAL,
        allow_network=False, phrasebook=book,
    )
    assert book.stats()["phrases"] == 0


# ------------------------------------------------------------------ socket


@pytest.fixture()
def ws(monkeypatch, tmp_path):
    monkeypatch.setattr(app_module, "ALLOW_NETWORK", False)
    monkeypatch.setattr(app_module, "_phrasebook", Phrasebook(tmp_path / "pb.sqlite3"))
    client = socketio.test_client(app)
    client.get_received()          # drop the "ready" greeting
    return client


def _partials(client):
    return [m for m in client.get_received() if m["name"] == "translation_partial"]


def test_a_partial_comes_back_over_the_socket(ws):
    ws.emit("translate_partial", {
        "text": "तुम कार्यालय जा", "seq": 1,
        "source_lang": "hi", "target_lang": "hi", "register": "casual",
    })
    received = _partials(ws)
    assert len(received) == 1
    payload = received[0]["args"][0]
    assert payload["partial"] is True
    assert payload["seq"] == 1
    assert payload["translated_text"]


def test_a_scrap_of_speech_is_not_worth_translating(ws):
    ws.emit("translate_partial", {
        "text": "a" * (PARTIAL_MIN_CHARS - 1), "seq": 1,
        "source_lang": "en", "target_lang": "bn",
    })
    assert _partials(ws) == []


def test_partials_arriving_too_fast_are_dropped_not_queued(ws):
    """Interim transcripts come several times a second; each is a real call."""
    for seq in range(1, 6):
        ws.emit("translate_partial", {
            "text": f"तुम कार्यालय जा रहे हो {seq}", "seq": seq,
            "source_lang": "hi", "target_lang": "hi",
        })
    assert len(_partials(ws)) == 1, "only the first inside the interval runs"

    time.sleep(app_module.PARTIAL_MIN_INTERVAL_S)
    ws.emit("translate_partial", {
        "text": "तुम कार्यालय जा रहे हो अब", "seq": 9,
        "source_lang": "hi", "target_lang": "hi",
    })
    assert len(_partials(ws)) == 1, "once the floor has passed, it runs again"


def test_an_older_partial_is_ignored_after_a_newer_one(ws):
    ws.emit("translate_partial", {
        "text": "तुम कार्यालय जा रहे हो", "seq": 5,
        "source_lang": "hi", "target_lang": "hi",
    })
    _partials(ws)
    time.sleep(app_module.PARTIAL_MIN_INTERVAL_S)
    ws.emit("translate_partial", {
        "text": "तुम कार्यालय जा रहे", "seq": 4,   # overtaken, arrived late
        "source_lang": "hi", "target_lang": "hi",
    })
    assert _partials(ws) == []


def test_a_failed_guess_is_silent(ws, monkeypatch):
    """
    The real translation is a moment away and reports anything that matters,
    so a broken guess must not put an error in front of the user.
    """
    def boom(*args, **kwargs):
        raise RuntimeError("engine on fire")

    monkeypatch.setattr(app_module, "translate_partial", boom)
    ws.emit("translate_partial", {
        "text": "तुम कार्यालय जा रहे हो", "seq": 1,
        "source_lang": "hi", "target_lang": "hi",
    })
    received = ws.get_received()
    assert received == [], "a failed guess said something to the user"


def test_disconnecting_forgets_the_connection(ws):
    """
    This failed when it was written: the handler took no arguments and
    Flask-SocketIO 5.6 passes a disconnect reason, so it never ran and every
    connection leaked an entry.
    """
    before = set(app_module._partial_state)
    ws.emit("translate_partial", {
        "text": "तुम कार्यालय जा रहे हो", "seq": 1,
        "source_lang": "hi", "target_lang": "hi",
    })
    added = set(app_module._partial_state) - before
    assert added, "the connection should be tracked"

    ws.disconnect()
    assert not (added & set(app_module._partial_state)), "state outlived the socket"


def test_state_from_vanished_connections_is_swept_up():
    """Belt and braces: one handler being wrong must not leak without limit."""
    app_module._partial_state.clear()
    now = time.monotonic()
    for index in range(70):
        app_module._partial_state[f"gone-{index}"] = {
            "seq": 1, "at": now - app_module.PARTIAL_STATE_TTL_S - 1,
        }
    app_module._partial_state["here"] = {"seq": 1, "at": now}

    app_module._forget_stale_connections(now)
    assert set(app_module._partial_state) == {"here"}
