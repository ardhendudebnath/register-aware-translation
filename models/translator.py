"""
Machine translation, with the register layer kept strictly on top of it.

Setu is engine-agnostic by design (blueprint 4): this module is the swappable
box, and nothing in it knows what a register is. It walks a fallback chain and
reports which link answered, so the UI can be honest about where a translation
came from:

    phrasebook cache  ->  local model  ->  public endpoint  ->  failure

The chain never dead-ends in silence. A tourist standing in a market does not
care *why* it failed, so the caller always gets a result object it can render.

The previous implementation returned f"Formal translation of: {text}".
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Optional, Tuple

from utils.helpers import normalise_text

__all__ = ["Translation", "translate", "available_backends", "MTError"]

#: Public keyless endpoint. Undocumented and rate-limited — fine for a free
#: tier and a prototype, not something to bill a customer against (blueprint 12).
_PUBLIC_ENDPOINT = "https://translate.googleapis.com/translate_a/single"

_TIMEOUT_S = float(os.environ.get("SETU_MT_TIMEOUT", "6"))
_USER_AGENT = "Setu/0.2 (+https://github.com/) Python-urllib"


class MTError(RuntimeError):
    """Raised only by callers that opt into strict mode."""


@dataclass
class Translation:
    text: str
    source_language: str
    target_language: str
    engine: str
    ok: bool = True
    message: str = ""
    cached: bool = False

    def as_dict(self) -> dict:
        return {
            "text": self.text,
            "source_language": self.source_language,
            "target_language": self.target_language,
            "engine": self.engine,
            "ok": self.ok,
            "message": self.message,
            "cached": self.cached,
        }


def available_backends() -> Tuple[str, ...]:
    """Which MT backends this install can reach, best first."""
    out = []
    try:
        import transformers  # noqa: F401
        out.append("local-marian")
    except ImportError:
        pass
    out.append("public-endpoint")
    return tuple(out)


def translate(
    text: str,
    source_lang: str,
    target_lang: str,
    *,
    allow_network: bool = True,
    prefer_local: bool = True,
) -> Translation:
    """
    Translate ``text`` from ``source_lang`` to ``target_lang``.

    Note the signature change: the old one took ``formality_score`` and baked
    politeness into the translation itself. Register is applied *after* this
    step by :mod:`register`, which is what lets the same output be re-levelled
    offline without another round trip.
    """
    source_lang = _norm(source_lang)
    target_lang = _norm(target_lang)

    if not isinstance(text, str) or not text.strip():
        return Translation("", source_lang, target_lang, "noop")

    if source_lang and source_lang == target_lang:
        return Translation(text, source_lang, target_lang, "identity")

    errors = []

    if prefer_local:
        local = _translate_local(text, source_lang, target_lang)
        if local is not None:
            return local
        errors.append("no local model for this pair")

    if allow_network:
        try:
            return _translate_public(text, source_lang, target_lang)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"public endpoint: {exc}")
    else:
        errors.append("network disabled")

    if not prefer_local:
        local = _translate_local(text, source_lang, target_lang)
        if local is not None:
            return local

    # Hand back the source rather than nothing, flagged as untranslated, so the
    # UI can show "here's what I heard" instead of an empty box.
    return Translation(
        text=text,
        source_language=source_lang,
        target_language=target_lang,
        engine="none",
        ok=False,
        message="Could not translate: " + "; ".join(errors),
    )


# --------------------------------------------------------------------------
# Backends
# --------------------------------------------------------------------------


def _translate_local(text: str, source: str, target: str) -> Optional[Translation]:
    """Helsinki-NLP MarianMT, if transformers is installed and a pair exists."""
    pipe = _load_marian(source, target)
    if pipe is None:
        return None
    try:
        out = pipe(text, max_length=512)
        translated = out[0]["translation_text"]
    except Exception:
        return None
    return Translation(translated, source, target, "local-marian")


@lru_cache(maxsize=8)
def _load_marian(source: str, target: str):
    """
    Cached MarianMT pipeline for one direction.

    Returns None — never raises — when transformers is absent or the model for
    this pair does not exist, because the caller has a fallback.
    """
    try:
        from transformers import pipeline
    except ImportError:
        return None

    model_name = f"Helsinki-NLP/opus-mt-{source}-{target}"
    try:
        return pipeline("translation", model=model_name)
    except Exception:
        return None


def _translate_public(text: str, source: str, target: str) -> Translation:
    """
    Keyless public endpoint.

    Undocumented, so treat any shape change as a failure rather than trusting
    the parse. See blueprint 12: move to Sarvam/Bhashini before charging anyone.
    """
    params = {
        "client": "gtx",
        "sl": source or "auto",
        "tl": target,
        "dt": "t",
        "q": text,
    }
    url = f"{_PUBLIC_ENDPOINT}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})

    with urllib.request.urlopen(request, timeout=_TIMEOUT_S) as response:
        raw = response.read().decode("utf-8", errors="replace")

    try:
        payload = json.loads(raw)
        chunks = payload[0]
        translated = "".join(chunk[0] for chunk in chunks if chunk and chunk[0])
        detected = payload[2] if len(payload) > 2 and isinstance(payload[2], str) else source
    except (ValueError, IndexError, TypeError) as exc:
        raise MTError(f"unexpected response shape ({exc})") from None

    if not translated.strip():
        raise MTError("empty translation")

    return Translation(
        text=translated,
        source_language=_norm(detected) or source,
        target_language=target,
        engine="public-endpoint",
    )


def _norm(code) -> str:
    if not isinstance(code, str):
        return ""
    return code.strip().lower().replace("_", "-").split("-")[0]
