"""
Turn a gold set into something a speaker can actually check.

Every row in ``data/gold/`` carries ``status: "draft"``, and for most of these
languages that is the literal truth: the sentences were compiled from grammars
by someone who does not speak them. The evaluation harness cannot find that
kind of error. It compares the engine against the gold set, so a row that is
wrong in the same direction as the table scores a confident 100%.

What it *can* find is inconsistency, and it has: rows asking the detector to
tell two identical strings apart, a vocative no speaker would say, rows filed
by the situation they belong to rather than by anything in the sentence. Those
surfaced because they collided with the engine. A row that is merely wrong
collides with nothing.

So this module exists to get the sets in front of people. It writes one
self-contained HTML page per language — no server, no dependencies, open it in
a browser — and the design follows from what makes review tractable:

**Ladders, not rows.** A sentence alone is hard to judge; the same sentence
beside its Casual and Polite counterparts is easy, because the question becomes
"is this the right step up from that?" rather than "is this right in the
abstract". Rows sharing an ``expected`` map are one ladder and are shown as
one.

**The hard questions first.** Every set carries deliberate ambiguities in its
``hard`` group, and those are worth more than the bulk: they are the places the
drafter already knew were uncertain.

**Worst first.** The index is ordered by declared confidence, so the languages
that need a speaker most are the ones at the top.

Usage::

    python -m evaluation.review              # every language
    python -m evaluation.review ml te ne     # just these
    python -m evaluation.review --out-dir /tmp/review
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from register import get_table, has_table
from utils.helpers import PROJECT_ROOT

from .gold_sets import GOLD_DIR

__all__ = ["build_pages", "main"]

DOCS_DIR = PROJECT_ROOT / "docs"
OUT_DIR = DOCS_DIR / "review"

#: Where the published copy lives. GitHub Pages serving from ``/docs`` puts
#: this folder at the site root, so the landing page has to exist or the root
#: URL is a 404 — the review pages are one level down at ``review/``.
SITE_URL = "https://ardhendudebnath.github.io/register-aware-translation/"
REPO_URL = "https://github.com/ardhendudebnath/register-aware-translation"

LEVEL_NAMES = {"0": "Close", "1": "Casual", "2": "Polite", "3": "Formal"}

#: Right-to-left scripts need the whole cell flipped, not just the font.
RTL_LANGUAGES = frozenset({"ur"})

#: Worst first — this is the review queue, not an alphabetical list.
CONFIDENCE_ORDER = {"low": 0, "medium": 1, "unrated": 2, "high": 3}

CONFIDENCE_BLURB = {
    "low": "Structurally sound, wording uncertain. Assume there are errors.",
    "medium": "Plausible, but every row needs checking before the numbers mean anything.",
    "high": "Common constructions, widely documented. Spot-check.",
    "unrated": "Hand-built and checked against native intuition. Spot-check.",
}

#: What the reviewer is actually being asked. Written for someone who speaks
#: the language and has never seen this repository.
INSTRUCTIONS = """
<p>Each block below is one <strong>ladder</strong> — the same thing said at two,
three or four levels of politeness. You are being asked one question about each:</p>
<p class="ask"><strong>Would a speaker say these, and is each one a step up from
the one above it?</strong></p>
<ul>
  <li>If a sentence is wrong, or nobody would say it that way, mark it and write
      what you would say instead.</li>
  <li>If two rungs are really the <em>same</em> level — no difference a speaker
      would feel — say so. That is as useful as a correction.</li>
  <li>If the order is wrong, say so.</li>
  <li>Regional usage counts. If it is right where you are from and wrong
      elsewhere, write down where.</li>
</ul>
<p>You do not need to be exhaustive and you do not need to finish. Anything
marked is worth more than nothing marked.</p>
"""


# --------------------------------------------------------------------------


@dataclass
class Ladder:
    """One contrast set: the same sentence at each level the row covers."""

    rungs: List[Tuple[str, str]]          # (level key, sentence)
    construction: str = ""
    context: str = ""
    domain: str = ""
    ids: List[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        return self.ids[0] if self.ids else ""


@dataclass
class Section:
    title: str
    blurb: str
    ladders: List[Ladder]


def load_rows(code: str, gold_dir: Path = GOLD_DIR) -> List[dict]:
    path = gold_dir / f"{code}.jsonl"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _ladders_from(rows: Sequence[dict]) -> List[Ladder]:
    """
    Collapse rows sharing an ``expected`` map into one ladder each.

    A triad emits one row per level, all carrying the same map. Showing them
    separately would ask the reviewer the same question three times and hide
    the contrast that makes it answerable.
    """
    seen: "OrderedDict[str, Ladder]" = OrderedDict()
    for row in rows:
        expected = row.get("expected")
        if not expected:
            continue
        signature = json.dumps(expected, ensure_ascii=False, sort_keys=True)
        ladder = seen.get(signature)
        if ladder is None:
            rungs = [(key, expected[key]) for key in sorted(expected)]
            ladder = Ladder(
                rungs=rungs,
                construction=row.get("construction", ""),
                context=row.get("context", ""),
                domain=row.get("domain", ""),
            )
            seen[signature] = ladder
        ladder.ids.append(row.get("id", ""))
    return list(seen.values())


def _singles(rows: Sequence[dict]) -> List[Ladder]:
    """Rows with no ladder — one sentence and one claimed level."""
    out = []
    for row in rows:
        level = row.get("level")
        key = "—" if level is None else str(level)
        out.append(
            Ladder(
                rungs=[(key, row.get("text", ""))],
                construction=row.get("construction", ""),
                context=row.get("note", "") or row.get("context", ""),
                domain=row.get("domain", ""),
                ids=[row.get("id", "")],
            )
        )
    return out


def build_sections(rows: Sequence[dict]) -> List[Section]:
    by_group: "OrderedDict[str, List[dict]]" = OrderedDict()
    for row in rows:
        by_group.setdefault(row.get("group", "other"), []).append(row)

    hard = by_group.pop("hard", [])
    negative = by_group.pop("negative", [])
    formal = by_group.pop("formal", [])

    sections: List[Section] = []

    if hard:
        sections.append(Section(
            "Questions we already know are hard",
            "These are the rows the drafter flagged as genuinely ambiguous. A "
            "ruling here is worth more than anywhere else on the page — each "
            "one is a place the language may not make the distinction the "
            "engine is trying to read.",
            _singles(hard),
        ))

    for group, group_rows in by_group.items():
        ladders = _ladders_from(group_rows)
        if ladders:
            sections.append(Section(group.replace("_", " "), "", ladders))

    if formal:
        sections.append(Section(
            "Formal",
            "Sentences claimed to sit above the honorific pronoun — formal by "
            "word choice rather than by grammar. Is each one actually a step "
            "beyond ordinary politeness, or just polite?",
            _singles(formal),
        ))

    if negative:
        sections.append(Section(
            "Should carry no register at all",
            "These are claimed to be neutral: nothing in them should tell you "
            "how the speaker regards the listener. If any of them does sound "
            "marked to you, that matters.",
            _singles(negative),
        ))

    return sections


# --------------------------------------------------------------------------


_CSS = """
:root{--bg:#fbfaf8;--fg:#1a1a1a;--muted:#6b6b6b;--line:#e2ded8;--card:#fff;
--accent:#8a5a2b;--warn:#a4442c;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,
"Noto Sans","Noto Sans Bengali","Noto Sans Devanagari","Noto Sans Gujarati",
"Noto Sans Gurmukhi","Noto Sans Oriya","Noto Sans Tamil","Noto Sans Telugu",
"Noto Sans Kannada","Noto Sans Malayalam","Noto Nastaliq Urdu","Noto Sans JP",
sans-serif;}
.wrap{max-width:60rem;margin:0 auto;padding:2rem 1.25rem 5rem}
h1{font-size:1.9rem;margin:0 0 .25rem;letter-spacing:-.01em}
h2{font-size:1.15rem;margin:2.5rem 0 .5rem;padding-bottom:.4rem;
border-bottom:1px solid var(--line);text-transform:lowercase;
font-variant:small-caps;letter-spacing:.04em;color:var(--accent)}
.sub{color:var(--muted);margin:0 0 1.5rem}
.banner{background:var(--card);border:1px solid var(--line);
border-left:4px solid var(--accent);padding:1rem 1.25rem;border-radius:6px;
margin:1.5rem 0}
.banner.low{border-left-color:var(--warn)}
.banner p{margin:.35rem 0}
.ask{font-size:1.05rem}
.blurb{color:var(--muted);margin:.25rem 0 1.25rem;max-width:46rem}
.card{background:var(--card);border:1px solid var(--line);border-radius:6px;
padding:.9rem 1.1rem;margin:0 0 .9rem}
.meta{color:var(--muted);font-size:.8rem;margin-bottom:.5rem;
display:flex;gap:.75rem;flex-wrap:wrap}
.meta code{background:#f2efe9;padding:.05rem .35rem;border-radius:3px;
font-size:.95em}
table{width:100%;border-collapse:collapse}
td{padding:.3rem .5rem;vertical-align:top;border:0}
td.lvl{width:6.5rem;color:var(--muted);font-size:.8rem;white-space:nowrap;
padding-top:.55rem;text-transform:uppercase;letter-spacing:.05em}
td.txt{font-size:1.2rem;line-height:1.75}
.rtl td.txt{direction:rtl;text-align:right}
.verdict{display:flex;gap:.6rem;align-items:center;margin-top:.6rem;
padding-top:.6rem;border-top:1px dashed var(--line);flex-wrap:wrap}
.verdict label{font-size:.85rem;color:var(--muted);cursor:pointer;
display:inline-flex;gap:.25rem;align-items:center}
.verdict input[type=text]{flex:1;min-width:14rem;border:1px solid var(--line);
border-radius:4px;padding:.35rem .5rem;font:inherit;font-size:.9rem;
background:var(--bg)}
.bar{position:fixed;left:0;right:0;bottom:0;background:var(--card);
border-top:1px solid var(--line);padding:.6rem 1.25rem;display:flex;
gap:1rem;align-items:center;justify-content:center;font-size:.85rem}
button{font:inherit;font-size:.85rem;padding:.4rem .9rem;border-radius:4px;
border:1px solid var(--accent);background:var(--accent);color:#fff;
cursor:pointer}
button.ghost{background:transparent;color:var(--accent)}
#out{display:none;width:100%;max-width:60rem;margin:1rem auto;height:14rem;
font:12px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;
border:1px solid var(--line);border-radius:6px;padding:.75rem}
a{color:var(--accent)}
@media print{.verdict input{border-bottom:1px solid #999}.bar,#out{display:none}}
"""

_JS = """
(function(){
  var KEY='register-review-'+document.body.dataset.lang;
  var saved={};
  try{saved=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){}
  function save(){try{localStorage.setItem(KEY,JSON.stringify(saved))}catch(e){}}
  document.querySelectorAll('[data-row]').forEach(function(card){
    var id=card.dataset.row, s=saved[id]||{};
    card.querySelectorAll('input[type=radio]').forEach(function(r){
      if(s.verdict===r.value) r.checked=true;
      r.addEventListener('change',function(){
        saved[id]=saved[id]||{}; saved[id].verdict=r.value; save();
      });
    });
    var note=card.querySelector('input[type=text]');
    if(note){
      if(s.note) note.value=s.note;
      note.addEventListener('input',function(){
        saved[id]=saved[id]||{}; saved[id].note=note.value; save();
      });
    }
  });
  var out=document.getElementById('out');
  document.getElementById('export').addEventListener('click',function(){
    var lines=Object.keys(saved).filter(function(k){
      var v=saved[k]; return v && (v.verdict||v.note);
    }).map(function(k){
      return JSON.stringify(Object.assign({id:k,language:document.body.dataset.lang},saved[k]));
    });
    out.style.display='block';
    out.value=lines.length?lines.join('\\n'):'Nothing marked yet.';
    out.select();
  });
  document.getElementById('clear').addEventListener('click',function(){
    if(!confirm('Clear everything you have marked on this page?'))return;
    saved={};save();location.reload();
  });
})();
"""


def _row_html(ladder: Ladder, index: int, rtl: bool) -> str:
    rows = []
    for key, text in ladder.rungs:
        name = LEVEL_NAMES.get(key, key)
        rows.append(
            f'<tr><td class="lvl">{html.escape(name)}</td>'
            f'<td class="txt">{html.escape(text)}</td></tr>'
        )
    meta = []
    if ladder.construction:
        meta.append(f"<code>{html.escape(ladder.construction)}</code>")
    if ladder.context and ladder.context != "n/a":
        meta.append(html.escape(ladder.context))
    if ladder.domain and ladder.domain not in ("n/a", "ambiguity"):
        meta.append(html.escape(ladder.domain))
    meta_html = (
        f'<div class="meta">{"".join(f"<span>{m}</span>" for m in meta)}</div>'
        if meta else ""
    )
    rid = html.escape(ladder.key or f"row-{index}")
    name = f"v{index}"
    return f"""
<div class="card{' rtl' if rtl else ''}" data-row="{rid}">
  {meta_html}
  <table>{''.join(rows)}</table>
  <div class="verdict">
    <label><input type="radio" name="{name}" value="ok"> looks right</label>
    <label><input type="radio" name="{name}" value="wrong"> wrong</label>
    <label><input type="radio" name="{name}" value="same"> these are the same level</label>
    <label><input type="radio" name="{name}" value="unsure"> not sure</label>
    <input type="text" placeholder="what would you say instead?">
  </div>
</div>"""


def render_language(code: str, rows: Sequence[dict]) -> str:
    name = get_table(code).name if has_table(code) else code
    confidence = next(
        (r.get("confidence") for r in rows if r.get("confidence")), "unrated"
    )
    rtl = code in RTL_LANGUAGES
    sections = build_sections(rows)

    counter = 0
    body = []
    for section in sections:
        body.append(f"<h2>{html.escape(section.title)}</h2>")
        if section.blurb:
            body.append(f'<p class="blurb">{html.escape(section.blurb)}</p>')
        for ladder in section.ladders:
            counter += 1
            body.append(_row_html(ladder, counter, rtl))

    banner_class = "banner low" if confidence == "low" else "banner"
    note = next((r.get("note") for r in rows if r.get("group") == "note"), "")

    return f"""<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(name)} — register review</title>
<style>{_CSS}</style>
<body data-lang="{html.escape(code)}">
<div class="wrap">
  <h1>{html.escape(name)}</h1>
  <p class="sub">{counter} things to check · declared confidence:
     <strong>{html.escape(confidence)}</strong></p>

  <div class="{banner_class}">
    <p><strong>{html.escape(CONFIDENCE_BLURB.get(confidence, ''))}</strong></p>
    <p>These sentences were drafted from reference grammars by someone who does
       not speak {html.escape(name)}. Nothing here has been checked by a
       speaker, which is what this page is for.</p>
    {f'<p>{html.escape(note)}</p>' if note else ''}
  </div>

  {INSTRUCTIONS}
  {''.join(body)}
  <textarea id="out" readonly></textarea>
</div>
<div class="bar">
  <span>Marks are saved in this browser as you go.</span>
  <button id="export">Show what I have marked</button>
  <button class="ghost" id="clear">Clear</button>
</div>
<script>{_JS}</script>
"""


def render_index(entries: Sequence[Tuple[str, str, str, int]]) -> str:
    items = []
    for code, name, confidence, count in entries:
        items.append(
            f'<li><a href="{html.escape(code)}.html">{html.escape(name)}</a>'
            f' <span class="meta"><span>{count} to check</span>'
            f'<span>confidence: {html.escape(confidence)}</span></span></li>'
        )
    return f"""<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Register gold sets — review</title>
<style>{_CSS} li{{margin:.6rem 0}} ul.langs{{list-style:none;padding:0}}</style>
<body data-lang="index">
<div class="wrap">
  <h1>Register gold sets</h1>
  <p class="sub">Ordered worst-first: the languages nearest the top are the
     ones that most need a speaker.</p>
  <div class="banner low">
    <p>Every set here is a <strong>draft</strong>. The evaluation harness scores
       the engine against these sentences, so where a sentence is wrong the
       score is wrong with it, confidently and invisibly.</p>
    <p>Checking one language is a real contribution. Checking the hard rows at
       the top of one language is a real contribution.</p>
  </div>
  <ul class="langs">{''.join(items)}</ul>
</div>
"""


# --------------------------------------------------------------------------


def render_landing(entries: Sequence[Tuple[str, str, str, int]]) -> str:
    """
    The front door, for ``docs/index.html``.

    Pages serving from ``/docs`` makes this folder the site root, so without
    this file the published URL is a 404 and every link anyone sends lands
    nowhere. It is also the first thing a reviewer sees, so it leads with the
    ask rather than with the project.
    """
    worst = [e for e in entries if e[2] == "low"]
    rest = [e for e in entries if e[2] != "low"]

    def row(entry: Tuple[str, str, str, int], urgent: bool = False) -> str:
        code, name, confidence, count = entry
        klass = ' class="urgent"' if urgent else ""
        return (
            f'<li{klass}><a href="review/{html.escape(code)}.html">'
            f'{html.escape(name)}</a>'
            f'<span class="meta"><span>{count} to check</span>'
            f'<span>{html.escape(confidence)}</span></span></li>'
        )

    return f"""<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Setu — help check a language</title>
<style>{_CSS}
ul.langs{{list-style:none;padding:0;margin:0}}
ul.langs li{{display:flex;justify-content:space-between;align-items:baseline;
gap:1rem;padding:.55rem .75rem;border-bottom:1px solid var(--line)}}
ul.langs li.urgent{{background:var(--card);border-left:3px solid var(--warn)}}
ul.langs a{{font-size:1.05rem;text-decoration:none}}
ul.langs a:hover{{text-decoration:underline}}
.lead{{font-size:1.15rem;max-width:44rem}}
</style>
<body data-lang="index">
<div class="wrap">
  <h1>Setu</h1>
  <p class="sub">A translator that tries to get <em>politeness</em> right,
     across twenty languages.</p>

  <div class="banner low">
    <p class="ask"><strong>Can you check some sentences in your
       language?</strong></p>
    <p>Setu is tested against 1,606 sentences written at each level of
       politeness. Most of them were compiled from reference grammars by
       someone who does not speak the language, and have never been checked by
       anyone who does.</p>
    <p>The tests currently report 100% for nineteen of the twenty languages.
       That number means only that the software agrees with sentences which
       may themselves be wrong — a sentence wrong in the same way the software
       is wrong scores perfectly. That is what this is asking you to fix.</p>
    <p>No account, nothing to install, and fifteen minutes is genuinely
       useful. Every page opens with the handful of questions we already know
       are hard; if you only have five minutes, do those.</p>
  </div>

  <h2>Nobody has checked these at all</h2>
  <p class="blurb">Drafted entirely from grammars. If you speak one of these,
     you would be the first person to look.</p>
  <ul class="langs">{''.join(row(e, urgent=True) for e in worst)}</ul>

  <h2>Every language</h2>
  <p class="blurb">Ordered worst-first. Bengali was written by a speaker, so it
     needs spot-checking rather than a full pass.</p>
  <ul class="langs">{''.join(row(e) for e in rest)}</ul>

  <h2>What happens to your corrections</h2>
  <p class="blurb">They go back into the sentence sets, the tests re-run
     against them, and the numbers start meaning something. There is no
     register benchmark for any of these languages — CoCoA-MT gave Hindi a
     yes/no formality benchmark in 2022 and the rest of India got nothing.
     Bengali has 228 million speakers, three grammatical registers, and no test
     set at all. That is what these pages are trying to become, and they cannot
     become it without speakers.</p>
  <p class="blurb"><a href="{REPO_URL}">The project on GitHub</a> ·
     <a href="{REPO_URL}/blob/main/REVIEWING.md">Longer explanation</a></p>
</div>
"""


def build_pages(codes: Optional[Iterable[str]] = None,
                out_dir: Path = OUT_DIR,
                gold_dir: Path = GOLD_DIR) -> List[Path]:
    if codes is None:
        codes = sorted(p.stem for p in gold_dir.glob("*.jsonl"))
    out_dir.mkdir(parents=True, exist_ok=True)

    written: List[Path] = []
    entries: List[Tuple[str, str, str, int]] = []
    for code in codes:
        rows = load_rows(code, gold_dir)
        if not rows:
            print(f"  {code}: no gold set, skipped")
            continue
        page = render_language(code, rows)
        path = out_dir / f"{code}.html"
        path.write_text(page, encoding="utf-8")
        written.append(path)

        name = get_table(code).name if has_table(code) else code
        confidence = next(
            (r.get("confidence") for r in rows if r.get("confidence")), "unrated"
        )
        checks = sum(len(s.ladders) for s in build_sections(rows))
        entries.append((code, name, confidence, checks))

    entries.sort(key=lambda e: (CONFIDENCE_ORDER.get(e[2], 9), e[1]))
    index = out_dir / "index.html"
    index.write_text(render_index(entries), encoding="utf-8")
    written.append(index)

    # The site root, one level up. Only when writing to the real docs folder —
    # a caller pointing somewhere else (a test, a scratch directory) wants the
    # review pages, not a landing page for a site that is not there.
    if out_dir == OUT_DIR:
        landing = DOCS_DIR / "index.html"
        landing.write_text(render_landing(entries), encoding="utf-8")
        written.append(landing)
    return written


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Write review pages for the draft gold sets."
    )
    parser.add_argument("languages", nargs="*",
                        help="language codes; default is every set found")
    parser.add_argument("--out-dir", default=str(OUT_DIR))
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir)
    written = build_pages(args.languages or None, out_dir)
    if not written:
        print("nothing written")
        return 1

    pages = [p for p in written if p.parent == out_dir and p.name != "index.html"]
    print(f"wrote {len(pages)} language pages to {out_dir}")
    if (DOCS_DIR / "index.html") in written:
        print(f"site root  {DOCS_DIR / 'index.html'}")
    print(f"open       {out_dir / 'index.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
