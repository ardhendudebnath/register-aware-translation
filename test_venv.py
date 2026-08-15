#!/usr/bin/env python
"""
Environment check.

Reports which optional backends are present, so a fresh checkout can tell at a
glance what will work and what will fall back. Nothing here is required — every
stage of the pipeline degrades rather than breaking when a dependency is absent.

    python test_venv.py
"""

from __future__ import annotations

import importlib
import sys

CORE = [
    ("flask", "web server"),
    ("flask_socketio", "streaming transport"),
    ("pandas", "data preparation"),
    ("sklearn", "split helpers and metrics"),
    ("pytest", "tests"),
]

OPTIONAL = [
    ("langdetect", "language ID for Latin/Devanagari", "stop-word vote"),
    ("gtts", "server-side speech synthesis", "browser speechSynthesis"),
    ("faster_whisper", "server-side speech recognition", "browser Web Speech API"),
    ("whisper", "server-side speech recognition (reference)", "browser Web Speech API"),
    ("torch", "classifier training", "register engine + lexical scoring"),
    ("transformers", "local MT and trained classifier", "public MT endpoint"),
    ("datasets", "training data loader", "n/a"),
    ("sentence_transformers", "semantic-preservation metric", "character similarity"),
]


def check(name: str) -> bool:
    try:
        importlib.import_module(name)
        return True
    except Exception:
        return False


def main() -> int:
    print(f"Python {sys.version.split()[0]}")
    print(f"        {sys.executable}\n")

    missing_core = []
    print("Core")
    for module, purpose in CORE:
        ok = check(module)
        print(f"  [{'x' if ok else ' '}] {module:<24} {purpose}")
        if not ok:
            missing_core.append(module)

    print("\nOptional")
    for module, purpose, fallback in OPTIONAL:
        ok = check(module)
        note = purpose if ok else f"{purpose}  →  falls back to {fallback}"
        print(f"  [{'x' if ok else ' '}] {module:<24} {note}")

    print()
    try:
        from register import TABLES, rewrite

        sample = rewrite("তুমি কি করছ?", "bn", 2).text
        print(f"Register engine  : OK — {len(TABLES)} tables")
        print(f"                   তুমি কি করছ?  ->  {sample}")
    except Exception as exc:
        print(f"Register engine  : FAILED — {exc}")
        return 1

    if missing_core:
        print(f"\nMissing core packages: {', '.join(missing_core)}")
        print("    pip install -r requirements.txt")
        return 1

    print("\nEnvironment OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
