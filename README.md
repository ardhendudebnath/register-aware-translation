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

## How it fits together

The whole design rests on one decision: **the register layer sits above the
translation engine, not inside it.** Everything else follows from that — the
engine is swappable, re-levelling needs no network, and the layer can be lifted
out and sold to anyone already doing translation.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/architecture-dark.svg">
    <img alt="Setu architecture: the register layer is a single slab spanning all three engine tiers, with the client on top" src="docs/architecture-light.svg" width="820">
  </picture>
</p>

The wide slab is the point. It spans all three engine tiers rather than sitting
inside any of them, so swapping what is underneath changes nothing above it.
Regenerate with `python docs/make_diagrams.py`.

### The three stages

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/pipeline-dark.svg">
    <img alt="The three-stage pipeline: speech in, pre-edit, translate, register post-edit, speech out. The translate stage is outlined as replaceable." src="docs/pipeline-light.svg" width="880">
  </picture>
</p>

Only the middle box is dashed, because it is the only one you would ever swap.
Pre-edit steers the source before the engine sees it; post-edit is where
register is actually applied, and it costs about a millisecond.

**Fallback chain:** cached phrase → on-device model → premium API → free
endpoint → *"I couldn't translate that, here's what I heard."* The user never
sees a dead end.

### The layer that makes it different

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/ladder-dark.svg">
    <img alt="The register ladder as a staircase: the same Bengali sentence at Close, Casual, Polite and Formal, with the top two rungs identical because Bengali uses one form for both." src="docs/ladder-light.svg" width="880">
  </picture>
</p>

A staircase is the honest shape: the levels are ordered and the rise is even.
Where a language does not distinguish two levels the rungs carry the same text —
Bengali uses আপনি for both Polite and Formal, and the diagram says so rather
than inventing a difference.

One symmetric dataset drives all three jobs — **upgrade, downgrade, detect** —
because every rule is the same thing said four ways.

### Module structure

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/modules-dark.svg">
    <img alt="Module structure stacked by dependency: register/ is the widest slab at the bottom with nothing beneath it, then models/, pipeline/ and app.py above." src="docs/modules-light.svg" width="880">
  </picture>
</p>

`register/` is the widest slab and sits at the bottom with nothing under it,
because it depends on nothing at all. That is what lets it run offline in about
a millisecond and be lifted out as a component.

<details>
<summary>The same structure as text</summary>

```mermaid
flowchart TD
    APP["app.py<br/><i>Flask + SocketIO + REST</i>"]

    subgraph PIPE["pipeline/ — orchestration"]
        CORE["core.py<br/>3-stage pipeline<br/>phrasebook"]
        CONV["conversation.py<br/>a register per direction"]
        REL["relationships.py<br/>per-contact memory"]
        LEARN["learner.py<br/>inverted pipeline"]
    end

    subgraph REG["register/ — the IP · zero dependencies"]
        TAB["tables.py<br/>20 rule tables"]
        ENG["engine.py<br/>rewrite · detect · ladder"]
        BOUND["boundaries.py<br/>Indic-safe word edges"]
        GEN["gender.py<br/>FR noun gender"]
        SPK["speaker.py<br/>first-person agreement"]
        SEL["selectors.py<br/>context-sensitive forms"]
    end

    subgraph MOD["models/ — swappable backends"]
        STT["stt.py"]
        LID["language_id.py"]
        CLF["classifier.py"]
        MT2["translator.py"]
        TTS2["tts.py"]
    end

    subgraph EVAL["evaluation/ — proof"]
        MET["metrics.py<br/>register · detection · semantic"]
        GOLD["gold_sets.py"]
    end

    APP --> PIPE
    PIPE --> REG
    PIPE --> MOD
    EVAL --> REG
    ENG --> TAB & BOUND & GEN & SPK & SEL

    style REG fill:#eef2ff,stroke:#3d5bd9,stroke-width:3px
    style ENG fill:#7c9cff,color:#fff
    style MOD fill:#fffaf0,stroke:#b4690e
```

</details>

All four figures are generated, not hand-drawn — `python docs/make_diagrams.py`
rebuilds them in both themes. The language count is read off the tables rather
than typed in, so adding a language cannot leave a diagram quietly claiming the
old number.

---

## What's here

| Path | What it is |
|---|---|
| `register/` | **The register engine.** Rule tables for 20 languages, plus rewrite / detect / ladder, noun gender, speaker agreement. Zero dependencies, works offline, ~1 ms. |
| `pipeline/` | Three-stage pipeline, phrasebook cache, asymmetric conversations, relationship memory, learner mode. |
| `models/` | Swappable backends: STT, language ID, formality classification, MT, TTS. |
| `data_preprocessing/` | Builds train/val/test splits from the FAME-MT corpus. |
| `classifier/` | Fine-tunes a formality classifier on those splits. |
| `evaluation/` | The four metrics that make the claim defensible, and the review pages that make them mean something. |
| `tests/` | 367 tests. |
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

### Coverage

<!-- coverage:begin -->
**20 languages, 1,369 rules.** Thirteen of them are Indian, which is the point: CoCoA-MT gave Hindi a *binary* formality benchmark in 2022 and every other Indian language got nothing at all.

| Code | Language | Levels | Rules | Vocatives | Gold | Second person |
|---|---|:-:|:-:|:-:|:-:|---|
| `bn` | Bengali | 4 | 118 | ✓ | speaker | তুই / তুমি / আপনি |
| `hi` | Hindi | 4 | 123 | ✓ | drafted · high | तू / तुम / आप |
| `mr` | Marathi | 4 | 74 | ✓ | drafted · medium | तू / तुम्ही / आपण |
| `gu` | Gujarati | 3 | 54 | ✓ | drafted · medium | તું / તમે / આપ |
| `pa` | Punjabi | 3 | 49 | ✓ | drafted · medium | ਤੂੰ / ਤੁਸੀਂ |
| `ur` | Urdu | 4 | 88 | ✓ | drafted · medium | تو / تم / آپ |
| `or` | Odia | 4 | 38 | ✓ | drafted · low | ତୁ / ତୁମେ / ଆପଣ |
| `as` | Assamese | 4 | 31 | ✓ | drafted · low | তই / তুমি / আপুনি |
| `ne` | Nepali | 4 | 36 | ✓ | drafted · low | तँ / तिमी / तपाईं / हजुर |
| `ta` | Tamil | 3 | 78 | ✓ | drafted · medium | நீ / நீங்கள் |
| `te` | Telugu | 3 | 109 | ✓ | drafted · medium | నువ్వు / మీరు |
| `kn` | Kannada | 3 | 112 | ✓ | drafted · medium | ನೀನು / ನೀವು |
| `ml` | Malayalam | 3 | 34 | ✓ | drafted · medium | നീ / നിങ്ങൾ / താങ്കൾ |
| `de` | German | 3 | 124 | — | drafted · high | du / Sie |
| `fr` | French | 3 | 39 | — | drafted · high | tu / vous |
| `es` | Spanish | 3 | 66 | — | drafted · high | tú / usted |
| `it` | Italian | 3 | 61 | — | drafted · high | tu / Lei |
| `pt` | Portuguese | 3 | 61 | — | drafted · medium | tu / você / o senhor |
| `ja` | Japanese | 3 | 43 | — | drafted · medium | plain / です・ます / 敬語 |
| `en` | English | 3 | 31 | — | drafted · high | *(no grammatical T/V)* |

**Levels** is how many of the four the language actually realises — the rest fold onto the nearest real one. **Vocatives** marks the languages that require an address term (দাদা, भैया, அண்ணா), which English leaves empty. **Gold** is how much the sentence set behind the numbers has been checked: `speaker` means written by one, and everything marked `drafted` was compiled from reference grammars and is waiting for one — see [REVIEWING.md](REVIEWING.md).

This table is generated. Run `python -m docs.make_coverage_table --write` after changing a table.
<!-- coverage:end -->

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

## Things no other translation product does

### Conversations are asymmetric

Your uncle says তুই to you. You say আপনি back. Both are correct, and neither is
the other's mirror — this is how most Indian conversations across a generation
gap actually work. Every product on the market applies one register to a whole
session and gets this exactly wrong.

```python
from pipeline import Conversation, Participant
from register import AUTO, POLITE

uncle = Participant("uncle", "bn", register=AUTO)               # speaks down
you   = Participant("you", "bn", register=POLITE,               # speaks up
                    addressee="elder_man")

convo = Conversation(uncle, you)
convo.say("uncle", "তুই কোথায় যাস?")
convo.say("you",   "তুমি কেমন আছ?")     # → "কাকু, আপনি কেমন আছেন?"

convo.is_asymmetric()          # True
convo.observed_registers()     # {'uncle': 0, 'you': 1}
```

The vocative — কাকু — is inserted automatically. English has no such slot, so
MT either drops it (sounding abrupt) or emits a stiff "sir" nobody says.

### Register attached to a person

```python
from pipeline import RelationshipBook

book = RelationshipBook()
book.remember("Rahul's father", language="bn",
              register=POLITE, addressee="elder_man")
```

The second conversation needs no configuration. Nobody else has this — not
because it is hard, but because you cannot attach a register to a contact until
register is a first-class object. This data never leaves the device: local
SQLite, no sync, no export endpoint.

### Learner mode — the pipeline run backwards

Duolingo teaches vocabulary and grammar. None of them teach *register*, which
is what actually determines whether a learner sounds rude.

```python
from pipeline import assess

assess("তুই কেমন আছিস?", "bn", "stranger").message
# 'You used Close with someone you have just met. That will sound too
#  familiar — native speakers would use Polite here.'
```

It accepts more than one answer where the language genuinely does. Family
elders are the contested case — high respect *and* high closeness — so both
তুমি and আপনি pass, because insisting on one would teach something false.

### Gender that MT throws away

`votre` carries no gender, so downgrading it has to guess — and every engine
guesses masculine, producing the wrong *ton maison*:

| | |
|---|---|
| `votre maison` → | `ta maison` (feminine noun) |
| `votre livre` → | `ton livre` (masculine noun) |
| `votre amie` → | `ton amie` (feminine, but vowel-initial) |

And in Hindi, Marathi, Punjabi and Gujarati the verb agrees with **who is
speaking**, so MT's masculine default misgenders half its users:

```python
rewrite("मैं काम करता हूँ", "hi", CASUAL, speaker_gender="female").text
# 'मैं काम करती हूँ'
```

Only first-person sentences are touched — Hindi has ordinary nouns ending in
ता (पिता, माता, नेता) and rewriting those would be far worse than leaving a
verb masculine.

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
python -m classifier.train --max-rows 400000 --epochs 2 --batch-size 64
```

### Classify the target, not the source

This is the single decision that matters most for accuracy, and it is easy to
get wrong. FAME-MT's label describes the **target** sentence's register: in
`en-de.formal.tsv` the German target says *Drücken Sie*, and in the informal
file it says *du*. The English source in both is formality-neutral, because
English has no grammatical T/V distinction to mark.

Training on `source_text` therefore asks the model to predict a property its
input does not contain. It can only latch onto weak stylistic correlations, and
it plateaus around 71% no matter how much data you feed it:

| Column | Rows | Epochs | Accuracy | F1 macro |
|---|--:|--:|--:|--:|
| `source_text` | 40k | 1 | 0.706 | 0.706 |
| `target_text` | 40k | 1 | 0.943 | 0.943 |
| `target_text` | 400k | 2 | **0.970** | **0.970** |

`--text-column` defaults to `target_text`. The 400k run scores
precision/recall of 0.971/0.969 formal and 0.968/0.971 informal — balanced,
rather than the lopsided model the old setup produced.

**The classifier is a fallback, not the main event.** For the 20 languages with
a rule table, the register engine reads grammar directly and takes precedence;
the model only answers when no register marker is present at all.

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

Verified on an RTX 5070 Ti Laptop (12 GB, compute 12.0): **934 samples/s** at
batch 64 in bf16 — 400k rows × 2 epochs in about 14 minutes.

> **Note on labels.** The filename is ground truth. Slang detection is recorded
> as a *feature column*, not a label override — overriding is opt-in behind
> `--slang-overrides-label`, because doing it by default is what corrupted the
> previous splits.

---

## Measuring it

Four metrics, tracked separately:

| Metric | Question |
|---|---|
| Register accuracy | Of translations requested at level N, what fraction land at level N? |
| Detection accuracy | When the speaker used আপনি, does Auto report Polite? |
| Semantic preservation | Did the register rewrite break the meaning? |
| Rewrite exactness | Is the output the *exact* sentence a speaker would use? |

Semantic preservation is the one that will bite you — a sentence can be
perfectly Polite and also nonsense, and register accuracy cannot see it.
Exactness is the strictest: it accepts nothing but the expected string, which
is how most of the real bugs in the tables were found.

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

All 20 languages are measured against 1,606 annotated sentences. Detection is
at 100% everywhere; exactness is at 100% in nineteen, and Bengali stops at
98.5% on a syncretism a substitution table cannot resolve — খাও is both the
তুমি present and the তুমি imperative, and no amount of rules separates them.

### One number that is not self-referential

Everything above compares the engine to sentence sets written alongside it.
FAME-MT does not: a formality-annotated corpus built by other people for other
reasons, and large enough that no amount of overfitting to a hand-written gold
set can flatter it.

```bash
python -m evaluation.external
```

```
de   agreement  99.5%   coverage  88.4%
fr   agreement  99.1%   coverage  83.9%
es   agreement  96.9%   coverage  77.6%
it   agreement  91.6%   coverage  65.5%
pt   agreement  90.0%   coverage  80.4%
en   agreement  66.1%   coverage   9.6%

overall 95.0% over 30,438 sentences
```

**Coverage** is how often a sentence carries a readable register marker at
all; the corpus labels every row regardless, so abstaining is counted apart
from being wrong rather than folded in as failure.

Two things this says plainly. **English is weak** — it reads a tenth of what it
is given and agrees about two thirds of the time, which is near enough to
chance to be worth stating rather than averaging away. That is what "no
grammatical T/V distinction" costs. And **FAME-MT covers six languages, none of
them Indian.** Not Bengali, Hindi, Marathi, Gujarati, Punjabi, Urdu, Odia,
Assamese, Nepali, Tamil, Telugu, Kannada or Malayalam. There is no external
corpus to check those against, which is the thesis of this project restated as
a missing file — and why the review pages below still matter.

### Read those numbers carefully

They measure agreement between the engine and sentence sets **largely written
by someone who does not speak the languages**. The harness cannot tell the
difference: a gold row that is wrong in the same direction as the table scores
a confident 100%.

What it *can* catch is inconsistency, and it has — rows asking the detector to
tell two identical strings apart, a vocative no speaker would say, rows filed
by the situation they belong to rather than by anything in the sentence. Each
surfaced by colliding with the engine. A row that is merely wrong collides with
nothing.

So the sets carry an honest confidence label, and every row says
`status: draft`:

| Confidence | Languages |
|---|---|
| low | Assamese, Nepali, Odia |
| medium | Gujarati, Japanese, Kannada, Malayalam, Marathi, Portuguese, Punjabi, Tamil, Telugu, Urdu |
| high | English, French, German, Hindi, Italian, Spanish |
| hand-written by a speaker | Bengali |

### Getting them reviewed

**<https://ardhendudebnath.github.io/register-aware-translation/>** — the
sentence sets, published as pages a speaker can check in a browser. No
account, nothing to install.

```bash
python -m evaluation.review
```

Regenerates those pages into `docs/` — no server, no dependencies. Run it
after changing a gold set. Sentences are grouped into
*ladders* rather than listed as rows, because "is this the right step up from
that?" is answerable and "is this right in the abstract?" is not. Bengali's 494
rows become 198 questions; most languages land between 22 and 37. The index is
ordered worst-first, and each page opens with that language's flagged
ambiguities.

**[REVIEWING.md](REVIEWING.md) is written for a speaker to be handed
directly** — no programming knowledge assumed.

This is the highest-leverage work left. CoCoA-MT gave Hindi a *binary*
formality benchmark in 2022; Bengali — 228 million speakers, three grammatical
registers — has nothing, and nor does Tamil, Telugu, Kannada, Malayalam,
Gujarati, Marathi, Punjabi, Odia or Assamese. The sentences now exist. What
they need is speakers, and it is the one asset a well-funded competitor cannot
shortcut.

---

## Tests

```bash
python -m pytest tests/ -q
```

367 tests covering the rule tables, round-trip stability, third-person safety,
Indic boundary handling, French noun gender, speaker agreement, asymmetric
conversations, learner feedback, the slang-detection regressions, and the
pipeline with networking disabled.

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
| `POST /api/conversation` | Start a two-party conversation with a register per direction. |
| `POST /api/conversation/<id>/say` | One turn, translated at the *speaker's* register. |
| `POST /api/learner/assess` | Judge a learner's sentence against who they are addressing. |
| `GET/POST /api/relationships` | Per-contact register memory (on-device). |

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
