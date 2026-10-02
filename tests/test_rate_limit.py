"""
Stopping one caller from spending the server's translation quota.

The MT endpoint is undocumented, keyless and rate-limited *against this
server*, so somebody scripting a corpus through a public demo does not get
throttled themselves — they take the demo down for everybody else. DEPLOY.md
warned about that before anything mitigated it; this is the mitigation.

Only the paths that reach the engine are counted. Re-levelling, detection and
the register pad are local string work, and a limit on them would protect
nothing.

It is not a security control and the docstrings say so: the forwarded header
it counts by is forgeable by anyone talking to the server directly. It stops
accidents and casual abuse, which is what a demo shown to twenty people
actually faces.
"""

from __future__ import annotations

import importlib
import time

import pytest

import app as app_module
from app import RateLimiter


# ------------------------------------------------------------- the limiter


def test_it_allows_up_to_the_limit_then_reports_the_wait():
    limiter = RateLimiter(limit=3, window_s=60)
    assert [limiter.check("a") for _ in range(3)] == [None, None, None]
    waited = limiter.check("a")
    assert waited is not None and 0 < waited <= 60


def test_callers_are_counted_separately():
    limiter = RateLimiter(limit=1, window_s=60)
    assert limiter.check("a") is None
    assert limiter.check("b") is None, "one caller's burst is not another's"
    assert limiter.check("a") is not None


def test_the_window_rolls_over():
    # Generous margins on purpose: the clock this runs against has about 15 ms
    # of granularity, and a test that fails on a slow afternoon teaches nobody
    # anything.
    limiter = RateLimiter(limit=1, window_s=0.05)
    assert limiter.check("a") is None
    assert limiter.check("a") is not None

    time.sleep(0.25)
    assert limiter.check("a") is None


def test_it_does_not_grow_without_limit():
    """One dict entry per caller, swept once there are enough to matter."""
    limiter = RateLimiter(limit=1, window_s=0.05)
    for index in range(2100):
        limiter.check(f"caller-{index}")
    assert len(limiter._hits) == 2100, "all still inside their window"

    time.sleep(0.25)
    limiter.check("someone-new")        # the sweep runs on the next call
    assert len(limiter._hits) == 1


# ------------------------------------------------------------------ shared


@pytest.fixture()
def shared(monkeypatch, tmp_path):
    monkeypatch.setenv("SETU_SHARED", "1")
    importlib.reload(app_module)
    monkeypatch.setattr(app_module, "ALLOW_NETWORK", False)
    monkeypatch.setattr(app_module, "_finals", RateLimiter(limit=2, window_s=60))
    yield app_module
    monkeypatch.delenv("SETU_SHARED", raising=False)
    importlib.reload(app_module)


def _translate(client, ip="203.0.113.7"):
    return client.post(
        "/api/translate",
        json={"text": "তুমি কেমন আছ?", "source_lang": "bn",
              "target_lang": "bn", "register": "polite"},
        headers={"X-Forwarded-For": ip},
    )


def test_a_burst_from_one_address_is_refused_with_a_wait(shared):
    client = shared.app.test_client()
    assert _translate(client).status_code == 200
    assert _translate(client).status_code == 200

    refused = _translate(client)
    assert refused.status_code == 429
    assert refused.headers["Retry-After"]
    body = refused.get_json()
    assert "too many" in body["error"] and body["retry_after_s"] > 0


def test_another_address_is_unaffected(shared):
    client = shared.app.test_client()
    _translate(client, ip="203.0.113.7")
    _translate(client, ip="203.0.113.7")
    assert _translate(client, ip="203.0.113.7").status_code == 429
    assert _translate(client, ip="198.51.100.4").status_code == 200


def test_local_work_is_not_limited(shared):
    """Re-levelling never leaves the machine; limiting it protects nothing."""
    client = shared.app.test_client()
    for _ in range(5):
        response = client.post("/api/relevel", json={
            "text": "আপনি কেমন আছেন?", "language": "bn", "register": "close",
        }, headers={"X-Forwarded-For": "203.0.113.7"})
        assert response.status_code == 200


# ------------------------------------------------------- one person's laptop


def test_nobody_is_limited_on_a_local_run(monkeypatch):
    monkeypatch.delenv("SETU_SHARED", raising=False)
    importlib.reload(app_module)
    monkeypatch.setattr(app_module, "ALLOW_NETWORK", False)
    monkeypatch.setattr(app_module, "_finals", RateLimiter(limit=1, window_s=60))
    client = app_module.app.test_client()
    for _ in range(4):
        assert _translate(client).status_code == 200
