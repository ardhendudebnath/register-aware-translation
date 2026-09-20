# Datasheet — Setu register sets

Following *Datasheets for Datasets* (Gebru et al., 2021). The counts below are
generated from the data by `python -m evaluation.release --refresh-datasheet`,
so they cannot drift from what is actually in the files.

> **Read this first.** No row in this dataset has been checked by a native
> speaker. Every sentence was written by its drafter and verified by nobody.
> That is not a caveat at the bottom of a page; it is the single most important
> fact about this data, and it is why nothing here is called a benchmark.

---

## Motivation

**Why was it created?** Bengali has around 228 million speakers and three
grammatical second-person registers, and no register dataset at all. The same
is true of Tamil, Telugu, Kannada, Malayalam, Gujarati, Marathi, Punjabi, Odia
and Assamese. What exists — CoCoA-MT (2022), FAME-MT — is binary
(formal/informal) and covers Hindi at best among Indian languages. A binary
label cannot represent a language with তুই / তুমি / আপনি, because the middle
term is not a midpoint: it is the form you use with a friend, while তুই is for
intimacy or contempt and আপনি for distance or respect.

These sets were built to evaluate this project's register engine. Releasing
them is a separate decision, made because the gap above is real and the cost of
publishing is one afternoon.

**Who created it?** Ardhendu Debnath, working with Claude (Anthropic's AI
assistant) as part of building the Setu translation system. Unfunded, no
institutional affiliation.

---

## Composition

**What do the instances represent?** Single sentences of everyday speech —
things said in a shop, a clinic, a station, at home — each labelled with the
politeness level it is in, and most of them paired with the same sentence
written at the other levels.

<!-- counts:begin -->
| Language | Rows | Ladders | Unmarked | Hard | Drafter confidence | Reviewed |
|---|---:|---:|---:|---:|---|---:|
| Assamese (`as`) | 44 | 11 | 6 | 3 | low | 0 |
| Bengali (`bn`) | 494 | 148 | 20 | 16 | unrated | 0 |
| English (`en`) | 44 | 10 | 7 | 4 | high | 0 |
| French (`fr`) | 56 | 19 | 9 | 6 | high | 0 |
| German (`de`) | 55 | 19 | 9 | 6 | high | 0 |
| Gujarati (`gu`) | 52 | 13 | 7 | 3 | medium | 0 |
| Hindi (`hi`) | 249 | 70 | 17 | 12 | high | 0 |
| Italian (`it`) | 36 | 11 | 8 | 4 | high | 0 |
| Japanese (`ja`) | 41 | 9 | 2 | 9 | medium | 0 |
| Kannada (`kn`) | 39 | 13 | 7 | 4 | medium | 0 |
| Malayalam (`ml`) | 51 | 12 | 7 | 5 | medium | 0 |
| Marathi (`mr`) | 67 | 19 | 9 | 4 | medium | 0 |
| Nepali (`ne`) | 45 | 11 | 6 | 3 | low | 0 |
| Odia (`or`) | 44 | 11 | 6 | 3 | low | 0 |
| Portuguese (`pt`) | 43 | 10 | 7 | 3 | medium | 0 |
| Punjabi (`pa`) | 36 | 12 | 6 | 3 | medium | 0 |
| Spanish (`es`) | 45 | 15 | 8 | 3 | high | 0 |
| Tamil (`ta`) | 51 | 18 | 8 | 5 | medium | 0 |
| Telugu (`te`) | 41 | 14 | 7 | 4 | medium | 0 |
| Urdu (`ur`) | 73 | 19 | 8 | 4 | medium | 0 |
| **20 languages** | **1606** | **464** | **164** | **104** | | **0** |
<!-- counts:end -->

**Ladders.** Rows sharing an `expected` map form one contrast set: the same
sentence at two, three or four levels. This is the unit that makes review
tractable, because "is this the right step up from that?" is a far easier
question than "is this right?".

**Unmarked rows** carry `"level": null`. They have no second-person marker at
all and exist to check that a system *abstains* rather than guessing.

**Hard rows** are deliberate ambiguities the drafter already knew were
uncertain — a bare imperative with no pronoun to lean on, a form that is both
present tense and imperative. A system that scores well everywhere else and
fails here has probably learnt a surface cue rather than register.

**Is it a sample or the whole?** Neither, in the statistical sense. It is a
constructed set covering the constructions that carry register in each language
(pronouns, verb endings, imperatives, negation, courtesy formulas) across a
spread of everyday domains. It is not sampled from any corpus and no claim is
made that its distribution matches real speech.

**What is missing?** Audio. Speaker metadata. Dialect labels. Inter-annotator
agreement — there is only one annotator per row. Regional variation is recorded
in a `note` when the drafter knew of it, and not otherwise.

**Does it contain personal or sensitive data?** No. Every sentence was written
for this purpose. Names in the sentences are generic (রাহুল, dadu). Nothing was
scraped, collected from users, or taken from private communication.

---

## Collection process

**How was the data acquired?** It was written, not collected.

For **Bengali**, by the maintainer, who speaks it natively, working from
everyday usage rather than from a grammar.

For the other nineteen languages, drafted from reference grammars and standard
descriptions by someone who does not speak them, working with an AI assistant.
Each set therefore carries a `confidence` field recording how much its drafter
trusts it — `high` where the constructions are common and widely documented
(Hindi, German, French, Spanish, Italian, English), `low` where they are not
(Assamese, Nepali, Odia).

**This is the dataset's central weakness and the reason the review pages
exist.** A sentence compiled from a grammar can be structurally correct and
still be something no living person would say.

**Who was involved and how were they compensated?** Nobody was paid. No
crowdworkers, no annotation platform, no third parties.

**Over what timeframe?** Written during 2025–2026 alongside the engine it
evaluates.

**Ethical review?** None; none was required. No human subjects, no collected
data.

---

## Preprocessing and labelling

Sentences are stored exactly as written, in native script with their own
punctuation (`।`, `۔`, `。`). No tokenisation, normalisation or case folding is
applied, because Indic combining marks and script-specific punctuation are
precisely what naive normalisation destroys.

Labels are the drafter's own judgement of the level, assigned at the time of
writing rather than by a later pass. Several sets have been revised during
development where rows collided with the engine — rows asking a detector to
tell two identical strings apart, a vocative nobody would say, rows filed by
the situation they belong to rather than by anything in the sentence. Those
revisions are in the repository's git history with their reasoning.

An important limit on that: the evaluation harness can only find rows that are
*inconsistent*. A row that is simply wrong — plausible, well-formed, and not
what anyone says — collides with nothing and survives.

---

## Uses

**What it is suitable for.** Developing and debugging multi-level register
systems. Checking that a detector abstains where there is no marker. Probing
the hard cases. As a starting point for a set a speaker then corrects.

**What it must not be used for.**

- **Reporting accuracy as if the labels were ground truth.** They are one
  person's judgement, unreviewed. A model scoring 99% here has agreed with that
  person, which is not the same as being right.
- **Training a production classifier.** It is small, constructed, and not
  distributed like real speech.
- **Claims about how a language "should" be spoken.** Register is contested;
  two native speakers will disagree about Polite versus Formal, and Kolkata and
  Dhaka Bengali differ. The sets record a judgement, not a standard.
- **Any inference about individuals.** There are none in it.

**Is there anything that could cause harm?** Register is tied to caste, class,
gender and age in every language here. A system that tells someone they are
addressing a person "incorrectly" is making a social claim, not a grammatical
one. This project's learner mode deliberately accepts more than one answer
where the language genuinely does, and anything built on this data should do
the same.

---

## Distribution

**How is it distributed?** As a versioned directory built by
`python -m evaluation.release`, containing the JSONL files, this datasheet, the
schema, SHA-256 checksums per file, and baseline numbers with their method
stated. Also browsable, one language per page, at the review site.

**Licence.** **Not yet chosen.** Until a `LICENSE` file exists in the
repository, these files are shared for review and correction only. For a
dataset, CC BY 4.0 or CC0 are the usual choices; this decision belongs to the
maintainer and has not been made.

**Version.** The release directory is named with a version, and the manifest
records a SHA-256 per file. Row `id`s are stable within a release but not
guaranteed across releases.

---

## Maintenance

**Who maintains it?** Ardhendu Debnath, via the repository.

**How can corrections be made?** That is the whole point of the review pages:
one language per page, ladders laid out, a box per row, nothing uploaded
anywhere — the reviewer copies what they marked and sends it back. Or open an
issue on the repository.

**How will updates be communicated?** Through the repository, and by the
version number and checksums in each release manifest.

**Will it be supported?** It is maintained as long as the project is. Row
`status` moves from `draft` to `verified` only when a speaker of that language
has checked the row; the release status, the directory name and the baseline
caveats all follow that field automatically, so the day this data stops being
a draft, the documents say so without anyone editing them.
