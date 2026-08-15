"""
Model wrappers: STT, language ID, formality classification, MT, TTS.

Nothing here loads a model at import time. Every backend is resolved lazily and
cached on first use, so importing this package is free and an absent optional
dependency degrades one stage instead of breaking start-up.

``load_all_models()`` is retained for compatibility with the previous entry
point, but it now reports what is genuinely available rather than printing
"Models loaded successfully" over a dict of Nones.
"""

from __future__ import annotations

from typing import Dict

from . import classifier, language_id, stt, translator, tts

__all__ = [
    "classifier",
    "language_id",
    "stt",
    "translator",
    "tts",
    "load_all_models",
    "backend_report",
]


def backend_report() -> Dict[str, object]:
    """What this install can actually do, for start-up logs and /api/health."""
    return {
        "stt": stt.available_backend(),
        "mt": list(translator.available_backends()),
        "tts": tts.available_backend(),
        "formality_model": classifier.load_trained_classifier() is not None,
    }


def load_all_models() -> Dict[str, object]:
    """
    Warm the lazily-loaded backends and return a capability report.

    Kept for compatibility with the original ``app.py``. The models themselves
    are still loaded on first use — eagerly loading Whisper at import time cost
    seconds of start-up for a request that might never come.
    """
    report = backend_report()
    print("Setu backends:")
    print(f"  speech-to-text   : {report['stt'] or 'none (use browser ASR)'}")
    print(f"  translation      : {', '.join(report['mt'])}")
    print(f"  text-to-speech   : {report['tts'] or 'none (use browser TTS)'}")
    print(f"  formality model  : {'trained' if report['formality_model'] else 'rules + lexical'}")
    return report
