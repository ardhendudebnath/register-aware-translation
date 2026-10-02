"""
Dravidian: Tamil, Telugu, Kannada, Malayalam.

Two pronoun levels each, and verb endings regular enough that one
builder — ``_dravidian_verb_rules`` — serves three of the four.
"""

from __future__ import annotations

from typing import Callable, Dict, Optional, Tuple

from .model import LanguageTable, Rule


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

