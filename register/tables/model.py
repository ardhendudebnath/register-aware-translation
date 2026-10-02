"""
The data model every table is written in: a rule, its guards, and the
table that holds them.

The tables themselves are in the sibling modules, one per language family.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Optional, Tuple

from ..boundaries import LEFT, RIGHT

__all__ = ["FormGuard", "Rule", "LanguageTable"]



@dataclass(frozen=True)
class FormGuard:
    """
    Constraints for one surface form of a rule.

    The plain tuple form — ``(form, guard_before, guard_after, require_before,
    require_after[, require_adjacent])`` — still works and means the same
    thing. This spells the fields out, and adds the one thing a tuple cannot
    say: that this form wants a *weaker* blocker than its rule rather than an
    additional one.
    """

    form: str
    guard_before: str = ""
    guard_after: str = ""
    require_before: str = ""
    require_after: str = ""
    require_adjacent: str = ""
    #: Use this form's blocking guards *instead of* the rule's, not as well as.
    #:
    #: Rare, and it needs a reason. French is the case it exists for: a verb
    #: rule blocks on a non-second-person subject and steps over the clitics
    #: that can sit between, "vous" among them — because "je vous vois" has
    #: vois in the first person. In front of a vous *form* that cannot happen,
    #: so the vous form needs the same guard minus one alternative, which is
    #: less than the rule's rather than more.
    replace: bool = False

    def as_spec(self) -> Tuple[str, ...]:
        return (self.form, self.guard_before, self.guard_after,
                self.require_before, self.require_after, self.require_adjacent)


@dataclass(frozen=True)
class Rule:
    """One variant set: the same thing said at four levels of politeness."""

    name: str
    forms: Tuple[str, str, str, str]
    gloss: str = ""
    #: Match case-sensitively. Set this wherever capitalisation is the only
    #: thing separating a polite pronoun from an unrelated word: German
    #: ``Sie``/``sie`` (you/she), ``Ihr``/``ihr`` (your/her), Italian
    #: ``Lei``/``lei`` (you/she), ``Le``/``le`` (you/the). Matching those
    #: case-insensitively would rewrite "she" into "you".
    cased: bool = False
    #: Contextual constraints, checked against the text either side of a match.
    #: These exist because several languages use one surface form for more than
    #: one thing, and only the neighbouring words tell them apart:
    #:
    #:   German  ``Sie sind`` is *you*, ``Sie ist`` is *she*
    #:   German  ``Ich sehe Sie`` is accusative (-> dich), not nominative (-> du)
    #:   French  ``vous êtes`` is a subject, ``je vous vois`` is an object clitic
    #:
    #: ``guard_*`` must NOT match; ``require_*`` MUST. All four are ordinary
    #: regexes evaluated in Python rather than baked into the main pattern, so
    #: the *_before forms are free to be variable-width — which ``re`` would
    #: refuse in a lookbehind.
    guard_before: str = ""
    guard_after: str = ""
    require_before: str = ""
    require_after: str = ""
    #: Pattern that must appear immediately before *or* immediately after the
    #: match — a disjunction the two ``require_*`` fields cannot express,
    #: because setting both demands that both hold.
    #:
    #: This is the shape of the Spanish and Italian problem. Their polite
    #: pronouns take third-person agreement, so "está" is equally "you are"
    #: and "it is", and no property of the verb settles it. What settles it is
    #: whether the pronoun is standing next to the verb — "¿Cómo está usted?"
    #: against "La tienda está cerrada" — and Spanish puts it on either side
    #: ("Usted es muy amable", "Es usted muy amable").
    #:
    #: Guarding instead against third-person *subjects* is the natural first
    #: try and cannot be finished: él and ella are a closed class, but any
    #: noun phrase at all can be a subject, so "El tren llega tarde" and "La
    #: tienda está cerrada" keep arriving. Requiring the pronoun is the same
    #: constraint stated positively, over a class of two words instead of
    #: every noun in the language.
    require_adjacent: str = ""
    #: Per-form context overrides, as ``(form, guard_before, guard_after,
    #: require_before, require_after)``, optionally with ``require_adjacent``
    #: as a sixth. An empty string leaves that constraint at the rule's own
    #: value.
    #:
    #: Needed where a rule's forms are not equally ambiguous. Portuguese "estás"
    #: is unmistakably second person, but "está" is equally "he/she/it is" — so
    #: "A loja está fechada" ("the shop is closed") was reading as Polite.
    #: Gujarati છે is the same shape of problem in the other direction: it is
    #: the તું copula *and* the ordinary third-person copula, so it needs a
    #: second-person subject nearby to count, while છો needs nothing.
    #:
    #: Japanese だ is a third case: with no word boundaries at all it matches
    #: inside ください, so it needs a require_after, while です needs nothing.
    #:
    #: A rule-level guard cannot express any of these: constraining the whole
    #: rule would also constrain the unambiguous form.
    #:
    #: **Blocking guards accumulate; requirements do not.** A ``guard_before``
    #: or ``guard_after`` here is added to the rule's own — both say "never
    #: here", and both go on applying. A ``require_*`` replaces the rule's,
    #: because a requirement is a licence and the form's own is the precise
    #: one.
    #:
    #: That asymmetry is here because the other arrangement cost real bugs.
    #: When a form guard replaced the rule's blocker, giving one Portuguese
    #: form a positional guard silently dropped its third-person guard, and
    #: "Ele fala português" came back as "Ele falas português". The repair was
    #: to paste the rule's guard into the form's — in thirty places, each one
    #: a copy that could drift.
    #:
    #: Where a form genuinely needs a *weaker* blocker than its rule, say so
    #: with :class:`FormGuard` and ``replace=True``; French is the one case,
    #: and it is marked.
    form_guards: Tuple[object, ...] = ()
    #: Use this rule when rewriting, but never as evidence when detecting.
    #:
    #: For words that are register-*neutral* in themselves but have a polite
    #: elaboration. Italian "Grazie" is said at every level; "La ringrazio" is
    #: markedly formal. Listing Grazie in the low slots makes the upgrade work,
    #: but it also let a bare "Grazie a Lei" outvote the Lei and detect as
    #: Casual — the rule was supplying evidence for a level the word does not
    #: actually carry.
    rewrite_only: bool = False
    #: The mirror of it: read this rule as evidence, but never rewrite with it.
    #:
    #: For forms that identify the register reliably and cannot be *changed*
    #: on their own. German is the case: du and Sie say which register a
    #: sentence is in beyond doubt, but swapping the pronoun alone produces
    #: "Du sind", because German moves the pronoun and the verb together. The
    #: clause rules own the rewriting and pair the two; this lets the pronoun
    #: still be read where no clause rule matched, which was most of the
    #: language — the clause rules cover an enumerated verb list, and "Wohin
    #: fährst du?" detected nothing at all with a du sitting in it.
    detect_only: bool = False
    #: Name of a selector in :mod:`register.selectors`, for rules whose
    #: replacement cannot be read straight out of the tuple because it depends
    #: on surrounding words. French ``votre`` carries no gender, so downgrading
    #: it needs the gender of the noun that follows: ``votre maison`` -> ``ta
    #: maison`` but ``votre livre`` -> ``ton livre``. Referenced by name rather
    #: than as a callable so the tables stay plain data.
    select: str = ""

    def __post_init__(self) -> None:
        if len(self.forms) != 4:
            raise ValueError(f"rule {self.name!r} must have exactly 4 forms")
        if not any(f.strip() for f in self.forms):
            raise ValueError(f"rule {self.name!r} is entirely empty")

    @property
    def is_discriminative(self) -> bool:
        """True when the rule can tell levels apart at all."""
        return len(set(self.forms)) > 1

    def levels_for(self, surface: str) -> Tuple[int, ...]:
        """Which levels a given surface form is consistent with."""
        return tuple(i for i, f in enumerate(self.forms) if f == surface)


@dataclass(frozen=True)
class LanguageTable:
    code: str
    name: str
    canon: Tuple[int, int, int, int]
    rules: Tuple[Rule, ...]
    boundary: str = "delimited"
    #: Politeness scaffolding prepended to bare imperatives at high levels.
    please: Tuple[str, str, str, str] = ("", "", "", "")
    #: Vocatives for the address-term slot (blueprint 13.2 #3), keyed by
    #: an addressee tag. Empty for languages that do not require one.
    address_terms: Dict[str, Tuple[str, str, str, str]] = None  # type: ignore[assignment]
    #: (pattern, replacement) pairs run *before* matching, to expand contracted
    #: forms into the shape the rules are written in. French "t'attends" has to
    #: become "te attends" for the clitic rule to see it at all.
    normalise: Tuple[Tuple[str, str], ...] = ()
    #: (pattern, replacement) pairs run *after* rewriting, to put the language's
    #: orthography back — "te attends" -> "t'attends".
    elide: Tuple[Tuple[str, str], ...] = ()
    #: Subject pronoun to *insert* when the verb form alone cannot carry the
    #: level, one per level; "" means never insert at that level.
    #:
    #: Portuguese is the case this exists for. It conjugates você and o senhor
    #: identically, so upgrading "És muito simpático" to the verb form "É muito
    #: simpático" is correct and still ambiguous — a Portuguese speaker says
    #: "Você é muito simpático". No amount of extra rules fixes that, because
    #: the missing information is a whole word that was never in the source.
    #: Level 0 stays empty: the tu conjugation is distinct, so it needs no help.
    insert_subject: Tuple[str, str, str, str] = ("", "", "", "")
    #: Which side of the verb the inserted subject goes on.
    #:
    #: ``before`` is the default. ``after`` is Spanish, which wants it there
    #: in every sentence type ("Es usted muy amable", "¿Dónde vive usted?");
    #: fronting it reads as a contrast nobody asked for.
    #:
    #: ``wh_inverted`` is European Portuguese, which does both and picks by
    #: sentence type: subject-first in statements and yes/no questions ("Você
    #: é muito simpático", "Você tem tempo?"), inverted after a question word
    #: ("Onde mora o senhor?", "Como está você?").
    subject_position: str = "before"

    def __post_init__(self) -> None:
        if len(self.canon) != 4:
            raise ValueError(f"{self.code}: canon must have 4 entries")
        if self.subject_position not in ("before", "after", "wh_inverted"):
            raise ValueError(
                f"{self.code}: subject_position must be 'before', 'after' "
                f"or 'wh_inverted'"
            )
        if any(c not in (0, 1, 2, 3) for c in self.canon):
            raise ValueError(f"{self.code}: canon entries must be levels 0..3")
        if self.boundary not in ("delimited", "none"):
            raise ValueError(f"{self.code}: unknown boundary mode {self.boundary!r}")
        if not self.rules:
            raise ValueError(f"{self.code}: table has no rules")
        seen = set()
        for rule in self.rules:
            if rule.name in seen:
                raise ValueError(f"{self.code}: duplicate rule name {rule.name!r}")
            seen.add(rule.name)
            if not rule.is_discriminative:
                raise ValueError(
                    f"{self.code}: rule {rule.name!r} has four identical forms "
                    "and cannot carry register information"
                )
        if self.address_terms is None:
            object.__setattr__(self, "address_terms", {})

    @property
    def distinct_levels(self) -> Tuple[int, ...]:
        """The levels this language actually realises, in order."""
        return tuple(sorted(set(self.canon)))

    def fold(self, level: int) -> int:
        """Fold a nominal level onto the nearest level this language has."""
        return self.canon[level]


