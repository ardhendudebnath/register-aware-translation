# Gold set file format

One file per language, `<code>.jsonl`, UTF-8 without a BOM. Every line is a
complete JSON object; blank lines and lines beginning `//` are comments and
must be skipped. Loading needs nothing from this repository:

```python
import json

with open("hi.jsonl", encoding="utf-8") as fh:
    rows = [json.loads(line) for line in fh
            if line.strip() and not line.startswith("//")]
```

## Fields

| Field | Type | Always present | What it is |
|---|---|---|---|
| `text` | string | yes | The sentence. Native script, with its own punctuation (`।`, `۔`, `。`). |
| `level` | integer 0–3, or `null` | yes | The register the sentence is in. `null` means it carries no second-person marker at all. |
| `expected` | object | no | The same sentence written at other levels: `{"0": "…", "1": "…"}`. Keys are strings. |
| `language` | string | yes | ISO 639-1 code, matching the filename. |
| `id` | string | yes | `<language>-<4 digits>`, e.g. `hi-0058`. Stable within a release, not across releases. |
| `group` | string | yes | What the row is testing: `pronouns`, `imperative`, `hard`, `negative`… |
| `construction` | string | yes | The grammatical construction, in the project's own shorthand: `v.imp.ana`, `pron.gen`. |
| `domain` | string | yes | Where it would be said: `medical`, `transit`, `shopping`, `family`… `n/a` when the row is not domain-specific. |
| `context` | string | yes | Who is being addressed: `stranger`, `shopkeeper`, `grandfather`. `n/a` where it does not apply. |
| `note` | string | yes | Free text from the drafter. On `hard` rows this says what the ambiguity is. |
| `status` | string | yes | `draft` until a native speaker has checked the row, then `verified`. |
| `confidence` | string | no | The drafter's own confidence in the whole set: `low`, `medium`, `high`. Absent where the set was hand-built rather than compiled. |

## The four levels

| Value | Name | Bengali | Hindi | German |
|---|---|---|---|---|
| 0 | Close | তুই | तू | du |
| 1 | Casual | তুমি | तुम | du |
| 2 | Polite | আপনি | आप | Sie |
| 3 | Formal | আপনি | आप | Sie |

Not every language fills all four slots. German has two forms and Tamil two;
where a language does not distinguish two levels, both map to the same surface
form, and `expected` simply repeats it. A level missing from `expected`
altogether means the row does not cover it — usually because the contrast
being tested does not extend that far.

`"level": null` is not missing data. Those rows exist to check that a detector
**abstains** instead of guessing: a sentence with no second-person marker has
no register to read, and a system that invents one for it will mirror noise.

## Rows, ladders and groups

Rows that share an `expected` map are one **ladder** — the same sentence at
each level — and are the unit a reviewer judges. A ladder is easier to check
than an isolated sentence, because the question becomes "is this the right step
up from that?" rather than "is this right in the abstract".

Two groups are not ladders and mean something specific:

- **`negative`** — the `"level": null` rows above.
- **`hard`** — deliberate ambiguities. The drafter already knew these were
  uncertain: a bare imperative with no pronoun to lean on, a form that is both
  present tense and imperative. They are worth more than the bulk of the set,
  and a system scoring well everywhere else while failing here has probably
  learnt a surface cue rather than the register.

## What the format does not carry

No speaker metadata, no audio, no provenance per row beyond `note`, and no
inter-annotator agreement — because as of this version no row has been
annotated by anybody other than its drafter. See `DATASHEET.md`, which is
blunter about this than a schema can be.
