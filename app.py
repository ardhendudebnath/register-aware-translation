"""
Setu — real-time formality-aware speech-to-speech translation.

    python app.py                 # http://localhost:5000
    SETU_DEBUG=1 python app.py    # reloader + verbose errors

The previous version loaded models at import, called four placeholder functions
that returned fixed strings, had no error handling, no REST surface, and ran
with debug=True unconditionally.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from flask import Flask, jsonify, render_template, request, send_from_directory
from flask_socketio import SocketIO, emit

from models import backend_report
from pipeline import translate_audio, translate_text
from pipeline.core import _phrasebook
from register import (
    AUTO,
    LEVELS,
    TABLES,
    coerce_level,
    detect as detect_register,
    has_table,
    level_name,
    level_slug,
    supported_languages,
)
from utils.helpers import PROJECT_ROOT

log = logging.getLogger("setu")

DEBUG = os.environ.get("SETU_DEBUG", "").lower() in ("1", "true", "yes")
HOST = os.environ.get("SETU_HOST", "127.0.0.1")
PORT = int(os.environ.get("SETU_PORT", "5000"))
#: Off by default. The public MT endpoint is undocumented and rate-limited;
#: an operator running an offline demo can disable it entirely.
ALLOW_NETWORK = os.environ.get("SETU_ALLOW_NETWORK", "1").lower() not in ("0", "false", "no")

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")


# --------------------------------------------------------------------------
# Pages and PWA plumbing
# --------------------------------------------------------------------------


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/manifest.json")
def manifest():
    return send_from_directory(PROJECT_ROOT / "static", "manifest.json",
                              mimetype="application/manifest+json")


@app.route("/sw.js")
def service_worker():
    # Must be served from the origin root, not /static/, or its scope cannot
    # cover the whole app. Browsers also refuse to register a worker from an
    # inline blob, which is why this is a real file (blueprint 8).
    response = send_from_directory(PROJECT_ROOT / "static", "sw.js",
                                   mimetype="application/javascript")
    response.headers["Service-Worker-Allowed"] = "/"
    return response


# --------------------------------------------------------------------------
# REST API
# --------------------------------------------------------------------------


@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "backends": backend_report(),
        "allow_network": ALLOW_NETWORK,
        "phrasebook": _phrasebook.stats(),
    })


@app.route("/api/languages")
def languages():
    """Languages with a register table, and how many levels each realises."""
    out = []
    for code in supported_languages():
        table = TABLES[code]
        out.append({
            "code": code,
            "name": table.name,
            "levels": [
                {"level": lvl, "name": level_name(lvl), "slug": level_slug(lvl),
                 "distinct": table.fold(lvl) == lvl}
                for lvl in LEVELS
            ],
            "distinct_levels": list(table.distinct_levels),
            "rule_count": len(table.rules),
            "address_terms": sorted(table.address_terms),
        })
    return jsonify({"languages": out, "registers": [
        {"level": lvl, "name": level_name(lvl), "slug": level_slug(lvl)} for lvl in LEVELS
    ]})


@app.route("/api/detect", methods=["POST"])
def api_detect():
    payload = _json_body()
    text = (payload.get("text") or "").strip()
    language = payload.get("language") or ""
    if not text:
        return jsonify({"error": "text is required"}), 400
    if not has_table(language):
        return jsonify({"error": f"no register table for {language!r}"}), 400
    return jsonify(detect_register(text, language).as_dict())


@app.route("/api/translate", methods=["POST"])
def api_translate():
    payload = _json_body()
    text = (payload.get("text") or "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400

    target = payload.get("target_lang") or payload.get("target") or "en"
    source = payload.get("source_lang") or payload.get("source") or None
    level = _parse_level(payload.get("register", AUTO))

    try:
        result = translate_text(
            text,
            target_lang=target,
            source_lang=source,
            register_level=level,
            addressee=payload.get("addressee") or None,
            soften=bool(payload.get("soften")),
            with_ladder=payload.get("ladder", True),
            with_audio=bool(payload.get("audio")),
            allow_network=ALLOW_NETWORK,
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("translate failed")
        return jsonify({"error": f"translation failed: {exc}"}), 500

    return jsonify(result.as_dict())


@app.route("/api/relevel", methods=["POST"])
def api_relevel():
    """
    Re-render already-translated text at a different register.

    No network, no MT call — this is the offline re-levelling that falls out of
    keeping the register layer above the engine (blueprint 13.3).
    """
    from register import ladder as register_ladder, rewrite as register_rewrite

    payload = _json_body()
    text = (payload.get("text") or "").strip()
    language = payload.get("language") or ""
    if not text:
        return jsonify({"error": "text is required"}), 400
    if not has_table(language):
        return jsonify({"error": f"no register table for {language!r}"}), 400

    if payload.get("all_levels"):
        rungs = register_ladder(text, language)
        return jsonify({
            "ladder": {level_slug(lvl): res.as_dict() for lvl, res in rungs.items()}
        })

    level = _parse_level(payload.get("register", AUTO))
    return jsonify(register_rewrite(text, language, level).as_dict())


@app.route("/api/phrasebook")
def api_phrasebook():
    return jsonify(_phrasebook.stats())


@app.errorhandler(404)
def not_found(_):
    return jsonify({"error": "not found"}), 404


@app.errorhandler(500)
def server_error(exc):
    log.exception("unhandled error")
    return jsonify({"error": "internal server error"}), 500


# --------------------------------------------------------------------------
# SocketIO
# --------------------------------------------------------------------------


@socketio.on("connect")
def on_connect():
    emit("ready", {"backends": backend_report(), "allow_network": ALLOW_NETWORK})


@socketio.on("translate")
def handle_translate(data):
    """Text arriving from the browser's own SpeechRecognition (the free path)."""
    data = data or {}
    text = (data.get("text") or "").strip()
    if not text:
        emit("translation_error", {"message": "Nothing to translate."})
        return

    try:
        result = translate_text(
            text,
            target_lang=data.get("target_lang") or "en",
            source_lang=data.get("source_lang") or None,
            register_level=_parse_level(data.get("register", AUTO)),
            addressee=data.get("addressee") or None,
            soften=bool(data.get("soften")),
            with_audio=bool(data.get("audio")),
            allow_network=ALLOW_NETWORK,
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("socket translate failed")
        emit("translation_error", {"message": str(exc)})
        return

    emit("translation_result", result.as_dict())


@socketio.on("audio_chunk")
def handle_audio_chunk(data):
    """Raw audio, for clients whose browser cannot do speech recognition."""
    data = data or {}
    try:
        result = translate_audio(
            data.get("audio"),
            target_lang=data.get("target_lang") or "en",
            source_lang=data.get("source_lang") or None,
            register_level=_parse_level(data.get("register", AUTO)),
            addressee=data.get("addressee") or None,
            with_audio=bool(data.get("audio_out")),
            allow_network=ALLOW_NETWORK,
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("socket audio failed")
        emit("translation_error", {"message": str(exc)})
        return

    if not result.ok and not result.original_text:
        emit("translation_error", {"message": result.message})
        return
    emit("translation_result", result.as_dict())


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _json_body() -> Dict[str, Any]:
    return request.get_json(silent=True) or {}


def _parse_level(value):
    """Accept 'auto', a slug, a name, or an int; fall back to Auto."""
    if value is None:
        return AUTO
    if isinstance(value, str) and value.strip().lower() == AUTO:
        return AUTO
    try:
        return coerce_level(value)
    except ValueError:
        return AUTO


def main() -> None:
    logging.basicConfig(
        level=logging.DEBUG if DEBUG else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    backend_report_data = backend_report()
    print()
    print("  Setu — formality-aware speech-to-speech translation")
    print(f"  http://{HOST}:{PORT}")
    print()
    print(f"  speech-to-text  : {backend_report_data['stt'] or 'browser (Web Speech API)'}")
    print(f"  translation     : {', '.join(backend_report_data['mt'])}")
    print(f"  text-to-speech  : {backend_report_data['tts'] or 'browser (speechSynthesis)'}")
    print(f"  formality model : {'trained' if backend_report_data['formality_model'] else 'rules + lexical'}")
    print(f"  register tables : {len(TABLES)} languages")
    print(f"  network         : {'enabled' if ALLOW_NETWORK else 'disabled (offline mode)'}")
    print()

    socketio.run(
        app,
        host=HOST,
        port=PORT,
        debug=DEBUG,
        allow_unsafe_werkzeug=True,
    )


if __name__ == "__main__":
    main()
