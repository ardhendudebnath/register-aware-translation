"""
Recording the register the engine got wrong.

The blueprint's advice for the week after this ships is to use it for real and
note every mistake, because that list is the actual roadmap. The hard part is
the noting: it happens mid-conversation and is gone by the evening. So the app
takes the report while the wrong answer is still on screen.

What these pin down is the line between a report and a gold row. A gold row is
a claim the project stands behind; a report is one person in a hurry. They are
written to a different file, carry ``status: reported`` rather than ``draft``,
and nothing promotes one automatically.
"""

from __future__ import annotations

import json

import pytest

import app as app_module
from pipeline.corrections import Correction, CorrectionLog
from register import CASUAL, CLOSE, POLITE


@pytest.fixture()
def log(tmp_path):
    return CorrectionLog(tmp_path / "corrections.jsonl")


# ------------------------------------------------------------------- the log


def test_a_correction_keeps_what_a_fix_would_need(log):
    saved = log.record(
        text="आप कैसे हैं?", language="hi", expected=CASUAL, detected=POLITE,
        rules=["pron.2sg.nom", "v.hona.pres.m"], note="my brother, not a stranger",
    )
    assert saved.expected == CASUAL and saved.detected == POLITE
    row = saved.as_dict()
    # The rules are the difference between a feeling and a place to start.
    assert row["rules"] == ["pron.2sg.nom", "v.hona.pres.m"]
    assert row["expected_name"] == "Casual" and row["detected_name"] == "Polite"
    assert row["status"] == "reported", "a report is not a gold row"


def test_it_survives_a_restart(log):
    log.record(text="তুমি কেমন আছ?", language="bn", expected=POLITE, detected=CASUAL)
    reopened = CorrectionLog(log.path)
    assert [c.text for c in reopened.all()] == ["তুমি কেমন আছ?"]
    assert reopened.summary()["by_language"] == {"bn": 1}


def test_one_json_object_per_line_like_the_gold_sets(log):
    log.record(text="तुम कैसे हो?", language="hi", expected=POLITE, detected=CASUAL)
    log.record(text="तू कैसा है?", language="hi", expected=CASUAL, detected=CLOSE)
    lines = log.path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert all(json.loads(line)["language"] == "hi" for line in lines)


@pytest.mark.parametrize("kwargs, message", [
    ({"text": "  ", "language": "hi", "expected": CASUAL}, "needs the sentence"),
    ({"text": "x", "language": "zz", "expected": CASUAL}, "no register table"),
    ({"text": "x", "language": "hi", "expected": CASUAL, "detected": CASUAL},
     "already agrees"),
])
def test_it_refuses_what_nobody_could_read_later(log, kwargs, message):
    with pytest.raises(ValueError, match=message):
        log.record(**kwargs)


def test_a_read_only_data_directory_does_not_lose_the_session(tmp_path):
    """The app must not fall over mid-conversation because a path is wrong."""
    log = CorrectionLog(tmp_path / "nowhere" / "nested" / "x.jsonl")
    log.path.parent.mkdir(parents=True)
    log.path.parent.chmod(0o500)          # best effort; Windows may ignore it
    saved = log.record(text="तुम कैसे हो?", language="hi", expected=POLITE,
                       detected=CASUAL)
    assert saved.text == "तुम कैसे हो?"
    assert log.all(), "the correction is still available this session"


# ------------------------------------------------------------------- the API


@pytest.fixture()
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(app_module, "ALLOW_NETWORK", False)
    monkeypatch.setattr(app_module, "_corrections",
                        CorrectionLog(tmp_path / "corrections.jsonl"))
    return app_module.app.test_client()


def test_the_api_records_and_counts(client):
    response = client.post("/api/corrections", json={
        "text": "आप कैसे हैं?", "language": "hi",
        "detected": "Polite", "expected": "casual",
        "rules": ["pron.2sg.nom"], "note": "my brother",
    })
    assert response.status_code == 200
    body = response.get_json()
    assert body["recorded"]["expected_name"] == "Casual"
    assert body["count"] == 1
    assert client.get("/api/corrections").get_json()["count"] == 1


def test_the_api_explains_a_refusal(client):
    response = client.post("/api/corrections", json={
        "text": "", "language": "hi", "expected": "casual",
    })
    assert response.status_code == 400
    assert "sentence" in response.get_json()["error"]


def test_a_shared_server_collects_nobody_elses_sentences(monkeypatch, tmp_path):
    """Same reasoning as relationship memory: not yours to collect."""
    import importlib

    monkeypatch.setenv("SETU_SHARED", "1")
    importlib.reload(app_module)
    try:
        shared = app_module.app.test_client()
        assert shared.post("/api/corrections", json={
            "text": "x", "language": "hi", "expected": "casual",
        }).status_code == 403
        assert shared.get("/api/corrections").status_code == 403
    finally:
        monkeypatch.delenv("SETU_SHARED", raising=False)
        importlib.reload(app_module)


def test_corrections_are_not_written_into_the_gold_sets():
    """
    A gold row is a claim the project stands behind. Nothing here promotes a
    report into one, and the file deliberately lives outside data/gold/.
    """
    from pipeline.corrections import CORRECTIONS_PATH

    assert CORRECTIONS_PATH.parent.name == "data"
    assert "gold" not in CORRECTIONS_PATH.parts
