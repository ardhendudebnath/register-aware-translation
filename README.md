# Setu — Real-Time Formality-Aware Speech-to-Speech Translation

Every speech translator answers *"what did they say?"* None of them answer
*"how did they say it — and how should I say it back?"*

In Bengali, saying **তুই** to your future father-in-law is an insult. Saying
**আপনি** to your best friend is cold. Hindi has तू / तुम / आप, Tamil நீ / நீங்கள்,
German du / Sie, French tu / vous. General-purpose engines collapse all of this
into one arbitrary choice, and for Indic languages they usually pick the
*informal* form — so a tourist asking an elderly shopkeeper for directions comes
out sounding like they are talking to a child.

**Setu treats register as a first-class control, not a side effect.** You get a
dial. The machine reads the register the speaker used and can mirror it. Every
translation shows which register it landed in and exactly what it changed.

---

## Quick start

```bash
python -m venv .venv
```

```bash
.venv\Scripts\activate
```

```bash
pip install -r requirements.txt
```

```bash
python app.py
```

Then open <http://localhost:5000>. Speech in and speech out use the browser's
own APIs — no API key, no cost.

---

## What's here

| Path | What it is |
|---|---|
| `register/` | **The register engine.** Rule tables for 16 languages, plus rewrite / detect / ladder. Zero dependencies, works offline, ~1 ms. |
| `pipeline/` | The three-stage pipeline: pre-edit → translate → post-edit, with the phrasebook cache. |
| `models/` | Swappable backends: STT, language ID, formality classification, MT, TTS. |
| `data_preprocessing/` | Builds train/val/test splits from the FAME-MT corpus. |
| `classifier/` | Fine-tunes a formality classifier on those splits. |
| `evaluation/` | The three metrics that make the claim defensible. |
| `tests/` | 207 tests. |
| `app.py` | Flask + SocketIO server and REST API. |

---

## The register model

Four levels on one scale:

| Level | Bengali | Hindi | Tamil | German | Japanese |
|---|---|---|---|---|---|
| 0 Close | তুই | तू | நீ | du | plain |
| 1 Casual | তুমি | तुम | நீ | du | plain |
| 2 Polite | আপনি | आप | நீங்கள் | Sie | です・ます |
| 3 Formal | আপনি | आप | நீங்கள் | Sie | 敬語 |

Not every language fills all four slots. Each table carries a `canon` map that
folds a requested level onto the nearest one the language actually realises, so
German `du` reports as *Casual*, not *Close*.

Every rule is a **4-tuple of equivalent surface forms**, one per level. Because
the table is symmetric, one dataset drives three jobs — upgrading, downgrading,
and detection:

```python
from register import rewrite, detect, ladder, POLITE, CLOSE

rewrite("তুমি কি করছ?", "bn", POLITE).text
# 'আপনি কি করছেন?'

detect("আপনি কেমন আছেন?", "bn").level
# 2  (Polite)

for level, result in ladder("তুমি কি করছ?", "bn").items():
    print(result.text)
# তুই কি করছিস?  /  তুমি কি করছ?  /  আপনি কি করছেন?  /  আপনি কি করছেন?
```

Adding a language means adding a table, not writing code.

### Why post-editing rather than prompting an LLM to "be formal"

It is free, instant, offline-capable and *auditable* — you can show the user
exactly what changed. An LLM prompt gives none of those four properties and will
silently drift.

```python
result = rewrite("Können Sie mir Ihr Buch geben?", "de", CLOSE)
result.text                      # 'Kannst du mir dein Buch geben?'
[e.describe() for e in result.edits]
# ['Können Sie → Kannst du  (clause.koennen.inv)', 'Ihr → dein  (poss.nom.m)']
```

### Handling the hard parts

The tables carry contextual guards, because several languages spell different
things the same way:

- German `Sie sind` is *you*, `Sie ist` is *she* — only the verb tells them apart.
- German `Ich sehe Sie` is accusative (→ `dich`), not nominative (→ `du`).
- French `vous êtes` is a subject, `je vous vois` an object clitic, `pour vous`
  tonic — three different targets, decided by the left context.
- Italian `ha` is both polite *you have* and *he/she has*.
- Gujarati `આપ` is both the formal pronoun *you* and the imperative *give!*
- Bengali spells *you say* and *say!* identically as `বলো`.

Pronouns and verbs move together, so `Sie sind sehr nett` becomes
`Du bist sehr nett` and never `Du sind sehr nett`.

**Known limitation:** Italian sentence-initial `Lei` is irreducibly ambiguous —
polite *you* and *she* both capitalise there and both take third-person verbs.
The engine reads it as polite. Mid-sentence casing is handled correctly.

---

## Offline

The register layer is pure client-side string processing, which gives it a
property no engine-integrated approach has: **a phrase cached at Polite can be
re-rendered at Formal with no network at all.**

- A service worker caches the app shell, so the app opens with no connection.
- Every translation is written to a phrasebook keyed by source → target → text,
  *not* by register — so one cached MT output serves all four levels.
- Repeats are free, which also makes the online experience faster.

```bash
SETU_ALLOW_NETWORK=0 python app.py
```

---

## Preparing data and training

The corpus is FAME-MT: parallel formal/informal pairs across 15 European
languages, under `data/dataset/`.

```bash
python -m data_preprocessing.build_splits
```

Streams ~11.2M rows and writes `data/splits/{train,val,test}.tsv` with a header.
Split assignment is a stable hash of the row, so it needs no shuffle buffer and
re-runs produce byte-identical splits. Rows then pass through a bounded shuffle
buffer on the way out, so any *prefix* of the output is a fair mix — without it
the head of `train.tsv` is one language pair and one class, and `--max-rows`
cannot train at all.

```bash
python -m data_preprocessing.build_splits --max-rows-per-file 5000
```

Then, with the training extras installed:

```bash
pip install -r requirements-train.txt
```

```bash
python -m classifier.train --max-rows 200000 --epochs 2
```

The device is configured from the card that is actually present: bf16 where
supported (same exponent range as fp32, so no loss scaling and no silent
overflow to NaN partway through a long run), TF32 matmul, and a batch size
sized to available VRAM.

**On a new GPU, check the wheel first.** A PyTorch build only ships kernels for
the architectures it was compiled for, and `torch.cuda.is_available()` returns
True on a card it cannot actually run — you get *"no kernel image is available
for execution on the device"* at the first forward pass, possibly an hour in.
The script checks the architecture up front and refuses to start, printing the
fix. For Blackwell (RTX 50-series, `sm_120`) that is:

```bash
pip install --force-reinstall torch --index-url https://download.pytorch.org/whl/cu128
```

Verified on an RTX 5070 Ti Laptop (12 GB, compute 12.0): 368 samples/s at
batch 32, bf16.

> **Note on labels.** The filename is ground truth. Slang detection is recorded
> as a *feature column*, not a label override — overriding is opt-in behind
> `--slang-overrides-label`, because doing it by default is what corrupted the
> previous splits.

---

## Measuring it

Three metrics, tracked separately:

| Metric | Question |
|---|---|
| Register accuracy | Of translations requested at level N, what fraction land at level N? |
| Detection accuracy | When the speaker used আপনি, does Auto report Polite? |
| Semantic preservation | Did the register rewrite break the meaning? |

The third is the one that will bite you — a sentence can be perfectly Polite and
also nonsense, and the first two metrics cannot see it.

```bash
python -m evaluation.run
```

```bash
python -m evaluation.run --lang bn --verbose --fail-under 0.9
```

Gold sets live in `data/gold/<lang>.jsonl`, one JSON object per line:

```json
{"text": "আপনি কেমন আছেন?", "level": 2, "note": "greeting, stranger"}
```

```bash
python -m evaluation.run --write-template bn
```

The built-in seed cases are enough to exercise the harness and **are not a
benchmark**. Eight of the sixteen tables have no gold data at all, and the
harness says so rather than reporting a flattering number over nothing.

---

## Tests

```bash
python -m pytest tests/ -q
```

207 tests covering the rule tables, round-trip stability, third-person safety,
Indic boundary handling, the slang-detection regressions, and the pipeline with
networking disabled.

---

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `SETU_HOST` | `127.0.0.1` | Bind address |
| `SETU_PORT` | `5000` | Port |
| `SETU_DEBUG` | off | Reloader and verbose errors |
| `SETU_ALLOW_NETWORK` | `1` | Set `0` to forbid outbound calls |
| `SETU_WHISPER_MODEL` | `base` | Whisper size when server-side ASR is installed |
| `SETU_MT_TIMEOUT` | `6` | Seconds before the MT endpoint is abandoned |

## API

| Endpoint | Purpose |
|---|---|
| `POST /api/translate` | Full pipeline. Returns text, register, edits, ladder, timings. |
| `POST /api/relevel` | Re-render existing text at another register. No MT call. |
| `POST /api/detect` | Read the register of a sentence. |
| `GET /api/languages` | Tables, levels, rule counts, address terms. |
| `GET /api/health` | Which backends are actually available. |

```bash
curl -s localhost:5000/api/translate -H 'Content-Type: application/json' -d '{"text":"Can you give me your book?","source_lang":"en","target_lang":"bn","register":"polite"}'
```

---

## Caveats worth knowing

- **The keyless MT endpoint is undocumented.** Fine for a prototype and a free
  tier; it can rate-limit or change shape without notice. Move to Sarvam or
  Bhashini before charging anyone.
- **iOS Safari speech recognition is weaker than Chrome's.** You will likely need
  to route ASR through a cloud API there. Budget for it now.
- **Register is culturally contested.** Two native speakers will disagree about
  whether a sentence is Polite or Formal, and regional variation is real
  (Kolkata vs Dhaka Bengali). The dial exists precisely because there is no
  single correct answer.

---

*Setu (সেতু) — "bridge." A bridge carries you across, but it also decides how
you arrive.*
