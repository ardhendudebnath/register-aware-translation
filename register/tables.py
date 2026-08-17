"""
Register rule tables — the linguistic asset.

Every rule is a 4-tuple of equivalent surface forms, one per level
(Close, Casual, Polite, Formal). Because the tuple is symmetric, one dataset
drives all three jobs the engine needs:

    upgrading   casual surface form -> formal surface form
    downgrading formal surface form -> casual surface form
    detection   read the speaker's level from which column their words sit in

Adding a language means adding a table here, not writing code.

Conventions
-----------
* A slot may repeat across levels when the language does not distinguish them
  (Bengali uses আপনি for both Polite and Formal). Repeats are fine and are
  handled by the detector, which splits its vote across matching levels.
* A rule whose four forms are all identical carries no register information.
  ``LanguageTable`` rejects those at construction time rather than letting them
  silently pollute detection.
* ``canon`` folds a nominal level onto the nearest level the language actually
  realises, so German ``du`` reports as Casual rather than Close.
* ``boundary`` is ``"delimited"`` for scripts that separate words with spaces
  and ``"none"`` for scripts that do not (Japanese).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Optional, Tuple

from .boundaries import LEFT, RIGHT

__all__ = [
    "Rule",
    "LanguageTable",
    "TABLES",
    "supported_languages",
    "get_table",
    "has_table",
]


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
    form_guards: Tuple[Tuple[str, ...], ...] = ()
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


# --------------------------------------------------------------------------
# Indo-Aryan
# --------------------------------------------------------------------------

# A second-person pronoun somewhere to the left. Used to tell a present-tense
# reading from an imperative where Bengali spells them the same.
#
# The window is deliberately generous. It was {0,4} and that was too tight for
# ordinary sentences: in "আপনি কি আমাকে আপনার বই দিতে পারেন?" the pronoun is six
# words before the verb, so the guard blocked a correct rewrite and পারেন
# survived into the Close rendering.
_BN_2P_CONTEXT = r"(?:তুই|তুমি|আপনি)(?:\s+\S+){0,10}\s+"

# --------------------------------------------------------------------------
# Bengali verb paradigms.
#
# Register in Bengali runs through the *whole* conjugation, not just the
# present. Writing rules by hand covered the tenses someone happened to think
# of, and the gold set found the rest: of 1,776 graded rewrites, the engine
# reproduced only 68.8% exactly, and almost every failure was the same shape —
# the pronoun moved and the verb stayed behind. "তুমি কোথায় যাচ্ছ?" upgraded to
# "আপনি কোথায় যাচ্ছ?" instead of "আপনি কোথায় যাচ্ছেন?".
#
# So the paradigm is data now. Each entry is (তুই, তুমি, আপনি); Formal reuses
# the আপনি column, since what separates Polite from Formal in Bengali is
# lexical rather than inflectional.
# --------------------------------------------------------------------------

_BN_PARADIGMS: Dict[str, Dict[str, Tuple[str, str, str]]] = {
    "kora": {  # to do
        "pres": ("করিস", "করো", "করেন"),
        "cont": ("করছিস", "করছ", "করছেন"),
        "perf": ("করেছিস", "করেছ", "করেছেন"),
        "past": ("করলি", "করলে", "করলেন"),
        "pastcont": ("করছিলি", "করছিলে", "করছিলেন"),
        "habitual": ("করতিস", "করতে", "করতেন"),
        "future": ("করবি", "করবে", "করবেন"),
        "perfneg": ("করিসনি", "করোনি", "করেননি"),
        "prohibitive": ("করিস না", "কোরো না", "করবেন না"),
        "imp": ("কর", "করো", "করুন"),
    },
    "jaoa": {  # to go
        "pres": ("যাস", "যাও", "যান"),
        "cont": ("যাচ্ছিস", "যাচ্ছ", "যাচ্ছেন"),
        "perf": ("গেছিস", "গেছ", "গেছেন"),
        "past": ("গেলি", "গেলে", "গেলেন"),
        "pastcont": ("যাচ্ছিলি", "যাচ্ছিলে", "যাচ্ছিলেন"),
        "habitual": ("যেতিস", "যেতে", "যেতেন"),
        "future": ("যাবি", "যাবে", "যাবেন"),
        "perfneg": ("যাসনি", "যাওনি", "যাননি"),
        "prohibitive": ("যাস না", "যেও না", "যাবেন না"),
        "imp": ("যা", "যাও", "যান"),
    },
    "asa": {  # to come
        "pres": ("আসিস", "আসো", "আসেন"),
        "cont": ("আসছিস", "আসছ", "আসছেন"),
        "perf": ("এসেছিস", "এসেছ", "এসেছেন"),
        "past": ("এলি", "এলে", "এলেন"),
        "pastcont": ("আসছিলি", "আসছিলে", "আসছিলেন"),
        "habitual": ("আসতিস", "আসতে", "আসতেন"),
        "future": ("আসবি", "আসবে", "আসবেন"),
        "perfneg": ("আসিসনি", "আসোনি", "আসেননি"),
        "prohibitive": ("আসিস না", "এসো না", "আসবেন না"),
        "imp": ("আয়", "এসো", "আসুন"),
    },
    "khaoa": {  # to eat
        "pres": ("খাস", "খাও", "খান"),
        "cont": ("খাচ্ছিস", "খাচ্ছ", "খাচ্ছেন"),
        "perf": ("খেয়েছিস", "খেয়েছ", "খেয়েছেন"),
        "past": ("খেলি", "খেলে", "খেলেন"),
        "future": ("খাবি", "খাবে", "খাবেন"),
        "perfneg": ("খাসনি", "খাওনি", "খাননি"),
        "imp": ("খা", "খাও", "খান"),
    },
    "bola": {  # to say
        "pres": ("বলিস", "বলো", "বলেন"),
        "cont": ("বলছিস", "বলছ", "বলছেন"),
        "perf": ("বলেছিস", "বলেছ", "বলেছেন"),
        "past": ("বললি", "বললে", "বললেন"),
        "future": ("বলবি", "বলবে", "বলবেন"),
        "prohibitive": ("বলিস না", "বোলো না", "বলবেন না"),
        "imp": ("বল", "বলো", "বলুন"),
    },
    "deoa": {  # to give
        "pres": ("দিস", "দাও", "দেন"),
        "perf": ("দিয়েছিস", "দিয়েছ", "দিয়েছেন"),
        "future": ("দিবি", "দেবে", "দেবেন"),
        "imp": ("দে", "দাও", "দিন"),
    },
    "neoa": {  # to take
        "pres": ("নিস", "নাও", "নেন"),
        "perf": ("নিয়েছিস", "নিয়েছ", "নিয়েছেন"),
        "future": ("নিবি", "নেবে", "নেবেন"),
        "imp": ("নে", "নাও", "নিন"),
    },
    "thaka": {  # to stay
        "pres": ("থাকিস", "থাকো", "থাকেন"),
        "perf": ("থেকেছিস", "থেকেছ", "থেকেছেন"),
        "future": ("থাকবি", "থাকবে", "থাকবেন"),
    },
    "para": {  # to be able
        "pres": ("পারিস", "পারো", "পারেন"),
        "future": ("পারবি", "পারবে", "পারবেন"),
    },
    "dekha": {  # to see
        "pres": ("দেখিস", "দেখো", "দেখেন"),
        "perf": ("দেখেছিস", "দেখেছ", "দেখেছেন"),
        "imp": ("দেখ", "দেখো", "দেখুন"),
    },
    "suna": {  # to hear
        "pres": ("শুনিস", "শোনো", "শোনেন"),
        "imp": ("শোন", "শোনো", "শুনুন"),
    },
    "achhe": {  # to be, existential
        "pres": ("আছিস", "আছ", "আছেন"),
        "past": ("ছিলি", "ছিলে", "ছিলেন"),
    },
    "pora": {  # to read/study
        "pres": ("পড়িস", "পড়ো", "পড়েন"),
        "perf": ("পড়েছিস", "পড়েছ", "পড়েছেন"),
    },
    "paoa": {  # to get
        "pres": ("পাস", "পাও", "পান"),
        "cont": ("পাচ্ছিস", "পাচ্ছ", "পাচ্ছেন"),
        "perf": ("পেয়েছিস", "পেয়েছ", "পেয়েছেন"),
    },
    "bojha": {  # to understand
        "pres": ("বুঝিস", "বোঝো", "বোঝেন"),
        "perf": ("বুঝেছিস", "বুঝেছ", "বুঝেছেন"),
    },
    "ghumano": {  # to sleep
        "pres": ("ঘুমাস", "ঘুমাও", "ঘুমান"),
        "perf": ("ঘুমিয়েছিস", "ঘুমিয়েছ", "ঘুমিয়েছেন"),
    },
    "pathano": {"perf": ("পাঠিয়েছিস", "পাঠিয়েছ", "পাঠিয়েছেন")},
    "otha": {"perf": ("উঠেছিস", "উঠেছ", "উঠেছেন")},
    "chena": {"pres": ("চিনিস", "চেনো", "চেনেন")},
    "chaoa": {"pres": ("চাস", "চাও", "চান")},
    "jana": {"pres": ("জানিস", "জানো", "জানেন")},
    "hooa": {"pres": ("হোস", "হও", "হন")},
    "bhoga": {"cont": ("ভুগছিস", "ভুগছ", "ভুগছেন")},
    "khoja": {"cont": ("খুঁজছিস", "খুঁজছ", "খুঁজছেন")},
    "phera": {"future": ("ফিরবি", "ফিরবে", "ফিরবেন")},
    "lekha": {
        "pres": ("লিখিস", "লেখো", "লেখেন"),
        "imp": ("লেখ", "লেখো", "লিখুন"),
    },
    # Imperative-only entries, for verbs that appear in commands far more often
    # than in second-person statements.
    # নাম is also the ordinary noun "name", which is vastly more common than
    # the imperative "get down". The gold set caught this reading "আপনার নাম কী?"
    # as Close. An imperative ends its clause; the noun does not — see
    # _BN_CLAUSE_FINAL below.
    "nama": {"imp": ("নাম", "নামো", "নামুন")},
    "daka": {"imp": ("ডাক", "ডাকো", "ডাকুন")},
    "khola": {"imp": ("খোল", "খোলো", "খুলুন")},
    "chala": {"imp": ("চল", "চলো", "চলুন")},
    "bosa": {"imp": ("বোস", "বসো", "বসুন")},
    "ana": {"imp": ("আন", "আনো", "আনুন")},
    "sara": {"imp": ("সর", "সরো", "সরুন")},
    "rakha": {"imp": ("রাখ", "রাখো", "রাখুন")},
    "bhaba": {"imp": ("ভাব", "ভাবো", "ভাবুন")},
    "ghora": {"imp": ("ঘোর", "ঘোরো", "ঘুরুন")},
    "darano": {"imp": ("দাঁড়া", "দাঁড়াও", "দাঁড়ান")},
    "soa": {"imp": ("শো", "শোও", "শুয়ে পড়ুন")},
    "kamano": {"imp": ("কমা", "কমাও", "কমান")},
    "sekhano": {"imp": ("শেখা", "শেখাও", "শেখান")},
}

#: Declaration order. Present tense must come before the imperative: Bengali
#: spells "you do" and "do!" identically as করো, the matcher breaks equal-length
#: ties by declaration order, and only the present-tense rule carries the
#: pronoun guard that tells them apart.
_BN_TENSE_ORDER = (
    "prohibitive", "perfneg", "pastcont", "habitual", "cont",
    "perf", "past", "future", "pres", "imp",
)

#: Tenses whose তুমি form collides with the imperative, so the present-tense
#: reading has to prove there is a second-person pronoun nearby.
_BN_NEEDS_PRONOUN = {"pres"}

#: An imperative closes its clause. Required by verbs whose imperative is also
#: a common noun, so the noun reading is left alone.
_BN_CLAUSE_FINAL = r"\s*(?:[।!?.,]|$)"

#: Verbs whose imperative form collides with an ordinary noun.
_BN_NOUN_COLLIDING_IMPERATIVES = {"nama"}   # নাম = "name" / "get down!"

#: The habitual-past তুমি form is spelled exactly like the infinitive: করতে is
#: both "you used to do" and the "to do" in "করতে পারিস". An infinitive is
#: followed by an auxiliary, a habitual past is not — so block the habitual
#: reading in front of one. Without this, "সাহায্য করতে পারিস" downgraded to the
#: nonsense "সাহায্য করতিস পারিস".
_BN_AUXILIARY_FOLLOWS = (
    r"\s+(?:পার|পারি|পারিস|পারো|পারেন|পারব|পারবি|পারবে|পারবেন|"
    r"চাই|চাস|চাও|চান|হবে|হয়|হল|দাও|দে|দিন|দিতে|যাব|থাক|লাগ)"
)


def _bn_verb_rules() -> Tuple[Rule, ...]:
    out = []
    for tense in _BN_TENSE_ORDER:
        for verb, paradigm in _BN_PARADIGMS.items():
            forms = paradigm.get(tense)
            if not forms:
                continue
            close, casual, polite = forms
            if len({close, casual, polite}) == 1:
                continue  # carries no register information
            # The pronoun requirement exists purely to separate a present-tense
            # reading from an identically spelled imperative. A verb with no
            # imperative — or one whose imperative differs — has nothing to be
            # confused with, so making it prove a nearby pronoun only loses
            # correct rewrites. পারা ("be able") is the case that matters: you
            # cannot command it, and it appears in almost every polite request.
            imperative = paradigm.get("imp")
            collides = bool(imperative) and imperative[1] == casual
            before = (
                _BN_2P_CONTEXT
                if tense in _BN_NEEDS_PRONOUN and collides
                else ""
            )
            after = (
                _BN_CLAUSE_FINAL
                if tense == "imp" and verb in _BN_NOUN_COLLIDING_IMPERATIVES
                else ""
            )
            guard_after = _BN_AUXILIARY_FOLLOWS if tense == "habitual" else ""
            out.append(
                Rule(f"v.{verb}.{tense}", (close, casual, polite, polite),
                     f"{verb} ({tense})",
                     require_before=before, require_after=after,
                     guard_after=guard_after)
            )
    return tuple(out)

BENGALI = LanguageTable(
    code="bn",
    name="Bengali",
    canon=(0, 1, 2, 3),
    please=("", "", "একটু ", "দয়া করে "),
    address_terms={
        "older_man": ("", "দাদা", "দাদা", "স্যার"),
        "older_woman": ("", "দিদি", "দিদি", "ম্যাডাম"),
        "elder_man": ("", "কাকু", "কাকু", "স্যার"),
        "elder_woman": ("", "কাকিমা", "কাকিমা", "ম্যাডাম"),
        "peer": ("", "ভাই", "দাদা", "স্যার"),
        "official": ("", "স্যার", "স্যার", "স্যার"),
    },
    rules=_bn_verb_rules() + (
        Rule("pron.2sg.nom", ("তুই", "তুমি", "আপনি", "আপনি"), "you"),
        Rule("pron.2sg.gen", ("তোর", "তোমার", "আপনার", "আপনার"), "your"),
        Rule("pron.2sg.acc", ("তোকে", "তোমাকে", "আপনাকে", "আপনাকে"), "you (obj)"),
        Rule("pron.2sg.loc", ("তোতে", "তোমাতে", "আপনাতে", "আপনাতে"), "in/at you"),
        Rule("pron.2pl.nom", ("তোরা", "তোমরা", "আপনারা", "আপনারা"), "you (pl)"),
        Rule("pron.2pl.gen", ("তোদের", "তোমাদের", "আপনাদের", "আপনাদের"), "your (pl)"),
        Rule("greet.hello", ("কি রে", "হ্যালো", "নমস্কার", "নমস্কার"), "hello"),
        # ধন্যবাদ is register-neutral — you say it to a sibling and to a
        # magistrate alike. The earlier table put থ্যাঙ্কস in the Close slot,
        # which made downgrading rewrite a perfectly good Bengali word into a
        # code-switched one nobody asked for. Only the Formal slot differs.
        Rule("greet.thanks", ("ধন্যবাদ", "ধন্যবাদ", "ধন্যবাদ", "অসংখ্য ধন্যবাদ"), "thanks"),
        Rule("greet.sorry", ("সরি", "সরি", "দুঃখিত", "আমি ক্ষমাপ্রার্থী"), "sorry"),
        # Polite and Formal share আপনি, so what separates them is lexical. Until
        # these were rules, every Formal sentence in the gold set read back as
        # Polite — the engine had no way to see the difference it was being
        # asked about.
        #
        # Only the Formal slot is filled. The first attempt put a Polite-level
        # alternative in each (একটু for দয়া করে, অনেক for অসংখ্য) and made things
        # worse: those are ordinary intensifiers meaning "a little" and "a lot",
        # they appear all over neutral speech, and treating them as register
        # markers dragged unrelated sentences toward Polite. A marker earns its
        # place only if its *presence* is evidence; একটু is not.
        Rule("courtesy.please", ("", "", "", "দয়া করে"), "please (formal)"),
        Rule("courtesy.kindly", ("", "", "", "অনুগ্রহ করে"), "kindly (formal)"),
        Rule("courtesy.sir", ("", "", "", "মহোদয়"), "sir (formal address)"),
        Rule("courtesy.grateful", ("", "", "", "কৃতজ্ঞ"), "grateful (formal)"),
        Rule("courtesy.many", ("", "", "", "অসংখ্য"), "innumerable (formal)"),
        Rule("courtesy.accepted", ("", "", "", "গৃহীত"), "accepted (formal)"),
        Rule("courtesy.consider", ("", "", "", "বিবেচনা"), "consideration (formal)"),
        Rule("courtesy.docs", ("", "", "", "নথিপত্র"), "documents (formal)"),
        Rule("courtesy.signature", ("", "", "", "স্বাক্ষর"), "signature (formal)"),
        Rule("courtesy.cooperation", ("", "", "", "সহযোগিতা"), "cooperation (formal)"),
        Rule("courtesy.identity", ("", "", "", "পরিচয়পত্র"), "identity card (formal)"),
    ),
)

# --------------------------------------------------------------------------
# Hindi verb paradigms.
#
# Same lesson Bengali taught, on a smaller table: hand-written rules covered
# the tenses someone happened to think of. Against 249 gold rows the engine
# detected only 72.3% and reproduced 57.0% exactly, and the failures were
# concentrated in tenses that simply had no rule — the continuous, the future,
# the perfective, and the ergative pronouns that Hindi past tense requires.
#
# Each entry is (तू, तुम, आप). Formal reuses the आप column: what separates
# Polite from Formal in Hindi is lexical (कृपया, Sanskritised vocabulary), not
# inflectional.
#
# Gendered slots are suffixed .m/.f. The participle agrees with the *addressee*
# here, which is a different axis from the speaker agreement in
# `register.speaker` — a man saying "you do" to a woman uses करती हो.
# --------------------------------------------------------------------------

_HI_PARADIGMS: Dict[str, Dict[str, Tuple[str, str, str]]] = {
    "karna": {  # to do
        "pres.m": ("करता है", "करते हो", "करते हैं"),
        "pres.f": ("करती है", "करती हो", "करती हैं"),
        "cont.m": ("कर रहा है", "कर रहे हो", "कर रहे हैं"),
        "cont.f": ("कर रही है", "कर रही हो", "कर रही हैं"),
        "future.m": ("करेगा", "करोगे", "करेंगे"),
        "future.f": ("करेगी", "करोगी", "करेंगी"),
        "subj": ("करे", "करो", "करें"),
        "prohibitive": ("मत कर", "मत करो", "मत कीजिए"),
        "imp": ("कर", "करो", "कीजिए"),
    },
    "jana": {  # to go
        "pres.m": ("जाता है", "जाते हो", "जाते हैं"),
        "pres.f": ("जाती है", "जाती हो", "जाती हैं"),
        "cont.m": ("जा रहा है", "जा रहे हो", "जा रहे हैं"),
        "cont.f": ("जा रही है", "जा रही हो", "जा रही हैं"),
        "future.m": ("जाएगा", "जाओगे", "जाएँगे"),
        "future.f": ("जाएगी", "जाओगी", "जाएँगी"),
        "prohibitive": ("मत जा", "मत जाओ", "मत जाइए"),
        "imp": ("जा", "जाओ", "जाइए"),
    },
    "lautna": {  # to return
        "pres.m": ("लौटता है", "लौटते हो", "लौटते हैं"),
        "pres.f": ("लौटती है", "लौटती हो", "लौटती हैं"),
        "future.m": ("लौटेगा", "लौटोगे", "लौटेंगे"),
        "future.f": ("लौटेगी", "लौटोगी", "लौटेंगी"),
        "imp": ("लौट", "लौटो", "लौटिए"),
    },
    "ana": {  # to come
        "pres.m": ("आता है", "आते हो", "आते हैं"),
        "pres.f": ("आती है", "आती हो", "आती हैं"),
        "cont.m": ("आ रहा है", "आ रहे हो", "आ रहे हैं"),
        "cont.f": ("आ रही है", "आ रही हो", "आ रही हैं"),
        # The perfective agrees with the pronoun like everything else, and it
        # appears bare under negation ("तू क्यों नहीं आया?") as well as with
        # the copula ("तू क्यों आया है?"), so both are forms in their own
        # right. The person guards keep the bare one off third-person
        # subjects, which share it.
        "perf.m": ("आया", "आए", "आए"),
        "perf.f": ("आई", "आई", "आईं"),
        "perf.pres.m": ("आया है", "आए हो", "आए हैं"),
        "perf.pres.f": ("आई है", "आई हो", "आई हैं"),
        "future.m": ("आएगा", "आओगे", "आएँगे"),
        "future.f": ("आएगी", "आओगी", "आएँगी"),
        "prohibitive": ("मत आ", "मत आओ", "मत आइए"),
        "imp": ("आ", "आओ", "आइए"),
    },
    "rahna": {  # to live, to stay
        "pres.m": ("रहता है", "रहते हो", "रहते हैं"),
        "pres.f": ("रहती है", "रहती हो", "रहती हैं"),
        "future.m": ("रहेगा", "रहोगे", "रहेंगे"),
        "imp": ("रह", "रहो", "रहिए"),
    },
    "bolna": {  # to speak
        "pres.m": ("बोलता है", "बोलते हो", "बोलते हैं"),
        "pres.f": ("बोलती है", "बोलती हो", "बोलती हैं"),
        "cont.m": ("बोल रहा है", "बोल रहे हो", "बोल रहे हैं"),
        "prohibitive": ("मत बोल", "मत बोलो", "मत बोलिए"),
        "imp": ("बोल", "बोलो", "बोलिए"),
    },
    "kahna": {  # to say
        "pres.m": ("कहता है", "कहते हो", "कहते हैं"),
        "imp": ("कह", "कहो", "कहिए"),
    },
    "batana": {  # to tell
        "pres.m": ("बताता है", "बताते हो", "बताते हैं"),
        "future.m": ("बताएगा", "बताओगे", "बताएँगे"),
        "imp": ("बता", "बताओ", "बताइए"),
    },
    "dekhna": {  # to see
        "pres.m": ("देखता है", "देखते हो", "देखते हैं"),
        "cont.m": ("देख रहा है", "देख रहे हो", "देख रहे हैं"),
        "imp": ("देख", "देखो", "देखिए"),
    },
    "sunna": {  # to hear
        "pres.m": ("सुनता है", "सुनते हो", "सुनते हैं"),
        "imp": ("सुन", "सुनो", "सुनिए"),
    },
    "khana": {  # to eat
        "pres.m": ("खाता है", "खाते हो", "खाते हैं"),
        "cont.m": ("खा रहा है", "खा रहे हो", "खा रहे हैं"),
        "future.m": ("खाएगा", "खाओगे", "खाएँगे"),
        "imp": ("खा", "खाओ", "खाइए"),
    },
    "pina": {  # to drink
        "pres.m": ("पीता है", "पीते हो", "पीते हैं"),
        "imp": ("पी", "पियो", "पीजिए"),
    },
    "lena": {  # to take
        "future.m": ("लेगा", "लोगे", "लेंगे"),
        "imp": ("ले", "लो", "लीजिए"),
    },
    "dena": {  # to give
        "future.m": ("देगा", "दोगे", "देंगे"),
        "imp": ("दे", "दो", "दीजिए"),
    },
    "baithna": {"imp": ("बैठ", "बैठो", "बैठिए")},
    "uthna": {"imp": ("उठ", "उठो", "उठिए")},
    "manna": {  # to mind, to take offence
        "prohibitive": ("मत मान", "मत मानो", "मत मानिए"),
    },
    "rukna": {
        "pres.m": ("रुकता है", "रुकते हो", "रुकते हैं"),
        "future.m": ("रुकेगा", "रुकोगे", "रुकेंगे"),
        "future.f": ("रुकेगी", "रुकोगी", "रुकेंगी"),
        "imp": ("रुक", "रुको", "रुकिए"),
        "prohibitive": ("मत रुक", "मत रुको", "मत रुकिए"),
    },
    "chalna": {
        "pres.m": ("चलता है", "चलते हो", "चलते हैं"),
        "imp": ("चल", "चलो", "चलिए"),
    },
    "sona": {
        "pres.m": ("सोता है", "सोते हो", "सोते हैं"),
        "imp": ("सो", "सोओ", "सोइए"),
    },
    "padhna": {  # to read, to study
        "pres.m": ("पढ़ता है", "पढ़ते हो", "पढ़ते हैं"),
        "imp": ("पढ़", "पढ़ो", "पढ़िए"),
    },
    "likhna": {
        "pres.m": ("लिखता है", "लिखते हो", "लिखते हैं"),
        "imp": ("लिख", "लिखो", "लिखिए"),
    },
    "samajhna": {  # to understand
        "pres.m": ("समझता है", "समझते हो", "समझते हैं"),
        "imp": ("समझ", "समझो", "समझिए"),
    },
    "janna": {  # to know
        "pres.m": ("जानता है", "जानते हो", "जानते हैं"),
        "pres.f": ("जानती है", "जानती हो", "जानती हैं"),
        # Hindi drops the copula under negation — "तू नहीं जानता?", not
        # "तू नहीं जानता है?" — so the bare participle is a form in its own
        # right. It is also the third-person participle, which is why the
        # generator makes these require a preceding नहीं.
        "pres.neg.m": ("जानता", "जानते", "जानते"),
        "pres.neg.f": ("जानती", "जानती", "जानतीं"),
    },
    "chahna": {  # to want
        "pres.m": ("चाहता है", "चाहते हो", "चाहते हैं"),
    },
    "sakna": {  # can — the most common request frame in Hindi
        "pres.m": ("सकता है", "सकते हो", "सकते हैं"),
        "pres.f": ("सकती है", "सकती हो", "सकती हैं"),
        "future.m": ("सकेगा", "सकोगे", "सकेंगे"),
    },
    "milna": {"future.m": ("मिलेगा", "मिलोगे", "मिलेंगे"), "imp": ("मिल", "मिलो", "मिलिए")},
    "lana": {"imp": ("ला", "लाओ", "लाइए")},
    "kharidna": {"imp": ("खरीद", "खरीदो", "खरीदिए")},
    "bulana": {"imp": ("बुला", "बुलाओ", "बुलाइए")},
    "puchhna": {"imp": ("पूछ", "पूछो", "पूछिए")},
    "utarna": {"imp": ("उतर", "उतरो", "उतरिए")},
    "kholna": {"imp": ("खोल", "खोलो", "खोलिए")},
    "band_karna": {"imp": ("बंद कर", "बंद करो", "बंद कीजिए")},
    "hatna": {"imp": ("हट", "हटो", "हटिए")},
    "letna": {"imp": ("लेट", "लेटो", "लेटिए")},
    "maf_karna": {"imp": ("माफ़ कर", "माफ़ करो", "माफ़ कीजिए")},
    "intezar": {"imp": ("इंतज़ार कर", "इंतज़ार करो", "इंतज़ार कीजिए")},
}

#: Declaration order. Longer, more specific tenses first; the bare imperative
#: last, because it is the shortest string and would otherwise win ties against
#: the continuous and present forms that contain it.
_HI_TENSE_ORDER = (
    "cont.m", "cont.f", "perf.pres.m", "perf.pres.f",
    "future.m", "future.f", "prohibitive",
    "pres.m", "pres.f", "pres.neg.m", "pres.neg.f",
    "perf.m", "perf.f", "subj", "imp",
)

#: A second-person pronoun to the left, for the tenses whose तुम form collides
#: with the imperative — करो is both "you do" and "do!". Same idea as Bengali,
#: same generous window: the pronoun is often several words back.
_HI_2P_CONTEXT = r"(?:तू|तुम|आप|तूने|तुमने|आपने)(?:\s+\S+){0,10}\s+"

#: Tenses that need it.
_HI_NEEDS_PRONOUN = {"subj"}

# --------------------------------------------------------------------------
# Hindi has the Urdu copula problem, which is no surprise — they are the same
# grammar in two scripts. है is the तू copula *and* the third-person copula,
# and unguarded it matched every statement in the language: "आपका नाम क्या है?"
# read Close off the copula while the आपका said Polite, and "तेरा नाम क्या है?"
# was conjugated down to "तुम्हारा नाम क्या हो?" on a verb whose subject is the
# name, not the listener.
#
# What licenses the second-person reading is the nominative तू and only that.
# तेरा is a genitive modifying a noun. Hindi is verb-final, so a bounded
# backscan from the copula reaches the pronoun.
# --------------------------------------------------------------------------

#: तूने as well as तू: the ergative fuses the postposition onto the pronoun, so
#: a boundary-respecting match for तू does not find it inside तूने — and the
#: perfective, which is exactly where ergative subjects live, would then have
#: nothing licensing it.
_HI_TU_BEFORE = rf"{LEFT}(?:तू|तूने){RIGHT}(?:\s+\S+){{0,10}}\s+"

#: The mirror of the same problem at the other end of the scale. The आप forms
#: are plural agreement, which Hindi also uses for हम and वे — so "हम कल
#: जाएँगे" (we will go tomorrow) read as Polite, and asking for Close
#: conjugated it to "हम कल जाएगा".
_HI_PLURAL_SUBJECT = rf"{LEFT}(?:हम|वे|ये|हमने|उन्होंने|इन्होंने){RIGHT}(?:\s+\S+){{0,10}}\s+"

#: The negated present drops the copula, leaving a bare participle that is also
#: the third-person one. नहीं is what marks the construction.
_HI_NEGATIVE_BEFORE = r"नहीं\s+"

#: A bare stem before an auxiliary is not an imperative: Hindi builds its
#: progressives, modals and compound verbs on the same form the तू imperative
#: takes, so "कर सकता है" and "चल रही है" look like commands to a matcher that
#: stops at the word.
_HI_AUX_AFTER = (
    r"\s+(?:रहा|रही|रहे"                        # progressive
    r"|सकता|सकती|सकते|सको|सके|सकें"             # modal: can
    r"|पाता|पाती|पाते|चुका|चुकी|चुके"           # manage to, have already
    r"|गया|गयी|गई|गये|गए|लिया|ली|लिए|दिया|दी|दिए)"  # compound verbs
)


def _hi_verb_rules() -> Tuple[Rule, ...]:
    out = []
    for tense in _HI_TENSE_ORDER:
        for verb, paradigm in _HI_PARADIGMS.items():
            forms = paradigm.get(tense)
            if not forms:
                continue
            tu, tum, aap = forms
            if len({tu, tum, aap}) == 1:
                continue  # carries no register information

            guards = []
            if tense not in ("imp", "prohibitive"):
                # Every finite तू form is singular, which is also the
                # third-person agreement — "वह क्या करता है?" is the same
                # string as the तू question.
                guards.append((tu, "", "", _HI_TU_BEFORE, "", ""))
                # And every आप form is plural agreement, which हम and वे share.
                guards.append((aap, _HI_PLURAL_SUBJECT, "", "", "", ""))
            # Only guard where the imperative genuinely collides.
            imperative = paradigm.get("imp")
            collides = bool(imperative) and imperative[1] == tum
            if tense in _HI_NEEDS_PRONOUN or (tense.startswith("pres") and collides):
                guards.append((tum, "", "", _HI_2P_CONTEXT, "", ""))

            out.append(
                Rule(f"v.{verb}.{tense}", (tu, tum, aap, aap),
                     f"{verb} · {tense}",
                     guard_after=_HI_AUX_AFTER if tense == "imp" else "",
                     require_before=(_HI_NEGATIVE_BEFORE
                                     if tense.startswith("pres.neg") else ""),
                     form_guards=tuple(guards))
            )
    return tuple(out)


HINDI = LanguageTable(
    code="hi",
    name="Hindi",
    canon=(0, 1, 2, 3),
    please=("", "", "ज़रा ", "कृपया "),
    address_terms={
        "older_man": ("", "भैया", "भाई साहब", "सर"),
        "older_woman": ("", "दीदी", "बहन जी", "मैडम"),
        "elder_man": ("", "अंकल", "अंकल जी", "सर"),
        "elder_woman": ("", "आंटी", "आंटी जी", "मैडम"),
        "peer": ("", "यार", "भाई", "सर"),
        "official": ("", "साहब", "साहब", "सर"),
    },
    rules=_hi_verb_rules() + (
        # Ergative — Hindi marks the subject of a perfective transitive with ने,
        # so the whole past tense is invisible without these. "तुमने खाना खाया?"
        # had no rule at all.
        Rule("pron.2sg.erg", ("तूने", "तुमने", "आपने", "आपने"), "you (ergative)"),
        Rule("pron.2sg.nom", ("तू", "तुम", "आप", "आप"), "you"),
        Rule("pron.2sg.acc", ("तुझे", "तुम्हें", "आपको", "आपको"), "to you"),
        Rule("pron.2sg.acc.ko", ("तुझको", "तुमको", "आपको", "आपको"), "to you (को)"),
        Rule("pron.2sg.abl", ("तुझसे", "तुमसे", "आपसे", "आपसे"), "from/with you"),
        Rule("pron.2sg.obl", ("तुझ", "तुम", "आप", "आप"), "you (oblique)"),
        Rule("pron.2sg.gen.m", ("तेरा", "तुम्हारा", "आपका", "आपका"), "your (m)"),
        Rule("pron.2sg.gen.f", ("तेरी", "तुम्हारी", "आपकी", "आपकी"), "your (f)"),
        Rule("pron.2sg.gen.pl", ("तेरे", "तुम्हारे", "आपके", "आपके"), "your (pl/obl)"),
        # है and था are third person as much as they are तू; हो and हैं are
        # not. हो also needs its auxiliary reading blocked — "बारिश हो रही है"
        # is the weather.
        Rule("cop.pres", ("है", "हो", "हैं", "हैं"), "you are",
             form_guards=(
                 ("है", "", "", _HI_TU_BEFORE, "", ""),
                 ("हो", "", _HI_AUX_AFTER, "", "", ""),
                 ("हैं", _HI_PLURAL_SUBJECT, "", "", "", ""),
             )),
        Rule("cop.past.m", ("था", "थे", "थे", "थे"), "you were (m)",
             form_guards=(("था", "", "", _HI_TU_BEFORE, "", ""),)),
        Rule("cop.past.f", ("थी", "थीं", "थीं", "थीं"), "you were (f)",
             form_guards=(("थी", "", "", _HI_TU_BEFORE, "", ""),)),
        # Hindi agrees the predicate adjective with the pronoun, and nothing
        # was moving it: "तू कैसा है?" upgraded to "तुम कैसा हो?" — the right
        # pronoun left in the wrong concord.
        # Only as a predicate adjective, which is what the copula after it
        # marks. The same word is also the manner adverb "how", and there it is
        # invariant and about the verb rather than the listener: "तू कैसे
        # आया?" (how did you come?) must keep कैसे at every level, and was
        # being agreed down to "तू कैसा आया?".
        # rewrite_only, and not for the usual reason. The honorific कैसे fills
        # three of the four slots, so it is nearly uninformative — but a vote
        # is a vote, and spreading a third across three levels *diluted* the
        # confidence of the pronoun and copula beside it. "आप कैसे हैं?" still
        # came out Polite, at 0.44 instead of 0.5, and the pipeline gates the
        # register engine at 0.5 — so the sentence fell through to the
        # statistical classifier and came back Close. The rule only fires with
        # a second-person pronoun already in front of it, and that pronoun has
        # voted; this one has nothing to add and should only do its own job.
        Rule("adj.kaisa", ("कैसा", "कैसे", "कैसे", "कैसे"), "how (m)",
             require_before=_HI_2P_CONTEXT,
             require_after=r"\s+(?:है|हो|हैं|था|थे|थी|थीं)",
             rewrite_only=True),
        Rule("greet.hello", ("ओए", "हैलो", "नमस्ते", "नमस्कार"), "hello"),
        # धन्यवाद is neutral below Formal — the gold says so plainly, with the
        # word constant across all four columns and only the pronoun moving —
        # and हार्दिक is what lifts it, which is the form the gold's own Formal
        # row uses. शुक्रिया and थैंक्स go: both are real Hindi, but pinning
        # them to levels made "तुझे धन्यवाद" read Polite off the noun instead
        # of Close off the तुझे.
        Rule("greet.thanks", ("धन्यवाद", "धन्यवाद", "धन्यवाद", "हार्दिक धन्यवाद"),
             "thanks"),
        Rule("greet.sorry", ("सॉरी", "सॉरी", "माफ़ कीजिए", "क्षमा कीजिए"), "sorry"),
        # कृपया is what separates Formal from Polite in a request — the आप
        # imperative covers both — so it has to be readable, not merely
        # insertable. ज़रा stays out: it means "a little" and softens a request
        # at any level.
        Rule("polite.particle", ("", "", "", "कृपया"), "please"),
        # Written-register vocabulary. These are the words that make a sentence
        # Formal when the pronoun has already gone as far as आप can take it:
        # आभारी over शुक्रगुज़ार, खेद over अफ़सोस, महोदय over साहब.
        Rule("voc.sir", ("", "भाई", "साहब", "महोदय"), "sir"),
        Rule("lex.grateful", ("खुश", "खुश", "शुक्रगुज़ार", "आभारी"), "grateful"),
        Rule("lex.regret", ("दुख", "दुख", "अफ़सोस", "खेद"), "regret"),
        # The Perso-Arabic/Sanskritic pair again, this time in the register of
        # official paperwork: अर्ज़ी is what you file at a counter, आवेदन what
        # the form calls it.
        Rule("lex.application", ("अर्ज़ी", "अर्ज़ी", "अर्ज़ी", "आवेदन"), "application"),
    ),
)

# --------------------------------------------------------------------------
# Marathi verb paradigms.
#
# Imperative-only again, and the gold set found two things. The verb paradigm
# was absent, so "तू काय करतोस?" detected nothing. And the genitive was missing
# its *neuter*: the table had तुझा (m) and तुझी (f) but not तुझं, which is the
# form in "तुझं नाव काय आहे?" — one of the most ordinary sentences in the
# language. Marathi has three genders and the table covered two.
#
# Each entry is (तू, तुम्ही, आपण). Verbs whose forms do not differ across the
# three are skipped by the generator rather than listed as dead rules.
# --------------------------------------------------------------------------

_MR_PARADIGMS: Dict[str, Dict[str, Tuple[str, str, str]]] = {
    "karne": {  # to do
        "pres.m": ("करतोस", "करता", "करता"),
        "pres.f": ("करतेस", "करता", "करता"),
        "future": ("करशील", "कराल", "कराल"),
        "imp": ("कर", "करा", "करा"),
    },
    "yene": {  # to come
        "pres.m": ("येतोस", "येता", "येता"),
        "pres.f": ("येतेस", "येता", "येता"),
        "future": ("येशील", "याल", "याल"),
        "imp": ("ये", "या", "या"),
    },
    "jane": {  # to go — the imperative is जा at every level, so only the
               # finite forms carry register
        "pres.m": ("जातोस", "जाता", "जाता"),
        "pres.f": ("जातेस", "जाता", "जाता"),
        "future": ("जाशील", "जाल", "जाल"),
    },
    "basne": {
        "pres.m": ("बसतोस", "बसता", "बसता"),
        "imp": ("बस", "बसा", "बसा"),
    },
    "bolne": {
        "pres.m": ("बोलतोस", "बोलता", "बोलता"),
        "pres.f": ("बोलतेस", "बोलता", "बोलता"),
        "imp": ("बोल", "बोला", "बोला"),
    },
    "baghne": {
        "pres.m": ("बघतोस", "बघता", "बघता"),
        "imp": ("बघ", "बघा", "बघा"),
    },
    "aikne": {
        "pres.m": ("ऐकतोस", "ऐकता", "ऐकता"),
        "imp": ("ऐक", "ऐका", "ऐका"),
    },
    "sangne": {
        "pres.m": ("सांगतोस", "सांगता", "सांगता"),
        "imp": ("सांग", "सांगा", "सांगा"),
    },
    "rahane": {  # to live, to stay
        "pres.m": ("राहतोस", "राहता", "राहता"),
        "pres.f": ("राहतेस", "राहता", "राहता"),
    },
    "khane": {
        "pres.m": ("खातोस", "खाता", "खाता"),
        "future": ("खाशील", "खाल", "खाल"),
    },
    "shakne": {  # can — the common request frame
        "pres.m": ("शकतोस", "शकता", "शकता"),
        "pres.f": ("शकतेस", "शकता", "शकता"),
    },
    "janne": {"pres.m": ("जाणतोस", "जाणता", "जाणता")},
    "samajne": {"pres.m": ("समजतोस", "समजता", "समजता")},
    "lihine": {
        "pres.m": ("लिहितोस", "लिहिता", "लिहिता"),
        "imp": ("लिही", "लिहा", "लिहा"),
    },
    "vachne": {
        "pres.m": ("वाचतोस", "वाचता", "वाचता"),
        "imp": ("वाच", "वाचा", "वाचा"),
    },
    "ghene": {"imp": ("घे", "घ्या", "घ्या")},
    "dene": {"imp": ("दे", "द्या", "द्या")},
    "thambne": {"imp": ("थांब", "थांबा", "थांबा")},
    "utarne": {"imp": ("उतर", "उतरा", "उतरा")},
    "ughadne": {"imp": ("उघड", "उघडा", "उघडा")},
    "vicharne": {"imp": ("विचार", "विचारा", "विचारा")},
    "bolavne": {"imp": ("बोलाव", "बोलावा", "बोलावा")},
    "madat_karne": {"imp": ("मदत कर", "मदत करा", "मदत करा")},
    # The one imperative with a third rung. The verb stops at two like all the
    # others — तुम्ही and आपण share करा — so the escalation is lexical: माफ is
    # the everyday word for pardon and क्षमा the Sanskritic one.
    "maf_karne": {"imp": ("माफ कर", "माफ करा", "क्षमा करा")},
}

_MR_TENSE_ORDER = ("future", "pres.m", "pres.f", "imp")

_MR_2P_CONTEXT = r"(?:तू|तुम्ही|आपण)(?:\s+\S+){0,10}\s+"

# --------------------------------------------------------------------------
# Marathi writes its postpositions onto the oblique pronoun rather than beside
# it: तुझ्या + साठी is one word, तुझ्यासाठी. The oblique rule was in the table
# and could never fire, because a whole-word match for तुझ्या does not find it
# inside तुझ्यासाठी — so "हे तुझ्यासाठी आहे" (this is for you), as ordinary a
# sentence as the language has, detected nothing and rewrote to nothing.
#
# The set is small and closed, so the forms are generated rather than listed.
# --------------------------------------------------------------------------

#: (तू stem, तुम्ही stem, आपण stem).
_MR_OBLIQUE = ("तुझ्या", "तुमच्या", "आपल्या")

_MR_POSTPOSITIONS = (
    ("sathi", "साठी"),        # for
    ("kade", "कडे"),          # to, at
    ("kadun", "कडून"),        # from, by
    ("barobar", "बरोबर"),     # with
    ("shi", "शी"),            # with, to
    ("mule", "मुळे"),         # because of
    ("var", "वर"),            # on
    ("pasun", "पासून"),       # from
    ("paryant", "पर्यंत"),    # up to
    ("vishayi", "विषयी"),     # about
    ("shivay", "शिवाय"),      # without
    ("sarkha", "सारखा"),      # like (m)
    ("sarkhe", "सारखे"),      # like (n/pl)
    ("madhe", "मध्ये"),       # in
    ("khali", "खाली"),        # under
)


def _mr_postposition_rules() -> Tuple[Rule, ...]:
    tu, tumhi, aapan = _MR_OBLIQUE
    return tuple(
        Rule(f"pron.obl.{name}",
             (tu + post, tu + post, tumhi + post, aapan + post),
             f"{post} you")
        for name, post in _MR_POSTPOSITIONS
    )


def _mr_verb_rules() -> Tuple[Rule, ...]:
    out = []
    for tense in _MR_TENSE_ORDER:
        for verb, paradigm in _MR_PARADIGMS.items():
            forms = paradigm.get(tense)
            if not forms:
                continue
            tu, tumhi, aapan = forms
            if len({tu, tumhi, aapan}) == 1:
                continue  # carries no register information
            # Marathi canon is (0, 1, 2, 3) with तू at both 0 and 1.
            out.append(
                Rule(f"v.{verb}.{tense}", (tu, tu, tumhi, aapan),
                     f"{verb} · {tense}")
            )
    return tuple(out)


MARATHI = LanguageTable(
    code="mr",
    name="Marathi",
    canon=(0, 1, 2, 3),
    please=("", "", "जरा ", "कृपया "),
    address_terms={
        "older_man": ("", "दादा", "दादा", "सर"),
        "older_woman": ("", "ताई", "ताई", "मॅडम"),
        "elder_man": ("", "काका", "काका", "सर"),
        "elder_woman": ("", "काकू", "काकू", "मॅडम"),
        "peer": ("", "अरे", "दादा", "सर"),
        "official": ("", "साहेब", "साहेब", "सर"),
    },
    rules=_mr_verb_rules() + _mr_postposition_rules() + (
        # आपण is the honorific "you" *and* the inclusive "we", which the gold
        # set flags as a real ambiguity. The hortative settles it: "आपण जाऊया"
        # is "let's go" and is about the speaker too, so it carries no register
        # toward the listener at all.
        Rule("pron.2sg.nom", ("तू", "तू", "तुम्ही", "आपण"), "you",
             guard_after=rf"\s+\S*(?:ऊया|ूया){RIGHT}"),
        Rule("pron.2sg.dat", ("तुला", "तुला", "तुम्हाला", "आपल्याला"), "to you"),
        Rule("pron.2sg.gen.m", ("तुझा", "तुझा", "तुमचा", "आपला"), "your (m)"),
        Rule("pron.2sg.gen.f", ("तुझी", "तुझी", "तुमची", "आपली"), "your (f)"),
        # Marathi has three genders and the table had two. तुझं is the neuter
        # and the form in "तुझं नाव काय आहे?" — about as ordinary a sentence as
        # the language has, and it detected nothing at all.
        Rule("pron.2sg.gen.n", ("तुझं", "तुझं", "तुमचं", "आपलं"), "your (n)"),
        Rule("pron.2sg.gen.n2", ("तुझे", "तुझे", "तुमचे", "आपले"), "your (n pl)"),
        Rule("pron.2sg.obl", ("तुझ्या", "तुझ्या", "तुमच्या", "आपल्या"), "your (oblique)"),
        Rule("cop.pres", ("आहेस", "आहेस", "आहात", "आहात"), "you are"),
        Rule("cop.past.m", ("होतास", "होतास", "होतात", "होतात"), "you were (m)"),
        Rule("cop.past.f", ("होतीस", "होतीस", "होतात", "होतात"), "you were (f)"),
        # Marathi agrees the predicate adjective with the pronoun, and nothing
        # was moving it: "तू कसा आहेस?" upgraded to "तुम्ही कसा आहात?", the
        # right pronoun left in the wrong concord. Same gap Urdu had with कیسا.
        Rule("adj.kasa", ("कसा", "कसा", "कसे", "कसे"), "how (m)",
             require_before=_MR_2P_CONTEXT),
        Rule("adj.kashi", ("कशी", "कशी", "कशा", "कशा"), "how (f)",
             require_before=_MR_2P_CONTEXT),
        Rule("greet.hello", ("ए", "हॅलो", "नमस्कार", "नमस्कार"), "hello"),
        Rule("greet.thanks", ("थँक्स", "धन्यवाद", "धन्यवाद", "मनःपूर्वक धन्यवाद"), "thanks"),
        Rule("greet.sorry", ("सॉरी", "सॉरी", "माफ करा", "क्षमस्व"), "sorry"),
        # कृपया is what separates Formal from Polite in a request — the
        # imperative covers both — so it has to be readable, not merely
        # insertable. जरा stays out: it means "a little" and softens a request
        # at any level, "जरा ऐक" included.
        Rule("polite.particle", ("", "", "", "कृपया"), "please"),
    ),
)

# --------------------------------------------------------------------------
# Gujarati verb paradigms.
#
# Another imperative-only table: 15 rules, 58.8% detection. Gujarati marks
# register on the verb ending throughout the present and future, none of which
# had rules, so any sentence without an imperative in it detected nothing.
#
# Each entry is (તું, તમે, આપ). The આપ column mostly reuses the તમે verb form —
# Gujarati carries the third level on the pronoun and on the -જો imperative
# ending rather than through the whole conjugation.
# --------------------------------------------------------------------------

_GU_PARADIGMS: Dict[str, Dict[str, Tuple[str, str, str]]] = {
    "karvu": {  # to do
        "pres": ("કરે છે", "કરો છો", "કરો છો"),
        "future": ("કરીશ", "કરશો", "કરશો"),
        "imp": ("કર", "કરો", "કરજો"),
    },
    "avvu": {  # to come
        "pres": ("આવે છે", "આવો છો", "આવો છો"),
        "future": ("આવીશ", "આવશો", "આવશો"),
        "imp": ("આવ", "આવો", "આવજો"),
    },
    "javu": {  # to go
        "pres": ("જાય છે", "જાઓ છો", "જાઓ છો"),
        "future": ("જઈશ", "જશો", "જશો"),
        "imp": ("જા", "જાઓ", "જજો"),
    },
    "rahevu": {  # to live, to stay
        "pres": ("રહે છે", "રહો છો", "રહો છો"),
        "imp": ("રહે", "રહો", "રહેજો"),
    },
    "bolvu": {  # to speak
        "pres": ("બોલે છે", "બોલો છો", "બોલો છો"),
        "imp": ("બોલ", "બોલો", "બોલજો"),
    },
    "kahevu": {  # to say
        "pres": ("કહે છે", "કહો છો", "કહો છો"),
        "imp": ("કહે", "કહો", "કહેજો"),
    },
    "khavu": {  # to eat
        "pres": ("ખાય છે", "ખાઓ છો", "ખાઓ છો"),
        "imp": ("ખા", "ખાઓ", "ખાજો"),
    },
    "pivu": {"imp": ("પી", "પીઓ", "પીજો")},
    "jovu": {  # to see
        "pres": ("જુએ છે", "જુઓ છો", "જુઓ છો"),
        "imp": ("જો", "જુઓ", "જોજો"),
    },
    "sambhalvu": {  # to listen
        "pres": ("સાંભળે છે", "સાંભળો છો", "સાંભળો છો"),
        "imp": ("સાંભળ", "સાંભળો", "સાંભળજો"),
    },
    "samajvu": {"pres": ("સમજે છે", "સમજો છો", "સમજો છો")},
    "janvu": {"pres": ("જાણે છે", "જાણો છો", "જાણો છો")},
    "levu": {"future": ("લઈશ", "લેશો", "લેશો"), "imp": ("લે", "લો", "લેજો")},
    "apvu": {"future": ("આપીશ", "આપશો", "આપશો"), "imp": ("આપ", "આપો", "આપજો")},
    "besvu": {"imp": ("બેસ", "બેસો", "બેસજો")},
    "uthvu": {"imp": ("ઊઠ", "ઊઠો", "ઊઠજો")},
    "thobhvu": {"imp": ("થોભ", "થોભો", "થોભજો")},
    "lakhvu": {"pres": ("લખે છે", "લખો છો", "લખો છો"), "imp": ("લખ", "લખો", "લખજો")},
    "vanchvu": {"pres": ("વાંચે છે", "વાંચો છો", "વાંચો છો"), "imp": ("વાંચ", "વાંચો", "વાંચજો")},
    "kharidvu": {"imp": ("ખરીદ", "ખરીદો", "ખરીદજો")},
    "utarvu": {"imp": ("ઉતર", "ઉતરો", "ઉતરજો")},
    "bolavvu": {"imp": ("બોલાવ", "બોલાવો", "બોલાવજો")},
    "puchvu": {"imp": ("પૂછ", "પૂછો", "પૂછજો")},
    "maf_karvu": {"imp": ("માફ કર", "માફ કરો", "માફ કરજો")},
    "madad_karvu": {"imp": ("મદદ કર", "મદદ કરો", "મદદ કરજો")},
}

#: Present and future before the imperative, for the usual reason: the તમે
#: imperative (કરો) is spelled identically to the તમે present stem inside
#: "કરો છો", and the shorter string would otherwise win the tie.
_GU_TENSE_ORDER = ("future", "pres", "imp")

#: આપ is both the formal pronoun and the imperative "give!", so a bare trailing
#: આપ is the verb. Reused from the pronoun rule below.
_GU_2P_CONTEXT = r"(?:તું|તમે|આપ)(?:\s+\S+){0,10}\s+"

#: The nominative તું alone, for the finite forms it shares with the third
#: person. Gujarati is verb-final, so the pronoun heads the clause.
_GU_TU_BEFORE = rf"{LEFT}તું{RIGHT}(?:\s+\S+){{0,10}}\s+"

#: An imperative closes its clause. Required by the verbs whose imperative
#: collides with something else: આપ is also the formal pronoun, જો is also the
#: conjunction "if". Generated rules are declared before the pronoun rules, so
#: without this the imperative wins the equal-length tie and "આપ કેમ છો?" reads
#: as Casual — which is how deepening the table briefly *lowered* Gujarati
#: register accuracy from 98.5% to 96.1%.
_GU_CLAUSE_FINAL = r"\s*(?:[।!?.,]|$)"
_GU_COLLIDING_IMPERATIVES = {"apvu", "jovu"}


def _gu_verb_rules() -> Tuple[Rule, ...]:
    out = []
    for tense in _GU_TENSE_ORDER:
        for verb, paradigm in _GU_PARADIGMS.items():
            forms = paradigm.get(tense)
            if not forms:
                continue
            tu, tame, aap = forms
            if len({tu, tame, aap}) == 1:
                continue
            imperative = paradigm.get("imp")
            collides = bool(imperative) and imperative[1] == tame
            before = _GU_2P_CONTEXT if (tense == "pres" and collides) else ""
            after = (
                _GU_CLAUSE_FINAL
                if tense == "imp" and verb in _GU_COLLIDING_IMPERATIVES
                else ""
            )
            # The તું form of a finite tense is also the third-person form —
            # "તું કરે છે" and "તે કરે છે" are the same string — so it needs a
            # તું in front of it to count. Without that, "તે શું કરે છે?" (what
            # does he do?) read as Casual at full confidence.
            guards = ()
            if tense != "imp" and not before:
                guards = ((tu, "", "", _GU_TU_BEFORE, "", ""),)
            # Gujarati canon is (1, 1, 2, 3): તું is Casual, not Close.
            out.append(
                Rule(f"v.{verb}.{tense}", (tu, tu, tame, aap),
                     f"{verb} · {tense}",
                     require_before=before, require_after=after,
                     form_guards=guards)
            )
    return tuple(out)


GUJARATI = LanguageTable(
    code="gu",
    name="Gujarati",
    # Three levels, not four: તું (intimate) / તમે (polite) / આપ (deferential).
    # See _gu_verb_rules above for the paradigm.
    # The table previously put તમે at both Casual and Polite, which made every
    # તમે sentence a permanent tie the detector had to break arbitrarily — it
    # read "તમે કેમ છો?" as Polite while the annotator called it Casual, and no
    # amount of tie-breaking could satisfy both. Collapsing Close and Casual
    # onto તું removes the ambiguity instead of arbitrating it.
    canon=(1, 1, 2, 3),
    please=("", "", "જરા ", "કૃપા કરીને "),
    address_terms={
        "older_man": ("", "ભાઈ", "ભાઈ", "સાહેબ"),
        "older_woman": ("", "બહેન", "બહેન", "મેડમ"),
        "elder_man": ("", "કાકા", "કાકા", "સાહેબ"),
        "elder_woman": ("", "કાકી", "કાકી", "મેડમ"),
        "peer": ("", "દોસ્ત", "ભાઈ", "સાહેબ"),
        "official": ("", "સાહેબ", "સાહેબ", "સાહેબ"),
    },
    rules=_gu_verb_rules() + (
        # આપ is both the formal pronoun "you" and the imperative "give!". A
        # subject pronoun is followed by the rest of its clause, whereas the
        # bare imperative ends the utterance — so a trailing આપ is the verb.
        # Without this, rewriting the command આપ to Close produced the pronoun તું.
        Rule("pron.2sg.nom", ("તું", "તું", "તમે", "આપ"), "you",
             guard_after=r"\s*(?:[।.!?,;:]|$)"),
        Rule("pron.2sg.dat", ("તને", "તને", "તમને", "આપને"), "to you"),
        Rule("pron.2sg.gen", ("તારું", "તારું", "તમારું", "આપનું"), "your"),
        # The other genitive genders and the oblique were missing, so
        # "આ તારા માટે છે" and "તારો આભાર" matched nothing.
        Rule("pron.2sg.gen.m", ("તારો", "તારો", "તમારો", "આપનો"), "your (m)"),
        Rule("pron.2sg.gen.f", ("તારી", "તારી", "તમારી", "આપની"), "your (f)"),
        Rule("pron.2sg.gen.obl", ("તારા", "તારા", "તમારા", "આપના"), "your (obl/pl)"),
        # છે is the તું copula and also the ordinary third-person copula, so
        # "આજે હવામાન સરસ છે" ("the weather is nice today") was detecting as
        # Casual. It only counts as second person with તું nearby; છો is
        # unambiguous and needs nothing.
        Rule("cop.pres", ("છે", "છે", "છો", "છો"), "you are",
             form_guards=(("છે", "", "", r"તું(?:\s+\S+){0,6}\s+", ""),)),
        # કૃપા કરીને is the marker that separates Formal from Polite here, so
        # it has to be readable, not just insertable via `please`. જરા is left
        # out for the same reason as Tamil கொஞ்சம் — it just means "a little".
        Rule("polite.particle", ("", "", "", "કૃપા કરીને"), "please"),
        Rule("cop.past.m", ("હતો", "હતો", "હતા", "હતા"), "you were (m)"),
        Rule("cop.past.f", ("હતી", "હતી", "હતાં", "હતાં"), "you were (f)"),
        Rule("greet.hello", ("એ", "હેલો", "નમસ્તે", "નમસ્કાર"), "hello"),
        # Gujarati reaches Formal with a pronoun — આપ — so the intensifier is
        # optional rather than load-bearing, and આભાર holds every level the
        # dial can produce. Forcing ખૂબ made "આપનો આભાર" unstable at its own
        # level: already Formal, yet rewritten on arriving there. Same as
        # Malayalam നന്ദി, and the opposite of Tamil, which has no formal
        # pronoun and needs the lexical step.
        Rule("greet.thanks", ("થેંક્સ", "આભાર", "આભાર", "આભાર"), "thanks"),
        Rule("greet.sorry", ("સોરી", "સોરી", "માફ કરશો", "ક્ષમા કરશો"), "sorry"),
    ),
)

# --------------------------------------------------------------------------
# Punjabi verb paradigms. (ਤੂੰ, ਤੁਸੀਂ)
#
# Imperative-only, like every other table before it was deepened, so the
# present, continuous and future all detected nothing.
# --------------------------------------------------------------------------

_PA_PARADIGMS: Dict[str, Dict[str, Tuple[str, str]]] = {
    "karna": {
        "pres.m": ("ਕਰਦਾ ਹੈਂ", "ਕਰਦੇ ਹੋ"),
        "pres.f": ("ਕਰਦੀ ਹੈਂ", "ਕਰਦੀਆਂ ਹੋ"),
        "cont.m": ("ਕਰ ਰਿਹਾ ਹੈਂ", "ਕਰ ਰਹੇ ਹੋ"),
        "future.m": ("ਕਰੇਂਗਾ", "ਕਰੋਗੇ"),
        "imp": ("ਕਰ", "ਕਰੋ"),
    },
    "jana": {
        "pres.m": ("ਜਾਂਦਾ ਹੈਂ", "ਜਾਂਦੇ ਹੋ"),
        "cont.m": ("ਜਾ ਰਿਹਾ ਹੈਂ", "ਜਾ ਰਹੇ ਹੋ"),
        "future.m": ("ਜਾਵੇਂਗਾ", "ਜਾਓਗੇ"),
        "imp": ("ਜਾ", "ਜਾਓ"),
    },
    "auna": {
        "pres.m": ("ਆਉਂਦਾ ਹੈਂ", "ਆਉਂਦੇ ਹੋ"),
        "future.m": ("ਆਵੇਂਗਾ", "ਆਓਗੇ"),
        "imp": ("ਆ", "ਆਓ"),
    },
    "rahna": {"pres.m": ("ਰਹਿੰਦਾ ਹੈਂ", "ਰਹਿੰਦੇ ਹੋ")},
    "bolna": {"pres.m": ("ਬੋਲਦਾ ਹੈਂ", "ਬੋਲਦੇ ਹੋ"), "imp": ("ਬੋਲ", "ਬੋਲੋ")},
    "dassna": {"pres.m": ("ਦੱਸਦਾ ਹੈਂ", "ਦੱਸਦੇ ਹੋ"), "imp": ("ਦੱਸ", "ਦੱਸੋ")},
    "vekhna": {"pres.m": ("ਵੇਖਦਾ ਹੈਂ", "ਵੇਖਦੇ ਹੋ"), "imp": ("ਵੇਖ", "ਵੇਖੋ")},
    "sunna": {"pres.m": ("ਸੁਣਦਾ ਹੈਂ", "ਸੁਣਦੇ ਹੋ"), "imp": ("ਸੁਣ", "ਸੁਣੋ")},
    "khana": {"pres.m": ("ਖਾਂਦਾ ਹੈਂ", "ਖਾਂਦੇ ਹੋ"), "imp": ("ਖਾ", "ਖਾਓ")},
    "samajhna": {"pres.m": ("ਸਮਝਦਾ ਹੈਂ", "ਸਮਝਦੇ ਹੋ")},
    "janna": {"pres.m": ("ਜਾਣਦਾ ਹੈਂ", "ਜਾਣਦੇ ਹੋ")},
    "sakna": {"pres.m": ("ਸਕਦਾ ਹੈਂ", "ਸਕਦੇ ਹੋ")},
    "pina": {"imp": ("ਪੀ", "ਪੀਓ")},
    "lena": {"imp": ("ਲੈ", "ਲਵੋ")},
    "dena": {"imp": ("ਦੇ", "ਦਿਓ")},
    "baithna": {"imp": ("ਬੈਠ", "ਬੈਠੋ")},
    "uthna": {"imp": ("ਉੱਠ", "ਉੱਠੋ")},
    "rukna": {"imp": ("ਰੁਕ", "ਰੁਕੋ")},
    "likhna": {"imp": ("ਲਿਖ", "ਲਿਖੋ")},
    "padhna": {"imp": ("ਪੜ੍ਹ", "ਪੜ੍ਹੋ")},
    "kholna": {"imp": ("ਖੋਲ੍ਹ", "ਖੋਲ੍ਹੋ")},
    "utarna": {"imp": ("ਉਤਰ", "ਉਤਰੋ")},
    "maf_karna": {"imp": ("ਮਾਫ਼ ਕਰ", "ਮਾਫ਼ ਕਰੋ")},
    "madad_karna": {"imp": ("ਮਦਦ ਕਰ", "ਮਦਦ ਕਰੋ")},
}

_PA_TENSE_ORDER = ("cont.m", "future.m", "pres.m", "pres.f", "imp")


def _pa_verb_rules() -> Tuple[Rule, ...]:
    out = []
    for tense in _PA_TENSE_ORDER:
        for verb, paradigm in _PA_PARADIGMS.items():
            forms = paradigm.get(tense)
            if not forms:
                continue
            tu, tusi = forms
            if tu == tusi:
                continue
            out.append(
                Rule(f"v.{verb}.{tense}", (tu, tu, tusi, tusi), f"{verb} · {tense}")
            )
    return tuple(out)


PUNJABI = LanguageTable(
    code="pa",
    name="Punjabi",
    # Binary pronoun system (du/Sie, tu/vous, நீ/நீங்கள்), but the lexical
    # politeness layer above it is not binary — "Vielen Dank" and "Herzlichen
    # Dank" are not the same register. Folding Polite and Formal together
    # would throw that away, so both slots stay live.
    canon=(1, 1, 2, 3),
    please=("", "", "ਜ਼ਰਾ ", "ਕਿਰਪਾ ਕਰਕੇ "),
    address_terms={
        "older_man": ("", "ਵੀਰ ਜੀ", "ਭਾਈ ਸਾਹਬ", "ਸਰ"),
        "older_woman": ("", "ਭੈਣ ਜੀ", "ਭੈਣ ਜੀ", "ਮੈਡਮ"),
        "elder_man": ("", "ਅੰਕਲ", "ਅੰਕਲ ਜੀ", "ਸਰ"),
        "elder_woman": ("", "ਆਂਟੀ", "ਆਂਟੀ ਜੀ", "ਮੈਡਮ"),
        "peer": ("", "ਯਾਰ", "ਵੀਰ ਜੀ", "ਸਰ"),
        "official": ("", "ਸਾਹਬ", "ਸਾਹਬ", "ਸਰ"),
    },
    rules=_pa_verb_rules() + (
        Rule("pron.2sg.nom", ("ਤੂੰ", "ਤੂੰ", "ਤੁਸੀਂ", "ਤੁਸੀਂ"), "you"),
        Rule("pron.2sg.dat", ("ਤੈਨੂੰ", "ਤੈਨੂੰ", "ਤੁਹਾਨੂੰ", "ਤੁਹਾਨੂੰ"), "to you"),
        Rule("pron.2sg.gen", ("ਤੇਰਾ", "ਤੇਰਾ", "ਤੁਹਾਡਾ", "ਤੁਹਾਡਾ"), "your"),
        # The oblique and feminine genitives were missing, so "ਇਹ ਤੇਰੇ ਲਈ ਹੈ"
        # matched nothing at all.
        Rule("pron.2sg.gen.obl", ("ਤੇਰੇ", "ਤੇਰੇ", "ਤੁਹਾਡੇ", "ਤੁਹਾਡੇ"), "your (obl)"),
        Rule("pron.2sg.gen.f", ("ਤੇਰੀ", "ਤੇਰੀ", "ਤੁਹਾਡੀ", "ਤੁਹਾਡੀ"), "your (f)"),
        Rule("cop.pres", ("ਹੈਂ", "ਹੈਂ", "ਹੋ", "ਹੋ"), "you are"),
        # ਕਿਰਪਾ ਕਰਕੇ is what marks Formal above the shared ਤੁਸੀਂ, so it has to
        # be readable. Empty low slots mean it is dropped on the way down.
        Rule("polite.particle", ("", "", "", "ਕਿਰਪਾ ਕਰਕੇ"), "please"),
        Rule("greet.hello", ("ਓਏ", "ਹੈਲੋ", "ਸਤ ਸ੍ਰੀ ਅਕਾਲ", "ਸਤ ਸ੍ਰੀ ਅਕਾਲ"), "hello"),
        # ਧੰਨਵਾਦ is the ordinary thanks word and is used at Casual as much as at
        # Polite, so it sits in both slots rather than only the upper one. That
        # is what stops "ਤੇਰਾ ਧੰਨਵਾਦ" reading Polite off the noun instead of
        # Casual off the ਤੇਰਾ — and unlike rewrite_only it leaves ਬਹੁਤ ਧੰਨਵਾਦ
        # free to be the evidence a Formal sentence needs.
        Rule("greet.thanks", ("ਧੰਨਵਾਦ", "ਧੰਨਵਾਦ", "ਧੰਨਵਾਦ", "ਬਹੁਤ ਬਹੁਤ ਧੰਨਵਾਦ"), "thanks"),
        # ਅਫ਼ਸੋਸ is the written-register regret, above ਦੁਖ.
        Rule("lex.regret", ("ਦੁਖ", "ਦੁਖ", "ਦੁਖ", "ਅਫ਼ਸੋਸ"), "regret"),
        Rule("greet.sorry", ("ਸੌਰੀ", "ਸੌਰੀ", "ਮਾਫ਼ ਕਰਨਾ", "ਖਿਮਾ ਕਰਨਾ"), "sorry"),
    ),
)

# --------------------------------------------------------------------------
# Dravidian
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# Tamil verb paradigms.
#
# Sixteen rules, nearly all imperatives, and the gold set found the rest: no
# present, no past, no future, and several ordinary imperatives absent
# entirely, so "என்னிடம் சொல்." and "கொஞ்சம் இரு." matched nothing.
#
# Each entry is (நீ, நீங்கள்). The -ங்கள் ending is what carries the register
# right across the paradigm, which is exactly why covering only the imperative
# leaves most of the language unreachable.
#
# Written Tamil throughout. Spoken Tamil diverges sharply — வர்றீங்க for
# வருகிறீர்கள் — and is a separate table's worth of work, not a variant of
# this one.
# --------------------------------------------------------------------------

_TA_PARADIGMS: Dict[str, Dict[str, Tuple[str, str]]] = {
    "varu": {  # to come
        "pres": ("வருகிறாய்", "வருகிறீர்கள்"),
        "past": ("வந்தாய்", "வந்தீர்கள்"),
        "future": ("வருவாய்", "வருவீர்கள்"),
        "imp": ("வா", "வாருங்கள்"),
    },
    "po": {  # to go
        "pres": ("போகிறாய்", "போகிறீர்கள்"),
        "past": ("போனாய்", "போனீர்கள்"),
        "future": ("போவாய்", "போவீர்கள்"),
        "imp": ("போ", "போங்கள்"),
    },
    "sey": {  # to do
        "pres": ("செய்கிறாய்", "செய்கிறீர்கள்"),
        "past": ("செய்தாய்", "செய்தீர்கள்"),
        "future": ("செய்வாய்", "செய்வீர்கள்"),
        "imp": ("செய்", "செய்யுங்கள்"),
    },
    "sollu": {  # to say
        "pres": ("சொல்கிறாய்", "சொல்கிறீர்கள்"),
        "past": ("சொன்னாய்", "சொன்னீர்கள்"),
        "imp": ("சொல்", "சொல்லுங்கள்"),
    },
    "sollu_alt": {"imp": ("சொல்லு", "சொல்லுங்கள்")},
    "iru": {  # to be, to stay
        "pres": ("இருக்கிறாய்", "இருக்கிறீர்கள்"),
        "past": ("இருந்தாய்", "இருந்தீர்கள்"),
        "future": ("இருப்பாய்", "இருப்பீர்கள்"),
        "imp": ("இரு", "இருங்கள்"),
    },
    "paar": {  # to see
        "pres": ("பார்க்கிறாய்", "பார்க்கிறீர்கள்"),
        "past": ("பார்த்தாய்", "பார்த்தீர்கள்"),
        "imp": ("பார்", "பாருங்கள்"),
    },
    "kel": {  # to ask, to listen
        "pres": ("கேட்கிறாய்", "கேட்கிறீர்கள்"),
        "imp": ("கேள்", "கேளுங்கள்"),
    },
    "kelu_alt": {"imp": ("கேளு", "கேளுங்கள்")},
    "saapidu": {  # to eat
        "pres": ("சாப்பிடுகிறாய்", "சாப்பிடுகிறீர்கள்"),
        "past": ("சாப்பிட்டாய்", "சாப்பிட்டீர்கள்"),
        "imp": ("சாப்பிடு", "சாப்பிடுங்கள்"),
    },
    "pesu": {  # to speak
        "pres": ("பேசுகிறாய்", "பேசுகிறீர்கள்"),
        "imp": ("பேசு", "பேசுங்கள்"),
    },
    "theri": {"pres": ("தெரிகிறாய்", "தெரிகிறீர்கள்")},
    "vaazh": {"pres": ("வாழ்கிறாய்", "வாழ்கிறீர்கள்")},
    "utkaar": {"imp": ("உட்கார்", "உட்காருங்கள்")},
    "kudi": {"imp": ("குடி", "குடியுங்கள்")},
    "vaangu": {"imp": ("வாங்கு", "வாங்குங்கள்")},
    "kodu": {"imp": ("கொடு", "கொடுங்கள்")},
    "edu": {"imp": ("எடு", "எடுங்கள்")},
    "irangu": {"imp": ("இறங்கு", "இறங்குங்கள்")},
    "ezhudhu": {"imp": ("எழுது", "எழுதுங்கள்")},
    "padi": {"imp": ("படி", "படியுங்கள்")},
    "manni": {"imp": ("மன்னி", "மன்னியுங்கள்")},
    "nil": {"imp": ("நில்", "நில்லுங்கள்")},
    "udhavu": {"imp": ("உதவு", "உதவுங்கள்")},
    "kaathiru": {"imp": ("காத்திரு", "காத்திருங்கள்")},
    "thodangu": {"imp": ("தொடங்கு", "தொடங்குங்கள்")},
}

#: Finite tenses before the imperative: the imperative is the shortest form and
#: is contained inside several of the others (இரு inside இருங்கள்).
_TA_TENSE_ORDER = ("pres", "past", "future", "imp")


def _dravidian_verb_rules(
    paradigms: Dict[str, Dict[str, Tuple[str, str]]],
    tense_order: Tuple[str, ...],
    *,
    question: Optional[Callable[[str], str]] = None,
    guard_before: str = "",
) -> Tuple[Rule, ...]:
    """
    Expand a two-column Dravidian paradigm into rules.

    Tamil, Telugu and Kannada share a shape: one familiar pronoun, one
    honorific, and a canon of ``(1, 1, 2, 3)`` — the familiar form is Casual,
    the honorific covers Polite *and* Formal, and the extra deference above
    Polite is lexical rather than morphological. So each paradigm entry is a
    pair and becomes ``(fam, fam, hon, hon)``.

    ``question`` supplies the yes/no interrogative, which in Telugu and Kannada
    is a clitic fused onto the finite verb (తిన్నావు → తిన్నావా). Written
    solid, it defeats a whole-word match, so the interrogative has to be
    generated as its own form rather than left to the matcher. Imperatives are
    excluded — they do not take the clitic.
    """
    out = []
    for tense in tense_order:
        for verb, paradigm in paradigms.items():
            forms = paradigm.get(tense)
            if not forms:
                continue
            fam, hon = forms
            if fam == hon:
                continue
            out.append(
                Rule(f"v.{verb}.{tense}", (fam, fam, hon, hon),
                     f"{verb} · {tense}", guard_before=guard_before)
            )
            if question is not None and tense != "imp":
                q_fam, q_hon = question(fam), question(hon)
                if q_fam != fam and q_fam != q_hon:
                    out.append(
                        Rule(f"v.{verb}.{tense}.q",
                             (q_fam, q_fam, q_hon, q_hon),
                             f"{verb} · {tense} · question",
                             guard_before=guard_before)
                    )
    return tuple(out)


def _ta_question(form: str) -> str:
    """
    Tamil yes/no questions append -ஆ to the finite verb, which absorbs the
    stem-final virama: சாப்பிட்டாய் → சாப்பிட்டாயா, சாப்பிட்டீர்கள் →
    சாப்பிட்டீர்களா.
    """
    stem = form[:-1] if form.endswith("்") else form
    return stem + "ா"


def _ta_verb_rules() -> Tuple[Rule, ...]:
    return _dravidian_verb_rules(
        _TA_PARADIGMS, _TA_TENSE_ORDER, question=_ta_question
    )


TAMIL = LanguageTable(
    code="ta",
    name="Tamil",
    # Binary pronoun system (du/Sie, tu/vous, நீ/நீங்கள்), but the lexical
    # politeness layer above it is not binary — "Vielen Dank" and "Herzlichen
    # Dank" are not the same register. Folding Polite and Formal together
    # would throw that away, so both slots stay live.
    canon=(1, 1, 2, 3),
    please=("", "", "கொஞ்சம் ", "தயவுசெய்து "),
    address_terms={
        "older_man": ("", "அண்ணா", "அண்ணா", "சார்"),
        "older_woman": ("", "அக்கா", "அக்கா", "மேடம்"),
        "elder_man": ("", "மாமா", "ஐயா", "சார்"),
        "elder_woman": ("", "அத்தை", "அம்மா", "மேடம்"),
        "peer": ("", "மச்சான்", "அண்ணா", "சார்"),
        "official": ("", "ஐயா", "ஐயா", "சார்"),
    },
    rules=_ta_verb_rules() + (
        Rule("pron.2sg.nom", ("நீ", "நீ", "நீங்கள்", "நீங்கள்"), "you"),
        Rule("pron.2sg.acc", ("உன்னை", "உன்னை", "உங்களை", "உங்களை"), "you (obj)"),
        Rule("pron.2sg.gen", ("உன்", "உன்", "உங்கள்", "உங்கள்"), "your"),
        Rule("pron.2sg.dat", ("உனக்கு", "உனக்கு", "உங்களுக்கு", "உங்களுக்கு"), "to you"),
        Rule("pron.2sg.soc", ("உன்னுடன்", "உன்னுடன்", "உங்களுடன்", "உங்களுடன்"), "with you"),
        Rule("pron.2sg.loc", ("உன்னிடம்", "உன்னிடம்", "உங்களிடம்", "உங்களிடம்"), "at/from you"),
        Rule("greet.hello", ("ஏய்", "ஹலோ", "வணக்கம்", "வணக்கம்"), "hello"),
        # தயவுசெய்து is what separates Formal from Polite in Tamil — நீங்கள்
        # covers both — so it has to be readable, not merely insertable.
        # கொஞ்சம் is deliberately *not* here: it means "a little" and is an
        # ordinary adverb, so "கொஞ்சம் இரு" (wait a bit) is perfectly casual.
        # Listing it as a politeness marker made every sentence containing it
        # read as Polite.
        Rule("polite.particle", ("", "", "", "தயவுசெய்து"), "please"),
        # Not rewrite_only, unlike Italian Grazie: நன்றி sits at Casual and
        # Polite rather than at the bottom two, so it never outvotes a நீங்கள்,
        # and மிக்க நன்றி is the only evidence a Formal sentence carries.
        Rule("greet.thanks", ("தேங்க்ஸ்", "நன்றி", "நன்றி", "மிக்க நன்றி"), "thanks"),
        Rule("greet.sorry", ("சாரி", "சாரி", "மன்னிக்கவும்", "மன்னிக்கவும்"), "sorry"),
    ),
)

# --------------------------------------------------------------------------
# Telugu — నువ్వు / మీరు
# --------------------------------------------------------------------------

#: (నువ్వు form, మీరు form). The agreement is a clean suffix alternation —
#: -వు against -రు — but the stems are not: వచ్చు suppletes to రా in the
#: imperative, and చేయు has చేస్- in the non-past against చేశ- in the past.
#: Storing whole forms rather than stem+suffix keeps those irregularities
#: honest instead of forcing them through a rule that does not fit.
_TE_PARADIGMS: Dict[str, Dict[str, Tuple[str, str]]] = {
    "undu": {  # to be, to stay
        "pres": ("ఉన్నావు", "ఉన్నారు"),
        "future": ("ఉంటావు", "ఉంటారు"),
        "imp": ("ఉండు", "ఉండండి"),
    },
    "vaccu": {  # to come
        "cont": ("వస్తున్నావు", "వస్తున్నారు"),
        "future": ("వస్తావు", "వస్తారు"),
        "past": ("వచ్చావు", "వచ్చారు"),
        "imp": ("రా", "రండి"),
    },
    "vellu": {  # to go
        "cont": ("వెళ్తున్నావు", "వెళ్తున్నారు"),
        "future": ("వెళ్తావు", "వెళ్తారు"),
        "past": ("వెళ్ళావు", "వెళ్ళారు"),
        "imp": ("వెళ్ళు", "వెళ్ళండి"),
    },
    "cheyyi": {  # to do
        "cont": ("చేస్తున్నావు", "చేస్తున్నారు"),
        "future": ("చేస్తావు", "చేస్తారు"),
        "past": ("చేశావు", "చేశారు"),
        "imp": ("చెయ్యి", "చెయ్యండి"),
    },
    "cheyu_alt": {"imp": ("చేయి", "చేయండి")},
    "cheppu": {  # to tell
        "cont": ("చెబుతున్నావు", "చెబుతున్నారు"),
        "future": ("చెబుతావు", "చెబుతారు"),
        "past": ("చెప్పావు", "చెప్పారు"),
        "imp": ("చెప్పు", "చెప్పండి"),
    },
    "choodu": {  # to see
        "cont": ("చూస్తున్నావు", "చూస్తున్నారు"),
        "future": ("చూస్తావు", "చూస్తారు"),
        "past": ("చూశావు", "చూశారు"),
        "imp": ("చూడు", "చూడండి"),
    },
    "tinu": {  # to eat
        "cont": ("తింటున్నావు", "తింటున్నారు"),
        "future": ("తింటావు", "తింటారు"),
        "past": ("తిన్నావు", "తిన్నారు"),
        "imp": ("తిను", "తినండి"),
    },
    "taagu": {  # to drink
        "future": ("తాగుతావు", "తాగుతారు"),
        "past": ("తాగావు", "తాగారు"),
        "imp": ("తాగు", "తాగండి"),
    },
    "ivvu": {  # to give
        "cont": ("ఇస్తున్నావు", "ఇస్తున్నారు"),
        "future": ("ఇస్తావు", "ఇస్తారు"),
        "past": ("ఇచ్చావు", "ఇచ్చారు"),
        "imp": ("ఇవ్వు", "ఇవ్వండి"),
    },
    "vinu": {  # to listen
        "cont": ("వింటున్నావు", "వింటున్నారు"),
        "future": ("వింటావు", "వింటారు"),
        "past": ("విన్నావు", "విన్నారు"),
        "imp": ("విను", "వినండి"),
    },
    "maatlaadu": {  # to speak
        "cont": ("మాట్లాడుతున్నావు", "మాట్లాడుతున్నారు"),
        "future": ("మాట్లాడతావు", "మాట్లాడతారు"),
        "imp": ("మాట్లాడు", "మాట్లాడండి"),
    },
    "raayi": {  # to write
        "future": ("రాస్తావు", "రాస్తారు"),
        "past": ("రాశావు", "రాశారు"),
        "imp": ("రాయి", "రాయండి"),
    },
    "chaduvu": {  # to read
        "future": ("చదువుతావు", "చదువుతారు"),
        "past": ("చదివావు", "చదివారు"),
        "imp": ("చదువు", "చదవండి"),
    },
    "aagu": {  # to stop, to wait
        "future": ("ఆగుతావు", "ఆగుతారు"),
        "past": ("ఆగావు", "ఆగారు"),
        "imp": ("ఆగు", "ఆగండి"),
    },
    "pampu": {  # to send
        "future": ("పంపుతావు", "పంపుతారు"),
        "past": ("పంపావు", "పంపారు"),
        "imp": ("పంపు", "పంపండి"),
    },
    "teliyu": {"future": ("తెలుసుకుంటావు", "తెలుసుకుంటారు")},
    "kurcho": {"imp": ("కూర్చో", "కూర్చోండి")},
    "kshaminchu": {"imp": ("క్షమించు", "క్షమించండి")},
    "veyyi": {"imp": ("వెయ్యి", "వేయండి")},
    "teccu": {"imp": ("తీసుకో", "తీసుకోండి")},
}

_TE_TENSE_ORDER = ("cont", "pres", "past", "future", "imp")


def _te_question(form: str) -> str:
    """
    Telugu yes/no questions fuse -ఆ onto the finite verb, replacing the final
    ు: తిన్నావు → తిన్నావా, తిన్నారు → తిన్నారా.
    """
    return form[:-1] + "ా" if form.endswith("ు") else form


def _te_verb_rules() -> Tuple[Rule, ...]:
    return _dravidian_verb_rules(
        _TE_PARADIGMS, _TE_TENSE_ORDER, question=_te_question
    )


TELUGU = LanguageTable(
    code="te",
    name="Telugu",
    # Binary pronoun system (du/Sie, tu/vous, நீ/நீங்கள்), but the lexical
    # politeness layer above it is not binary — "Vielen Dank" and "Herzlichen
    # Dank" are not the same register. Folding Polite and Formal together
    # would throw that away, so both slots stay live.
    canon=(1, 1, 2, 3),
    please=("", "", "కొంచెం ", "దయచేసి "),
    address_terms={
        "older_man": ("", "అన్నా", "అన్నా", "సర్"),
        "older_woman": ("", "అక్కా", "అక్కా", "మేడమ్"),
        "elder_man": ("", "మామయ్యా", "అయ్యా", "సర్"),
        "elder_woman": ("", "అత్తయ్యా", "అమ్మా", "మేడమ్"),
        "peer": ("", "బాబు", "అన్నా", "సర్"),
        "official": ("", "అయ్యా", "అయ్యా", "సర్"),
    },
    rules=_te_verb_rules() + (
        Rule("pron.2sg.nom", ("నువ్వు", "నువ్వు", "మీరు", "మీరు"), "you"),
        Rule("pron.2sg.acc", ("నిన్ను", "నిన్ను", "మిమ్మల్ని", "మిమ్మల్ని"), "you (obj)"),
        Rule("pron.2sg.gen", ("నీ", "నీ", "మీ", "మీ"), "your"),
        Rule("pron.2sg.dat", ("నీకు", "నీకు", "మీకు", "మీకు"), "to you"),
        Rule("pron.2sg.soc", ("నీతో", "నీతో", "మీతో", "మీతో"), "with you"),
        Rule("pron.2sg.loc", ("నీ దగ్గర", "నీ దగ్గర", "మీ దగ్గర", "మీ దగ్గర"), "at you"),
        Rule("pron.2sg.abl", ("నీ నుండి", "నీ నుండి", "మీ నుండి", "మీ నుండి"), "from you"),
        Rule("greet.hello", ("ఏయ్", "హలో", "నమస్కారం", "నమస్కారం"), "hello"),
        # దయచేసి is what separates Formal from Polite in Telugu — మీరు covers
        # both — so it has to be readable, not merely insertable. కొంచెం stays
        # out for the same reason Tamil's கொஞ்சம் does: it means "a little" and
        # is an ordinary adverb, so "కొంచెం ఆగు" is perfectly casual.
        Rule("polite.particle", ("", "", "", "దయచేసి"), "please"),
        # ధన్యవాదాలు spans Casual and Polite rather than sitting at one of
        # them. Pinned to Casual it outvoted the మీకు in "మీకు ధన్యవాదాలు",
        # which is Polite by the pronoun and neutral by the noun.
        Rule("greet.thanks", ("థాంక్స్", "ధన్యవాదాలు", "ధన్యవాదాలు", "చాలా ధన్యవాదాలు"), "thanks"),
        Rule("greet.sorry", ("సారీ", "సారీ", "క్షమించండి", "క్షమించండి"), "sorry"),
    ),
)

# --------------------------------------------------------------------------
# Kannada — ನೀನು / ನೀವು
# --------------------------------------------------------------------------

#: (ನೀನು form, ನೀವು form). ಹೇಗಿದ್ದೀಯ is listed as its own verb rather than
#: derived: ಹೇಗೆ + ಇದ್ದೀಯ is written solid, so a rule for the copula alone
#: never matches the commonest greeting in the language.
_KN_PARADIGMS: Dict[str, Dict[str, Tuple[str, str]]] = {
    "iru": {  # to be, to stay
        "pres": ("ಇದ್ದೀಯ", "ಇದ್ದೀರಿ"),
        "cont": ("ಇರುತ್ತಿದ್ದೀಯ", "ಇರುತ್ತಿದ್ದೀರಿ"),
        "future": ("ಇರುತ್ತೀಯ", "ಇರುತ್ತೀರಿ"),
        "past": ("ಇದ್ದೆ", "ಇದ್ದಿರಿ"),
        "imp": ("ಇರು", "ಇರಿ"),
    },
    "hegiru": {"pres": ("ಹೇಗಿದ್ದೀಯ", "ಹೇಗಿದ್ದೀರಿ")},  # how are you
    "baru": {  # to come
        "cont": ("ಬರುತ್ತಿದ್ದೀಯ", "ಬರುತ್ತಿದ್ದೀರಿ"),
        "future": ("ಬರುತ್ತೀಯ", "ಬರುತ್ತೀರಿ"),
        "past": ("ಬಂದೆ", "ಬಂದಿರಿ"),
        "imp": ("ಬಾ", "ಬನ್ನಿ"),
    },
    "hogu": {  # to go
        "cont": ("ಹೋಗುತ್ತಿದ್ದೀಯ", "ಹೋಗುತ್ತಿದ್ದೀರಿ"),
        "future": ("ಹೋಗುತ್ತೀಯ", "ಹೋಗುತ್ತೀರಿ"),
        "past": ("ಹೋದೆ", "ಹೋದಿರಿ"),
        "imp": ("ಹೋಗು", "ಹೋಗಿ"),
    },
    "maadu": {  # to do
        "cont": ("ಮಾಡುತ್ತಿದ್ದೀಯ", "ಮಾಡುತ್ತಿದ್ದೀರಿ"),
        "future": ("ಮಾಡುತ್ತೀಯ", "ಮಾಡುತ್ತೀರಿ"),
        "past": ("ಮಾಡಿದೆ", "ಮಾಡಿದಿರಿ"),
        "imp": ("ಮಾಡು", "ಮಾಡಿ"),
    },
    "helu": {  # to tell
        "cont": ("ಹೇಳುತ್ತಿದ್ದೀಯ", "ಹೇಳುತ್ತಿದ್ದೀರಿ"),
        "future": ("ಹೇಳುತ್ತೀಯ", "ಹೇಳುತ್ತೀರಿ"),
        "past": ("ಹೇಳಿದೆ", "ಹೇಳಿದಿರಿ"),
        "imp": ("ಹೇಳು", "ಹೇಳಿ"),
    },
    "nodu": {  # to look
        "cont": ("ನೋಡುತ್ತಿದ್ದೀಯ", "ನೋಡುತ್ತಿದ್ದೀರಿ"),
        "future": ("ನೋಡುತ್ತೀಯ", "ನೋಡುತ್ತೀರಿ"),
        "past": ("ನೋಡಿದೆ", "ನೋಡಿದಿರಿ"),
        "imp": ("ನೋಡು", "ನೋಡಿ"),
    },
    "kelu": {  # to ask, to listen
        "cont": ("ಕೇಳುತ್ತಿದ್ದೀಯ", "ಕೇಳುತ್ತಿದ್ದೀರಿ"),
        "future": ("ಕೇಳುತ್ತೀಯ", "ಕೇಳುತ್ತೀರಿ"),
        "past": ("ಕೇಳಿದೆ", "ಕೇಳಿದಿರಿ"),
        "imp": ("ಕೇಳು", "ಕೇಳಿ"),
    },
    "tinnu": {  # to eat
        "cont": ("ತಿನ್ನುತ್ತಿದ್ದೀಯ", "ತಿನ್ನುತ್ತಿದ್ದೀರಿ"),
        "future": ("ತಿನ್ನುತ್ತೀಯ", "ತಿನ್ನುತ್ತೀರಿ"),
        "past": ("ತಿಂದೆ", "ತಿಂದಿರಿ"),
        "imp": ("ತಿನ್ನು", "ತಿನ್ನಿ"),
    },
    "kudi": {  # to drink
        "future": ("ಕುಡಿಯುತ್ತೀಯ", "ಕುಡಿಯುತ್ತೀರಿ"),
        "past": ("ಕುಡಿದೆ", "ಕುಡಿದಿರಿ"),
        "imp": ("ಕುಡಿ", "ಕುಡಿಯಿರಿ"),
    },
    "kodu": {  # to give
        "future": ("ಕೊಡುತ್ತೀಯ", "ಕೊಡುತ್ತೀರಿ"),
        "past": ("ಕೊಟ್ಟೆ", "ಕೊಟ್ಟಿರಿ"),
        "imp": ("ಕೊಡು", "ಕೊಡಿ"),
    },
    "bare": {  # to write
        "future": ("ಬರೆಯುತ್ತೀಯ", "ಬರೆಯುತ್ತೀರಿ"),
        "past": ("ಬರೆದೆ", "ಬರೆದಿರಿ"),
        "imp": ("ಬರೆ", "ಬರೆಯಿರಿ"),
    },
    "odu": {  # to read
        "future": ("ಓದುತ್ತೀಯ", "ಓದುತ್ತೀರಿ"),
        "past": ("ಓದಿದೆ", "ಓದಿದಿರಿ"),
        "imp": ("ಓದು", "ಓದಿ"),
    },
    "nillu": {  # to stop, to stand
        "future": ("ನಿಲ್ಲುತ್ತೀಯ", "ನಿಲ್ಲುತ್ತೀರಿ"),
        "past": ("ನಿಂತೆ", "ನಿಂತಿರಿ"),
        "imp": ("ನಿಲ್ಲು", "ನಿಲ್ಲಿ"),
    },
    "kaayu": {  # to wait
        "future": ("ಕಾಯುತ್ತೀಯ", "ಕಾಯುತ್ತೀರಿ"),
        "past": ("ಕಾದೆ", "ಕಾದಿರಿ"),
        "imp": ("ಕಾಯಿ", "ಕಾಯಿರಿ"),
    },
    "maatanaadu": {  # to speak
        "future": ("ಮಾತನಾಡುತ್ತೀಯ", "ಮಾತನಾಡುತ್ತೀರಿ"),
        "imp": ("ಮಾತನಾಡು", "ಮಾತನಾಡಿ"),
    },
    "kalisu": {  # to send
        "future": ("ಕಳಿಸುತ್ತೀಯ", "ಕಳಿಸುತ್ತೀರಿ"),
        "past": ("ಕಳಿಸಿದೆ", "ಕಳಿಸಿದಿರಿ"),
        "imp": ("ಕಳಿಸು", "ಕಳಿಸಿ"),
    },
    "tegeduko": {"imp": ("ತೆಗೆದುಕೋ", "ತೆಗೆದುಕೊಳ್ಳಿ")},  # to take
    "kulitu": {"imp": ("ಕುಳಿತುಕೋ", "ಕುಳಿತುಕೊಳ್ಳಿ")},  # to sit
    "kshamisu": {"imp": ("ಕ್ಷಮಿಸು", "ಕ್ಷಮಿಸಿ")},  # to forgive
}

_KN_TENSE_ORDER = ("cont", "pres", "past", "future", "imp")

#: Kannada past syncretises 1sg and 2sg: ಮಾಡಿದೆ is both "I did" and "you did".
#: Left ungated, every "ನಾನು ... ಮಾಡಿದೆ" would be read as the listener's
#: register when it is the speaker's own verb and carries none. The pattern
#: scans back over a few intervening words because Kannada is verb-final and
#: the subject rarely abuts the verb.
_KN_FIRST_PERSON = r"ನಾನು(?:\s+\S+){0,4}\s*"


def _kn_question(form: str) -> str:
    """
    Kannada yes/no questions fuse -ಆ onto the finite verb: ಮಾಡುತ್ತೀಯ →
    ಮಾಡುತ್ತೀಯಾ, ಮಾಡುತ್ತೀರಿ → ಮಾಡುತ್ತೀರಾ. Forms ending in ಿ replace it; the
    rest, ending in an inherent -a, simply take the sign.
    """
    return form[:-1] + "ಾ" if form.endswith("ಿ") else form + "ಾ"


def _kn_verb_rules() -> Tuple[Rule, ...]:
    return _dravidian_verb_rules(
        _KN_PARADIGMS, _KN_TENSE_ORDER,
        question=_kn_question, guard_before=_KN_FIRST_PERSON,
    )


KANNADA = LanguageTable(
    code="kn",
    name="Kannada",
    # Binary pronoun system (du/Sie, tu/vous, நீ/நீங்கள்), but the lexical
    # politeness layer above it is not binary — "Vielen Dank" and "Herzlichen
    # Dank" are not the same register. Folding Polite and Formal together
    # would throw that away, so both slots stay live.
    canon=(1, 1, 2, 3),
    please=("", "", "ಸ್ವಲ್ಪ ", "ದಯವಿಟ್ಟು "),
    address_terms={
        "older_man": ("", "ಅಣ್ಣಾ", "ಅಣ್ಣಾ", "ಸರ್"),
        "older_woman": ("", "ಅಕ್ಕಾ", "ಅಕ್ಕಾ", "ಮೇಡಂ"),
        "elder_man": ("", "ಮಾವ", "ಸ್ವಾಮಿ", "ಸರ್"),
        "elder_woman": ("", "ಚಿಕ್ಕಮ್ಮ", "ಅಮ್ಮಾ", "ಮೇಡಂ"),
        "peer": ("", "ಗುರು", "ಅಣ್ಣಾ", "ಸರ್"),
        "official": ("", "ಸ್ವಾಮಿ", "ಸ್ವಾಮಿ", "ಸರ್"),
    },
    rules=_kn_verb_rules() + (
        Rule("pron.2sg.nom", ("ನೀನು", "ನೀನು", "ನೀವು", "ನೀವು"), "you"),
        Rule("pron.2sg.acc", ("ನಿನ್ನನ್ನು", "ನಿನ್ನನ್ನು", "ನಿಮ್ಮನ್ನು", "ನಿಮ್ಮನ್ನು"), "you (obj)"),
        Rule("pron.2sg.gen", ("ನಿನ್ನ", "ನಿನ್ನ", "ನಿಮ್ಮ", "ನಿಮ್ಮ"), "your"),
        Rule("pron.2sg.dat", ("ನಿನಗೆ", "ನಿನಗೆ", "ನಿಮಗೆ", "ನಿಮಗೆ"), "to you"),
        Rule("pron.2sg.soc", ("ನಿನ್ನೊಂದಿಗೆ", "ನಿನ್ನೊಂದಿಗೆ", "ನಿಮ್ಮೊಂದಿಗೆ", "ನಿಮ್ಮೊಂದಿಗೆ"), "with you"),
        Rule("pron.2sg.ins", ("ನಿನ್ನಿಂದ", "ನಿನ್ನಿಂದ", "ನಿಮ್ಮಿಂದ", "ನಿಮ್ಮಿಂದ"), "by/from you"),
        Rule("pron.2sg.loc", ("ನಿನ್ನಲ್ಲಿ", "ನಿನ್ನಲ್ಲಿ", "ನಿಮ್ಮಲ್ಲಿ", "ನಿಮ್ಮಲ್ಲಿ"), "at you"),
        Rule("greet.hello", ("ಏ", "ಹಲೋ", "ನಮಸ್ಕಾರ", "ನಮಸ್ಕಾರ"), "hello"),
        # ದಯವಿಟ್ಟು is what separates Formal from Polite in Kannada — ನೀವು covers
        # both — so it has to be readable, not merely insertable. ಸ್ವಲ್ಪ stays
        # out: it means "a little" and is an ordinary adverb, so "ಸ್ವಲ್ಪ ನಿಲ್ಲು"
        # is perfectly casual.
        Rule("polite.particle", ("", "", "", "ದಯವಿಟ್ಟು"), "please"),
        # ಧನ್ಯವಾದ spans Casual and Polite rather than sitting at one of them.
        # Pinned to Casual it outvoted the ನಿಮಗೆ in "ನಿಮಗೆ ಧನ್ಯವಾದ", which is
        # Polite by the pronoun and neutral by the noun.
        Rule("greet.thanks", ("ಥ್ಯಾಂಕ್ಸ್", "ಧನ್ಯವಾದ", "ಧನ್ಯವಾದ", "ಅನಂತ ಧನ್ಯವಾದಗಳು"), "thanks"),
        Rule("greet.sorry", ("ಸಾರಿ", "ಸಾರಿ", "ಕ್ಷಮಿಸಿ", "ಕ್ಷಮಿಸಿ"), "sorry"),
    ),
)

# --------------------------------------------------------------------------
# Malayalam — നീ / നിങ്ങൾ / താങ്കൾ
# --------------------------------------------------------------------------

#: (നീ form, നിങ്ങൾ form, താങ്കൾ form).
#:
#: Malayalam is the one Dravidian language here that needs no verb paradigm and
#: a three-column imperative — the opposite of its neighbours. Finite verbs do
#: not agree with the subject at all, so ചെയ്യുന്നു is identical under നീ,
#: നിങ്ങൾ and താങ്കൾ and carries no register: the pronoun is the whole signal.
#: The imperative, by contrast, distinguishes all three levels, where Tamil,
#: Telugu and Kannada distinguish two — bare stem, -ഊ, and the necessitative
#: -അണം, which asks rather than tells and is the deferential one.
_ML_IMPERATIVES: Dict[str, Tuple[str, str, str]] = {
    "varuka": ("വാ", "വരൂ", "വരണം"),  # come
    "pokuka": ("പോ", "പോകൂ", "പോകണം"),  # go
    "parayuka": ("പറ", "പറയൂ", "പറയണം"),  # say
    "cheyyuka": ("ചെയ്യ്", "ചെയ്യൂ", "ചെയ്യണം"),  # do
    "nokkuka": ("നോക്ക്", "നോക്കൂ", "നോക്കണം"),  # look
    "irikkuka": ("ഇരി", "ഇരിക്കൂ", "ഇരിക്കണം"),  # sit
    "kelkkuka": ("കേൾക്ക്", "കേൾക്കൂ", "കേൾക്കണം"),  # listen
    "kshamikkuka": ("ക്ഷമിക്ക്", "ക്ഷമിക്കൂ", "ക്ഷമിക്കണം"),  # forgive
    "tharuka": ("താ", "തരൂ", "തരണം"),  # give (to me)
    "kodukkuka": ("കൊടുക്ക്", "കൊടുക്കൂ", "കൊടുക്കണം"),  # give (to another)
    "edukkuka": ("എടുക്ക്", "എടുക്കൂ", "എടുക്കണം"),  # take
    "kazhikkuka": ("കഴിക്ക്", "കഴിക്കൂ", "കഴിക്കണം"),  # eat
    "kudikkuka": ("കുടിക്ക്", "കുടിക്കൂ", "കുടിക്കണം"),  # drink
    "ezhuthuka": ("എഴുത്", "എഴുതൂ", "എഴുതണം"),  # write
    "vaayikkuka": ("വായിക്ക്", "വായിക്കൂ", "വായിക്കണം"),  # read
    "kaathirikkuka": ("കാത്തിരിക്ക്", "കാത്തിരിക്കൂ", "കാത്തിരിക്കണം"),  # wait
    "nirthuka": ("നിർത്ത്", "നിർത്തൂ", "നിർത്തണം"),  # stop
    "sahaayikkuka": ("സഹായിക്ക്", "സഹായിക്കൂ", "സഹായിക്കണം"),  # help
    "oppiduka": ("ഒപ്പിട്", "ഒപ്പിടൂ", "ഒപ്പിടണം"),  # sign
    "samsaarikkuka": ("സംസാരിക്ക്", "സംസാരിക്കൂ", "സംസാരിക്കണം"),  # speak
    "ayakkuka": ("അയക്ക്", "അയക്കൂ", "അയക്കണം"),  # send
    "thudanguka": ("തുടങ്ങ്", "തുടങ്ങൂ", "തുടങ്ങണം"),  # begin
    "kaanikkuka": ("കാണിക്ക്", "കാണിക്കൂ", "കാണിക്കണം"),  # show
    "vaangikkuka": ("വാങ്ങ്", "വാങ്ങൂ", "വാങ്ങണം"),  # buy
}


def _ml_verb_rules() -> Tuple[Rule, ...]:
    return tuple(
        Rule(f"v.{verb}.imp", (fam, fam, polite, formal), f"{verb} · imperative")
        for verb, (fam, polite, formal) in _ML_IMPERATIVES.items()
    )


MALAYALAM = LanguageTable(
    code="ml",
    name="Malayalam",
    canon=(1, 1, 2, 3),
    please=("", "", "ഒന്ന് ", "ദയവായി "),
    address_terms={
        "older_man": ("", "ചേട്ടാ", "ചേട്ടാ", "സാർ"),
        "older_woman": ("", "ചേച്ചി", "ചേച്ചി", "മാഡം"),
        "elder_man": ("", "അമ്മാവാ", "സാർ", "സാർ"),
        "elder_woman": ("", "ആന്റി", "ആന്റി", "മാഡം"),
        "peer": ("", "മോനേ", "ചേട്ടാ", "സാർ"),
        "official": ("", "സാർ", "സാർ", "സാർ"),
    },
    rules=_ml_verb_rules() + (
        Rule("pron.2sg.nom", ("നീ", "നീ", "നിങ്ങൾ", "താങ്കൾ"), "you"),
        Rule("pron.2sg.acc", ("നിന്നെ", "നിന്നെ", "നിങ്ങളെ", "താങ്കളെ"), "you (obj)"),
        Rule("pron.2sg.gen", ("നിന്റെ", "നിന്റെ", "നിങ്ങളുടെ", "താങ്കളുടെ"), "your"),
        Rule("pron.2sg.dat", ("നിനക്ക്", "നിനക്ക്", "നിങ്ങൾക്ക്", "താങ്കൾക്ക്"), "to you"),
        Rule("pron.2sg.soc", ("നിന്നോട്", "നിന്നോട്", "നിങ്ങളോട്", "താങ്കളോട്"), "to/with you"),
        Rule("pron.2sg.loc", ("നിന്നിൽ", "നിന്നിൽ", "നിങ്ങളിൽ", "താങ്കളിൽ"), "in you"),
        Rule("greet.hello", ("എടാ", "ഹലോ", "നമസ്കാരം", "നമസ്കാരം"), "hello"),
        # ദയവായി is readable as well as insertable, like Tamil's தயவுசெய்து.
        # ഒന്ന് is deliberately not a rule: it means "one/a bit" and softens
        # any request, casual ones included.
        Rule("polite.particle", ("", "", "", "ദയവായി"), "please"),
        # Unlike its neighbours, Malayalam reaches Formal with a pronoun —
        # താങ്കൾ — so the intensifier is optional rather than load-bearing, and
        # slot 3 stays നന്ദി. Forcing വളരെ made "താങ്കൾക്ക് നന്ദി" unstable at
        # its own level: already Formal, yet rewritten on arriving there.
        Rule("greet.thanks", ("താങ്ക്സ്", "നന്ദി", "നന്ദി", "നന്ദി"), "thanks"),
        # Tracks the imperative ladder rather than repeating ക്ഷമിക്കണം at
        # both honorific levels, which made the necessitative unreadable as
        # the Formal step it is.
        Rule("greet.sorry", ("സോറി", "സോറി", "ക്ഷമിക്കൂ", "ക്ഷമിക്കണം"), "sorry"),
    ),
)

# --------------------------------------------------------------------------
# European
# --------------------------------------------------------------------------

# German changes the pronoun *and* the verb together: du bist / Sie sind. A bare
# pronoun swap produces "Du sind", which is worse than leaving the sentence
# alone. So the subject pronoun is only ever rewritten as part of a two-word
# clause rule that carries the matching verb form with it, in both word orders
# (statement "du bist", question "bist du").
_DE_VERBS = (
    # rule stem, du-form,       Sie-form,    gloss
    ("sein", "bist", "sind", "you are"),
    ("haben", "hast", "haben", "you have"),
    ("koennen", "kannst", "können", "you can"),
    ("wollen", "willst", "wollen", "you want"),
    ("muessen", "musst", "müssen", "you must"),
    ("duerfen", "darfst", "dürfen", "you may"),
    ("sollen", "sollst", "sollen", "you should"),
    ("werden", "wirst", "werden", "you will"),
    ("moegen", "magst", "mögen", "you like"),
    ("moechten", "möchtest", "möchten", "you would like"),
    ("koennten", "könntest", "könnten", "you could"),
    ("wuerden", "würdest", "würden", "you would"),
    ("haetten", "hättest", "hätten", "you would have"),
    ("waeren", "wärst", "wären", "you would be"),
    ("machen", "machst", "machen", "you do"),
    ("gehen", "gehst", "gehen", "you go"),
    ("kommen", "kommst", "kommen", "you come"),
    ("sehen", "siehst", "sehen", "you see"),
    ("sprechen", "sprichst", "sprechen", "you speak"),
    ("wissen", "weißt", "wissen", "you know"),
    ("nehmen", "nimmst", "nehmen", "you take"),
    ("geben", "gibst", "geben", "you give"),
    ("brauchen", "brauchst", "brauchen", "you need"),
    ("moechte_helfen", "hilfst", "helfen", "you help"),
    ("arbeiten", "arbeitest", "arbeiten", "you work"),
    ("wohnen", "wohnst", "wohnen", "you live"),
    ("heissen", "heißt", "heißen", "you are called"),
    ("verstehen", "verstehst", "verstehen", "you understand"),
    # The list is the whole of German's coverage — the clause rules are the
    # only thing that rewrites a subject — so a verb missing from it is a
    # sentence the engine cannot touch. "Wohin fährst du?" was one.
    ("fahren", "fährst", "fahren", "you travel"),
    ("essen", "isst", "essen", "you eat"),
    ("trinken", "trinkst", "trinken", "you drink"),
    ("lesen", "liest", "lesen", "you read"),
    ("schreiben", "schreibst", "schreiben", "you write"),
    ("fragen", "fragst", "fragen", "you ask"),
    ("warten", "wartest", "warten", "you wait"),
    ("bleiben", "bleibst", "bleiben", "you stay"),
    ("finden", "findest", "finden", "you find"),
    ("denken", "denkst", "denken", "you think"),
    ("glauben", "glaubst", "glauben", "you believe"),
    ("bringen", "bringst", "bringen", "you bring"),
    ("sitzen", "sitzt", "sitzen", "you sit"),
    ("stehen", "stehst", "stehen", "you stand"),
    ("lernen", "lernst", "lernen", "you learn"),
    ("spielen", "spielst", "spielen", "you play"),
    ("kaufen", "kaufst", "kaufen", "you buy"),
    ("zahlen", "zahlst", "zahlen", "you pay"),
    ("hoeren", "hörst", "hören", "you hear"),
    ("schlafen", "schläfst", "schlafen", "you sleep"),
    ("suchen", "suchst", "suchen", "you look for"),
    ("zeigen", "zeigst", "zeigen", "you show"),
    ("sagen", "sagst", "sagen", "you say"),
    ("meinen", "meinst", "meinen", "you mean"),
    ("brauchen_alt", "benötigst", "benötigen", "you require"),
    ("moechten_haben", "hättest gern", "hätten gern", "you would like"),
)

#: Third-person singular verbs. Capitalised "Sie" is the polite pronoun, but it
#: is also sentence-initial "she", and only the agreement separates them:
#: "Sie ist nett" is about her, "Sie sind nett" about the listener.
_DE_THIRD_SINGULAR = (
    r"\s+(?:ist|hat|kann|will|muss|darf|soll|wird|mag|möchte|könnte|würde|"
    r"hätte|wäre|macht|geht|kommt|sieht|spricht|weiß|nimmt|gibt|braucht|"
    r"hilft|arbeitet|wohnt|heißt|versteht|fährt|isst|trinkt|liest|schreibt|"
    r"fragt|wartet|bleibt|findet|denkt|glaubt|bringt|sitzt|steht|lernt|"
    r"spielt|kauft|zahlt|hört|schläft|sucht|zeigt|sagt|meint)\b"
)


def _de_clause_rules() -> Tuple[Rule, ...]:
    """Two rules per verb — statement order and question/inversion order."""
    out = []
    for stem, du_form, sie_form, gloss in _DE_VERBS:
        out.append(
            Rule(
                f"clause.{stem}.stmt",
                (f"du {du_form}", f"du {du_form}", f"Sie {sie_form}", f"Sie {sie_form}"),
                gloss,
                cased=True,
            )
        )
        out.append(
            Rule(
                f"clause.{stem}.inv",
                (f"{du_form} du", f"{du_form} du", f"{sie_form} Sie", f"{sie_form} Sie"),
                gloss,
                cased=True,
            )
        )
    return tuple(out)


# Object "Sie" only becomes "dich" in an unambiguous object slot: after a
# preposition, or after a first/third-person verb. Anywhere else ("Wo wohnen
# Sie?") the pronoun is a subject and the clause rules own it.
_DE_OBJECT_CONTEXT = (
    r"\b(?:für|ohne|um|gegen|durch|über|auf|an|in|mit|bei|nach|von|zu|"
    r"sehe|höre|verstehe|frage|rufe|treffe|kenne|liebe|brauche|besuche|"
    r"bitte|danke|meine|suche|finde|erwarte|begleite|informiere|"
    r"sieht|hört|versteht|fragt|ruft|trifft|kennt|liebt|braucht|besucht)\s+"
)

GERMAN = LanguageTable(
    code="de",
    name="German",
    # Binary pronoun system (du/Sie), but the lexical politeness layer above it
    # is not binary — "Vielen Dank" and "Herzlichen Dank" are not the same
    # register. Folding Polite and Formal together would throw that away, so
    # both slots stay live.
    canon=(1, 1, 2, 3),
    please=("", "", "bitte ", "bitte "),
    rules=_de_clause_rules() + (
        # detect_only. The clause rules do the rewriting, because German moves
        # the pronoun and the verb together and a bare swap gives "Du sind" —
        # but they only cover the verbs listed above, and until now anything
        # outside that list read as nothing at all. The pronoun is unambiguous
        # evidence; it just cannot be changed by itself.
        # Guarded off the object slot as well, or it shadows the accusative
        # rule below — both match "Sie", this one is declared first, and being
        # detect_only it would swallow the span and rewrite nothing, leaving
        # "Das ist für Sie" stuck at every level.
        Rule("pron.2sg.nom", ("du", "du", "Sie", "Sie"), "you", cased=True,
             detect_only=True, guard_before=_DE_OBJECT_CONTEXT,
             form_guards=(("Sie", _DE_OBJECT_CONTEXT, _DE_THIRD_SINGULAR,
                           "", "", ""),)),
        Rule("pron.2sg.acc", ("dich", "dich", "Sie", "Sie"), "you (acc)",
             cased=True, require_before=_DE_OBJECT_CONTEXT),
        Rule("pron.2sg.dat", ("dir", "dir", "Ihnen", "Ihnen"), "you (dat)", cased=True),
        Rule("poss.nom.m", ("dein", "dein", "Ihr", "Ihr"), "your", cased=True),
        Rule("poss.nom.f", ("deine", "deine", "Ihre", "Ihre"), "your (f/pl)", cased=True),
        Rule("poss.acc.m", ("deinen", "deinen", "Ihren", "Ihren"), "your (acc m)", cased=True),
        Rule("poss.dat.m", ("deinem", "deinem", "Ihrem", "Ihrem"), "your (dat m)", cased=True),
        Rule("poss.dat.f", ("deiner", "deiner", "Ihrer", "Ihrer"), "your (dat f)", cased=True),
        Rule("greet.hello", ("Hi", "Hallo", "Guten Tag", "Guten Tag"), "hello"),
        Rule("greet.bye", ("Tschüss", "Tschüss", "Auf Wiedersehen", "Auf Wiedersehen"), "goodbye"),
        # Danke is neutral across everything below Formal — the gold says so,
        # with "Danke dir" and "Danke Ihnen" differing only in the pronoun —
        # and Herzlichen is what lifts it. It used to escalate at Polite, so
        # "Danke dir" came back as "Vielen Dank Ihnen", which is not a thing
        # anyone says.
        Rule("greet.thanks", ("Danke", "Danke", "Danke", "Herzlichen Dank"), "thanks"),
        Rule("greet.sorry", ("Sorry", "Sorry", "Entschuldigung", "Verzeihung"), "sorry"),
        # entschuldigen as an imperative rather than an interjection: it agrees
        # like any other verb, and pinning "Entschuldigen Sie bitte" to Formal
        # alone made the ordinary polite apology read as the formal one.
        Rule("v.entschuldigen.imp",
             ("Entschuldige", "Entschuldige", "Entschuldigen Sie", "Entschuldigen Sie"),
             "excuse me", cased=True),
        # detect_only: a fixed formal turn of phrase with no natural casual
        # counterpart. Rewriting it down collapsed the whole clause to
        # "Danke.", which is not what the sentence said and does not read as
        # Close either. Better to recognise it and leave it alone.
        Rule("clause.bedanken", ("Danke", "Danke", "Vielen Dank",
                                 "Ich bedanke mich vielmals"), "I thank you",
             detect_only=True),
        # A sign-off and a salutation are pure register: no content at all, and
        # the choice between them is the entire message.
        Rule("close.signoff", ("Bis dann", "Liebe Grüße", "Viele Grüße",
                               "Mit freundlichen Grüßen"), "sign-off", cased=True),
        Rule("open.salutation", ("Hey", "Hallo zusammen", "Guten Tag",
                                 "Sehr geehrte Damen und Herren"),
             "salutation", cased=True),
    ),
)

# French "vous" wears three hats and only the left context tells them apart:
#   subject   "vous êtes"      -> tu
#   clitic    "je vous vois"   -> te
#   tonic     "c'est pour vous"-> toi
_FR_CLITIC_CONTEXT = r"\b(?:je|tu|il|elle|on|nous|ils|elles|ne|me|te|se)\s+|\bj'|\bn'"
_FR_PREP_CONTEXT = r"\b(?:pour|avec|chez|sans|à|de|comme|que|sur|sous|vers|entre|contre)\s+"

# A French verb rule must not fire when the subject is not second person:
# "je vois" and "tu vois" are spelled identically, so upgrading "je te vois"
# would otherwise produce "je vous voyez". Clitics may sit between the subject
# and the verb, so the pattern skips over them.
_FR_NON_2P_SUBJECT = (
    r"(?:\bje\b|\bj'|\bil\b|\belle\b|\bon\b|\bnous\b|\bils\b|\belles\b|\bqui\b)"
    r"(?:\s+(?:me|te|se|nous|vous|le|la|les|lui|leur|y|en))*\s+"
)

_FR_VERBS = (
    ("etre", "es", "êtes", "you are"),
    ("avoir", "as", "avez", "you have"),
    ("pouvoir", "peux", "pouvez", "you can"),
    ("vouloir", "veux", "voulez", "you want"),
    ("devoir", "dois", "devez", "you must"),
    ("aller", "vas", "allez", "you go"),
    ("faire", "fais", "faites", "you do"),
    ("venir", "viens", "venez", "you come"),
    ("savoir", "sais", "savez", "you know"),
    ("voir", "vois", "voyez", "you see"),
    ("prendre", "prends", "prenez", "you take"),
    ("comprendre", "comprends", "comprenez", "you understand"),
    ("connaitre", "connais", "connaissez", "you know (someone)"),
    ("parler", "parles", "parlez", "you speak"),
    ("habiter", "habites", "habitez", "you live"),
    ("travailler", "travailles", "travaillez", "you work"),
    ("aimer", "aimes", "aimez", "you like"),
    ("attendre", "attends", "attendez", "you wait"),
)


def _fr_verb_rules() -> Tuple[Rule, ...]:
    return tuple(
        Rule(f"v.{stem}", (tu_form, tu_form, vous_form, vous_form), gloss,
             guard_before=_FR_NON_2P_SUBJECT)
        for stem, tu_form, vous_form, gloss in _FR_VERBS
    )


_FR_VOWEL = "aàâeéèêëiîïoôöuùûüyhAÀÂEÉÈÊËIÎÏOÔÖUÙÛÜYH"

FRENCH = LanguageTable(
    code="fr",
    name="French",
    # Binary pronoun system (du/Sie, tu/vous, நீ/நீங்கள்), but the lexical
    # politeness layer above it is not binary — "Vielen Dank" and "Herzlichen
    # Dank" are not the same register. Folding Polite and Formal together
    # would throw that away, so both slots stay live.
    canon=(1, 1, 2, 3),
    please=("", "", "s'il vous plaît ", "s'il vous plaît "),
    # "Je t'attends" has to be seen as "je te attends" for the clitic rule to
    # fire at all, then put back into real orthography afterwards.
    normalise=((r"\bt'", "te "), (r"\bT'", "Te ")),
    elide=(
        (rf"\bte (?=[{_FR_VOWEL}])", "t'"),
        (rf"\bTe (?=[{_FR_VOWEL}])", "T'"),
    ),
    rules=_fr_verb_rules() + (
        Rule("clause.peux_tu", ("peux-tu", "peux-tu", "pouvez-vous", "pouvez-vous"), "can you"),
        Rule("clause.pourrais_tu", ("pourrais-tu", "pourrais-tu", "pourriez-vous", "pourriez-vous"), "could you"),
        Rule("clause.as_tu", ("as-tu", "as-tu", "avez-vous", "avez-vous"), "have you"),
        Rule("clause.es_tu", ("es-tu", "es-tu", "êtes-vous", "êtes-vous"), "are you"),
        Rule("clause.stp", ("s'il te plaît", "s'il te plaît", "s'il vous plaît", "s'il vous plaît"), "please"),
        # Reflexive questions move three things at once — the clitic, the verb
        # ending and the inverted subject — so they have to be one rule.
        # Rewriting them piecemeal produced "Comment t'appelles-vous ?", which
        # is the polite pronoun on the familiar verb, and "Comment tu
        # appelez-tu ?" coming back down.
        #
        # Written against the *normalised* text: `normalise` above expands t'
        # to "te " before anything is matched, so a rule spelling it "t'appelles"
        # can never fire. The elision is put back afterwards.
        Rule("clause.appeler.inv",
             ("te appelles-tu", "te appelles-tu",
              "vous appelez-vous", "vous appelez-vous"), "what are you called"),
        Rule("clause.sens.inv",
             ("te sens-tu", "te sens-tu", "vous sentez-vous", "vous sentez-vous"),
             "how do you feel"),
        # Veuillez is the formal imperative of vouloir and the standard opener
        # of a written instruction — the register of a notice rather than a
        # request between people. Nothing matched it, so both formal rows read
        # as no register at all.
        Rule("clause.veuillez", ("", "", "", "Veuillez"), "kindly (formal imperative)"),
        # Subject "vous": neither in a clitic slot nor after a preposition.
        Rule("pron.2sg.nom", ("tu", "tu", "vous", "vous"), "you",
             guard_before=f"(?:{_FR_CLITIC_CONTEXT}|{_FR_PREP_CONTEXT})"),
        # Object "vous": only in a clitic slot, where it becomes "te".
        Rule("pron.2sg.obj", ("te", "te", "vous", "vous"), "you (obj)",
             require_before=_FR_CLITIC_CONTEXT),
        # Tonic "vous": after a preposition, where it becomes "toi".
        Rule("pron.2sg.tonic", ("toi", "toi", "vous", "vous"), "you (tonic)",
             require_before=_FR_PREP_CONTEXT),
        # Both singular possessives collapse to "votre" going up. Coming back
        # down, the selector consults the following noun's gender, so
        # "votre maison" -> "ta maison" rather than the wrong "ton maison".
        # poss.m is declared first, so it is the rule that matches "votre" and
        # therefore the one that carries the selector.
        Rule("poss.m", ("ton", "ton", "votre", "votre"), "your (m)",
             select="fr_possessive"),
        Rule("poss.f", ("ta", "ta", "votre", "votre"), "your (f)"),
        Rule("poss.pl", ("tes", "tes", "vos", "vos"), "your (pl)"),
        Rule("greet.hello", ("Coucou", "Salut", "Bonjour", "Bonjour"), "hello"),
        Rule("greet.bye", ("Ciao", "Salut", "Au revoir", "Au revoir"), "goodbye"),
        # Merci is neutral below Formal — "Merci à toi" and "Merci à vous"
        # differ only in the pronoun — so it no longer escalates at Polite,
        # and no longer outvotes the vous beside it. Same shape as five other
        # languages here.
        Rule("greet.thanks", ("Merci", "Merci", "Merci", "Merci beaucoup"), "thanks"),
        # greet.sorry no longer owns "Excusez-moi": the imperative rule below
        # does, and with both holding it the first-declared won and dragged
        # "Excusez-moi" down to "Désolé" instead of "Excuse-moi".
        Rule("greet.sorry", ("Désolé", "Désolé", "Je suis désolé",
                             "Je vous prie de m'excuser"), "sorry"),
        # excuser as an imperative rather than an interjection: it agrees like
        # any other verb, and only the honorific half was in the table, so
        # "Excuse-moi" read as nothing and could not be climbed.
        Rule("v.excuser.imp", ("Excuse-moi", "Excuse-moi", "Excusez-moi", "Excusez-moi"),
             "excuse me"),
        # detect_only, and the middle slots are the tu counterpart rather than
        # a ladder: the vous form of remercier *is* the formal register, so it
        # is the only rung that carries information. Rewriting with it would
        # substitute a clause for the word Merci — the "La ringrazio a Lei"
        # mistake — so it only ever reads.
        Rule("clause.remercier", ("je te remercie", "je te remercie",
                                  "je te remercie", "je vous remercie"),
             "I thank you", detect_only=True),
        # A sign-off is pure register: no content at all, and the choice
        # between them is the whole message.
        Rule("close.signoff", ("Bisous", "À plus", "Bien à vous", "Cordialement"),
             "sign-off"),
    ),
)

# --------------------------------------------------------------------------
# Spanish verbs.
#
# Same shape of problem as Italian — usted takes third-person agreement, so
# "es" is both "you are" and "he/she is" — but *without* Italian's escape
# hatch: Spanish does not capitalise usted, so there is no casing cue. The
# left-context guard is the only tool, and Spanish drops subject pronouns
# freely, so some ambiguity is irreducible.
#
# Each entry is (tú, usted).
# --------------------------------------------------------------------------

_ES_VERBS: Tuple[Tuple[str, str, str, str], ...] = (
    ("ser", "eres", "es", "you are"),
    ("estar", "estás", "está", "you are (state)"),
    ("tener", "tienes", "tiene", "you have"),
    ("poder", "puedes", "puede", "you can"),
    ("querer", "quieres", "quiere", "you want"),
    ("ir", "vas", "va", "you go"),
    ("venir", "vienes", "viene", "you come"),
    ("hacer", "haces", "hace", "you do"),
    ("decir", "dices", "dice", "you say"),
    ("dar", "das", "da", "you give"),
    ("ver", "ves", "ve", "you see"),
    ("saber", "sabes", "sabe", "you know"),
    ("conocer", "conoces", "conoce", "you know (someone)"),
    ("hablar", "hablas", "habla", "you speak"),
    ("vivir", "vives", "vive", "you live"),
    ("trabajar", "trabajas", "trabaja", "you work"),
    ("comer", "comes", "come", "you eat"),
    ("beber", "bebes", "bebe", "you drink"),
    ("entender", "entiendes", "entiende", "you understand"),
    ("necesitar", "necesitas", "necesita", "you need"),
    ("llegar", "llegas", "llega", "you arrive"),
    ("esperar", "esperas", "espera", "you wait"),
    ("pagar", "pagas", "paga", "you pay"),
    ("comprar", "compras", "compra", "you buy"),
    ("ayudar", "ayudas", "ayuda", "you help"),
    ("escribir", "escribes", "escribe", "you write"),
    ("leer", "lees", "lee", "you read"),
    ("abrir", "abres", "abre", "you open"),
    ("pensar", "piensas", "piensa", "you think"),
    ("volver", "vuelves", "vuelve", "you return"),
)

#: Reflexives and the dative frame, where the clitic moves with the register:
#: te llamas -> se llama, te gusta -> le gusta.
_ES_CLITIC: Tuple[Tuple[str, str, str, str], ...] = (
    ("llamarse", "te llamas", "se llama", "you are called"),
    ("sentarse", "te sientas", "se sienta", "you sit"),
    ("gustar", "te gusta", "le gusta", "you like"),
    ("parecer", "te parece", "le parece", "you think"),
    ("importar", "te importa", "le importa", "you mind"),
)

#: Imperatives, built from the subjunctive for usted and so not derivable from
#: the indicative. Several tú forms are irregular one-syllable stems.
_ES_IMPERATIVES: Tuple[Tuple[str, str, str, str], ...] = (
    ("hablar", "habla", "hable", "speak!"),
    ("comer", "come", "coma", "eat!"),
    ("abrir", "abre", "abra", "open!"),
    ("venir", "ven", "venga", "come!"),
    ("decir", "di", "diga", "say!"),
    ("hacer", "haz", "haga", "do!"),
    ("ir", "ve", "vaya", "go!"),
    ("tener", "ten", "tenga", "have!"),
    ("poner", "pon", "ponga", "put!"),
    ("salir", "sal", "salga", "leave!"),
    ("esperar", "espera", "espere", "wait!"),
    ("perdonar", "perdona", "perdone", "forgive!"),
    ("disculpar", "disculpa", "disculpe", "excuse!"),
    ("pasar", "pasa", "pase", "come in!"),
    ("mirar", "mira", "mire", "look!"),
    ("escuchar", "escucha", "escuche", "listen!"),
    ("dime", "dime", "dígame", "tell me!"),
)

#: Explicit third-person subjects. Spanish omits pronouns far more than Italian
#: does, so this catches fewer cases than the Italian equivalent — the residue
#: is genuine ambiguity, not a missing rule.
_ES_3P_SUBJECT = r"\b(?:él|ella|ellos|ellas|quien|quién|que|uno|alguien|nadie)\s+"

#: An imperative heads its clause. This is what separates the two readings of
#: "espera": the *usted* indicative ("he/she waits", "you wait") and the *tú*
#: imperative ("wait!") are the same string at opposite ends of the scale, so
#: "Espere un momento" downgraded to "Espera un momento" and then read back as
#: Polite. Position is the only cue Spanish gives.
_CLAUSE_INITIAL = r"(?:^|[.!?¡¿,;:]\s*)"

#: The pronoun that licenses reading a third-person form as second person.
_ES_USTED = r"usted(?:es)?\b"

#: Spanish keeps a distinct pronoun for the object of a preposition: "para ti",
#: never "para tú". Both cases share one form at the honorific levels — usted
#: is usted either way — so coming down, only the preceding preposition says
#: which of the two the sentence wants.
_ES_PREPOSITION = (
    r"\b(?:a|de|en|con|por|para|sin|sobre|hacia|hasta|desde|entre|según|"
    r"contra|tras|ante|bajo)\s+"
)


def _es_verb_rules() -> Tuple[Rule, ...]:
    """
    Build the indicative, clitic and imperative rules.

    The constraints go on the *usted* form alone, via ``form_guards``. They
    were on the rule, which also constrained the tú form, and that is why
    "¿Hablas inglés?" detected nothing: `habla` collides with a tú imperative,
    so the whole rule was kept out of clause-initial position — and `hablas`,
    which is unambiguous and needs no help, was kept out with it.

    That clause-initial guard is gone. It existed to stop "Espera un momento"
    reading as an indicative, and requiring an adjacent usted already does
    that, more precisely: it blocked the reading wherever the verb led its
    clause, including "¿Habla usted inglés?", where Spanish inverts and the
    indicative is exactly what is meant.
    """
    out = []
    for stem, tu, usted, gloss in _ES_VERBS:
        out.append(
            Rule(f"v.{stem}", (tu, tu, usted, usted), gloss,
                 form_guards=((usted, _ES_3P_SUBJECT, "", "", "", _ES_USTED),))
        )
    out += [
        Rule(f"v.{stem}.clitic", (tu, tu, usted, usted), gloss,
             form_guards=((usted, "", "", "", "", _ES_USTED),))
        for stem, tu, usted, gloss in _ES_CLITIC
    ]
    # Imperatives need no adjacency requirement — the usted imperative comes
    # from the subjunctive rather than the third person, so "Venga aquí" is
    # unambiguous. They need the opposite guard instead: an imperative takes no
    # subject, so an adjacent usted rules the reading out. Without it "¿Habla
    # usted inglés?" parsed as the tú imperative "habla" and read Casual —
    # the one form that is both an imperative and an indicative.
    out += [
        Rule(f"v.{stem}.imp", (tu, tu, usted, usted), gloss,
             guard_before=rf"{_ES_USTED}\s+", guard_after=rf"\s+{_ES_USTED}")
        for stem, tu, usted, gloss in _ES_IMPERATIVES
    ]
    return tuple(out)


SPANISH = LanguageTable(
    code="es",
    name="Spanish",
    # Binary pronoun system (du/Sie, tu/vous, நீ/நீங்கள்), but the lexical
    # politeness layer above it is not binary — "Vielen Dank" and "Herzlichen
    # Dank" are not the same register. Folding Polite and Formal together
    # would throw that away, so both slots stay live.
    canon=(1, 1, 2, 3),
    please=("", "", "por favor ", "por favor "),
    # usted takes third-person agreement, so a rewritten verb alone leaves the
    # sentence ambiguous — "¿Dónde vive?" is equally "where does he live?".
    # Spanish puts the pronoun after the verb, where Portuguese puts it before.
    insert_subject=("", "", "usted", "usted"),
    subject_position="after",
    rules=_es_verb_rules() + (
        Rule("clause.como_estas", ("¿Cómo estás?", "¿Cómo estás?", "¿Cómo está usted?", "¿Cómo está usted?"), "how are you"),
        # Prepositional before nominative, and each guarded off the other's
        # ground: Spanish uses a distinct oblique form, so "para usted" has to
        # come down to "para ti" rather than "para tú".
        Rule("pron.2sg.prep", ("ti", "ti", "usted", "usted"), "you (prep)",
             require_before=_ES_PREPOSITION),
        Rule("pron.2sg.nom", ("tú", "tú", "usted", "usted"), "you",
             guard_before=_ES_PREPOSITION),
        Rule("pron.2sg.obj", ("te", "te", "le", "le"), "you (obj)"),
        Rule("pron.2sg.com", ("contigo", "contigo", "con usted", "con usted"), "with you"),
        Rule("poss.sg", ("tu", "tu", "su", "su"), "your"),
        Rule("poss.pl", ("tus", "tus", "sus", "sus"), "your (pl)"),
        Rule("greet.hello", ("Ey", "Hola", "Buenos días", "Buenos días"), "hello"),
        Rule("greet.bye", ("Chao", "Adiós", "Hasta luego", "Que tenga un buen día"), "goodbye"),
        # Gracias holds the middle two slots as well as Close, the shape Tamil
        # and Punjabi ended up with. It is register-neutral — said at every
        # level — so pinning it low let it outvote an usted, which is what
        # rewrite_only was suppressing. Spanning the range instead means it
        # never contradicts the pronoun, and it leaves Muchísimas as the one
        # piece of Formal evidence a thanks-sentence carries. The cost is that
        # "Muchas gracias" is no longer produced: there are four slots and the
        # neutral word needs three of them.
        Rule("greet.thanks", ("Gracias", "Gracias", "Gracias", "Muchísimas gracias"),
             "thanks"),
        # Same shape: "mucho" is what lifts an already-honorific clause to
        # Formal, since le agradezco alone is equally Polite.
        Rule("clause.agradezco", ("te agradezco", "te agradezco",
                                  "le agradezco", "le agradezco mucho"), "I thank you"),
        Rule("greet.sorry", ("Perdón", "Perdón", "Disculpe", "Le pido disculpas"), "sorry"),
        # Readable as well as insertable: "por favor" is what separates Formal
        # from Polite in a request, since usted covers both.
        Rule("polite.particle", ("", "", "", "por favor"), "please"),
        # A sign-off is pure register — it carries no content at all, and the
        # choice between them is the entire message.
        Rule("close.signoff", ("Un abrazo", "Un saludo", "Saludos cordiales",
                               "Atentamente"), "sign-off"),
    ),
)

# Lowercase third-person subjects. Capitalised "Lei" is the polite pronoun and
# must NOT appear here.
_IT_3P_SUBJECT = r"\b(?:lui|lei|egli|ella|esso|essa|chi)\s+"

# --------------------------------------------------------------------------
# Italian verbs.
#
# Harder than French, and it showed: 66.7% detection, the worst in the project.
# French marks the polite form with its own conjugation (êtes, avez), so the
# verb alone settles it. Italian polite Lei takes *third-person* agreement, so
# "è" is both "you are" and "he/she is" and the verb settles nothing.
#
# Two things carry the distinction, and the table uses both:
#   * capitalisation — polite Lei is capitalised by convention even
#     mid-sentence, so `cased` rules can tell Lei from lei (she)
#   * the left context — a lowercase third-person subject blocks the reading
#
# Each entry is (tu, Lei).
# --------------------------------------------------------------------------

_IT_VERBS: Tuple[Tuple[str, str, str, str], ...] = (
    # stem,        tu,          Lei,        gloss
    ("essere", "sei", "è", "you are"),
    ("avere", "hai", "ha", "you have"),
    ("stare", "stai", "sta", "you are (state)"),
    ("fare", "fai", "fa", "you do"),
    ("andare", "vai", "va", "you go"),
    ("venire", "vieni", "viene", "you come"),
    ("potere", "puoi", "può", "you can"),
    ("volere", "vuoi", "vuole", "you want"),
    ("dovere", "devi", "deve", "you must"),
    ("sapere", "sai", "sa", "you know"),
    ("dire", "dici", "dice", "you say"),
    ("dare", "dai", "dà", "you give"),
    ("vedere", "vedi", "vede", "you see"),
    ("parlare", "parli", "parla", "you speak"),
    ("abitare", "abiti", "abita", "you live"),
    ("lavorare", "lavori", "lavora", "you work"),
    ("mangiare", "mangi", "mangia", "you eat"),
    ("bere", "bevi", "beve", "you drink"),
    ("capire", "capisci", "capisce", "you understand"),
    ("conoscere", "conosci", "conosce", "you know (someone)"),
    ("prendere", "prendi", "prende", "you take"),
    ("aspettare", "aspetti", "aspetta", "you wait"),
    ("arrivare", "arrivi", "arriva", "you arrive"),
    ("pagare", "paghi", "paga", "you pay"),
    ("comprare", "compri", "compra", "you buy"),
    ("aiutare", "aiuti", "aiuta", "you help"),
    ("sentire", "senti", "sente", "you hear"),
    ("scrivere", "scrivi", "scrive", "you write"),
    ("leggere", "leggi", "legge", "you read"),
    ("vivere", "vivi", "vive", "you live"),
)

#: Reflexives, where the clitic moves too: ti chiami -> si chiama.
_IT_REFLEXIVES: Tuple[Tuple[str, str, str, str], ...] = (
    ("chiamarsi", "ti chiami", "si chiama", "you are called"),
    ("sentirsi", "ti senti", "si sente", "you feel"),
    ("accomodarsi", "ti accomodi", "si accomoda", "you make yourself comfortable"),
)

#: Imperatives. Italian builds the polite one from the subjunctive, so it is
#: not derivable from the indicative above.
_IT_IMPERATIVES: Tuple[Tuple[str, str, str, str], ...] = (
    ("parlare", "parla", "parli", "speak!"),
    ("mangiare", "mangia", "mangi", "eat!"),
    ("prendere", "prendi", "prenda", "take!"),
    ("aspettare", "aspetta", "aspetti", "wait!"),
    # "scusare" is deliberately absent: greet.sorry owns Scusa, whose polite
    # form is the whole phrase "Mi scusi" rather than the bare "scusi" this
    # list would produce.
    ("dire", "di'", "dica", "say!"),
    ("fare", "fa'", "faccia", "do!"),
    ("andare", "va'", "vada", "go!"),
    ("venire", "vieni", "venga", "come!"),
    ("dare", "da'", "dia", "give!"),
    ("sentire", "senti", "senta", "listen!"),
    ("entrare", "entra", "entri", "come in!"),
    ("guardare", "guarda", "guardi", "look!"),
)

#: Lowercase third-person subjects. Capitalised "Lei" is the polite pronoun and
#: must never appear here.
_IT_3P_SUBJECT_FULL = r"\b(?:lui|lei|egli|ella|esso|essa|chi|che)\s+"

# --------------------------------------------------------------------------
# Italian cannot use the Spanish fix, and the difference is instructive.
#
# Spanish spells out usted whenever the polite reading is meant, so requiring
# it next to the verb settles every case. Italian drops Lei almost always:
# "Come sta?", "Ha tempo?" and "Parla inglese?" are all polite with no pronoun
# anywhere. Requiring one would reject the whole language.
#
# What Italian does instead is spell out its *third-person* subjects. "Il
# treno è in ritardo" names the train; the polite sentences name nobody. So
# here the blocklist is the workable side, as long as it covers noun phrases
# and not just the handful of bare pronouns it started with — a determiner
# plus a word is enough to recognise one without parsing.
#
# Three shapes, all third person and none of them polite:
# --------------------------------------------------------------------------

_IT_DET = r"(?i:il|lo|la|i|gli|le|un|uno|una|questo|questa|quel|quello|quella)"

#: A noun phrase before the verb — "Il treno è", "Oggi il tempo è".
_IT_NP_BEFORE = rf"\b{_IT_DET}\s+\w+\s+"

#: A bare demonstrative subject — "Questo è per te".
_IT_DEM_BEFORE = r"\b(?i:questo|questa|quello|quella|ciò)\s+"

#: A noun phrase *after* the verb, which is Italian's question inversion:
#: "È il Suo libro?" is about the book, not about the listener.
_IT_NP_AFTER = rf"\s+{_IT_DET}\s+"

#: A gerund after the verb is the progressive: "Sta piovendo" is the weather.
_IT_GERUND = r"\s+\w+(?:ando|endo)\b"

_IT_3P_BEFORE = f"{_IT_3P_SUBJECT_FULL}|{_IT_NP_BEFORE}|{_IT_DEM_BEFORE}"
_IT_3P_AFTER = f"{_IT_NP_AFTER}|{_IT_GERUND}"

#: Prepositions that take the tonic pronoun rather than the nominative.
_IT_PREPOSITION = r"\b(?i:per|con|da|a|di|su|tra|fra|come)\s+"


def _it_verb_rules() -> Tuple[Rule, ...]:
    # The guards sit on the Lei form alone. On the rule they also constrained
    # the tu form, which is unambiguous and needs no constraining.
    out = [
        Rule(f"v.{stem}", (tu, tu, lei, lei), gloss, cased=True,
             form_guards=((lei, _IT_3P_BEFORE, _IT_3P_AFTER, "", ""),))
        for stem, tu, lei, gloss in _IT_VERBS
    ]
    out += [
        Rule(f"v.{stem}.refl", (tu, tu, lei, lei), gloss, cased=True,
             form_guards=((lei, _IT_3P_BEFORE, _IT_3P_AFTER, "", ""),))
        for stem, tu, lei, gloss in _IT_REFLEXIVES
    ]
    out += [
        Rule(f"v.{stem}.imp", (tu, tu, lei, lei), gloss, cased=True)
        for stem, tu, lei, gloss in _IT_IMPERATIVES
    ]
    return tuple(out)


ITALIAN = LanguageTable(
    code="it",
    name="Italian",
    # Binary pronoun system (du/Sie, tu/vous, நீ/நீங்கள்), but the lexical
    # politeness layer above it is not binary — "Vielen Dank" and "Herzlichen
    # Dank" are not the same register. Folding Polite and Formal together
    # would throw that away, so both slots stay live.
    canon=(1, 1, 2, 3),
    please=("", "", "per favore ", "per cortesia "),
    rules=_it_verb_rules() + (
        # Known limitation. Italian polite "Lei" is capitalised by convention
        # even mid-sentence, which is what makes `cased` work here — lowercase
        # "lei" (she) and "le" (the/to her) are correctly left alone. But at the
        # start of a sentence both readings capitalise, and polite Lei takes the
        # same 3sg verb as she ("Lei è ..."), so no verb-agreement guard of the
        # German kind can separate them. Sentence-initial Lei is therefore read
        # as polite. Mid-sentence casing carries the distinction correctly.
        Rule("clause.come_stai", ("Come stai?", "Come stai?", "Come sta?", "Come sta?"), "how are you"),
        Rule("clause.dimmi", ("dimmi", "dimmi", "mi dica", "mi dica"), "tell me!"),
        # Tonic before nominative, and each kept off the other's ground.
        # Italian, like Spanish, uses a distinct form after a preposition and
        # collapses the distinction at the polite level — Lei is Lei either
        # way — so coming down, only the preposition says which is meant, and
        # "per Lei" was arriving as "per tu".
        Rule("pron.2sg.tonic", ("te", "te", "Lei", "Lei"), "you (tonic)", cased=True,
             require_before=_IT_PREPOSITION),
        Rule("pron.2sg.nom", ("tu", "tu", "Lei", "Lei"), "you", cased=True,
             guard_before=_IT_PREPOSITION),
        Rule("pron.2sg.obj", ("ti", "ti", "Le", "Le"), "you (obj)", cased=True),
        Rule("poss.m", ("tuo", "tuo", "Suo", "Suo"), "your (m)", cased=True),
        Rule("poss.f", ("tua", "tua", "Sua", "Sua"), "your (f)", cased=True),
        Rule("poss.m.pl", ("tuoi", "tuoi", "Suoi", "Suoi"), "your (m pl)", cased=True),
        Rule("poss.f.pl", ("tue", "tue", "Sue", "Sue"), "your (f pl)", cased=True),
        Rule("greet.hello", ("Ehi", "Ciao", "Buongiorno", "Buongiorno"), "hello"),
        Rule("greet.bye", ("Ciao", "Ciao", "Arrivederci", "ArrivederLa"), "goodbye"),
        # Grazie and Scusa are said at every level; only their elaborations are
        # marked. Rewriting up should still reach "La ringrazio", but neither
        # may vote when detecting — a bare "Grazie a Lei" was outvoting the Lei
        # and reading as Casual.
        # Every slot has to be a drop-in for the others: this is a token
        # substitution table, not a sentence rewriter. "La ringrazio" is a full
        # clause meaning "I thank you", so substituting it for the word Grazie
        # turned "Grazie a Lei" into "La ringrazio a Lei" — two objects and no
        # grammar. The escalation stays lexical instead.
        #
        # Grazie now spans the middle two slots as well, the shape Tamil and
        # Spanish ended up with, and no longer needs rewrite_only: a word said
        # at every level cannot contradict the pronoun if it covers the range,
        # and Grazie infinite is left as the one piece of Formal evidence a
        # thanks-sentence carries. The cost is that "Grazie mille" is no longer
        # produced — four slots, and the neutral word needs three of them.
        Rule("greet.thanks", ("Grazie", "Grazie", "Grazie", "Grazie infinite"),
             "thanks"),
        # "molto" is what lifts an already-honorific clause to Formal, since
        # La ringrazio on its own is equally Polite.
        Rule("clause.ringrazio", ("ti ringrazio", "ti ringrazio",
                                  "La ringrazio", "La ringrazio molto"), "I thank you"),
        # "La prego" is markedly more deferential than "Le chiedo" — it is the
        # register of a notice rather than a request between colleagues.
        Rule("clause.prego", ("ti chiedo di", "ti chiedo di",
                              "Le chiedo di", "La prego di"), "I ask you to"),
        Rule("greet.sorry", ("Scusa", "Scusa", "Mi scusi", "Le chiedo scusa"), "sorry"),
        # A sign-off is pure register: no content at all, and the choice
        # between them is the entire message.
        Rule("close.signoff", ("Un bacio", "Un saluto", "Cordiali saluti",
                               "Distinti saluti"), "sign-off"),
    ),
)

# --------------------------------------------------------------------------
# Portuguese verbs.
#
# The thinnest table in the project at 13 rules, and it measured accordingly:
# 47.6% detection against the gold set, the worst of the twenty. Most failures
# were simply verbs with no rule — "Onde moras?" and "Falas inglês?" detected
# nothing at all, because morar and falar were not in the table.
#
# Each entry is (tu, você, o senhor). Note that você and o senhor share their
# verb form throughout: Portuguese marks the third level on the pronoun, not
# the verb, so a verb-only sentence is genuinely ambiguous between them. That
# is a property of the language, not a gap — the pronoun is what settles it.
# --------------------------------------------------------------------------

_PT_VERBS: Tuple[Tuple[str, str, str, str], ...] = (
    # stem,        tu,          você / o senhor,  gloss
    ("ser", "és", "é", "you are"),
    ("estar", "estás", "está", "you are (state)"),
    ("ter", "tens", "tem", "you have"),
    ("poder", "podes", "pode", "you can"),
    ("querer", "queres", "quer", "you want"),
    ("ir", "vais", "vai", "you go"),
    ("vir", "vens", "vem", "you come"),
    ("fazer", "fazes", "faz", "you do"),
    ("dizer", "dizes", "diz", "you say"),
    ("dar", "dás", "dá", "you give"),
    ("ver", "vês", "vê", "you see"),
    ("saber", "sabes", "sabe", "you know"),
    ("conhecer", "conheces", "conhece", "you know (someone)"),
    ("falar", "falas", "fala", "you speak"),
    ("morar", "moras", "mora", "you live"),
    ("trabalhar", "trabalhas", "trabalha", "you work"),
    ("comer", "comes", "come", "you eat"),
    ("beber", "bebes", "bebe", "you drink"),
    ("gostar", "gostas", "gosta", "you like"),
    ("precisar", "precisas", "precisa", "you need"),
    ("entender", "entendes", "entende", "you understand"),
    ("chegar", "chegas", "chega", "you arrive"),
    ("ficar", "ficas", "fica", "you stay"),
    ("levar", "levas", "leva", "you take"),
    ("comprar", "compras", "compra", "you buy"),
    ("pagar", "pagas", "paga", "you pay"),
    ("esperar", "esperas", "espera", "you wait"),
    ("ajudar", "ajudas", "ajuda", "you help"),
    ("abrir", "abres", "abre", "you open"),
    ("viver", "vives", "vive", "you live"),
)

#: Imperatives. Portuguese builds the polite imperative from the subjunctive,
#: so these are not derivable from the indicative forms above.
_PT_IMPERATIVES: Tuple[Tuple[str, str, str, str], ...] = (
    ("falar", "fala", "fale", "speak!"),
    ("comer", "come", "coma", "eat!"),
    ("abrir", "abre", "abra", "open!"),
    ("ir", "vai", "vá", "go!"),
    ("ser", "sê", "seja", "be!"),
    ("ter", "tem", "tenha", "have!"),
    ("fazer", "faz", "faça", "do!"),
    ("dizer", "diz", "diga", "say!"),
    ("vir", "vem", "venha", "come!"),
    ("dar", "dá", "dê", "give!"),
    ("esperar", "espera", "espere", "wait!"),
    ("aguardar", "aguarda", "aguarde", "wait!"),
    ("ouvir", "ouve", "ouça", "listen!"),
    ("seguir", "segue", "siga", "follow!"),
    # desculpar is deliberately absent: "Desculpa"/"Desculpe" is carried by
    # greet.sorry below, which also has the level-3 "Peço desculpa". Two rules
    # for one word disagreed about its level and produced "Desculpa" ->
    # "Desculpe" when asked for Casual.
    ("entrar", "entra", "entre", "come in!"),
    ("sentar", "senta", "sente", "sit!"),
    ("olhar", "olha", "olhe", "look!"),
)

#: A verb form only counts as second person when the subject is not third —
#: "é" is both "you are" (você) and "he/she is". Portuguese drops subject
#: pronouns freely, so this cannot be fully resolved; blocking the clear
#: third-person subjects removes the common false positives.
_PT_3P_SUBJECT = r"\b(?:ele|ela|eles|elas|quem|que)\s+"

#: The syncretic forms of ser and estar are also the third-person forms, and
#: Portuguese drops subjects freely, so they need far more than a pronoun list:
#: a determiner and noun ("A loja está"), a fronted adverb ("Hoje está"), or
#: nothing at all ("Está a chover"). Only these two verbs are this ambiguous
#: — and only in their polite form, which is why this is a per-form guard.
_PT_IMPERSONAL = (
    r"\b(?:ele|ela|eles|elas|quem|que|isto|isso|aquilo|tudo|nada)\s+"
    # "o senhor" looks exactly like a determiner and a noun, and it is the
    # polite *second* person — the one subject in this shape that must not be
    # blocked. Without the exception "O senhor é muito simpático" kept its
    # third-person verb all the way down to "Tu é muito simpático".
    r"|\b(?:o|a|os|as|um|uma|uns|umas|este|esta|esse|essa|aquele|aquela)\s+"
    r"(?!senhor(?:a|es|as)?\b)\w+\s+"
    r"|\b(?:hoje|ontem|amanhã|aqui|ali|lá|agora|ainda|já|também)\s*"
    r"|^\s*"
)

_PT_SYNCRETIC = {"ser": "é", "estar": "está"}

#: Prepositions taking the tonic pronoun rather than the nominative. "a" is
#: absent: it contracts with o senhor and is handled by its own rule.
_PT_PREPOSITION = (
    r"\b(?:para|por|de|em|com|sem|sobre|até|desde|entre|contra|após)\s+"
)


def _pt_verb_rules() -> Tuple[Rule, ...]:
    out = [
        Rule(f"v.{stem}", (tu, polite, polite, polite), gloss,
             guard_before=_PT_3P_SUBJECT,
             form_guards=(((_PT_SYNCRETIC[stem], _PT_IMPERSONAL, "", "", ""),)
                          if stem in _PT_SYNCRETIC else ()))
        for stem, tu, polite, gloss in _PT_VERBS
    ]
    out += [
        Rule(f"v.{stem}.imp", (tu, polite, polite, polite), gloss)
        for stem, tu, polite, gloss in _PT_IMPERATIVES
    ]
    return tuple(out)


PORTUGUESE = LanguageTable(
    code="pt",
    name="Portuguese",
    canon=(0, 1, 2, 2),
    please=("", "", "por favor ", "por favor "),
    insert_subject=("", "você", "o senhor", "o senhor"),
    subject_position="wh_inverted",
    rules=_pt_verb_rules() + (
        # "a" contracts with the article inside "o senhor", so the preposition
        # changes shape with the register: a ti, a você, *ao* senhor. Listed
        # ahead of the bare tonic rule and longer than it, so it wins the span.
        Rule("prep.a.2sg", ("a ti", "a você", "ao senhor", "ao senhor"),
             "to you"),
        # Portuguese conjugates você and o senhor alike, so after a preposition
        # the pronoun is the only thing carrying the level. These were "si" at
        # every level above tu, which is the reflexive — "para si" is "for
        # yourself" — and it erased the você/senhor distinction the language
        # keeps precisely here.
        Rule("pron.2sg.tonic", ("ti", "você", "o senhor", "o senhor"),
             "you (after preposition)", require_before=_PT_PREPOSITION),
        Rule("pron.2sg.nom", ("tu", "você", "o senhor", "o senhor"), "you",
             guard_before=_PT_PREPOSITION),
        Rule("pron.2sg.obj", ("te", "lhe", "lhe", "lhe"), "you (obj)"),
        Rule("pron.2sg.com", ("contigo", "consigo", "consigo", "consigo"), "with you"),
        Rule("poss.m", ("teu", "seu", "seu", "seu"), "your (m)"),
        Rule("poss.f", ("tua", "sua", "sua", "sua"), "your (f)"),
        Rule("poss.m.pl", ("teus", "seus", "seus", "seus"), "your (m pl)"),
        Rule("poss.f.pl", ("tuas", "suas", "suas", "suas"), "your (f pl)"),
        Rule("greet.hello", ("Oi", "Olá", "Bom dia", "Bom dia"), "hello"),
        Rule("greet.bye", ("Tchau", "Tchau", "Até logo", "Passe bem"), "goodbye"),
        # Obrigado spans the middle two slots, so it never contradicts the
        # pronoun and no longer needs rewrite_only — the shape Tamil, Spanish
        # and Italian all ended up with. "Agradeço muito" is gone from the top
        # slot: it is a clause, not a drop-in for a word, and substituting it
        # turned "Agradeço muito a sua ajuda" into "Obrigado a sua ajuda" on
        # the way down. Same lesson as "La ringrazio a Lei".
        # Obrigado is neutral across every level Portuguese reaches by
        # rewriting — the gold says it plainly, with "Obrigado" in all three
        # columns and only the pronoun moving. It used to escalate, so asking
        # for Close turned "Obrigado a ti" into "Valeu a ti", swapping in slang
        # nobody requested. Valeu is gone with it: it is real Portuguese, but
        # there is no level here that means it.
        Rule("greet.thanks", ("Obrigado", "Obrigado", "Obrigado", "Muito obrigado"),
             "thanks"),
        # "Desculpa" is the tu form and "Desculpe" the você one — an
        # imperative, not an invariant interjection, so it moves with the
        # register like any other verb.
        #
        # "Desculpe" used to sit at Polite as well as Casual, which put the
        # same string in two slots and left nothing to tell them apart; the
        # gold set asked the detector to distinguish two identical sentences
        # and one of the two rows could only fail. It also stranded "Peço
        # desculpa" at slot 3, which this canon never requests — (0, 1, 2, 2)
        # folds Formal onto Polite, so the top slot is unreachable and the
        # phrase could not be produced at all. Moving it down one gives the
        # ladder three distinct rungs and the language its o senhor form.
        Rule("greet.sorry", ("Desculpa", "Desculpe", "Peço desculpa", "Peço desculpa"), "sorry"),
        # A sign-off is pure register: no content at all, and the choice
        # between them is the entire message.
        Rule("close.signoff", ("Beijinhos", "Abraço", "Com os melhores cumprimentos",
                               "Com os melhores cumprimentos"), "sign-off"),
    ),
)

# --------------------------------------------------------------------------
# East Asian
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# Japanese verb paradigms.
#
# Japanese is the one language here where register does not attach to a second
# person at all. です and ます mark the speaker's stance toward the *listener*,
# so "今日はいい天気です" is polite while being about the weather. Everything
# else in this project keys off a pronoun; Japanese keys off the sentence
# ending, and the table is a list of those endings.
#
# Each entry is (plain, ます, 敬語). The third column is honorific or humble
# vocabulary rather than an inflection — 見る becomes 拝見する, not 見られる —
# which is why real keigo needs morphological analysis and this table only
# claims the sentence-final spine.
# --------------------------------------------------------------------------

_JA_PARADIGMS: Tuple[Tuple[str, str, str, str], ...] = (
    # gloss,     plain,        masu,            keigo
    ("suru", "する", "します", "いたします"),
    ("suru.past", "した", "しました", "いたしました"),
    ("suru.neg", "しない", "しません", "いたしません"),
    ("iku", "行く", "行きます", "まいります"),
    ("iku.past", "行った", "行きました", "まいりました"),
    ("kuru", "来る", "来ます", "まいります"),
    ("kuru.past", "来た", "来ました", "まいりました"),
    ("miru", "見る", "見ます", "拝見します"),
    ("miru.past", "見た", "見ました", "拝見しました"),
    ("taberu", "食べる", "食べます", "いただきます"),
    ("nomu", "飲む", "飲みます", "いただきます"),
    ("iu", "言う", "言います", "申します"),
    ("iru", "いる", "います", "おります"),
    ("aru", "ある", "あります", "ございます"),
    ("nai", "ない", "ありません", "ございません"),
    ("morau", "もらう", "もらいます", "いただきます"),
    ("shiru", "知ってる", "知っています", "存じております"),
    ("kau", "買う", "買います", "お求めになります"),
    ("matsu", "待つ", "待ちます", "お待ちします"),
    ("hanasu", "話す", "話します", "お話しします"),
    ("kiku", "聞く", "聞きます", "伺います"),
    ("yomu", "読む", "読みます", "拝読します"),
    ("kaku", "書く", "書きます", "お書きします"),
    ("wakaru", "分かる", "分かります", "承知しております"),
    ("dekiru", "できる", "できます", "いたしかねます"),
    ("omou", "思う", "思います", "存じます"),
    ("au", "会う", "会います", "お目にかかります"),
    ("kaeru", "帰る", "帰ります", "失礼します"),
    ("tsukau", "使う", "使います", "使わせていただきます"),
    ("motsu", "持つ", "持ちます", "お持ちします"),
    ("suwaru", "座る", "座ります", "お掛けになります"),
    ("yasumu", "休む", "休みます", "お休みになります"),
    ("oshieru", "教える", "教えます", "お教えします"),
    ("mirareru", "見せる", "見せます", "お見せします"),
    ("ageru", "あげる", "あげます", "差し上げます"),
)

#: The bare copula only counts at the end of a clause.
#:
#: Japanese has no word boundaries, so matching is substring-based, and だ
#: occurs inside perfectly ordinary words — ください is く-だ-さい. Without this
#: the honorific "恐れ入りますが、少々お待ちください" detected as Casual with
#: full confidence, on the strength of the だ buried in ください.
_JA_CLAUSE_FINAL = r"(?:[。．.!?！？、，]|$|ね|よ|な|ぞ|わ)"


# --------------------------------------------------------------------------
# Japanese humble verbs collapse distinctions the plain forms keep, so one
# keigo form serves two verbs and the downgrade has to guess. いただきます is
# humble for 食べる and 飲む both; まいります for 行く and 来る.
#
# The object settles the first: 食べる takes food and 飲む takes drink, and the
# noun is right there in front of the verb. A destination settles the second.
# Without them the first-declared verb simply won, so "お茶をいただきます" came
# down to "お茶を食べる" — drinking tea rendered as eating it.
#
# The guards go on the *keigo* form alone. Put on the rule they would also
# bind 行く, and "明日行く。" would need a destination to be recognised at all.
# --------------------------------------------------------------------------

_JA_DRINK = r"(?:お茶|茶|水|お水|コーヒー|紅茶|ビール|お酒|酒|ジュース|ミルク|牛乳|スープ)を"
_JA_DESTINATION = r"(?:へ|に)"

#: verb -> (keigo form, pattern that must precede it, pattern that must not)
_JA_KEIGO_GUARDS = {
    "nomu": (_JA_DRINK, ""),
    "taberu": ("", _JA_DRINK),
    "iku": (_JA_DESTINATION, ""),
    "kuru": ("", _JA_DESTINATION),
    "nomu.past": (_JA_DRINK, ""),
    "taberu.past": ("", _JA_DRINK),
    "iku.past": (_JA_DESTINATION, ""),
    "kuru.past": ("", _JA_DESTINATION),
}


def _ja_verb_rules() -> Tuple[Rule, ...]:
    out = []
    for name, plain, masu, keigo in _JA_PARADIGMS:
        if len({plain, masu, keigo}) <= 1:
            continue
        require, forbid = _JA_KEIGO_GUARDS.get(name, ("", ""))
        guards = ((keigo, forbid, "", require, "", ""),) if (require or forbid) else ()
        out.append(
            Rule(f"v.{name}", (plain, plain, masu, keigo), name, form_guards=guards)
        )
    return tuple(out)


JAPANESE = LanguageTable(
    code="ja",
    name="Japanese",
    canon=(1, 1, 2, 3),
    boundary="none",
    please=("", "", "", ""),
    # Matching is longest-first, so the multi-character spines beat the bare
    # copula nested inside them without needing declaration order to say so.
    rules=_ja_verb_rules() + (
        Rule("polite.arigatou", ("ありがと", "ありがとう", "ありがとうございます", "誠にありがとうございます"), "thanks"),
        Rule("polite.gomen", ("ごめん", "ごめんね", "すみません", "申し訳ございません"), "sorry"),
        Rule("polite.onegai", ("頼む", "お願い", "お願いします", "お願いいたします"), "please"),
        # 恐れ入りますが used to fill both honorific slots, so it split its vote
        # and a request opening with it read as Polite. 恐縮ですが is the
        # ordinary polite hedge and 恐れ入りますが the deferential one.
        Rule("polite.osoreirimasu", ("悪いけど", "すみませんが", "恐縮ですが",
                                     "恐れ入りますが"), "excuse me, but"),
        # The request ladder. お待ちください is the polite request form and had
        # no rule at all, so "少々お待ちください。" read as nothing.
        Rule("polite.kudasai", ("待って", "待ってください", "お待ちください",
                                "お待ちくださいませ"), "please wait"),
        # The copula drops entirely before the question particle: plain
        # "これはいくらか。" against polite "これはいくらですか。". Rewriting です to
        # だ blindly produced "だか", which is not Japanese. Longer than cop.da,
        # so it wins the match; the bare か is clause-final only, or it would
        # fire inside から and every disjunction.
        Rule("cop.desu.ka", ("か", "か", "ですか", "でございますか"), "is …?",
             form_guards=(("か", "", "", "", _JA_CLAUSE_FINAL),)),
        # だ only counts clause-finally — see _JA_CLAUSE_FINAL. です needs no
        # such guard: it does not occur inside other words.
        Rule("cop.da", ("だ", "だ", "です", "でございます"), "is",
             form_guards=(("だ", "", "", "", _JA_CLAUSE_FINAL),)),
        Rule("greet.hello", ("やあ", "こんにちは", "こんにちは", "お世話になっております"), "hello"),
    ),
)

# --------------------------------------------------------------------------
# English — weak register, but the contrast is real and users expect the dial
# to do *something* when English is the target.
# --------------------------------------------------------------------------

ENGLISH = LanguageTable(
    code="en",
    name="English",
    canon=(1, 1, 2, 3),
    please=("", "", "please ", "kindly "),
    rules=(
        # English has no T/V distinction at all, so every rule here is lexical
        # or a hedge. That also means a bare imperative — "Send it over." —
        # genuinely carries no register, and the detector abstaining on it is
        # correct rather than a gap.
        # The canon is (1, 1, 2, 3): English has no Close level distinct from
        # Casual, which is what "no T/V distinction" amounts to here. So slot 0
        # is never a rewrite target, and the informal forms that used to sit
        # there alone — wanna, yeah, gonna, loads of — could be read but never
        # produced. Asking for Casual returned the *neutral* form instead:
        # "I wanna go" came back as "I want to go", which is not a register
        # step, it is just a different sentence.
        #
        # They occupy slot 1 now, beside slot 0, the way greet.thanks and
        # greet.sorry already did. The neutral forms they displaced — want to,
        # yes, a lot of — leave the table altogether, which is right: they are
        # unmarked English and abstaining on them is the correct answer.
        Rule("polite.particle", ("", "", "please", "kindly"), "please"),
        Rule("clause.can_you", ("can you", "can you", "could you", "could you kindly"), "request"),
        Rule("clause.could_i", ("can i", "can I", "could I", "might I"), "may I"),
        Rule("clause.i_think", ("i reckon", "i reckon", "I believe",
                                "I am of the view"), "I think"),
        Rule("clause.writing", ("just a note", "just a note", "I am writing",
                                "I am writing to enquire"), "correspondence opener"),
        Rule("clause.sorry_but", ("sorry but", "sorry but", "I am afraid",
                                  "I regret to say"), "softened refusal"),
        Rule("clause.need_help", ("need a hand", "need a hand",
                                  "need some assistance", "require assistance"), "help"),
        Rule("clause.want_to", ("wanna", "wanna", "would like to", "should like to"), "want to"),
        Rule("clause.going_to", ("gonna", "gonna", "going to", "intending to"), "going to"),
        Rule("clause.got_to", ("gotta", "gotta", "need to", "am required to"), "have to"),
        Rule("clause.let_me_know", ("lmk", "lmk", "please let me know", "kindly inform me"), "inform me"),
        Rule("word.ok", ("kk", "kk", "very well", "very well"), "assent"),
        Rule("word.yes", ("yeah", "yeah", "yes", "certainly"), "yes"),
        Rule("word.no", ("nope", "nope", "no", "unfortunately not"), "no"),
        Rule("word.lots", ("loads of", "loads of", "many", "a great deal of"), "many"),
        Rule("word.buy", ("grab", "grab", "purchase", "purchase"), "buy"),
        Rule("word.start", ("kick off", "kick off", "begin", "commence"), "start"),
        # These are neutral in themselves and only their elaborations are
        # marked, so they rewrite but do not vote. A full Casual vote from a
        # word as ordinary as "about" was enough to outweigh the actual signal:
        # "I am writing to enquire about the position advertised" scored
        # Casual, on the strength of the "about".
        Rule("word.show", ("show", "show", "indicate", "indicate"), "show",
             rewrite_only=True),
        Rule("word.enough", ("enough", "enough", "sufficient", "sufficient"), "enough",
             rewrite_only=True),
        Rule("word.about", ("about", "about", "regarding", "with regard to"), "about",
             rewrite_only=True),
        Rule("word.but", ("but", "but", "however", "however"), "but",
             rewrite_only=True),
        Rule("word.so", ("so", "so", "therefore", "therefore"), "so",
             rewrite_only=True),
        Rule("word.kids", ("kids", "kids", "children", "children"), "children",
             rewrite_only=True),
        Rule("word.ask", ("ask", "ask", "request", "request"), "ask",
             rewrite_only=True),
        Rule("greet.hello", ("hey", "hi", "hello", "good day"), "hello"),
        Rule("greet.bye", ("bye", "bye", "goodbye", "I bid you goodbye"), "goodbye"),
        Rule("greet.thanks", ("thanks", "thanks", "thank you", "thank you very much"), "thanks"),
        Rule("greet.sorry", ("sorry", "sorry", "I apologise", "I sincerely apologise"), "sorry"),
        # Written-register formulae. Each is fixed enough that the whole phrase
        # is the marker, and none had a rule, so a formal letter read as
        # nothing at all.
        Rule("clause.grateful", ("thanks a lot", "thanks a lot", "I would appreciate",
                                 "I would be grateful"), "grateful"),
        # "please find" and not "please find attached": the formula is
        # discontinuous — "please find the requested documents attached" — and
        # only its head is reliably contiguous. The head is enough, and it is
        # unmistakably correspondence English.
        #
        # There is no rule for "assistance" against "help". Written as a
        # variant set it cannot tell the noun from the verb, so "Can you help
        # me?" came out as "Can you a hand me?", and it flattened the idiom in
        # "give me a hand" to "give me help".
        Rule("clause.please_find", ("here's", "here's", "here is", "please find"),
             "enclosing"),
        Rule("close.signoff", ("cheers", "cheers", "best wishes", "Yours sincerely"),
             "sign-off"),
    ),
)


# --------------------------------------------------------------------------
# Blueprint phase 3 — the scheduled languages with nothing built for them.
#
# CoCoA-MT gave Hindi a binary formality benchmark in 2022 and the rest of India
# got nothing. These four are the next ones by speaker count, and none of them
# has a register-controlled MT resource of any kind.
#
# Confidence note: the Bengali, Hindi and Marathi tables above are checked
# against native intuition. These four are compiled from standard grammars and
# have NOT been reviewed by a native speaker. Treat the forms as a starting
# point and run `python -m evaluation.run --lang ur` after any correction.
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# Urdu verb paradigms.
#
# Grammatically parallel to Hindi — same تو/تم/آپ system, same tense
# structure — so the paradigm has the same shape and the same slots. What the
# gold set found was the same absence: an imperative-only table, so the
# continuous, the future and the entire perfective past detected nothing.
# "یہ تیرے لیے ہے" was invisible because the oblique genitive تیرے was missing,
# and "آپ کیا کر رہے ہیں؟" because the continuous was.
#
# Each entry is (تو, تم, آپ); Formal reuses the آپ column, since Urdu marks the
# extra deference lexically (براہ کرم, معذرت) rather than inflectionally.
# --------------------------------------------------------------------------

_UR_PARADIGMS: Dict[str, Dict[str, Tuple[str, str, str]]] = {
    "karna": {
        "pres.m": ("کرتا ہے", "کرتے ہو", "کرتے ہیں"),
        "pres.f": ("کرتی ہے", "کرتی ہو", "کرتی ہیں"),
        "cont.m": ("کر رہا ہے", "کر رہے ہو", "کر رہے ہیں"),
        "cont.f": ("کر رہی ہے", "کر رہی ہو", "کر رہی ہیں"),
        "future.m": ("کرے گا", "کرو گے", "کریں گے"),
        "future.f": ("کرے گی", "کرو گی", "کریں گی"),
        "prohibitive": ("مت کر", "مت کرو", "مت کیجیے"),
        "imp": ("کر", "کرو", "کیجیے"),
    },
    "jana": {
        "pres.m": ("جاتا ہے", "جاتے ہو", "جاتے ہیں"),
        "pres.f": ("جاتی ہے", "جاتی ہو", "جاتی ہیں"),
        "cont.m": ("جا رہا ہے", "جا رہے ہو", "جا رہے ہیں"),
        "cont.f": ("جا رہی ہے", "جا رہی ہو", "جا رہی ہیں"),
        "future.m": ("جائے گا", "جاؤ گے", "جائیں گے"),
        "prohibitive": ("مت جا", "مت جاؤ", "مت جائیے"),
        "imp": ("جا", "جاؤ", "جائیے"),
    },
    "ana": {
        "pres.m": ("آتا ہے", "آتے ہو", "آتے ہیں"),
        "pres.f": ("آتی ہے", "آتی ہو", "آتی ہیں"),
        "cont.m": ("آ رہا ہے", "آ رہے ہو", "آ رہے ہیں"),
        "future.m": ("آئے گا", "آؤ گے", "آئیں گے"),
        "imp": ("آ", "آؤ", "آئیے"),
    },
    "rahna": {
        "pres.m": ("رہتا ہے", "رہتے ہو", "رہتے ہیں"),
        "pres.f": ("رہتی ہے", "رہتی ہو", "رہتی ہیں"),
        "imp": ("رہ", "رہو", "رہیے"),
    },
    "bolna": {
        "pres.m": ("بولتا ہے", "بولتے ہو", "بولتے ہیں"),
        "cont.m": ("بول رہا ہے", "بول رہے ہو", "بول رہے ہیں"),
        "imp": ("بول", "بولو", "بولیے"),
    },
    "kahna": {
        "pres.m": ("کہتا ہے", "کہتے ہو", "کہتے ہیں"),
        "imp": ("کہہ", "کہو", "کہیے"),
    },
    "batana": {
        "pres.m": ("بتاتا ہے", "بتاتے ہو", "بتاتے ہیں"),
        "imp": ("بتا", "بتاؤ", "بتائیے"),
    },
    "dekhna": {
        "pres.m": ("دیکھتا ہے", "دیکھتے ہو", "دیکھتے ہیں"),
        "cont.m": ("دیکھ رہا ہے", "دیکھ رہے ہو", "دیکھ رہے ہیں"),
        "imp": ("دیکھ", "دیکھو", "دیکھیے"),
    },
    "sunna": {
        "pres.m": ("سنتا ہے", "سنتے ہو", "سنتے ہیں"),
        "imp": ("سن", "سنو", "سنیے"),
    },
    "khana": {
        "pres.m": ("کھاتا ہے", "کھاتے ہو", "کھاتے ہیں"),
        "cont.m": ("کھا رہا ہے", "کھا رہے ہو", "کھا رہے ہیں"),
        "future.m": ("کھائے گا", "کھاؤ گے", "کھائیں گے"),
        "imp": ("کھا", "کھاؤ", "کھائیے"),
    },
    "pina": {
        "pres.m": ("پیتا ہے", "پیتے ہو", "پیتے ہیں"),
        "imp": ("پی", "پیو", "پیجیے"),
    },
    "lena": {"future.m": ("لے گا", "لو گے", "لیں گے"), "imp": ("لے", "لو", "لیجیے")},
    "dena": {"future.m": ("دے گا", "دو گے", "دیں گے"), "imp": ("دے", "دو", "دیجیے")},
    "samajhna": {
        "pres.m": ("سمجھتا ہے", "سمجھتے ہو", "سمجھتے ہیں"),
        "imp": ("سمجھ", "سمجھو", "سمجھیے"),
    },
    "janna": {
        "pres.m": ("جانتا ہے", "جانتے ہو", "جانتے ہیں"),
        "pres.f": ("جانتی ہے", "جانتی ہو", "جانتی ہیں"),
    },
    "chahna": {"pres.m": ("چاہتا ہے", "چاہتے ہو", "چاہتے ہیں")},
    "sakna": {
        "pres.m": ("سکتا ہے", "سکتے ہو", "سکتے ہیں"),
        "pres.f": ("سکتی ہے", "سکتی ہو", "سکتی ہیں"),
    },
    "likhna": {
        "pres.m": ("لکھتا ہے", "لکھتے ہو", "لکھتے ہیں"),
        "imp": ("لکھ", "لکھو", "لکھیے"),
    },
    "padhna": {
        "pres.m": ("پڑھتا ہے", "پڑھتے ہو", "پڑھتے ہیں"),
        "imp": ("پڑھ", "پڑھو", "پڑھیے"),
    },
    "chalna": {
        "pres.m": ("چلتا ہے", "چلتے ہو", "چلتے ہیں"),
        "imp": ("چل", "چلو", "چلیے"),
    },
    "sona": {"pres.m": ("سوتا ہے", "سوتے ہو", "سوتے ہیں"), "imp": ("سو", "سوؤ", "سوئیے")},
    "baithna": {"imp": ("بیٹھ", "بیٹھو", "بیٹھیے")},
    "uthna": {"imp": ("اٹھ", "اٹھو", "اٹھیے")},
    "rukna": {"imp": ("رک", "رکو", "رکیے"), "prohibitive": ("مت رک", "مت رکو", "مت رکیے")},
    "kholna": {"imp": ("کھول", "کھولو", "کھولیے")},
    "utarna": {"imp": ("اتر", "اترو", "اتریے")},
    "bulana": {"imp": ("بلا", "بلاؤ", "بلائیے")},
    "puchhna": {"imp": ("پوچھ", "پوچھو", "پوچھیے")},
    "hatna": {"imp": ("ہٹ", "ہٹو", "ہٹیے")},
    "maf_karna": {"imp": ("معاف کر", "معاف کرو", "معاف کیجیے")},
    "intezar": {"imp": ("انتظار کر", "انتظار کرو", "انتظار کیجیے")},
}

#: Same ordering rule as Hindi: the bare imperative is the shortest string and
#: must be declared last so it does not win ties against the longer tenses that
#: contain it.
_UR_TENSE_ORDER = (
    "cont.m", "cont.f", "future.m", "future.f", "prohibitive",
    "pres.m", "pres.f", "imp",
)

_UR_2P_CONTEXT = r"(?:تو|تم|آپ)(?:\s+\S+){0,10}\s+"

# --------------------------------------------------------------------------
# The Urdu copula is the project's fourth encounter with one verb form doing
# two jobs, and the worst of them: ہے is the تو copula *and* the ordinary
# third-person copula. Unguarded it matched every statement in the language,
# so "آج موسم بہت اچھا ہے" — the weather is nice — detected Close at full
# confidence, and "تیرا نام کیا ہے" was conjugated down to "تمہارا نام کیا ہو"
# on a verb whose subject is the name, not the listener.
#
# What licenses the second-person reading is the *nominative* تو, and only
# that. تیرا is the genitive and modifies a noun — in "تیرا نام کیا ہے" the
# subject is نام and the copula agrees with it, which is exactly why the gold
# set keeps ہے unchanged across that row's Close and Casual columns.
#
# Urdu is verb-final, so the pronoun sits at the head of the clause and the
# copula at the end: a bounded backscan reaches it. Every Close row in the
# gold that carries ہے also carries تو, and no negative row does.
# --------------------------------------------------------------------------

_UR_TU_BEFORE = rf"{LEFT}تو{RIGHT}(?:\s+\S+){{0,10}}\s+"

#: ہو is the تم copula, but ہونا is also the auxiliary in "بارش ہو رہی ہے"
#: (it is raining) and the subjunctive in "ہو سکتا ہے". A following participle
#: or modal marks those, and neither is about the listener.
_UR_HO_AUX_AFTER = r"\s+(?:رہا|رہی|رہے|گیا|گئی|گئے|چکا|چکی|چکے|سکتا|سکتی|سکے)"


#: A bare stem followed by an auxiliary is not an imperative. Urdu builds its
#: progressives, modals and compound verbs on exactly the form the تو
#: imperative takes, so "کر سکتا ہے" (can do) and "چل رہی ہے" (is running) look
#: like commands to a matcher that stops at the word. Unguarded, the first was
#: rewritten to "کرو سکتے ہو" and the second made "the train is late" read as
#: Close at full confidence.
_UR_AUX_AFTER = (
    r"\s+(?:رہا|رہی|رہے"                        # progressive
    r"|سکتا|سکتی|سکتے|سکو|سکے|سکیں"             # modal: can
    r"|پاتا|پاتی|پاتے|چکا|چکی|چکے"              # manage to, have already
    r"|گیا|گئی|گئے|لیا|لی|لیے|دیا|دی|دیے)"      # compound verbs
)


def _ur_verb_rules() -> Tuple[Rule, ...]:
    out = []
    for tense in _UR_TENSE_ORDER:
        for verb, paradigm in _UR_PARADIGMS.items():
            forms = paradigm.get(tense)
            if not forms:
                continue
            tu, tum, aap = forms
            if len({tu, tum, aap}) == 1:
                continue
            guards = []
            if tense not in ("imp", "prohibitive"):
                # Every finite تو form is masculine or feminine *singular*,
                # which is also the third-person agreement — "وہ کیا کرتا ہے؟"
                # is the same string as the تو question. It needs the same
                # nominative تو the copula needs, and for the same reason.
                guards.append((tu, "", "", _UR_TU_BEFORE, "", ""))
            imperative = paradigm.get("imp")
            if (imperative and imperative[1] == tum
                    and tense.startswith("pres")):
                # The تم present collides with some verb's تم imperative.
                guards.append((tum, "", "", _UR_2P_CONTEXT, "", ""))
            out.append(
                Rule(f"v.{verb}.{tense}", (tu, tum, aap, aap),
                     f"{verb} · {tense}",
                     guard_after=_UR_AUX_AFTER if tense == "imp" else "",
                     form_guards=tuple(guards))
            )
    return tuple(out)


URDU = LanguageTable(
    code="ur",
    name="Urdu",
    canon=(0, 1, 2, 3),
    please=("", "", "ذرا ", "براہ کرم "),
    address_terms={
        "older_man": ("", "بھائی", "بھائی صاحب", "سر"),
        "older_woman": ("", "باجی", "باجی", "میڈم"),
        "elder_man": ("", "انکل", "انکل جی", "سر"),
        "elder_woman": ("", "آنٹی", "آنٹی جی", "میڈم"),
        "peer": ("", "یار", "بھائی", "سر"),
        "official": ("", "صاحب", "صاحب", "سر"),
    },
    rules=_ur_verb_rules() + (
        # Ergative — Urdu marks the subject of a perfective transitive with نے,
        # so without these the whole past tense is unreachable.
        Rule("pron.2sg.erg", ("تو نے", "تم نے", "آپ نے", "آپ نے"), "you (ergative)"),
        Rule("pron.2sg.nom", ("تو", "تم", "آپ", "آپ"), "you"),
        Rule("pron.2sg.acc", ("تجھے", "تمہیں", "آپ کو", "آپ کو"), "to you"),
        Rule("pron.2sg.abl", ("تجھ سے", "تم سے", "آپ سے", "آپ سے"), "from/with you"),
        Rule("pron.2sg.gen", ("تیرا", "تمہارا", "آپ کا", "آپ کا"), "your"),
        # The oblique and feminine genitives were missing, which is why
        # "یہ تیرے لیے ہے" and "مجھے تیری مدد چاہیے" detected nothing at all.
        Rule("pron.2sg.gen.f", ("تیری", "تمہاری", "آپ کی", "آپ کی"), "your (f)"),
        Rule("pron.2sg.gen.obl", ("تیرے", "تمہارے", "آپ کے", "آپ کے"), "your (obl/pl)"),
        Rule("cop.pres", ("ہے", "ہو", "ہیں", "ہیں"), "you are",
             form_guards=(
                 ("ہے", "", "", _UR_TU_BEFORE, "", ""),
                 ("ہو", "", _UR_HO_AUX_AFTER, "", "", ""),
             )),
        # تھا is third person too ("وہ کہاں تھا؟"), so it takes the same
        # requirement as ہے. تھے and تھیں are honorific-or-plural and do not.
        Rule("cop.past.m", ("تھا", "تھے", "تھے", "تھے"), "you were (m)",
             form_guards=(("تھا", "", "", _UR_TU_BEFORE, "", ""),)),
        Rule("cop.past.f", ("تھی", "تھیں", "تھیں", "تھیں"), "you were (f)",
             form_guards=(("تھی", "", "", _UR_TU_BEFORE, "", ""),)),
        # Second-person adjective and participle agreement. Urdu makes the
        # predicate agree with the pronoun, so moving تو to تم without moving
        # کیسا to کیسے leaves "تم کیسا ہو؟" — the right pronoun in the wrong
        # concord.
        # Masculine only: the feminine کیسی is the same at every level, so it
        # carries no register information and the table refuses it.
        # rewrite_only for the same reason as Hindi's: کیسے fills three slots,
        # so its vote says almost nothing while still diluting the pronoun's.
        Rule("adj.kaisa", ("کیسا", "کیسے", "کیسے", "کیسے"), "how (m)",
             require_before=_UR_2P_CONTEXT, rewrite_only=True),
        Rule("greet.hello", ("اوے", "ہیلو", "السلام علیکم", "السلام علیکم"), "hello"),
        # شکریہ is neutral across every level below Formal — the shape Tamil,
        # Spanish, Italian and Portuguese all ended up with — so it never
        # contradicts the pronoun, and بہت بہت شکریہ is left as the Formal
        # evidence. It used to escalate at Polite, so asking for Polite turned
        # "آپ کا بہت بہت شکریہ" into "آپ کا بہت شکریہ", which read Formal
        # anyway; and asking for Close turned "تیرا شکریہ" into "تیرا تھینکس",
        # swapping in an English loan nobody requested. تھینکس goes with it,
        # for the same reason Portuguese lost "Valeu": it is real Urdu, but no
        # level here means it.
        Rule("greet.thanks", ("شکریہ", "شکریہ", "شکریہ", "بہت بہت شکریہ"), "thanks"),
        Rule("greet.sorry", ("سوری", "سوری", "معاف کیجیے", "معذرت چاہتا ہوں"), "sorry"),
        # براہ کرم is what separates Formal from Polite in a request — آپ
        # covers both — so it has to be readable, not merely insertable. ذرا
        # stays out: it means "a little" and softens requests at any level.
        Rule("polite.particle", ("", "", "", "براہ کرم"), "please"),
        # جناب is a Formal vocative, and "مجھے افسوس ہے" is the register of a
        # written apology rather than a spoken one.
        Rule("voc.sir", ("", "بھائی", "صاحب", "جناب"), "sir"),
        Rule("clause.afsos", ("سوری", "سوری", "معاف کیجیے", "مجھے افسوس ہے"),
             "I am sorry"),
    ),
)

# --------------------------------------------------------------------------
# Odia verb paradigms.
#
# The smallest table in the project at 13 rules. Two gaps the gold set found:
# no finite verb forms at all, so anything without an imperative in it detected
# nothing; and the ତୁ imperatives were listed without their halanta, so
# "ଏଠିକି ଆସ୍।" and "ମୋତେ କୁହ୍।" did not match. Both spellings occur, so both are
# listed rather than picking one.
#
# Each entry is (ତୁ, ତୁମେ, ଆପଣ). Lowest-confidence table in the project —
# drafted from grammars, and the place a speaker's review is worth most.
# --------------------------------------------------------------------------

_OR_PARADIGMS: Dict[str, Dict[str, Tuple[str, str, str]]] = {
    "kariba": {  # to do
        "cont": ("କରୁଛୁ", "କରୁଛ", "କରୁଛନ୍ତି"),
        "future": ("କରିବୁ", "କରିବ", "କରିବେ"),
        "imp": ("କର୍", "କର", "କରନ୍ତୁ"),
    },
    "asiba": {  # to come
        "cont": ("ଆସୁଛୁ", "ଆସୁଛ", "ଆସୁଛନ୍ତି"),
        "future": ("ଆସିବୁ", "ଆସିବ", "ଆସିବେ"),
        "imp": ("ଆସ୍", "ଆସ", "ଆସନ୍ତୁ"),
    },
    "jiba": {  # to go
        "cont": ("ଯାଉଛୁ", "ଯାଉଛ", "ଯାଉଛନ୍ତି"),
        "future": ("ଯିବୁ", "ଯିବ", "ଯିବେ"),
        "imp": ("ଯା", "ଯାଅ", "ଯାଆନ୍ତୁ"),
    },
    "kahiba": {  # to say
        "cont": ("କହୁଛୁ", "କହୁଛ", "କହୁଛନ୍ତି"),
        "imp": ("କୁହ୍", "କୁହ", "କୁହନ୍ତୁ"),
    },
    "basiba": {  # to sit
        "cont": ("ବସୁଛୁ", "ବସୁଛ", "ବସୁଛନ୍ତି"),
        "imp": ("ବସ୍", "ବସ", "ବସନ୍ତୁ"),
    },
    "dekhiba": {  # to see
        "cont": ("ଦେଖୁଛୁ", "ଦେଖୁଛ", "ଦେଖୁଛନ୍ତି"),
        "imp": ("ଦେଖ୍", "ଦେଖ", "ଦେଖନ୍ତୁ"),
    },
    "suniba": {  # to hear
        "cont": ("ଶୁଣୁଛୁ", "ଶୁଣୁଛ", "ଶୁଣୁଛନ୍ତି"),
        "imp": ("ଶୁଣ୍", "ଶୁଣ", "ଶୁଣନ୍ତୁ"),
    },
    "khaiba": {  # to eat
        "cont": ("ଖାଉଛୁ", "ଖାଉଛ", "ଖାଉଛନ୍ତି"),
        "imp": ("ଖା", "ଖାଅ", "ଖାଆନ୍ତୁ"),
    },
    "rahiba": {"cont": ("ରହୁଛୁ", "ରହୁଛ", "ରହୁଛନ୍ତି")},
    "janiba": {"cont": ("ଜାଣୁଛୁ", "ଜାଣୁଛ", "ଜାଣୁଛନ୍ତି")},
    "deba": {"imp": ("ଦେ", "ଦିଅ", "ଦିଅନ୍ତୁ")},
    "neba": {"imp": ("ନେ", "ନିଅ", "ନିଅନ୍ତୁ")},
    "lekhiba": {"imp": ("ଲେଖ୍", "ଲେଖ", "ଲେଖନ୍ତୁ")},
    "padhiba": {"imp": ("ପଢ଼୍", "ପଢ଼", "ପଢ଼ନ୍ତୁ")},
    "kshama_kariba": {"imp": ("କ୍ଷମା କର୍", "କ୍ଷମା କର", "କ୍ଷମା କରନ୍ତୁ")},
    "sahajya_kariba": {"imp": ("ସାହାଯ୍ୟ କର୍", "ସାହାଯ୍ୟ କର", "ସାହାଯ୍ୟ କରନ୍ତୁ")},
}

_OR_TENSE_ORDER = ("cont", "future", "imp")


def _or_verb_rules() -> Tuple[Rule, ...]:
    out = []
    for tense in _OR_TENSE_ORDER:
        for verb, paradigm in _OR_PARADIGMS.items():
            forms = paradigm.get(tense)
            if not forms:
                continue
            tu, tume, apana = forms
            if len({tu, tume, apana}) == 1:
                continue
            out.append(
                Rule(f"v.{verb}.{tense}", (tu, tume, apana, apana),
                     f"{verb} · {tense}")
            )
    return tuple(out)


ODIA = LanguageTable(
    code="or",
    name="Odia",
    canon=(0, 1, 2, 3),
    please=("", "", "ଟିକେ ", "ଦୟାକରି "),
    address_terms={
        "older_man": ("", "ଭାଇ", "ଭାଇନା", "ସାର୍"),
        "older_woman": ("", "ନାନୀ", "ଆପା", "ମାଡାମ୍"),
        "elder_man": ("", "କାକା", "କାକା", "ସାର୍"),
        "elder_woman": ("", "ମାଉସୀ", "ମାଉସୀ", "ମାଡାମ୍"),
        "peer": ("", "ସାଙ୍ଗ", "ଭାଇ", "ସାର୍"),
        "official": ("", "ସାର୍", "ସାର୍", "ସାର୍"),
    },
    # The old hand-written imperatives are gone: v.kara.imp had ତୁମେ taking
    # କରନ୍ତୁ, the ଆପଣ form, which put the honorific one level too low. The
    # generated paradigm has ("କର୍", "କର", "କରନ୍ତୁ").
    rules=_or_verb_rules() + (
        Rule("pron.2sg.nom", ("ତୁ", "ତୁମେ", "ଆପଣ", "ଆପଣ"), "you"),
        # Odia has a long and a short genitive at every level, and the two
        # rules used to pair them symmetrically — long with long, short with
        # short. That is not how the language distributes them: ତୋର and ତୁମର
        # are the ordinary informal genitives, while the honorific one is
        # ordinarily ଆପଣଙ୍କ, the ଙ୍କ already carrying the force that ର adds
        # lower down. The symmetric pairing meant every upgrade produced
        # ଆପଣଙ୍କର and every downgrade produced the clipped ତୋ.
        #
        # So the primary rule crosses: long below, short above. The other two
        # exist to catch the variants and send them to the same place.
        Rule("pron.2sg.gen", ("ତୋର", "ତୁମର", "ଆପଣଙ୍କ", "ଆପଣଙ୍କ"), "your"),
        Rule("pron.2sg.gen.short", ("ତୋ", "ତୁମ", "ଆପଣଙ୍କ", "ଆପଣଙ୍କ"), "your (short)"),
        Rule("pron.2sg.gen.long", ("ତୋର", "ତୁମର", "ଆପଣଙ୍କର", "ଆପଣଙ୍କର"),
             "your (long honorific)"),
        Rule("pron.2sg.acc", ("ତୋତେ", "ତୁମକୁ", "ଆପଣଙ୍କୁ", "ଆପଣଙ୍କୁ"), "to you"),
        Rule("cop.pres", ("ଅଛୁ", "ଅଛ", "ଅଛନ୍ତି", "ଅଛନ୍ତି"), "you are"),
        Rule("cop.past", ("ଥିଲୁ", "ଥିଲ", "ଥିଲେ", "ଥିଲେ"), "you were"),
        Rule("greet.hello", ("ଏ", "ହେଲୋ", "ନମସ୍କାର", "ନମସ୍କାର"), "hello"),
        # ଧନ୍ୟବାଦ is neutral below Formal, so asking for Close no longer swaps
        # in the English loan: "ତୋତେ ଧନ୍ୟବାଦ" came back as "ତୋତେ ଥ୍ୟାଙ୍କ୍ସ".
        # Same shape as Urdu, Hindi and Portuguese.
        Rule("greet.thanks", ("ଧନ୍ୟବାଦ", "ଧନ୍ୟବାଦ", "ଧନ୍ୟବାଦ", "ବହୁତ ଧନ୍ୟବାଦ"), "thanks"),
        Rule("greet.sorry", ("ସରି", "ସରି", "କ୍ଷମା କରନ୍ତୁ", "କ୍ଷମା କରନ୍ତୁ"), "sorry"),
        # ଦୟାକରି is what separates Formal from Polite in a request — ଆପଣ covers
        # both — so it has to be readable, not merely insertable. ଟିକେ stays
        # out: it means "a little" and softens a request at any level.
        Rule("polite.particle", ("", "", "", "ଦୟାକରି"), "please"),
    ),
)

# --------------------------------------------------------------------------
# Assamese verb paradigms. (তই, তুমি, আপুনি)
#
# Shares the Bengali script but not the morphology, and the endings differ more
# than the shared alphabet suggests. Thirteen rules covered a handful of
# imperatives, so everything finite detected nothing.
#
# Lowest-confidence table in the project along with Odia and Nepali: drafted
# from grammars, not spoken.
# --------------------------------------------------------------------------

_AS_PARADIGMS: Dict[str, Dict[str, Tuple[str, str, str]]] = {
    "kara": {  # to do
        "pres": ("কৰ", "কৰা", "কৰে"),
        "cont": ("কৰি আছ", "কৰি আছা", "কৰি আছে"),
        "future": ("কৰিবি", "কৰিবা", "কৰিব"),
        "imp": ("কৰ", "কৰা", "কৰক"),
    },
    "jaa": {  # to go
        "pres": ("যা", "যোৱা", "যায়"),
        "future": ("যাবি", "যাবা", "যাব"),
        "imp": ("যা", "যোৱা", "যাওক"),
    },
    "aha": {  # to come
        "pres": ("আহ", "আহা", "আহে"),
        "future": ("আহিবি", "আহিবা", "আহিব"),
        "imp": ("আহ", "আহা", "আহক"),
    },
    "thaka": {  # to stay, to live
        "pres": ("থাক", "থাকা", "থাকে"),
        "imp": ("থাক", "থাকা", "থাকক"),
    },
    "khaa": {  # to eat
        "pres": ("খা", "খোৱা", "খায়"),
        "imp": ("খা", "খোৱা", "খাওক"),
    },
    "saa": {"imp": ("চা", "চোৱা", "চাওক")},        # to look
    "suna": {"imp": ("শুন", "শুনা", "শুনক")},        # to hear
    "diya": {"imp": ("দে", "দিয়া", "দিয়ক")},        # to give
    "loa": {"imp": ("ল", "লোৱা", "লওক")},           # to take
    "baha": {"imp": ("বহ", "বহা", "বহক")},          # to sit
    "likha": {"imp": ("লিখ", "লিখা", "লিখক")},      # to write
    "para": {"imp": ("পঢ়", "পঢ়া", "পঢ়ক")},         # to read
    "kaba": {"imp": ("ক", "কোৱা", "কওক")},          # to say
}

_AS_TENSE_ORDER = ("cont", "future", "pres", "imp")

#: An imperative closes its clause. Required by কোৱা's তই form, which is the
#: single character ক — and the apostrophe in ক'ত ("where") counts as a word
#: boundary, so a bare ক matched inside it and "আপোনাৰ ঘৰ ক'ত?" detected as
#: Close off a one-letter false positive.
_AS_CLAUSE_FINAL = r"\s*(?:[।!?.,]|$)"
_AS_SHORT_IMPERATIVES = {"kaba", "loa"}


#: A second-person pronoun to the left. Assamese present and imperative are
#: identical in the তই and তুমি forms and differ only in the আপুনি one — আহ,
#: আহা for both, then আহে against আহক. The present is declared first, so it won
#: every match and "ইয়ালৈ আহ।" (come here) climbed to "ইয়ালৈ আহে।", which is
#: the present indicative, not the imperative the sentence was.
#:
#: The subject settles it: a present tense has one, an imperative does not.
_AS_2P_CONTEXT = r"(?:তই|তুমি|আপুনি)(?:\s+\S+){0,10}\s+"


def _as_verb_rules() -> Tuple[Rule, ...]:
    out = []
    for tense in _AS_TENSE_ORDER:
        for verb, paradigm in _AS_PARADIGMS.items():
            forms = paradigm.get(tense)
            if not forms:
                continue
            toi, tumi, apuni = forms
            if len({toi, tumi, apuni}) == 1:
                continue
            after = (
                _AS_CLAUSE_FINAL
                if tense == "imp" and verb in _AS_SHORT_IMPERATIVES
                else ""
            )
            imperative = paradigm.get("imp")
            collides = (tense != "imp" and imperative is not None
                        and imperative[:2] == (toi, tumi))
            out.append(
                Rule(f"v.{verb}.{tense}", (toi, tumi, apuni, apuni),
                     f"{verb} · {tense}", require_after=after,
                     require_before=_AS_2P_CONTEXT if collides else "")
            )
    return tuple(out)


ASSAMESE = LanguageTable(
    code="as",
    name="Assamese",
    canon=(0, 1, 2, 3),
    please=("", "", "অলপ ", "অনুগ্ৰহ কৰি "),
    address_terms={
        "older_man": ("", "দাদা", "ডাঙৰীয়া", "চাৰ"),
        "older_woman": ("", "বাইদেউ", "বাইদেউ", "মেডাম"),
        "elder_man": ("", "খুৰা", "খুৰা", "চাৰ"),
        "elder_woman": ("", "খুৰী", "খুৰী", "মেডাম"),
        "peer": ("", "বন্ধু", "দাদা", "চাৰ"),
        "official": ("", "চাৰ", "চাৰ", "চাৰ"),
    },
    rules=_as_verb_rules() + (
        Rule("pron.2sg.nom", ("তই", "তুমি", "আপুনি", "আপুনি"), "you"),
        Rule("pron.2sg.gen", ("তোৰ", "তোমাৰ", "আপোনাৰ", "আপোনাৰ"), "your"),
        Rule("pron.2sg.acc", ("তোক", "তোমাক", "আপোনাক", "আপোনাক"), "to you"),
        Rule("pron.2sg.dat", ("তোলৈ", "তোমালৈ", "আপোনালৈ", "আপোনালৈ"), "to you (dat)"),
        # আছে is the আপুনি copula and also the ordinary third-person one, so
        # "বৰষুণ দি আছে" ("it is raining") read as Polite. It needs a
        # second-person pronoun nearby to count; আছ and আছা are unambiguous.
        # Same shape as Gujarati છે.
        Rule("cop.pres", ("আছ", "আছা", "আছে", "আছে"), "you are",
             form_guards=(("আছে", "", "",
                           r"(?:তই|তুমি|আপুনি|তোৰ|তোমাৰ|আপোনাৰ)(?:\s+\S+){0,6}\s+",
                           ""),)),
        # অনুগ্ৰহ কৰি marks Formal above the shared আপুনি, so it has to be
        # readable, not merely insertable; the empty low slots drop it on the
        # way down.
        Rule("polite.particle", ("", "", "", "অনুগ্ৰহ কৰি"), "please"),
        Rule("greet.hello", ("এই", "হেলো", "নমস্কাৰ", "নমস্কাৰ"), "hello"),
        # Neutral below Formal, so asking for Close no longer swaps in the
        # English loan: "তোক ধন্যবাদ" came back as "তোক থেংকছ".
        Rule("greet.thanks", ("ধন্যবাদ", "ধন্যবাদ", "ধন্যবাদ", "বহুত ধন্যবাদ"), "thanks"),
        Rule("greet.sorry", ("চৰি", "চৰি", "ক্ষমা কৰিব", "ক্ষমা কৰিব"), "sorry"),
    ),
)

# --------------------------------------------------------------------------
# Nepali verb paradigms. (तँ, तिमी, तपाईं)
#
# Nepali produced a profile no other language did: 93.3% detection against
# 59.1% exactness. It found the register reliably and then rendered it wrong,
# because the pronoun rules were there and the verb rules were not — so
# "तँ कस्तो छस्?" upgraded to "तिमी कस्तो छस्?" instead of "तिमी कस्तो छौ?".
# The pronoun moved and the copula stayed behind, in every single sentence.
#
# Nepali agreement is heavier than its neighbours': the honorific level takes a
# whole -नुहुन्छ construction rather than a suffix swap, so the तपाईं column is
# not derivable from the others.
# --------------------------------------------------------------------------

_NE_PARADIGMS: Dict[str, Dict[str, Tuple[str, str, str]]] = {
    "hunu": {  # to be
        "pres": ("छस्", "छौ", "हुनुहुन्छ"),
        "past": ("थिइस्", "थियौ", "हुनुहुन्थ्यो"),
    },
    "garnu": {  # to do
        "pres": ("गर्छस्", "गर्छौ", "गर्नुहुन्छ"),
        "past": ("गरिस्", "गर्यौ", "गर्नुभयो"),
        "imp": ("गर्", "गर", "गर्नुहोस्"),
    },
    "jaanu": {  # to go
        "pres": ("जान्छस्", "जान्छौ", "जानुहुन्छ"),
        "imp": ("जा", "जाऊ", "जानुहोस्"),
    },
    "aaunu": {  # to come
        "pres": ("आउँछस्", "आउँछौ", "आउनुहुन्छ"),
        "imp": ("आइज", "आऊ", "आउनुहोस्"),
    },
    "basnu": {  # to sit, to live
        "pres": ("बस्छस्", "बस्छौ", "बस्नुहुन्छ"),
        "imp": ("बस्", "बस", "बस्नुहोस्"),
    },
    "bhannu": {  # to say
        "pres": ("भन्छस्", "भन्छौ", "भन्नुहुन्छ"),
        "imp": ("भन्", "भन", "भन्नुहोस्"),
    },
    "khaanu": {  # to eat
        "pres": ("खान्छस्", "खान्छौ", "खानुहुन्छ"),
        "imp": ("खा", "खाऊ", "खानुहोस्"),
    },
    "hernu": {  # to look
        "pres": ("हेर्छस्", "हेर्छौ", "हेर्नुहुन्छ"),
        "imp": ("हेर्", "हेर", "हेर्नुहोस्"),
    },
    "sunnu": {  # to hear
        "pres": ("सुन्छस्", "सुन्छौ", "सुन्नुहुन्छ"),
        "imp": ("सुन्", "सुन", "सुन्नुहोस्"),
    },
    "saknu": {"pres": ("सक्छस्", "सक्छौ", "सक्नुहुन्छ")},          # can
    "jaannu": {"pres": ("जान्दछस्", "जान्दछौ", "जान्नुहुन्छ")},     # to know
    "parkhanu": {"imp": ("पर्ख्", "पर्ख", "पर्खनुहोस्")},          # to wait
    "dinu": {"imp": ("दे", "देऊ", "दिनुहोस्")},                   # to give
    "linu": {"imp": ("ले", "लेऊ", "लिनुहोस्")},                   # to take
    "lekhnu": {"imp": ("लेख्", "लेख", "लेख्नुहोस्")},              # to write
    "padhnu": {"imp": ("पढ्", "पढ", "पढ्नुहोस्")},                # to read
    "maaf_garnu": {"imp": ("माफ गर्", "माफ गर", "माफ गर्नुहोस्")},
}

_NE_TENSE_ORDER = ("pres", "past", "imp")


def _ne_verb_rules() -> Tuple[Rule, ...]:
    out = []
    for tense in _NE_TENSE_ORDER:
        for verb, paradigm in _NE_PARADIGMS.items():
            forms = paradigm.get(tense)
            if not forms:
                continue
            ta, timi, tapai = forms
            if len({ta, timi, tapai}) == 1:
                continue
            # Nepali canon is (0, 1, 2, 3) with हजुर at Formal, but the verb
            # does not change again above तपाईं — only the pronoun does.
            out.append(
                Rule(f"v.{verb}.{tense}", (ta, timi, tapai, tapai),
                     f"{verb} · {tense}")
            )
    return tuple(out)


NEPALI = LanguageTable(
    code="ne",
    name="Nepali",
    canon=(0, 1, 2, 3),
    please=("", "", "अलिकति ", "कृपया "),
    address_terms={
        "older_man": ("", "दाइ", "दाइ", "सर"),
        "older_woman": ("", "दिदी", "दिदी", "म्याडम"),
        "elder_man": ("", "काका", "काका", "सर"),
        "elder_woman": ("", "काकी", "काकी", "म्याडम"),
        "peer": ("", "साथी", "दाइ", "सर"),
        "official": ("", "हजुर", "हजुर", "सर"),
    },
    rules=_ne_verb_rules() + (
        Rule("pron.2sg.nom", ("तँ", "तिमी", "तपाईं", "हजुर"), "you"),
        Rule("pron.2sg.gen", ("तेरो", "तिम्रो", "तपाईंको", "हजुरको"), "your"),
        Rule("pron.2sg.acc", ("तँलाई", "तिमीलाई", "तपाईंलाई", "हजुरलाई"), "to you"),
        # Nepali has two copulas and हुनुहुन्छ is the honorific of both:
        #
        #   छ-series  attributive   तँ कस्तो छस् / तिमी कस्तो छौ
        #   हो-series identificational  तँ को होस् / तिमी को हौ
        #
        # Upward both collapse to हुनुहुन्छ, which is unambiguous. Downward it
        # is a real fork, and the engine has to pick one: it takes the छ-series,
        # because "कस्तो" — the commonest frame by far — is attributive.
        # Flagged for a speaker; this is a low-confidence table.
        Rule("cop.ho", ("होस्", "हौ", "हुनुहुन्छ", "हुनुहुन्छ"), "you are (identity)"),
        # कृपया marks Formal above तपाईं, so it has to be readable.
        Rule("polite.particle", ("", "", "", "कृपया"), "please"),
        Rule("greet.hello", ("ए", "हेलो", "नमस्ते", "नमस्कार"), "hello"),
        Rule("greet.thanks", ("धन्यवाद", "धन्यवाद", "धन्यवाद", "धेरै धन्यवाद"), "thanks"),
        # क्षमाप्रार्थी is the written-register apology, above माफ.
        Rule("lex.apology", ("माफ", "माफ", "माफ", "क्षमाप्रार्थी"), "apology"),
        Rule("greet.sorry", ("सरी", "सरी", "माफ गर्नुहोस्", "क्षमा गर्नुहोस्"), "sorry"),
    ),
)


TABLES: Dict[str, LanguageTable] = {
    t.code: t
    for t in (
        BENGALI,
        HINDI,
        MARATHI,
        GUJARATI,
        PUNJABI,
        URDU,
        ODIA,
        ASSAMESE,
        NEPALI,
        TAMIL,
        TELUGU,
        KANNADA,
        MALAYALAM,
        GERMAN,
        FRENCH,
        SPANISH,
        ITALIAN,
        PORTUGUESE,
        JAPANESE,
        ENGLISH,
    )
}


def supported_languages() -> Tuple[str, ...]:
    """Language codes that have a register table, in table order."""
    return tuple(TABLES.keys())


def has_table(code: str) -> bool:
    return _normalise(code) in TABLES


def get_table(code: str) -> LanguageTable:
    key = _normalise(code)
    try:
        return TABLES[key]
    except KeyError:
        raise KeyError(
            f"no register table for language {code!r}; "
            f"available: {', '.join(sorted(TABLES))}"
        ) from None


def _normalise(code: str) -> str:
    """Accept 'bn', 'BN', 'bn-IN', 'bn_IN' and land on 'bn'."""
    if not isinstance(code, str):
        return ""
    return code.strip().lower().replace("_", "-").split("-")[0]
