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
from typing import Dict, Tuple

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
    #: Use this rule when rewriting, but never as evidence when detecting.
    #:
    #: For words that are register-*neutral* in themselves but have a polite
    #: elaboration. Italian "Grazie" is said at every level; "La ringrazio" is
    #: markedly formal. Listing Grazie in the low slots makes the upgrade work,
    #: but it also let a bare "Grazie a Lei" outvote the Lei and detect as
    #: Casual — the rule was supplying evidence for a level the word does not
    #: actually carry.
    rewrite_only: bool = False
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

    def __post_init__(self) -> None:
        if len(self.canon) != 4:
            raise ValueError(f"{self.code}: canon must have 4 entries")
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
    "ana": {  # to come
        "pres.m": ("आता है", "आते हो", "आते हैं"),
        "pres.f": ("आती है", "आती हो", "आती हैं"),
        "cont.m": ("आ रहा है", "आ रहे हो", "आ रहे हैं"),
        "cont.f": ("आ रही है", "आ रही हो", "आ रही हैं"),
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
    "rukna": {
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
    "cont.m", "cont.f", "future.m", "future.f", "prohibitive",
    "pres.m", "pres.f", "subj", "imp",
)

#: A second-person pronoun to the left, for the tenses whose तुम form collides
#: with the imperative — करो is both "you do" and "do!". Same idea as Bengali,
#: same generous window: the pronoun is often several words back.
_HI_2P_CONTEXT = r"(?:तू|तुम|आप|तूने|तुमने|आपने)(?:\s+\S+){0,10}\s+"

#: Tenses that need it.
_HI_NEEDS_PRONOUN = {"subj"}


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

            # Only guard where the imperative genuinely collides.
            imperative = paradigm.get("imp")
            collides = bool(imperative) and imperative[1] == tum
            before = _HI_2P_CONTEXT if (tense in _HI_NEEDS_PRONOUN or
                                        (tense.startswith("pres") and collides)) else ""

            out.append(
                Rule(f"v.{verb}.{tense}", (tu, tum, aap, aap),
                     f"{verb} · {tense}", require_before=before)
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
        Rule("cop.pres", ("है", "हो", "हैं", "हैं"), "you are"),
        Rule("cop.past.m", ("था", "थे", "थे", "थे"), "you were (m)"),
        Rule("cop.past.f", ("थी", "थीं", "थीं", "थीं"), "you were (f)"),
        Rule("greet.hello", ("ओए", "हैलो", "नमस्ते", "नमस्कार"), "hello"),
        Rule("greet.thanks", ("थैंक्स", "शुक्रिया", "धन्यवाद", "बहुत धन्यवाद"), "thanks"),
        Rule("greet.sorry", ("सॉरी", "सॉरी", "माफ़ कीजिए", "क्षमा कीजिए"), "sorry"),
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
    "maf_karne": {"imp": ("माफ कर", "माफ करा", "माफ करा")},
}

_MR_TENSE_ORDER = ("future", "pres.m", "pres.f", "imp")

_MR_2P_CONTEXT = r"(?:तू|तुम्ही|आपण)(?:\s+\S+){0,10}\s+"


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
    rules=_mr_verb_rules() + (
        Rule("pron.2sg.nom", ("तू", "तू", "तुम्ही", "आपण"), "you"),
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
        Rule("greet.hello", ("ए", "हॅलो", "नमस्कार", "नमस्कार"), "hello"),
        Rule("greet.thanks", ("थँक्स", "धन्यवाद", "धन्यवाद", "मनःपूर्वक धन्यवाद"), "thanks"),
        Rule("greet.sorry", ("सॉरी", "सॉरी", "माफ करा", "क्षमस्व"), "sorry"),
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
            # Gujarati canon is (1, 1, 2, 3): તું is Casual, not Close.
            out.append(
                Rule(f"v.{verb}.{tense}", (tu, tu, tame, aap),
                     f"{verb} · {tense}",
                     require_before=before, require_after=after)
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
        Rule("cop.pres", ("છે", "છે", "છો", "છો"), "you are"),
        Rule("cop.past.m", ("હતો", "હતો", "હતા", "હતા"), "you were (m)"),
        Rule("cop.past.f", ("હતી", "હતી", "હતાં", "હતાં"), "you were (f)"),
        Rule("greet.hello", ("એ", "હેલો", "નમસ્તે", "નમસ્કાર"), "hello"),
        Rule("greet.thanks", ("થેંક્સ", "આભાર", "આભાર", "ખૂબ આભાર"), "thanks"),
        Rule("greet.sorry", ("સોરી", "સોરી", "માફ કરશો", "ક્ષમા કરશો"), "sorry"),
    ),
)

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
    rules=(
        Rule("pron.2sg.nom", ("ਤੂੰ", "ਤੂੰ", "ਤੁਸੀਂ", "ਤੁਸੀਂ"), "you"),
        Rule("pron.2sg.dat", ("ਤੈਨੂੰ", "ਤੈਨੂੰ", "ਤੁਹਾਨੂੰ", "ਤੁਹਾਨੂੰ"), "to you"),
        Rule("pron.2sg.gen", ("ਤੇਰਾ", "ਤੇਰਾ", "ਤੁਹਾਡਾ", "ਤੁਹਾਡਾ"), "your"),
        Rule("cop.pres", ("ਹੈਂ", "ਹੈਂ", "ਹੋ", "ਹੋ"), "you are"),
        Rule("v.karna.imp", ("ਕਰ", "ਕਰ", "ਕਰੋ", "ਕਰੋ"), "do!"),
        Rule("v.auna.imp", ("ਆ", "ਆ", "ਆਓ", "ਆਓ"), "come!"),
        Rule("v.jana.imp", ("ਜਾ", "ਜਾ", "ਜਾਓ", "ਜਾਓ"), "go!"),
        Rule("v.baithna.imp", ("ਬੈਠ", "ਬੈਠ", "ਬੈਠੋ", "ਬੈਠੋ"), "sit!"),
        Rule("v.dassna.imp", ("ਦੱਸ", "ਦੱਸ", "ਦੱਸੋ", "ਦੱਸੋ"), "tell!"),
        Rule("v.lena.imp", ("ਲੈ", "ਲੈ", "ਲਵੋ", "ਲਵੋ"), "take!"),
        Rule("v.dena.imp", ("ਦੇ", "ਦੇ", "ਦਿਓ", "ਦਿਓ"), "give!"),
        Rule("v.vekhna.imp", ("ਵੇਖ", "ਵੇਖ", "ਵੇਖੋ", "ਵੇਖੋ"), "look!"),
        Rule("greet.hello", ("ਓਏ", "ਹੈਲੋ", "ਸਤ ਸ੍ਰੀ ਅਕਾਲ", "ਸਤ ਸ੍ਰੀ ਅਕਾਲ"), "hello"),
        Rule("greet.thanks", ("ਥੈਂਕਸ", "ਸ਼ੁਕਰੀਆ", "ਧੰਨਵਾਦ", "ਬਹੁਤ ਧੰਨਵਾਦ"), "thanks"),
        Rule("greet.sorry", ("ਸੌਰੀ", "ਸੌਰੀ", "ਮਾਫ਼ ਕਰਨਾ", "ਖਿਮਾ ਕਰਨਾ"), "sorry"),
    ),
)

# --------------------------------------------------------------------------
# Dravidian
# --------------------------------------------------------------------------

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
    rules=(
        Rule("pron.2sg.nom", ("நீ", "நீ", "நீங்கள்", "நீங்கள்"), "you"),
        Rule("pron.2sg.acc", ("உன்னை", "உன்னை", "உங்களை", "உங்களை"), "you (obj)"),
        Rule("pron.2sg.gen", ("உன்", "உன்", "உங்கள்", "உங்கள்"), "your"),
        Rule("pron.2sg.dat", ("உனக்கு", "உனக்கு", "உங்களுக்கு", "உங்களுக்கு"), "to you"),
        Rule("v.varu.imp", ("வா", "வா", "வாருங்கள்", "வாருங்கள்"), "come!"),
        Rule("v.po.imp", ("போ", "போ", "போங்கள்", "போங்கள்"), "go!"),
        Rule("v.sollu.imp", ("சொல்லு", "சொல்லு", "சொல்லுங்கள்", "சொல்லுங்கள்"), "say!"),
        Rule("v.sey.imp", ("செய்", "செய்", "செய்யுங்கள்", "செய்யுங்கள்"), "do!"),
        Rule("v.paar.imp", ("பார்", "பார்", "பாருங்கள்", "பாருங்கள்"), "look!"),
        Rule("v.utkaar.imp", ("உட்கார்", "உட்கார்", "உட்காருங்கள்", "உட்காருங்கள்"), "sit!"),
        Rule("v.kelu.imp", ("கேளு", "கேளு", "கேளுங்கள்", "கேளுங்கள்"), "ask/listen!"),
        Rule("v.sey.pres", ("செய்கிறாய்", "செய்கிறாய்", "செய்கிறீர்கள்", "செய்கிறீர்கள்"), "you do"),
        Rule("v.iru.pres", ("இருக்கிறாய்", "இருக்கிறாய்", "இருக்கிறீர்கள்", "இருக்கிறீர்கள்"), "you are"),
        Rule("greet.hello", ("ஏய்", "ஹலோ", "வணக்கம்", "வணக்கம்"), "hello"),
        Rule("greet.thanks", ("தேங்க்ஸ்", "நன்றி", "நன்றி", "மிக்க நன்றி"), "thanks"),
        Rule("greet.sorry", ("சாரி", "சாரி", "மன்னிக்கவும்", "மன்னிக்கவும்"), "sorry"),
    ),
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
    rules=(
        Rule("pron.2sg.nom", ("నువ్వు", "నువ్వు", "మీరు", "మీరు"), "you"),
        Rule("pron.2sg.acc", ("నిన్ను", "నిన్ను", "మిమ్మల్ని", "మిమ్మల్ని"), "you (obj)"),
        Rule("pron.2sg.gen", ("నీ", "నీ", "మీ", "మీ"), "your"),
        Rule("pron.2sg.dat", ("నీకు", "నీకు", "మీకు", "మీకు"), "to you"),
        Rule("v.raa.imp", ("రా", "రా", "రండి", "రండి"), "come!"),
        Rule("v.vellu.imp", ("వెళ్ళు", "వెళ్ళు", "వెళ్ళండి", "వెళ్ళండి"), "go!"),
        Rule("v.cheppu.imp", ("చెప్పు", "చెప్పు", "చెప్పండి", "చెప్పండి"), "tell!"),
        Rule("v.cheyyi.imp", ("చెయ్యి", "చెయ్యి", "చెయ్యండి", "చెయ్యండి"), "do!"),
        Rule("v.choodu.imp", ("చూడు", "చూడు", "చూడండి", "చూడండి"), "look!"),
        Rule("v.kurcho.imp", ("కూర్చో", "కూర్చో", "కూర్చోండి", "కూర్చోండి"), "sit!"),
        Rule("v.vinu.imp", ("విను", "విను", "వినండి", "వినండి"), "listen!"),
        Rule("v.ivvu.imp", ("ఇవ్వు", "ఇవ్వు", "ఇవ్వండి", "ఇవ్వండి"), "give!"),
        Rule("greet.hello", ("ఏయ్", "హలో", "నమస్కారం", "నమస్కారం"), "hello"),
        Rule("greet.thanks", ("థాంక్స్", "ధన్యవాదాలు", "ధన్యవాదాలు", "చాలా ధన్యవాదాలు"), "thanks"),
        Rule("greet.sorry", ("సారీ", "సారీ", "క్షమించండి", "క్షమించండి"), "sorry"),
    ),
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
    rules=(
        Rule("pron.2sg.nom", ("ನೀನು", "ನೀನು", "ನೀವು", "ನೀವು"), "you"),
        Rule("pron.2sg.acc", ("ನಿನ್ನನ್ನು", "ನಿನ್ನನ್ನು", "ನಿಮ್ಮನ್ನು", "ನಿಮ್ಮನ್ನು"), "you (obj)"),
        Rule("pron.2sg.gen", ("ನಿನ್ನ", "ನಿನ್ನ", "ನಿಮ್ಮ", "ನಿಮ್ಮ"), "your"),
        Rule("pron.2sg.dat", ("ನಿನಗೆ", "ನಿನಗೆ", "ನಿಮಗೆ", "ನಿಮಗೆ"), "to you"),
        Rule("v.baa.imp", ("ಬಾ", "ಬಾ", "ಬನ್ನಿ", "ಬನ್ನಿ"), "come!"),
        Rule("v.hogu.imp", ("ಹೋಗು", "ಹೋಗು", "ಹೋಗಿ", "ಹೋಗಿ"), "go!"),
        Rule("v.helu.imp", ("ಹೇಳು", "ಹೇಳು", "ಹೇಳಿ", "ಹೇಳಿ"), "tell!"),
        Rule("v.maadu.imp", ("ಮಾಡು", "ಮಾಡು", "ಮಾಡಿ", "ಮಾಡಿ"), "do!"),
        Rule("v.nodu.imp", ("ನೋಡು", "ನೋಡು", "ನೋಡಿ", "ನೋಡಿ"), "look!"),
        Rule("v.kulitu.imp", ("ಕುಳಿತುಕೋ", "ಕುಳಿತುಕೋ", "ಕುಳಿತುಕೊಳ್ಳಿ", "ಕುಳಿತುಕೊಳ್ಳಿ"), "sit!"),
        Rule("v.kelu.imp", ("ಕೇಳು", "ಕೇಳು", "ಕೇಳಿ", "ಕೇಳಿ"), "listen!"),
        Rule("v.kodu.imp", ("ಕೊಡು", "ಕೊಡು", "ಕೊಡಿ", "ಕೊಡಿ"), "give!"),
        Rule("greet.hello", ("ಏ", "ಹಲೋ", "ನಮಸ್ಕಾರ", "ನಮಸ್ಕಾರ"), "hello"),
        Rule("greet.thanks", ("ಥ್ಯಾಂಕ್ಸ್", "ಧನ್ಯವಾದ", "ಧನ್ಯವಾದಗಳು", "ಅನಂತ ಧನ್ಯವಾದಗಳು"), "thanks"),
        Rule("greet.sorry", ("ಸಾರಿ", "ಸಾರಿ", "ಕ್ಷಮಿಸಿ", "ಕ್ಷಮಿಸಿ"), "sorry"),
    ),
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
    rules=(
        Rule("pron.2sg.nom", ("നീ", "നീ", "നിങ്ങൾ", "താങ്കൾ"), "you"),
        Rule("pron.2sg.gen", ("നിന്റെ", "നിന്റെ", "നിങ്ങളുടെ", "താങ്കളുടെ"), "your"),
        Rule("pron.2sg.dat", ("നിനക്ക്", "നിനക്ക്", "നിങ്ങൾക്ക്", "താങ്കൾക്ക്"), "to you"),
        Rule("v.varu.imp", ("വാ", "വാ", "വരൂ", "വരണം"), "come!"),
        Rule("v.pokuka.imp", ("പോ", "പോ", "പോകൂ", "പോകണം"), "go!"),
        Rule("v.parayuka.imp", ("പറ", "പറ", "പറയൂ", "പറയണം"), "say!"),
        Rule("v.cheyyuka.imp", ("ചെയ്യ്", "ചെയ്യ്", "ചെയ്യൂ", "ചെയ്യണം"), "do!"),
        Rule("v.nokkuka.imp", ("നോക്ക്", "നോക്ക്", "നോക്കൂ", "നോക്കണം"), "look!"),
        Rule("v.irikkuka.imp", ("ഇരി", "ഇരി", "ഇരിക്കൂ", "ഇരിക്കണം"), "sit!"),
        Rule("v.kelkkuka.imp", ("കേൾക്ക്", "കേൾക്ക്", "കേൾക്കൂ", "കേൾക്കണം"), "listen!"),
        Rule("greet.hello", ("എടാ", "ഹലോ", "നമസ്കാരം", "നമസ്കാരം"), "hello"),
        Rule("greet.thanks", ("താങ്ക്സ്", "നന്ദി", "നന്ദി", "വളരെ നന്ദി"), "thanks"),
        Rule("greet.sorry", ("സോറി", "സോറി", "ക്ഷമിക്കണം", "ക്ഷമിക്കണം"), "sorry"),
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
        Rule("greet.thanks", ("Danke", "Danke", "Vielen Dank", "Herzlichen Dank"), "thanks"),
        Rule("greet.sorry", ("Sorry", "Sorry", "Entschuldigung", "Entschuldigen Sie bitte"), "sorry"),
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
        Rule("greet.thanks", ("Merci", "Merci", "Merci beaucoup", "Je vous remercie"), "thanks"),
        Rule("greet.sorry", ("Désolé", "Désolé", "Excusez-moi", "Je vous prie de m'excuser"), "sorry"),
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


def _es_verb_rules() -> Tuple[Rule, ...]:
    imperative_tu = {tu for _, tu, _, _ in _ES_IMPERATIVES}
    out = []
    for stem, tu, usted, gloss in _ES_VERBS:
        # Where the usted indicative collides with some verb's tú imperative,
        # keep the indicative out of clause-initial position.
        collides = usted in imperative_tu
        out.append(
            Rule(f"v.{stem}", (tu, tu, usted, usted), gloss,
                 guard_before=(f"{_ES_3P_SUBJECT}|{_CLAUSE_INITIAL}"
                               if collides else _ES_3P_SUBJECT))
        )
    out += [
        Rule(f"v.{stem}.clitic", (tu, tu, usted, usted), gloss)
        for stem, tu, usted, gloss in _ES_CLITIC
    ]
    out += [
        Rule(f"v.{stem}.imp", (tu, tu, usted, usted), gloss)
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
    rules=_es_verb_rules() + (
        Rule("clause.como_estas", ("¿Cómo estás?", "¿Cómo estás?", "¿Cómo está usted?", "¿Cómo está usted?"), "how are you"),
        Rule("pron.2sg.nom", ("tú", "tú", "usted", "usted"), "you"),
        Rule("pron.2sg.obj", ("te", "te", "le", "le"), "you (obj)"),
        Rule("pron.2sg.prep", ("ti", "ti", "usted", "usted"), "you (prep)"),
        Rule("pron.2sg.com", ("contigo", "contigo", "con usted", "con usted"), "with you"),
        Rule("poss.sg", ("tu", "tu", "su", "su"), "your"),
        Rule("poss.pl", ("tus", "tus", "sus", "sus"), "your (pl)"),
        Rule("greet.hello", ("Ey", "Hola", "Buenos días", "Buenos días"), "hello"),
        Rule("greet.bye", ("Chao", "Adiós", "Hasta luego", "Que tenga un buen día"), "goodbye"),
        # Drop-in at every slot — see the Italian note. "Le agradezco mucho" is
        # a clause and produced "Le agradezco mucho a usted".
        Rule("greet.thanks", ("Gracias", "Gracias", "Muchas gracias", "Muchísimas gracias"),
             "thanks", rewrite_only=True),
        Rule("clause.agradezco", ("te agradezco", "te agradezco",
                                  "le agradezco", "le agradezco"), "I thank you"),
        Rule("greet.sorry", ("Perdón", "Perdón", "Disculpe", "Le pido disculpas"), "sorry"),
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
    ("scusare", "scusa", "scusi", "excuse!"),
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


def _it_verb_rules() -> Tuple[Rule, ...]:
    out = [
        Rule(f"v.{stem}", (tu, tu, lei, lei), gloss,
             cased=True, guard_before=_IT_3P_SUBJECT_FULL)
        for stem, tu, lei, gloss in _IT_VERBS
    ]
    out += [
        Rule(f"v.{stem}.refl", (tu, tu, lei, lei), gloss, cased=True)
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
        Rule("pron.2sg.nom", ("tu", "tu", "Lei", "Lei"), "you", cased=True),
        Rule("pron.2sg.obj", ("ti", "ti", "Le", "Le"), "you (obj)", cased=True),
        # Tonic "te" after a preposition was missing, so "Questo è per te"
        # had only the ambiguous "è" to go on and read as Polite.
        Rule("pron.2sg.tonic", ("te", "te", "Lei", "Lei"), "you (tonic)", cased=True,
             require_before=r"\b(?:per|con|da|a|di|su|tra|fra|come)\s+"),
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
        Rule("greet.thanks", ("Grazie", "Grazie", "Grazie mille", "Grazie infinite"),
             "thanks", rewrite_only=True),
        Rule("clause.ringrazio", ("ti ringrazio", "ti ringrazio",
                                  "La ringrazio", "La ringrazio"), "I thank you"),
        Rule("greet.sorry", ("Scusa", "Scusa", "Mi scusi", "Le chiedo scusa"), "sorry"),
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


def _pt_verb_rules() -> Tuple[Rule, ...]:
    out = [
        Rule(f"v.{stem}", (tu, polite, polite, polite), gloss,
             guard_before=_PT_3P_SUBJECT)
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
    rules=_pt_verb_rules() + (
        Rule("pron.2sg.nom", ("tu", "você", "o senhor", "o senhor"), "you"),
        Rule("pron.2sg.obj", ("te", "lhe", "lhe", "lhe"), "you (obj)"),
        # The tonic pronouns were missing entirely, so "Isto é para ti" had
        # nothing to match on.
        Rule("pron.2sg.tonic", ("ti", "si", "si", "si"), "you (after preposition)"),
        Rule("pron.2sg.com", ("contigo", "consigo", "consigo", "consigo"), "with you"),
        Rule("poss.m", ("teu", "seu", "seu", "seu"), "your (m)"),
        Rule("poss.f", ("tua", "sua", "sua", "sua"), "your (f)"),
        Rule("poss.m.pl", ("teus", "seus", "seus", "seus"), "your (m pl)"),
        Rule("poss.f.pl", ("tuas", "suas", "suas", "suas"), "your (f pl)"),
        Rule("greet.hello", ("Oi", "Olá", "Bom dia", "Bom dia"), "hello"),
        Rule("greet.bye", ("Tchau", "Tchau", "Até logo", "Passe bem"), "goodbye"),
        Rule("greet.thanks", ("Valeu", "Obrigado", "Muito obrigado", "Agradeço muito"), "thanks"),
        # "Desculpa" is the tu form and "Desculpe" the você/o senhor one — it
        # is an imperative, not an invariant interjection, so it moves with the
        # register like any other verb.
        Rule("greet.sorry", ("Desculpa", "Desculpe", "Desculpe", "Peço desculpa"), "sorry"),
    ),
)

# --------------------------------------------------------------------------
# East Asian
# --------------------------------------------------------------------------

JAPANESE = LanguageTable(
    code="ja",
    name="Japanese",
    canon=(1, 1, 2, 3),
    boundary="none",
    please=("", "", "", ""),
    rules=(
        # Ordered so that longer, more specific spines win over bare copulas.
        Rule("polite.arigatou", ("ありがと", "ありがとう", "ありがとうございます", "誠にありがとうございます"), "thanks"),
        Rule("polite.gomen", ("ごめん", "ごめんね", "すみません", "申し訳ございません"), "sorry"),
        Rule("v.suru", ("する", "する", "します", "いたします"), "do"),
        Rule("v.shita", ("した", "した", "しました", "いたしました"), "did"),
        Rule("v.iku", ("行く", "行く", "行きます", "まいります"), "go"),
        Rule("v.kuru", ("来る", "来る", "来ます", "まいります"), "come"),
        Rule("v.miru", ("見る", "見る", "見ます", "拝見します"), "see"),
        Rule("v.taberu", ("食べる", "食べる", "食べます", "いただきます"), "eat"),
        Rule("v.iu", ("言う", "言う", "言います", "申します"), "say"),
        Rule("v.iru", ("いる", "いる", "います", "おります"), "be (animate)"),
        Rule("v.aru", ("ある", "ある", "あります", "ございます"), "be (inanimate)"),
        Rule("v.morau", ("もらう", "もらう", "もらいます", "いただきます"), "receive"),
        Rule("v.shiru", ("知ってる", "知っている", "知っています", "存じております"), "know"),
        Rule("cop.da", ("だ", "だ", "です", "でございます"), "is"),
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
        Rule("clause.can_you", ("can you", "can you", "could you", "could you kindly"), "request"),
        Rule("clause.want_to", ("wanna", "want to", "would like to", "should like to"), "want to"),
        Rule("clause.going_to", ("gonna", "going to", "going to", "intending to"), "going to"),
        Rule("clause.got_to", ("gotta", "have to", "need to", "am required to"), "have to"),
        Rule("clause.let_me_know", ("lmk", "let me know", "please let me know", "kindly inform me"), "inform me"),
        Rule("word.yes", ("yeah", "yes", "yes", "certainly"), "yes"),
        Rule("word.no", ("nope", "no", "no", "unfortunately not"), "no"),
        Rule("word.kids", ("kids", "kids", "children", "children"), "children"),
        Rule("word.lots", ("loads of", "a lot of", "many", "a great deal of"), "many"),
        Rule("word.ask", ("ask", "ask", "request", "request"), "ask"),
        Rule("greet.hello", ("hey", "hi", "hello", "good day"), "hello"),
        Rule("greet.bye", ("bye", "bye", "goodbye", "I bid you goodbye"), "goodbye"),
        Rule("greet.thanks", ("thanks", "thanks", "thank you", "thank you very much"), "thanks"),
        Rule("greet.sorry", ("sorry", "sorry", "I apologise", "I sincerely apologise"), "sorry"),
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
            imperative = paradigm.get("imp")
            collides = bool(imperative) and imperative[1] == tum
            before = _UR_2P_CONTEXT if (tense.startswith("pres") and collides) else ""
            out.append(
                Rule(f"v.{verb}.{tense}", (tu, tum, aap, aap),
                     f"{verb} · {tense}", require_before=before)
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
        Rule("cop.pres", ("ہے", "ہو", "ہیں", "ہیں"), "you are"),
        Rule("cop.past.m", ("تھا", "تھے", "تھے", "تھے"), "you were (m)"),
        Rule("cop.past.f", ("تھی", "تھیں", "تھیں", "تھیں"), "you were (f)"),
        Rule("greet.hello", ("اوے", "ہیلو", "السلام علیکم", "السلام علیکم"), "hello"),
        Rule("greet.thanks", ("تھینکس", "شکریہ", "شکریہ", "بہت شکریہ"), "thanks"),
        Rule("greet.sorry", ("سوری", "سوری", "معاف کیجیے", "معذرت چاہتا ہوں"), "sorry"),
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
        Rule("pron.2sg.gen", ("ତୋର", "ତୁମର", "ଆପଣଙ୍କର", "ଆପଣଙ୍କର"), "your"),
        # The genitive also occurs without the final ର, which is the form in
        # "ଆପଣଙ୍କ ନାଁ କଣ?" — it matched nothing until now.
        Rule("pron.2sg.gen.short", ("ତୋ", "ତୁମ", "ଆପଣଙ୍କ", "ଆପଣଙ୍କ"), "your (short)"),
        Rule("pron.2sg.acc", ("ତୋତେ", "ତୁମକୁ", "ଆପଣଙ୍କୁ", "ଆପଣଙ୍କୁ"), "to you"),
        Rule("cop.pres", ("ଅଛୁ", "ଅଛ", "ଅଛନ୍ତି", "ଅଛନ୍ତି"), "you are"),
        Rule("cop.past", ("ଥିଲୁ", "ଥିଲ", "ଥିଲେ", "ଥିଲେ"), "you were"),
        Rule("greet.hello", ("ଏ", "ହେଲୋ", "ନମସ୍କାର", "ନମସ୍କାର"), "hello"),
        Rule("greet.thanks", ("ଥ୍ୟାଙ୍କ୍ସ", "ଧନ୍ୟବାଦ", "ଧନ୍ୟବାଦ", "ବହୁତ ଧନ୍ୟବାଦ"), "thanks"),
        Rule("greet.sorry", ("ସରି", "ସରି", "କ୍ଷମା କରନ୍ତୁ", "କ୍ଷମା କରନ୍ତୁ"), "sorry"),
    ),
)

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
    rules=(
        Rule("pron.2sg.nom", ("তই", "তুমি", "আপুনি", "আপুনি"), "you"),
        Rule("pron.2sg.gen", ("তোৰ", "তোমাৰ", "আপোনাৰ", "আপোনাৰ"), "your"),
        Rule("pron.2sg.acc", ("তোক", "তোমাক", "আপোনাক", "আপোনাক"), "to you"),
        Rule("cop.pres", ("আছ", "আছা", "আছে", "আছে"), "you are"),
        Rule("v.kara.pres", ("কৰ", "কৰা", "কৰে", "কৰে"), "you do"),
        Rule("v.kara.imp", ("কৰ", "কৰা", "কৰক", "কৰক"), "do!"),
        Rule("v.jaa.imp", ("যা", "যোৱা", "যাওক", "যাওক"), "go!"),
        Rule("v.aha.imp", ("আয়", "আহা", "আহক", "আহক"), "come!"),
        Rule("v.kaba.imp", ("ক", "কোৱা", "কওক", "কওক"), "say!"),
        Rule("v.baha.imp", ("বহ", "বহা", "বহক", "বহক"), "sit!"),
        Rule("greet.hello", ("এই", "হেলো", "নমস্কাৰ", "নমস্কাৰ"), "hello"),
        Rule("greet.thanks", ("থেংকছ", "ধন্যবাদ", "ধন্যবাদ", "বহুত ধন্যবাদ"), "thanks"),
        Rule("greet.sorry", ("চৰি", "চৰি", "ক্ষমা কৰিব", "ক্ষমা কৰিব"), "sorry"),
    ),
)

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
    rules=(
        Rule("pron.2sg.nom", ("तँ", "तिमी", "तपाईं", "हजुर"), "you"),
        Rule("pron.2sg.gen", ("तेरो", "तिम्रो", "तपाईंको", "हजुरको"), "your"),
        Rule("pron.2sg.acc", ("तँलाई", "तिमीलाई", "तपाईंलाई", "हजुरलाई"), "to you"),
        Rule("cop.pres", ("होस्", "हौ", "हुनुहुन्छ", "हुनुहुन्छ"), "you are"),
        Rule("v.garnu.imp", ("गर्", "गर", "गर्नुहोस्", "गर्नुहोस्"), "do!"),
        Rule("v.janu.imp", ("जा", "जाऊ", "जानुहोस्", "जानुहोस्"), "go!"),
        Rule("v.aunu.imp", ("आइज", "आऊ", "आउनुहोस्", "आउनुहोस्"), "come!"),
        Rule("v.bhannu.imp", ("भन्", "भन", "भन्नुहोस्", "भन्नुहोस्"), "say!"),
        Rule("v.basnu.imp", ("बस्", "बस", "बस्नुहोस्", "बस्नुहोस्"), "sit!"),
        Rule("v.hernu.imp", ("हेर्", "हेर", "हेर्नुहोस्", "हेर्नुहोस्"), "look!"),
        Rule("greet.hello", ("ए", "हेलो", "नमस्ते", "नमस्कार"), "hello"),
        Rule("greet.thanks", ("थ्याङ्क्स", "धन्यवाद", "धन्यवाद", "धेरै धन्यवाद"), "thanks"),
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
