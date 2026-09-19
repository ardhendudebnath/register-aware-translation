"""
Start-up must not load the model to find out whether there is one.

backend_report() used to call load_trained_classifier() and check the result
was not None — which loaded 519 MB of transformer weights, at every server
start, before the page could be served, to print "formality model: trained".
It took 65 seconds. The first time it was seen during this project it looked
like the server had crashed.

The regression is silent: nothing fails, the app just takes a minute to open.
So these assert the property directly — that reporting does not load.
"""

from __future__ import annotations

import pytest

from models import backend_report, classifier


@pytest.fixture()
def load_counter(monkeypatch):
    """Count calls into the real loader, without letting any of them load."""
    calls = []

    def counted():
        calls.append(1)
        return None

    counted.cache_clear = lambda: None  # stands in for the lru_cache wrapper
    monkeypatch.setattr(classifier, "load_trained_classifier", counted)
    return calls


def test_reporting_backends_does_not_load_the_classifier(load_counter):
    backend_report()
    assert load_counter == [], (
        "backend_report() loaded the classifier to find out whether it exists"
    )


def test_availability_is_answered_from_the_filesystem(tmp_path, monkeypatch):
    monkeypatch.setattr(classifier, "MODEL_DIR", tmp_path)
    assert classifier.trained_classifier_available() is False

    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    assert classifier.trained_classifier_available() is False, (
        "a config with no weights is not a model"
    )

    (tmp_path / "model.safetensors").write_bytes(b"")
    assert classifier.trained_classifier_available() is True


def test_sharded_checkpoints_count_as_present(tmp_path, monkeypatch):
    monkeypatch.setattr(classifier, "MODEL_DIR", tmp_path)
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    (tmp_path / "model.safetensors.index.json").write_text("{}", encoding="utf-8")
    assert classifier.trained_classifier_available() is True


def test_a_missing_model_directory_is_simply_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(classifier, "MODEL_DIR", tmp_path / "nowhere")
    assert classifier.trained_classifier_available() is False
