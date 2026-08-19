# Can you check some sentences in your language?

You do not need to know anything about programming to help with this, and you
do not need to finish. Fifteen minutes is genuinely useful.

## What this is

Setu is a translator that tries to get *politeness* right. Every translator
gets the words right and the tone wrong — it will hand your grandmother the
pronoun you would use for a stranger. So this one treats politeness as
something the speaker chooses, across twenty languages.

To know whether it works, it is tested against sets of sentences written at
each level of politeness — 1,606 of them so far.

**Here is the problem.** Most of those sentences were compiled from reference
grammars by someone who does not speak the language. They have never been
checked by anyone who does. The test currently reports 100% for nineteen of
the twenty languages, and that number means only that the software agrees with
sentences that may themselves be wrong. A sentence that is wrong in the same
way the software is wrong scores perfectly.

That is what this is asking you to fix.

## What you are being asked

Open the page for your language. You will see blocks like this — the same
thing said at two, three or four levels of politeness:

```
Casual    তুমি কেমন আছ?
Polite    আপনি কেমন আছেন?
```

One question about each:

> **Would a speaker say these, and is each one a step up from the one above?**

Then mark it. Four buttons — *looks right* · *wrong* · *these are the same
level* · *not sure* — and a box to write what you would say instead.

Things worth saying:

- A sentence nobody would actually say, even if it is grammatically fine.
- Two rungs that are really the **same** level. That is as useful as a
  correction, and the software currently believes they differ.
- The order being wrong.
- Regional usage. If it is right where you are from and wrong elsewhere, say
  where — that is information, not a complication.
- Anything that sounds stiff, old-fashioned, or like a textbook.

Each page starts with a short section called **"Questions we already know are
hard."** Those are the places the drafter knew they were guessing, and a
ruling there is worth more than anywhere else on the page. If you only have
five minutes, do those.

## How to open it

**<https://ardhendudebnath.github.io/register-aware-translation/>**

That is the whole thing. No account, no install, nothing to run. Pick your
language and start.

Your marks are saved in your own browser as you go, so you can close the tab
and come back to it. When you are done — or when you have had enough — press
**"Show what I have marked"** at the bottom. That gives you a block of text to
copy and send back.

Nothing you mark is uploaded anywhere. It stays in your browser until you copy
it out and send it yourself.

<details>
<summary>Running it locally instead</summary>

If you have the repository and would rather not use the published pages:

```bash
python -m evaluation.review
```

That writes the same pages into `docs/`. Open `docs/index.html` in any
browser.
</details>

## Which languages need it most

The index lists them worst first. Right now:

| Most needed | | Then | | Least needed |
|---|---|---|---|---|
| Assamese | | Gujarati, Japanese, Kannada, | | English, French, |
| Nepali | | Malayalam, Marathi, Portuguese, | | German, Hindi, |
| Odia | | Punjabi, Tamil, Telugu, Urdu | | Italian, Spanish |

Bengali is listed separately: it was hand-written by a speaker, so it needs
spot-checking rather than a full pass.

The three at the top were drafted entirely from grammars. Nobody has looked at
them. If you speak Assamese, Nepali or Odia, you are the first person who
could.

## What happens to your corrections

They go back into the sentence sets, the tests re-run against them, and the
numbers start meaning something. Every correction is credited in the commit
that applies it, and the sets are intended for public release — so this is
work that outlives the app.

There is no register benchmark for any of these languages. CoCoA-MT gave Hindi
a yes/no formality benchmark in 2022 and the rest of India got nothing. Bengali
has 228 million speakers, three grammatical registers, and no test set at all.
That is what these files are trying to become, and they cannot become it
without speakers.
