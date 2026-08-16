"""
Gold sets — annotated sentences with the register a native speaker says they
are in.

Blueprint 9: build a formality test set, 200 sentence pairs per language, and
run it as a regression suite on every rule-table change. Blueprint 13.2 #7 goes
further: publicly releasing a multi-level Indic register benchmark is the single
highest-leverage asset here, because CoCoA-MT gave Hindi a *binary* benchmark in
2022 and Bengali — 228 million speakers, three grammatical registers — has
nothing at all.

This module is the seed and the format. Sets live in ``data/gold/<lang>.jsonl``,
one JSON object per line::

    {"text": "আপনি কেমন আছেন?", "level": 2, "note": "greeting, stranger"}

The built-in set below is deliberately small and is *not* a benchmark. It exists
so the harness has something to run against on a fresh checkout. The real work
is 500 Bengali sentences annotated by hand — which per the blueprint you are
uniquely placed to produce, and which is the asset nobody can copy.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from register import CASUAL, CLOSE, FORMAL, POLITE
from utils.helpers import PROJECT_ROOT

from .metrics import Case

__all__ = ["GOLD_DIR", "load_gold_set", "available_gold_sets", "SEED_CASES"]

GOLD_DIR = PROJECT_ROOT / "data" / "gold"


#: A starter set. Enough to exercise the harness; nowhere near enough to claim
#: a number. Grow ``data/gold/bn.jsonl`` to 500 and this becomes meaningful.
SEED_CASES: List[Case] = [
    # Bengali — three genuine registers
    Case("bn", "তুই কোথায় যাস?", CLOSE, note="to a younger sibling"),
    Case("bn", "তুই কি করছিস?", CLOSE),
    Case("bn", "তুমি কি করছ?", CASUAL, note="to a friend"),
    Case("bn", "তুমি কেমন আছ?", CASUAL),
    Case("bn", "তুমি কোথায় যাও?", CASUAL),
    Case("bn", "আপনি কেমন আছেন?", POLITE, note="to a stranger"),
    Case("bn", "আপনি কি আমাকে সাহায্য করতে পারেন?", POLITE),
    Case("bn", "আপনি কোথায় যান?", POLITE),

    # Hindi
    Case("hi", "तू क्या करता है?", CLOSE),
    Case("hi", "तुम क्या करते हो?", CASUAL),
    Case("hi", "तुम कैसे हो?", CASUAL),
    Case("hi", "आप कैसे हैं?", POLITE),
    Case("hi", "आप क्या करते हैं?", POLITE),

    # German — two pronoun levels
    Case("de", "Kannst du mir helfen?", CASUAL),
    Case("de", "Wo wohnst du?", CASUAL),
    Case("de", "Können Sie mir helfen?", POLITE),
    Case("de", "Wo wohnen Sie?", POLITE),

    # French
    Case("fr", "Tu es très gentil.", CASUAL),
    Case("fr", "Peux-tu m'aider ?", CASUAL),
    Case("fr", "Vous êtes très gentil.", POLITE),
    Case("fr", "Pouvez-vous m'aider ?", POLITE),

    # Spanish / Italian
    Case("es", "¿Puedes darme tu libro?", CASUAL),
    Case("es", "¿Puede darme su libro?", POLITE),
    Case("it", "Puoi darmi il tuo libro?", CASUAL),
    Case("it", "Può darmi il Suo libro?", POLITE),

    # Tamil
    Case("ta", "நீ எப்படி இருக்கிறாய்?", CASUAL),
    Case("ta", "நீங்கள் எப்படி இருக்கிறீர்கள்?", POLITE),

    # Japanese — three levels
    Case("ja", "これをする。", CASUAL),
    Case("ja", "これをします。", POLITE),
    Case("ja", "これをいたします。", FORMAL),

    # Marathi
    Case("mr", "तू काय करतोस?", CASUAL),
    Case("mr", "तुम्ही कसे आहात?", POLITE),
    Case("mr", "आपण कसे आहात?", FORMAL),

    # Gujarati — તું / તમે / આપ, so તમે is the polite form, not the casual one
    Case("gu", "તું શું કરે છે?", CASUAL),
    Case("gu", "તમે કેમ છો?", POLITE),
    Case("gu", "આપ કેમ છો?", FORMAL),

    # Punjabi
    Case("pa", "ਤੂੰ ਕੀ ਕਰਦਾ ਹੈਂ?", CASUAL),
    Case("pa", "ਤੁਸੀਂ ਕਿਵੇਂ ਹੋ?", POLITE),

    # Telugu
    Case("te", "నువ్వు ఎలా ఉన్నావు?", CASUAL),
    Case("te", "మీరు ఎలా ఉన్నారు?", POLITE),
    Case("te", "మీరు చెప్పండి", POLITE),

    # Kannada
    Case("kn", "ನೀನು ಹೇಗಿದ್ದೀಯ?", CASUAL),
    Case("kn", "ನೀವು ಹೇಗಿದ್ದೀರಿ?", POLITE),
    Case("kn", "ನೀವು ಹೇಳಿ", POLITE),

    # Malayalam
    Case("ml", "നീ എങ്ങനെ ഉണ്ട്?", CASUAL),
    Case("ml", "നിങ്ങൾ എങ്ങനെ ഉണ്ട്?", POLITE),
    Case("ml", "താങ്കൾ എങ്ങനെ ഉണ്ട്?", FORMAL),

    # Portuguese — tu / você / o senhor
    Case("pt", "Tu és muito simpático.", CLOSE),
    Case("pt", "Você é muito simpático.", CASUAL),
    Case("pt", "O senhor é muito simpático.", POLITE),

    # English — weak register, but the contrast is real
    Case("en", "hey, can you gimme a hand?", CASUAL),
    Case("en", "hello, could you help me?", POLITE),
    Case("en", "good day, could you kindly assist me?", FORMAL),

    # ---- blueprint phase 3: the scheduled languages with nothing built ----
    # Compiled from standard grammars, NOT yet reviewed by a native speaker.
    # Flagged here so nobody mistakes these for annotated gold data.

    # Urdu — تو / تم / آپ
    Case("ur", "تو کیسے ہے", CLOSE, note="unverified"),
    Case("ur", "تم کیسے ہو", CASUAL, note="unverified"),
    Case("ur", "آپ کیسے ہیں", POLITE, note="unverified"),

    # Odia — ତୁ / ତୁମେ / ଆପଣ
    Case("or", "ତୁ କେମିତି ଅଛୁ", CLOSE, note="unverified"),
    Case("or", "ତୁମେ କେମିତି ଅଛ", CASUAL, note="unverified"),
    Case("or", "ଆପଣ କେମିତି ଅଛନ୍ତି", POLITE, note="unverified"),

    # Assamese — তই / তুমি / আপুনি
    Case("as", "তই কেনে আছ", CLOSE, note="unverified"),
    Case("as", "তুমি কেনে আছা", CASUAL, note="unverified"),
    Case("as", "আপুনি কেনে আছে", POLITE, note="unverified"),

    # Nepali — तँ / तिमी / तपाईं
    Case("ne", "तँ कस्तो होस्", CLOSE, note="unverified"),
    Case("ne", "तिमी कस्तो हौ", CASUAL, note="unverified"),
    Case("ne", "तपाईं कस्तो हुनुहुन्छ", POLITE, note="unverified"),
]


def available_gold_sets() -> List[str]:
    """Language codes that have a gold set file on disk."""
    if not GOLD_DIR.exists():
        return []
    return sorted(p.stem for p in GOLD_DIR.glob("*.jsonl"))


def load_gold_set(language: str) -> List[Case]:
    """
    Load ``data/gold/<language>.jsonl``, falling back to the seed cases for that
    language when no file exists yet.
    """
    path = GOLD_DIR / f"{language}.jsonl"
    if not path.exists():
        return [c for c in SEED_CASES if c.language == language]

    cases: List[Case] = []
    with path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, 1):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no} is not valid JSON: {exc}") from None

            missing = {"text", "level"} - set(row)
            if missing:
                raise ValueError(f"{path}:{line_no} is missing {sorted(missing)}")

            # level may be null: those rows carry no second-person marker at
            # all, and exist to check that detection abstains rather than
            # guessing. A detector that invents a level for them would make
            # Auto mode mirror noise.
            raw_level = row["level"]
            cases.append(
                Case(
                    language=row.get("language", language),
                    text=row["text"],
                    level=None if raw_level is None else int(raw_level),
                    expected={int(k): v for k, v in (row.get("expected") or {}).items()},
                    note=row.get("note", ""),
                    domain=row.get("domain", ""),
                    construction=row.get("construction", ""),
                    status=row.get("status", "draft"),
                    case_id=row.get("id", f"{language}-{line_no:04d}"),
                )
            )
    return cases


def write_template(language: str, overwrite: bool = False) -> Path:
    """
    Write a starter ``data/gold/<lang>.jsonl`` from the seed cases, so a native
    speaker has the right shape to fill in rather than a blank file.
    """
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    path = GOLD_DIR / f"{language}.jsonl"
    if path.exists() and not overwrite:
        return path

    rows = [c for c in SEED_CASES if c.language == language]
    with path.open("w", encoding="utf-8") as fh:
        for case in rows:
            fh.write(json.dumps(
                {"text": case.text, "level": case.level, "note": case.note},
                ensure_ascii=False,
            ) + "\n")
    return path
