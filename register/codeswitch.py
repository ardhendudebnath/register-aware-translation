"""
Code-switching — keep the English people actually say (blueprint 13.2 #8).

Nobody in urban India speaks pure Hindi or pure Bengali. "मैं ऑफिस जा रहा हूँ"
is what people say; "मैं कार्यालय जा रहा हूँ" is what a machine translator
writes, and it sounds like a government circular read aloud. Every MT and ASR
system treats the English in an Indian sentence as noise to normalise away.
This module treats it as something the speaker did on purpose, and does two
separate things with it.

**Measure.** :func:`measure` counts the English words in a sentence written in
an Indian script — Latin-script words ("আমি office যাচ্ছি") and known English
loans written in the native script ("আমি অফিসে যাচ্ছি") — and reports the rate.

It reports a rate and deliberately **no register**. English in an Indian
sentence marks education and formality in some settings and casual urban
speech in others; which one depends on the speaker, the setting and the word.
Nothing in this project can check a mapping from one to the other, so there
isn't one. The rate is exposed as a feature in its own right, and it never
votes in :func:`register.detect`.

**Keep.** :func:`keep_english` puts the everyday English word back where MT
chose a bookish native one, at Close and Casual only — and at every level for
the words the speaker themselves said in English, because preserving a
code-switch is the point and resolving it is the thing everybody else does.
At Polite and Formal nothing else is touched in either direction: this never
*purifies* a sentence, since the English in a formal sentence may be exactly
what the speaker meant.

What is and is not in the word lists
------------------------------------
A word qualifies when the native form is what you would write in a letter and
hardly anybody says aloud (कार्यालय, সপ্তাহান্ত), and the English loan is what
people do say. Everyday native words are left alone however English-y the
speaker: दोस्त, कमरा and Bengali সমস্যা and জন্মদিন are ordinary casual words,
and swapping them would be pushing a style rather than undoing MT's.

Hindi nouns have gender, and a swap that changes it breaks agreement
elsewhere in the sentence (मेरा तनाव → *मेरा टेंशन — टेंशन is feminine). Every
Hindi entry therefore records a gender that native and loan share, and the
pairs that do not share one are listed in :data:`REJECTED` with the reason.

These lists were chosen by hand and have **not** been checked by a native
speaker or against any corpus — there is no native-script code-mixing corpus
for either language to check them against. They are small on purpose, and
they are on the review pages for exactly that reason.

Not covered: romanised Hindi or Bengali written entirely in Latin script
("kal office jaana hai") reads as English to language ID and never reaches
here; languages beyond Hindi and Bengali are measured for Latin-script words
but have no loan list.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from typing import Collection, Dict, List, Optional, Pattern, Tuple

from .boundaries import DELIMITER_CLASS, LEFT, RIGHT
from .engine import Edit
from .levels import CASUAL, CLOSE, coerce_level

__all__ = [
    "Loan",
    "Insertion",
    "CodeSwitch",
    "Mixed",
    "LOANS",
    "REJECTED",
    "measure",
    "keep_english",
    "loan_languages",
]


@dataclass(frozen=True)
class Loan:
    """One English word that everyday speech keeps in English."""

    #: The English headword, lower case: "office".
    english: str
    #: How it is written when said in English, in the native script: "ऑफिस".
    loan: str
    #: The bookish native forms MT tends to choose instead: ("कार्यालय",).
    native: Tuple[str, ...]
    #: Hindi only: the grammatical gender native and loan share, "m" or "f".
    #: Empty for words that do not inflect for it (adjectives, Bengali).
    gender: str = ""
    #: Other spellings of the loan, recognised when measuring.
    also: Tuple[str, ...] = ()
    #: Leave the native form alone when this matches just before it — for
    #: institution names such as केंद्रीय विद्यालय, which are names, not nouns.
    not_after: str = ""
    #: Leave it alone when this matches just after it: বার্তা সংস্থা is a news
    #: agency, not a message organisation.
    not_before: str = ""


# ---------------------------------------------------------------------------
# The word lists
# ---------------------------------------------------------------------------

#: School names are written with the bookish word and must keep it.
_HI_INSTITUTION = r"(?:केंद्रीय|केन्द्रीय|नवोदय|सैनिक|राजकीय|आदर्श|उच्च|माध्यमिक|प्राथमिक)\s+"
_BN_INSTITUTION = r"(?:উচ্চ|মাধ্যমিক|প্রাথমিক|বালিকা|বালক|আদর্শ|সরকারি)\s+"

LOANS: Dict[str, Tuple[Loan, ...]] = {
    "hi": (
        Loan("office", "ऑफिस", ("कार्यालय",), "m", also=("ऑफ़िस", "आफिस")),
        Loan("meeting", "मीटिंग", ("बैठक",), "f"),
        Loan("message", "मैसेज", ("संदेश", "सन्देश"), "m", also=("मेसेज",)),
        Loan("weekend", "वीकेंड", ("सप्ताहांत",), "m", also=("वीकएंड",)),
        Loan("traffic", "ट्रैफिक", ("यातायात",), "m", also=("ट्रैफ़िक",)),
        Loan("problem", "प्रॉब्लम", ("समस्या",), "f", also=("प्रोब्लम",)),
        # अस्त-व्यस्त is "in a mess", not "busy".
        Loan("busy", "बिज़ी", ("व्यस्त",), also=("बिजी",), not_after=r"अस्त[\s-]"),
        Loan("school", "स्कूल", ("विद्यालय",), "m", not_after=_HI_INSTITUTION),
        Loan("college", "कॉलेज", ("महाविद्यालय",), "m", not_after=_HI_INSTITUTION),
        Loan("doctor", "डॉक्टर", ("चिकित्सक",), "m", also=("डाक्टर",)),
        Loan("phone", "फ़ोन", ("दूरभाष",), "m", also=("फोन",)),
        Loan("train", "ट्रेन", ("रेलगाड़ी", "रेलगाडी"), "f"),
        Loan("computer", "कंप्यूटर", ("संगणक",), "m", also=("कम्प्यूटर",)),
    ),
    "bn": (
        Loan("office", "অফিস", ("কার্যালয়",)),
        # Not সভা: বিধান সভা and লোক সভা are parliaments, and are often
        # written as two words.
        Loan("meeting", "মিটিং", ("বৈঠক",)),
        Loan("message", "মেসেজ", ("বার্তা",), not_before=r"\s+সংস্থা"),
        Loan("weekend", "উইকেন্ড", ("সপ্তাহান্ত",), also=("উইকএন্ড",)),
        Loan("school", "স্কুল", ("বিদ্যালয়",), not_after=_BN_INSTITUTION),
        Loan("college", "কলেজ", ("মহাবিদ্যালয়",), not_after=_BN_INSTITUTION),
        Loan("doctor", "ডাক্তার", ("চিকিৎসক",)),
        Loan("phone", "ফোন", ("দূরভাষ",)),
    ),
}

#: Candidates considered and left out, with the reason. Kept as data so the
#: reason travels with the decision, and so a test can stop them creeping back.
REJECTED: Dict[str, Dict[str, str]] = {
    "hi": {
        "tension": "तनाव is masculine and टेंशन feminine: मेरा तनाव would become *मेरा टेंशन",
        "plan": "योजना is feminine and प्लान masculine; योजना is also a government scheme",
        "exam": "परीक्षा is feminine and एग्जाम usually masculine",
        "university": "विश्वविद्यालय is masculine and यूनिवर्सिटी feminine",
        "film": "चलचित्र is masculine and फ़िल्म feminine",
        "tv": "दूरदर्शन is also the name of the national broadcaster",
        "result": "परिणाम also means consequence, which रिजल्ट does not",
        "birthday": "जन्मदिन is an everyday word, not a bookish one",
        "please": "कृपया is a politeness marker the register tables already own",
        "sorry": "an apology is register-bearing and belongs to the register tables",
        "thanks": "धन्यवाद is a politeness marker the register tables already own",
    },
    "bn": {
        "problem": "সমস্যা is an everyday casual word, not a bookish one",
        "birthday": "জন্মদিন is an everyday casual word, not a bookish one",
        "busy": "ব্যস্ত is an everyday casual word, not a bookish one",
        "meeting (সভা)": "বিধান সভা and লোক সভা are parliaments, often written as two words",
        "please": "দয়া করে is a politeness marker the register tables already own",
        "thanks": "ধন্যবাদ is a politeness marker the register tables already own",
    },
}


def loan_languages() -> Tuple[str, ...]:
    """Languages with a loan list. Others are measured for Latin script only."""
    return tuple(sorted(LOANS))


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Insertion:
    """One English word found in a sentence."""

    #: As written: "office", "অফিসে".
    surface: str
    #: The English headword: "office".
    english: str
    #: "latin" for a word in Latin script, "loan" for a known English word
    #: written in the native script.
    kind: str
    start: int

    def as_dict(self) -> dict:
        return {
            "surface": self.surface,
            "english": self.english,
            "kind": self.kind,
            "start": self.start,
        }


@dataclass(frozen=True)
class CodeSwitch:
    """
    How much English a sentence mixes in.

    Deliberately carries no register. See the module docstring for why.
    """

    language: str
    #: Word tokens in the sentence, excluding numbers and punctuation.
    words: int
    insertions: Tuple[Insertion, ...] = ()

    @property
    def rate(self) -> float:
        return len(self.insertions) / self.words if self.words else 0.0

    @property
    def english_words(self) -> Tuple[str, ...]:
        """The English headwords the speaker used, in order, without repeats."""
        seen: Dict[str, None] = {}
        for insertion in self.insertions:
            seen.setdefault(insertion.english, None)
        return tuple(seen)

    def as_dict(self) -> dict:
        return {
            "language": self.language,
            "words": self.words,
            "english": len(self.insertions),
            "rate": round(self.rate, 3),
            "insertions": [i.as_dict() for i in self.insertions],
            "english_words": list(self.english_words),
        }


@dataclass(frozen=True)
class Mixed:
    """The result of :func:`keep_english`: the text, and every swap made."""

    text: str
    edits: Tuple[Edit, ...] = ()


# ---------------------------------------------------------------------------
# Measuring
# ---------------------------------------------------------------------------

#: A word, with hyphenated parts kept together: "meeting-এর" is one English
#: word with a Bengali ending, not two words.
_TOKEN_RE = re.compile(f"[^{DELIMITER_CLASS}]+(?:-[^{DELIMITER_CLASS}]+)*")

#: Languages written in Latin script. English in them is not a code-switch
#: this module can see, so measuring them would only produce noise.
_LATIN_SCRIPT = frozenset({"en", "de", "fr", "es", "it", "pt"})


def _is_latin_letter(ch: str) -> bool:
    code = ord(ch)
    return code < 0x0250 or 0x1E00 <= code <= 0x1EFF


def measure(text: str, language: str) -> Optional[CodeSwitch]:
    """
    Count the English words in ``text``, a sentence in ``language``.

    Returns None when there is nothing meaningful to measure: empty text, a
    Latin-script language, or a sentence with no native-script words at all
    (which is romanised text, or English, and not a code-switch this can
    see).
    """
    language = _code(language)
    if not isinstance(text, str) or not text.strip() or language in _LATIN_SCRIPT:
        return None

    words = 0
    native_words = 0
    found: List[Insertion] = []
    loans = _loan_lookup(language)

    for match in _TOKEN_RE.finditer(text):
        token = match.group(0)
        letters = [ch for ch in token if ch.isalpha()]
        if not letters:
            continue  # a number, or stray marks
        words += 1
        latin = sum(1 for ch in letters if _is_latin_letter(ch))
        if latin * 2 >= len(letters):
            found.append(Insertion(token, _headword(token), "latin", match.start()))
            continue
        native_words += 1
        english = _match_loan(token, language, loans)
        if english:
            found.append(Insertion(token, english, "loan", match.start()))

    if not native_words:
        return None
    return CodeSwitch(language=language, words=words, insertions=tuple(found))


_LATIN_RUN = re.compile(r"[A-Za-zÀ-ɏḀ-ỿ'’]+")


def _headword(token: str) -> str:
    """
    The English word in a Latin-script token, lower-cased, with an English
    plural taken off when that finds a loan. A native case ending typed straight
    onto the English ("officeএ") is dropped.
    """
    run = _LATIN_RUN.match(token)
    word = (run.group(0) if run else token).lower().strip("'’")
    known = {loan.english for loans in LOANS.values() for loan in loans}
    if word in known:
        return word
    for suffix in ("es", "s"):
        if word.endswith(suffix) and word[: -len(suffix)] in known:
            return word[: -len(suffix)]
    return word


def _loan_lookup(language: str) -> Dict[str, str]:
    """Every spelling of every loan in ``language``, to its English headword."""
    out: Dict[str, str] = {}
    for loan in LOANS.get(language, ()):
        for spelling in (loan.loan, *loan.also):
            out[_nfc(spelling)] = loan.english
    return out


def _match_loan(token: str, language: str, loans: Dict[str, str]) -> str:
    """The headword if ``token`` is a known loan, bare or with a case ending."""
    token = _nfc(token)
    if token in loans:
        return loans[token]
    for spelling, english in loans.items():
        if token.startswith(spelling):
            rest = token[len(spelling):]
            if rest in _all_endings(language):
                return english
    return ""


# ---------------------------------------------------------------------------
# Keeping
# ---------------------------------------------------------------------------


def keep_english(
    text: str,
    language: str,
    level,
    *,
    keep: Collection[str] = (),
) -> Mixed:
    """
    Put the everyday English word back where the sentence has a bookish one.

    At Close and Casual every word in the language's list is swapped. At
    Polite and Formal only the words in ``keep`` are — the English headwords
    the speaker used themselves (``CodeSwitch.english_words``), because what
    somebody chose to say in English should survive translation at any level.
    Nothing is ever swapped the other way.
    """
    language = _code(language)
    entries = LOANS.get(language, ())
    if not isinstance(text, str) or not text or not entries:
        return Mixed(text if isinstance(text, str) else "")

    level = coerce_level(level)
    casual = level in (CLOSE, CASUAL)
    wanted = {word.lower() for word in keep}
    active = [loan for loan in entries if casual or loan.english in wanted]
    if not active:
        return Mixed(text)

    # Every swap is found against the original string, then applied right to
    # left, so one replacement never shifts or feeds another.
    swaps: List[Tuple[int, int, str, Loan]] = []
    for loan in active:
        for compiled in _patterns(language, loan):
            for m in compiled.finditer(text):
                if any(m.start() < end and start < m.end() for start, end, _, _ in swaps):
                    continue
                replacement = _replacement(language, loan, compiled.native, m)
                swaps.append((m.start(), m.end(), replacement, loan))

    if not swaps:
        return Mixed(text)

    swaps.sort(key=lambda s: s[0])
    edits = tuple(
        Edit(
            rule=f"english.{loan.english}",
            gloss=(
                "everyday speech says this in English"
                if loan.english not in wanted
                else "you said this in English, so it stays in English"
            ),
            before=text[start:end],
            after=replacement,
            start=start,
            from_levels=(),
            to_level=level,
        )
        for start, end, replacement, loan in swaps
    )
    out = text
    for start, end, replacement, _ in reversed(swaps):
        out = out[:start] + replacement + out[end:]
    return Mixed(out, edits)


# ---------------------------------------------------------------------------
# Inflection: carrying a case ending from the native word onto the loan
# ---------------------------------------------------------------------------
#
# Hindi writes its postpositions as separate words, so the only ending that
# attaches is the oblique plural ों (कार्यालयों में → ऑफिसों में), and only
# between two consonant-final nouns of the same gender. Vowel-final plurals
# (समस्याओं) are left alone rather than guessed at.
#
# Bengali attaches its case endings, and the locative and genitive take a
# different shape after a consonant, a vowel and the anusvara ং:
#
#               consonant      vowel         ং
#   locative    অফিসে          বার্তায়/-তে     মিটিংয়ে
#   genitive    অফিসের         বার্তার        মিটিংয়ের
#
# so বৈঠকের becomes মিটিংয়ের, not *মিটিংের. Classifier and object endings
# (-টা, -গুলো, -কে) attach the same way to everything, and any ending can take
# the emphatic ও or ই after it.

_HI_OBLIQUE_PLURAL = "ों"  # ों

_BN_LOC = {"C": ("ে",), "V": ("য়", "তে"), "N": ("য়ে",)}
_BN_GEN = {"C": ("ের",), "V": ("র",), "N": ("য়ের",)}
_BN_SHARED = (
    "কে", "টা", "টি", "গুলো", "গুলি",
    "টার", "টায়", "টাতে", "টাকে", "টির", "টিতে", "টিকে",
    "গুলোর", "গুলোতে", "গুলোকে", "গুলির", "গুলিতে", "গুলিকে",
)
_BN_EMPHATIC = ("ও", "ই")

_BN_VOWEL_SIGNS = frozenset("ািীুূৃেৈোৌ")
_BN_VOWELS = frozenset("অআইঈউঊঋএঐওঔ")
_HI_VOWEL_SIGNS = frozenset("ािीुूृॅेैॉोौ")


def _bn_class(word: str) -> str:
    last = word[-1]
    if last == "ং":
        return "N"
    if last in _BN_VOWEL_SIGNS or last in _BN_VOWELS:
        return "V"
    return "C"


def _hi_consonant_final(word: str) -> bool:
    return word[-1] not in _HI_VOWEL_SIGNS and word[-1] not in "ंँः्"


def _bn_endings(cls: str) -> Tuple[str, ...]:
    return tuple(_nfc(e) for e in (*_BN_LOC[cls], *_BN_GEN[cls], *_BN_SHARED))


@lru_cache(maxsize=None)
def _all_endings(language: str) -> frozenset:
    """Every ending a loan may carry when measuring, emphatics included."""
    if language == "hi":
        return frozenset({_HI_OBLIQUE_PLURAL})
    if language == "bn":
        base = {e for cls in ("C", "V", "N") for e in _bn_endings(cls)}
        withemph = {b + _nfc(x) for b in base for x in _BN_EMPHATIC}
        return frozenset(base | withemph | {_nfc(x) for x in _BN_EMPHATIC})
    return frozenset()


@dataclass(frozen=True)
class _NativePattern:
    """A compiled pattern for one native form of a loan, with its guards."""

    native: str
    pattern: Pattern
    #: Checked against the text before a match. Separate from ``pattern``
    #: because Python lookbehinds must be fixed width and the institution
    #: guards (केंद्रीय, नवोदय…) are not.
    not_after: Optional[Pattern] = None

    def finditer(self, text: str):
        for m in self.pattern.finditer(text):
            if self.not_after is not None and self.not_after.search(text, 0, m.start()):
                continue
            yield m


@lru_cache(maxsize=None)
def _patterns(language: str, loan: Loan) -> Tuple[_NativePattern, ...]:
    """One pattern per native form, with its possible endings as groups."""
    out = []
    for native in loan.native:
        native = _nfc(native)
        if language == "hi":
            ending = ""
            if loan.gender and _hi_consonant_final(native) and _hi_consonant_final(_nfc(loan.loan)):
                ending = f"(?P<case>{_flex(_HI_OBLIQUE_PLURAL)})?"
        elif language == "bn":
            endings = sorted(_bn_endings(_bn_class(native)), key=len, reverse=True)
            ending = (
                "(?P<case>" + "|".join(_flex(e) for e in endings) + ")?"
                "(?P<emph>" + "|".join(_flex(e) for e in _BN_EMPHATIC) + ")?"
            )
        else:
            ending = ""
        # A hyphen on either side means the word is half of a compound
        # (अस्त-व्यस्त, समस्या-समाधान), and compounds are left whole.
        not_before = f"(?!{loan.not_before})" if loan.not_before else ""
        body = f"{LEFT}(?<!-){_flex(native)}{ending}{RIGHT}(?!-){not_before}"
        out.append(
            _NativePattern(
                native=native,
                pattern=re.compile(body),
                not_after=re.compile(f"(?:{loan.not_after})$") if loan.not_after else None,
            )
        )
    return tuple(out)


def _replacement(language: str, loan: Loan, native: str, m: "re.Match") -> str:
    """The loan, carrying whatever ending the native word had."""
    word = _nfc(loan.loan)
    groups = m.groupdict()
    case = _nfc(groups.get("case") or "")
    emph = _nfc(groups.get("emph") or "")
    if language == "bn" and case:
        # Re-shape a locative or genitive for the loan's own final sound.
        native_cls, loan_cls = _bn_class(native), _bn_class(word)
        if case in {_nfc(e) for e in _BN_LOC[native_cls]}:
            # After a vowel -তে reads more naturally on a loan than -য়.
            case = _nfc(_BN_LOC[loan_cls][-1])
        elif case in {_nfc(e) for e in _BN_GEN[native_cls]}:
            case = _nfc(_BN_GEN[loan_cls][0])
    return word + case + emph


# ---------------------------------------------------------------------------
# Spelling
# ---------------------------------------------------------------------------

#: Letters with a nukta have two encodings: one code point, or the base letter
#: plus the nukta. Unicode normalisation (NFC) picks the two-code-point form,
#: and so do the register tables, but text arriving from MT or a keyboard may
#: use either, so patterns accept both.
_NUKTA_LETTERS = {
    "ড়": "ড়", "ঢ়": "ঢ়", "য়": "য়",
    "क़": "क़", "ख़": "ख़", "ग़": "ग़",
    "ज़": "ज़", "ड़": "ड़", "ढ़": "ढ़",
    "फ़": "फ़", "य़": "य़",
}
_DECOMPOSED_TO_SINGLE = {pair: single for single, pair in _NUKTA_LETTERS.items()}


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def _flex(text: str) -> str:
    """A regex for ``text`` that accepts either encoding of a nukta letter."""
    text = _nfc(text)
    out: List[str] = []
    i = 0
    while i < len(text):
        pair = text[i:i + 2]
        if pair in _DECOMPOSED_TO_SINGLE:
            out.append(f"(?:{re.escape(pair)}|{_DECOMPOSED_TO_SINGLE[pair]})")
            i += 2
        else:
            out.append(re.escape(text[i]))
            i += 1
    return "".join(out)


def _code(language) -> str:
    if not isinstance(language, str):
        return ""
    return language.strip().lower().replace("_", "-").split("-")[0]
