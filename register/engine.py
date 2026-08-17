"""
The register engine — deterministic, auditable, offline, ~0 ms.

One symmetric dataset (``register.tables``) drives three jobs:

    rewrite()  move a sentence to a requested level, in either direction
    detect()   read the level the speaker actually used
    ladder()   render the same sentence at all four levels

Everything here is pure string processing over compiled regexes. There is no
model, no network call and no hidden state, which is what lets the register
layer keep working when every other stage of the pipeline is offline, and what
lets the UI show the user exactly which rules fired.

Matching notes
--------------
*Boundaries.* Indic scripts attach combining vowel marks that Python's ``\\b``
does not treat as word characters, so ``\\bকরো\\b`` fails on a perfectly ordinary
Bengali word. We therefore delimit on an explicit punctuation/whitespace class
instead of relying on ``\\w``.

*Case.* Most forms match case-insensitively and the replacement inherits the
source's capitalisation. That is wrong for German ``Sie``/``sie`` (you/she) and
Italian ``Lei``/``lei`` (you/she), where case is the only thing distinguishing a
polite pronoun from an unrelated word — those rules are marked ``cased`` and
match exactly, plus a sentence-initial capitalised variant of the lower forms.

*Overlaps.* All candidate matches are found against the original string, then
resolved longest-first into a non-overlapping set before a single replacement
pass. A rewrite therefore never feeds its own output back into another rule,
which is what would otherwise let ``kannst du -> können Sie`` be re-matched by
the bare ``du -> Sie`` rule.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Sequence, Tuple

from .boundaries import LEFT, RIGHT, delimited
from .selectors import get_selector
from .speaker import apply_speaker_gender, supports_speaker_gender
from .levels import (
    AUTO,
    CASUAL,
    CLOSE,
    FORMAL,
    LEVELS,
    POLITE,
    coerce_level,
    formality_percent,
    level_name,
)
from .tables import LanguageTable, Rule, get_table, has_table, supported_languages

__all__ = [
    "Edit",
    "RewriteResult",
    "Detection",
    "rewrite",
    "detect",
    "ladder",
    "pre_edit",
    "prosody",
    "address_term",
    "politeness_warning",
    "supported_languages",
    "has_table",
]


#: Cache of compiled per-language matchers, built lazily on first use.
_COMPILED: Dict[str, "_Matcher"] = {}


# --------------------------------------------------------------------------
# Results
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Edit:
    """One rule firing — what changed, where, and why."""

    rule: str
    gloss: str
    before: str
    after: str
    start: int
    from_levels: Tuple[int, ...]
    to_level: int

    def describe(self) -> str:
        return f"{self.before} → {self.after}  ({self.rule})"


@dataclass(frozen=True)
class RewriteResult:
    text: str
    level: int
    source_level: Optional[int]
    edits: Tuple[Edit, ...] = ()
    language: str = ""

    @property
    def changed(self) -> bool:
        return bool(self.edits)

    def trace(self) -> List[str]:
        """Human-readable list of the edits, for the 'show the rules' panel."""
        return [e.describe() for e in self.edits]

    def as_dict(self) -> dict:
        return {
            "text": self.text,
            "language": self.language,
            "level": self.level,
            "level_name": level_name(self.level),
            "source_level": self.source_level,
            "source_level_name": (
                level_name(self.source_level) if self.source_level is not None else None
            ),
            "formality_percent": formality_percent(self.level),
            "edits": [
                {
                    "rule": e.rule,
                    "gloss": e.gloss,
                    "before": e.before,
                    "after": e.after,
                    "start": e.start,
                }
                for e in self.edits
            ],
        }


@dataclass(frozen=True)
class Detection:
    """The register the speaker used, plus the evidence for it."""

    level: Optional[int]
    confidence: float
    votes: Dict[int, float] = field(default_factory=dict)
    evidence: Tuple[Tuple[str, str], ...] = ()
    language: str = ""

    @property
    def is_confident(self) -> bool:
        return self.level is not None and self.confidence >= 0.6

    def as_dict(self) -> dict:
        return {
            "language": self.language,
            "level": self.level,
            "level_name": level_name(self.level) if self.level is not None else None,
            "confidence": round(self.confidence, 3),
            "votes": {level_name(k): round(v, 3) for k, v in sorted(self.votes.items())},
            "evidence": [{"surface": s, "rule": r} for s, r in self.evidence],
        }


# --------------------------------------------------------------------------
# Compilation
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class _Guards:
    """Compiled contextual constraints for one rule."""

    before: Optional[re.Pattern] = None
    after: Optional[re.Pattern] = None
    required_before: Optional[re.Pattern] = None
    required_after: Optional[re.Pattern] = None
    #: The two halves of one `require_adjacent` constraint: satisfied if
    #: *either* side matches, which is why it cannot be expressed as a
    #: required_before plus a required_after.
    adjacent_before: Optional[re.Pattern] = None
    adjacent_after: Optional[re.Pattern] = None

    def allows(self, text: str, start: int, end: int) -> bool:
        prefix, suffix = text[:start], text[end:]
        if self.before is not None and self.before.search(prefix):
            return False
        if self.after is not None and self.after.match(suffix):
            return False
        if self.required_before is not None and not self.required_before.search(prefix):
            return False
        if self.required_after is not None and not self.required_after.match(suffix):
            return False
        if self.adjacent_before is not None and not (
            self.adjacent_before.search(prefix) or self.adjacent_after.match(suffix)
        ):
            return False
        return True


@dataclass(frozen=True)
class _Pattern:
    regex: re.Pattern
    rule: Rule
    form: str
    length: int
    cased: bool
    guards: _Guards


class _Matcher:
    """All patterns for one language, ordered longest-first."""

    def __init__(self, table: LanguageTable) -> None:
        self.table = table
        self.patterns: List[_Pattern] = []

        for rule in table.rules:
            guards = self._guards(rule)
            overrides = {
                spec[0]: self._guards(
                    rule,
                    guard_before=spec[1] or None,
                    guard_after=spec[2] or None,
                    require_before=spec[3] or None,
                    require_after=spec[4] or None,
                    require_adjacent=(spec[5] if len(spec) > 5 else "") or None,
                )
                for spec in rule.form_guards
            }
            seen_forms = set()
            for form in rule.forms:
                form = form.strip()
                if not form or form in seen_forms:
                    continue
                seen_forms.add(form)
                form_guards = overrides.get(form, guards)
                for variant, cased in self._variants(form, rule):
                    self.patterns.append(
                        _Pattern(
                            regex=self._compile(variant, cased, table.boundary),
                            rule=rule,
                            form=form,
                            length=len(variant),
                            cased=cased,
                            guards=form_guards,
                        )
                    )

        # Longest first so multi-word clause rules beat the bare pronouns
        # nested inside them.
        self.patterns.sort(key=lambda p: p.length, reverse=True)

        self.normalise = tuple(
            (re.compile(pat), repl) for pat, repl in table.normalise
        )
        self.elide = tuple((re.compile(pat), repl) for pat, repl in table.elide)

    def expand(self, text: str) -> str:
        """Contractions -> the shape the rules are written in."""
        for pattern, repl in self.normalise:
            text = pattern.sub(repl, text)
        return text

    def contract(self, text: str) -> str:
        """Back to the language's real orthography."""
        for pattern, repl in self.elide:
            text = pattern.sub(repl, text)
        return text

    @staticmethod
    def _variants(form: str, rule: Rule) -> List[Tuple[str, bool]]:
        """
        Surface variants to look for. Cased rules match exactly, plus a
        capitalised version of any lower-case form so that a sentence-initial
        "Du kommst" is still recognised without "sie" (she) leaking in.
        """
        if not rule.cased:
            return [(form, False)]
        variants = [(form, True)]
        if form[:1].islower():
            variants.append((form[0].upper() + form[1:], True))
        return variants

    @staticmethod
    def _guards(rule: Rule, guard_before: Optional[str] = None,
                guard_after: Optional[str] = None,
                require_before: Optional[str] = None,
                require_after: Optional[str] = None,
                require_adjacent: Optional[str] = None) -> _Guards:
        flags = re.IGNORECASE if not rule.cased else 0
        overrides = {
            "guard_before": guard_before,
            "guard_after": guard_after,
            "require_before": require_before,
            "require_after": require_after,
            "require_adjacent": require_adjacent,
        }
        supplied = {k: v for k, v in overrides.items() if v is not None}
        if supplied:
            rule = replace(rule, **supplied)
        # The *_before patterns are anchored to the end of the prefix, so they
        # mean "immediately before the match".
        def _before(pattern: str) -> Optional[re.Pattern]:
            return re.compile(f"(?:{pattern})$", flags) if pattern else None

        def _after(pattern: str) -> Optional[re.Pattern]:
            return re.compile(pattern, flags) if pattern else None

        # One pattern, compiled for both sides: anchored to the end of the
        # prefix, and plain for the suffix. `\s*` on the inner edge lets the
        # word sit against the match with the space between them.
        adjacent = rule.require_adjacent
        return _Guards(
            before=_before(rule.guard_before),
            after=_after(rule.guard_after),
            required_before=_before(rule.require_before),
            required_after=_after(rule.require_after),
            adjacent_before=(
                re.compile(rf"(?:{adjacent})\s*$", flags) if adjacent else None
            ),
            adjacent_after=(
                re.compile(rf"\s*(?:{adjacent})", flags) if adjacent else None
            ),
        )

    @staticmethod
    def _compile(form: str, cased: bool, boundary: str) -> re.Pattern:
        body = re.escape(form)
        if boundary == "delimited":
            body = delimited(body)
        flags = 0 if cased else re.IGNORECASE
        return re.compile(body, flags)


def _matcher(code: str) -> _Matcher:
    table = get_table(code)
    cached = _COMPILED.get(table.code)
    if cached is None:
        cached = _Matcher(table)
        _COMPILED[table.code] = cached
    return cached


# --------------------------------------------------------------------------
# Match resolution
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class _Hit:
    start: int
    end: int
    surface: str
    rule: Rule
    form: str
    cased: bool


def _find_hits(text: str, matcher: _Matcher) -> List[_Hit]:
    """
    Every candidate match, resolved into a non-overlapping set. Patterns are
    already sorted longest-first, so a greedy sweep gives the longest match at
    each position without a full interval-scheduling pass.
    """
    hits: List[_Hit] = []
    taken: List[Tuple[int, int]] = []

    for pattern in matcher.patterns:
        for m in pattern.regex.finditer(text):
            span = (m.start(), m.end())
            if any(span[0] < t_end and t_start < span[1] for t_start, t_end in taken):
                continue
            if not pattern.guards.allows(text, m.start(), m.end()):
                continue
            taken.append(span)
            hits.append(
                _Hit(
                    start=m.start(),
                    end=m.end(),
                    surface=m.group(0),
                    rule=pattern.rule,
                    form=pattern.form,
                    cased=pattern.cased,
                )
            )

    hits.sort(key=lambda h: h.start)
    return hits


def _match_case(source: str, replacement: str) -> str:
    """Carry the source's capitalisation onto the replacement."""
    if not source or not replacement:
        return replacement
    if len(source) > 1 and source.isupper():
        return replacement.upper()
    if source[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def _restore_initial_capital(original: str, rewritten: str) -> str:
    """
    If the original sentence began with a capital and the rewrite left a
    lower-case letter there (German "Sie" -> "du"), put the capital back.
    """
    o = original.lstrip()
    r = rewritten.lstrip()
    if not o or not r or not o[:1].isupper() or not r[:1].islower():
        return rewritten
    idx = len(rewritten) - len(r)
    return rewritten[:idx] + r[0].upper() + r[1:]


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------


def detect(text: str, language: str) -> Detection:
    """
    Read the register the speaker used. Each matched form votes for the levels
    whose column it sits in, split evenly when a form spans several levels
    (Bengali আপনি is both Polite and Formal). Votes are folded onto the levels
    the language actually realises before the winner is picked.
    """
    if not isinstance(text, str) or not text.strip() or not has_table(language):
        return Detection(level=None, confidence=0.0, language=language)

    matcher = _matcher(language)
    table = matcher.table
    votes: Dict[int, float] = {level: 0.0 for level in LEVELS}
    evidence: List[Tuple[str, str]] = []

    for hit in _find_hits(matcher.expand(text), matcher):
        if hit.rule.rewrite_only:
            continue  # neutral in itself; only its elaboration is marked
        levels = hit.rule.levels_for(hit.form)
        if not levels or len(levels) == 4:
            continue  # carries no register information
        # Fold before splitting, not after. A form spans however many levels
        # the *language* realises, which is not always how many slots it fills:
        # Portuguese "seu" sits in three slots, but canon (0, 1, 2, 2) makes
        # the top two one level, so it spans two. Splitting first gave that
        # level a double share and tipped every ambiguous Portuguese sentence
        # to Polite — "É o seu livro?" scored 0.67 for a distinction the
        # sentence does not make.
        folded = {table.fold(level) for level in levels}
        if len(folded) == len(LEVELS):
            continue  # every level the language has — no information after all
        share = 1.0 / len(folded)
        for level in folded:
            votes[level] += share
        evidence.append((hit.surface, hit.rule.name))

    total = sum(votes.values())
    if total <= 0:
        return Detection(level=None, confidence=0.0, language=table.code)

    # Ties break toward the socially unmarked reading — the level nearest
    # Polite, then the lower one. A bare Bengali আপনি spans Polite and Formal
    # equally; reporting it as Polite matches what a native speaker would say,
    # and reserves Formal for sentences that also carry দয়া করে and friends.
    best = min(votes, key=lambda level: (-votes[level], abs(level - POLITE), level))
    return Detection(
        level=best,
        confidence=votes[best] / total,
        votes={k: v for k, v in votes.items() if v > 0},
        evidence=tuple(evidence),
        language=table.code,
    )


def rewrite(
    text: str,
    language: str,
    target_level,
    *,
    soften: bool = False,
    addressee: Optional[str] = None,
    speaker_gender: Optional[str] = None,
) -> RewriteResult:
    """
    Move ``text`` to ``target_level``. Works in both directions off the same
    table; ``target_level`` may be :data:`~register.levels.AUTO`, in which case
    the speaker's own level is detected and mirrored.

    ``soften`` prepends the language's politeness particle at Polite/Formal
    (Hindi कृपया, Bengali দয়া করে). ``addressee`` inserts the vocative that
    Indian languages require when opening with a stranger (blueprint 13.2 #3).
    ``speaker_gender`` fixes first-person verb agreement in Hindi, Marathi,
    Punjabi and Gujarati, where the verb agrees with who is *speaking* — MT
    defaults to masculine and so misgenders half its users.
    """
    if not isinstance(text, str):
        raise TypeError(f"text must be str, got {type(text).__name__}")

    if not has_table(language):
        # Unknown language: pass the text through untouched rather than
        # guessing. The caller still gets a well-formed result.
        level = CASUAL if target_level == AUTO else coerce_level(target_level)
        return RewriteResult(text=text, level=level, source_level=None, language=language)

    matcher = _matcher(language)
    table = matcher.table

    detected = detect(text, language)
    if target_level == AUTO:
        level = detected.level if detected.level is not None else CASUAL
    else:
        level = coerce_level(target_level)
    level = table.fold(level)

    if not text.strip():
        return RewriteResult(text=text, level=level, source_level=detected.level,
                             language=table.code)

    original = text
    text = matcher.expand(text)

    edits: List[Edit] = []
    pieces: List[str] = []
    cursor = 0

    for hit in _find_hits(text, matcher):
        replacement = hit.rule.forms[level]

        # A few rules cannot answer from the tuple alone — French "votre" needs
        # the gender of the noun after it. Those defer to a selector.
        if hit.rule.select:
            selector = get_selector(hit.rule.select)
            if selector is not None:
                chosen = selector(hit.surface, level, text, hit.start, hit.end)
                if chosen:
                    replacement = chosen

        if not replacement:
            # An empty slot means the level has no equivalent, so the word goes
            # away rather than surviving the rewrite. Politeness particles are
            # the case: Tamil தயவுசெய்து and Gujarati કૃપા કરીને belong to the
            # Formal rendering only, and leaving them in a downgraded sentence
            # made it read back as Formal.
            pieces.append(text[cursor:hit.start])
            cursor = hit.end
            while cursor < len(text) and text[cursor] == " ":
                cursor += 1
            edits.append(
                Edit(
                    rule=hit.rule.name,
                    gloss=hit.rule.gloss,
                    before=hit.surface,
                    after="",
                    start=hit.start,
                    from_levels=hit.rule.levels_for(hit.form),
                    to_level=level,
                )
            )
            continue
        if not hit.cased:
            replacement = _match_case(hit.surface, replacement)
        if replacement == hit.surface:
            continue

        pieces.append(text[cursor:hit.start])
        pieces.append(replacement)
        cursor = hit.end
        edits.append(
            Edit(
                rule=hit.rule.name,
                gloss=hit.rule.gloss,
                before=hit.surface,
                after=replacement,
                start=hit.start,
                from_levels=hit.rule.levels_for(hit.form),
                to_level=level,
            )
        )

    pieces.append(text[cursor:])
    result = matcher.contract("".join(pieces))
    result = _restore_initial_capital(original, result)

    # A language whose only change was normalise-then-contract has not actually
    # been edited; hand back exactly what came in.
    if not edits:
        result = original
    elif result == original:
        # Every edit cancelled out — the usual cause is a replacement that
        # differed only in case, which _restore_initial_capital then undid.
        # Reporting edits for text that did not change is wrong on its own
        # terms, and it also made the semantic metric mask spans that were
        # never really touched, scoring an unchanged "Scusa." at 0.29.
        edits = []

    # Portuguese needs a subject pronoun the source never carried; see
    # _insert_subject_pronoun. Runs before the softener and vocative so those
    # attach to the finished clause.
    result, subject_edit = _insert_subject_pronoun(result, table, level, edits)
    if subject_edit is not None:
        edits.append(subject_edit)

    if speaker_gender:
        result, gender_edits = apply_speaker_gender(result, table.code, speaker_gender)
        for edit in gender_edits:
            edits.append(
                Edit(
                    rule="speaker.gender",
                    gloss=f"first-person agreement ({speaker_gender})",
                    before=edit.before,
                    after=edit.after,
                    start=edit.start,
                    from_levels=(),
                    to_level=level,
                )
            )

    if soften:
        result = _apply_softener(result, table, level)
    if addressee:
        result = _apply_address_term(result, table, level, addressee)

    return RewriteResult(
        text=result,
        level=level,
        source_level=detected.level,
        edits=tuple(edits),
        language=table.code,
    )


def ladder(text: str, language: str, **kwargs) -> Dict[int, RewriteResult]:
    """
    The same sentence at every level the language distinguishes. This is the
    five-second demo: one call, four renderings, side by side.
    """
    out: Dict[int, RewriteResult] = {}
    if not has_table(language):
        for level in LEVELS:
            out[level] = RewriteResult(text=text, level=level, source_level=None,
                                       language=language)
        return out

    table = get_table(language)
    cache: Dict[int, RewriteResult] = {}
    for level in LEVELS:
        folded = table.fold(level)
        if folded not in cache:
            cache[folded] = rewrite(text, language, folded, **kwargs)
        out[level] = cache[folded]
    return out


def pre_edit(text: str, source_language: str, target_level) -> str:
    """
    Steer the source *before* the MT engine sees it (blueprint 3.3 stage 1).

    MT inherits register from surface politeness markers, so nudging the source
    is high-leverage and nearly free. This is deliberately conservative: it only
    adds or strips politeness scaffolding, never touches content words.
    """
    if not isinstance(text, str) or not text.strip():
        return text
    if target_level == AUTO:
        return text

    level = coerce_level(target_level)
    stripped = text.strip()

    if source_language and _normalise_code(source_language) != "en":
        # Source steering is tuned for English input; other sources are handled
        # well enough by the target-side post-edit.
        return text

    if level >= POLITE:
        if not re.search(r"\b(please|kindly|could you|would you|may I)\b", stripped, re.I):
            if re.match(r"^(give|send|tell|show|bring|open|close|come|go|wait|stop|help|take|put)\b",
                        stripped, re.I):
                return "Please " + stripped[0].lower() + stripped[1:]
    else:
        stripped = re.sub(r"\b(could|would) you kindly\b", "can you", stripped, flags=re.I)
        stripped = re.sub(r"\bkindly\s+", "", stripped, flags=re.I)
        stripped = re.sub(r"\bI should like to\b", "I want to", stripped, flags=re.I)
        stripped = re.sub(r"\bI would like to\b", "I want to", stripped, flags=re.I)
        return stripped

    return text


def prosody(level) -> Dict[str, float]:
    """
    Register should drive the voice, not just the words (blueprint 13.2 #4).
    Formal speech is slower, lower and more evenly paced; casual speech is
    faster and more clipped. Returns TTS parameters, not audio.
    """
    level = coerce_level(level)
    return {
        CLOSE: {"rate": 1.10, "pitch": 1.03, "pause_ms": 90},
        CASUAL: {"rate": 1.05, "pitch": 1.00, "pause_ms": 110},
        POLITE: {"rate": 0.97, "pitch": 0.98, "pause_ms": 160},
        FORMAL: {"rate": 0.90, "pitch": 0.96, "pause_ms": 210},
    }[level]


def address_term(language: str, level, addressee: str) -> str:
    """
    The vocative the target language requires but the English source leaves
    empty — দাদা, भैया, அண்ணா (blueprint 13.2 #3). Returns "" when the
    language or addressee has no entry.
    """
    if not has_table(language):
        return ""
    table = get_table(language)
    forms = table.address_terms.get(addressee)
    if not forms:
        return ""
    return forms[table.fold(coerce_level(level))]


def politeness_warning(text: str, language: str, intended_level) -> Optional[str]:
    """
    A rudeness warning — Grammarly for social register (blueprint 13.2 #5).

    Returns a short warning when the chosen level is likely to land badly, or
    None when it looks fine. The detector already exists; this is the second,
    more valuable use of it.
    """
    if not has_table(language) or intended_level == AUTO:
        return None

    table = get_table(language)
    level = table.fold(coerce_level(intended_level))
    if level > CASUAL:
        return None

    probe = rewrite(text, language, level)
    if not probe.edits:
        return None

    polite_form = _polite_pronoun(table)
    if not polite_form:
        return None
    if level == CLOSE:
        return (
            f"This will sound very familiar — {table.name} {level_name(level)} is "
            f"reserved for children and close friends. Did you mean {polite_form}?"
        )
    return (
        f"This is {level_name(level)} register. With someone you have just met, "
        f"{polite_form} is the safer choice."
    )


# --------------------------------------------------------------------------
# Internals
# --------------------------------------------------------------------------


def _insert_subject_pronoun(
    text: str,
    table: LanguageTable,
    level: int,
    edits: List[Edit],
) -> Tuple[str, Optional[Edit]]:
    """
    Add the subject pronoun the target level needs but the source never had.

    Every other rewrite in this engine is a substitution: something was there,
    something else goes in its place. This one creates a word out of nothing,
    which is why it is a separate pass and why it is deliberately narrow.

    It fires only when all of these hold:

    * the language declares an ``insert_subject`` form for this level
    * the sentence has no second-person subject already — otherwise "Você é"
      would grow a second one every time it was re-levelled
    * a *finite* verb was actually rewritten, so there is a clause to attach to
      and we are not decorating an imperative ("Fale" must not become
      "Você fale")

    The pronoun goes on whichever side of that verb the language wants — see
    ``subject_position``. Before is the neutral Portuguese order and the only
    position right in both statements ("Você é...") and wh-questions ("Onde
    você mora?"); Spanish wants it after ("¿Dónde vive usted?").
    """
    # `any`, not a truthiness test: the default is a tuple of four empty
    # strings, which is itself truthy, so a bare check passes for every
    # language that never declares one — and then the removal branch below
    # deletes subject pronouns out of French and Italian.
    if not any(table.insert_subject) or not text.strip():
        return text, None
    pronoun = table.insert_subject[level]

    already_present = any(
        form and re.search(delimited(re.escape(form)), text, re.IGNORECASE)
        for form in table.insert_subject
    )
    pronoun_rule = next(
        (r for r in table.rules if r.name == "pron.2sg.nom"), None
    )
    if pronoun_rule is not None and not already_present:
        already_present = any(
            form and re.search(delimited(re.escape(form)), text, re.IGNORECASE)
            for form in pronoun_rule.forms
        )

    verb_edit = next(
        (e for e in edits
         if e.rule.startswith("v.")
         and ".imp" not in e.rule
         and e.after
         and e.after in text),
        None,
    )
    if verb_edit is None:
        return text, None

    index = text.find(verb_edit.after)
    if index < 0:
        return text, None

    if not pronoun:
        # Going the other way. The pronoun this pass adds is required at the
        # honorific levels and merely redundant below them, so a downgrade has
        # to take it back out — "¿Cómo se llama usted?" is "¿Cómo te llamas?",
        # not "¿Cómo te llamas tú?", where the leftover pronoun reads as
        # contrastive emphasis nobody asked for.
        #
        # Only a pronoun standing against the rewritten verb goes. In "Esto es
        # para usted" the usted is a prepositional object and belongs to no
        # verb, so it is translated rather than dropped.
        return _remove_subject_pronoun(
            text, pronoun_rule, level, index, len(verb_edit.after),
            "after" if _subject_goes_after(table.subject_position, text)
            else "before",
        )
    if already_present:
        return text, None

    if _subject_goes_after(table.subject_position, text):
        end = index + len(verb_edit.after)
        return (
            text[:end] + " " + pronoun + text[end:],
            Edit(
                rule="subject.insert",
                gloss="subject pronoun required by the target level",
                before="",
                after=pronoun,
                start=end,
                from_levels=(),
                to_level=level,
            ),
        )

    if not text[:index].strip():
        # Clause-initial: the pronoun takes the capital and the verb loses it.
        head = pronoun[:1].upper() + pronoun[1:]
        rewritten = (
            text[:index] + head + " " + text[index].lower() + text[index + 1:]
        )
    else:
        rewritten = text[:index] + pronoun + " " + text[index:]

    return rewritten, Edit(
        rule="subject.insert",
        gloss="subject pronoun required by the target level",
        before="",
        after=pronoun,
        start=index,
        from_levels=(),
        to_level=level,
    )


#: Words that front a wh-question in the languages using ``wh_inverted``.
#: Portuguese only, for now — "o que" and "por que" are covered by their first
#: word, so the list stays at the heads.
_WH_INITIAL = re.compile(
    r"^\s*(?:o\s+que|por\s*que|porque|que|qual|quais|quem|quando|onde|aonde|"
    r"como|quanto|quanta|quantos|quantas)\b",
    re.IGNORECASE,
)


def _subject_goes_after(position: str, text: str) -> bool:
    """Resolve ``subject_position`` against the sentence in hand."""
    if position == "after":
        return True
    if position == "wh_inverted":
        return bool(_WH_INITIAL.match(text)) and "?" in text
    return False


def _remove_subject_pronoun(
    text: str,
    pronoun_rule: Optional[Rule],
    level: int,
    verb_start: int,
    verb_length: int,
    position: str,
) -> Tuple[str, Optional[Edit]]:
    """Drop a subject pronoun left redundant by a downgrade. See the caller."""
    if pronoun_rule is None:
        return text, None
    form = pronoun_rule.forms[level]
    if not form:
        return text, None

    verb_end = verb_start + verb_length
    if position == "after":
        match = re.compile(
            rf"\s+{re.escape(form)}{RIGHT}", re.IGNORECASE
        ).match(text, verb_end)
        if match is None:
            return text, None
        start, end = match.start(), match.end()
    else:
        match = re.compile(
            rf"{LEFT}{re.escape(form)}\s+$", re.IGNORECASE
        ).search(text[:verb_start])
        if match is None:
            return text, None
        start, end = match.start(), match.end()

    rewritten = text[:start] + text[end:]
    if not text[:start].strip():
        # The pronoun was carrying the sentence's capital; whatever follows it
        # inherits it. Otherwise "Você é muito simpático" comes down to
        # "és muito simpático" — the mirror of the capital the insert path
        # hands over in the other direction.
        head = len(rewritten) - len(rewritten.lstrip())
        if head < len(rewritten):
            rewritten = (
                rewritten[:head]
                + rewritten[head].upper()
                + rewritten[head + 1:]
            )

    return rewritten, Edit(
        rule="subject.remove",
        gloss="subject pronoun redundant at the target level",
        before=form,
        after="",
        start=start,
        from_levels=(),
        to_level=level,
    )


def _polite_pronoun(table: LanguageTable) -> str:
    """
    The language's polite second-person pronoun, for the rudeness warning.

    Looked up by rule name rather than taken from ``rules[0]``. The warning used
    to read the first rule in the table and assumed it was the pronoun — which
    silently became false the moment prohibitive rules were added to the front
    of the Bengali table, and the warning started suggesting "করবেন না" (do not
    do) where it meant আপনি.
    """
    for name in ("pron.2sg.nom", "pron.2sg.subj", "pron.2sg"):
        for rule in table.rules:
            if rule.name == name:
                return rule.forms[table.fold(POLITE)]
    return ""


def _apply_softener(text: str, table: LanguageTable, level: int) -> str:
    particle = table.please[level]
    if not particle or not text.strip():
        return text
    if text.lstrip().startswith(particle.strip()):
        return text
    leading = text[: len(text) - len(text.lstrip())]
    return f"{leading}{particle}{text.lstrip()}"


def _apply_address_term(text: str, table: LanguageTable, level: int, addressee: str) -> str:
    forms = table.address_terms.get(addressee)
    if not forms:
        return text
    term = forms[level]
    if not term or not text.strip():
        return text
    if term in text:
        return text
    body = text.rstrip()
    tail = text[len(body):]
    return f"{term}, {body}{tail}" if body else text


def _normalise_code(code: str) -> str:
    if not isinstance(code, str):
        return ""
    return code.strip().lower().replace("_", "-").split("-")[0]
