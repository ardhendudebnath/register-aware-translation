"""
Indo-Aryan: Bengali, Hindi, Marathi, Gujarati, Punjabi, Urdu, Odia,
Assamese, Nepali.

They share a three-way pronoun system and the same two traps: a bare
verb stem that is also the familiar imperative, and a third-person
form that doubles as the polite second person. The guards against both
live beside the tables that need them.
"""

from __future__ import annotations

from typing import Dict, Tuple

from ..boundaries import LEFT, RIGHT
from .model import LanguageTable, Rule


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

#: A vocative is set off by a comma, and nothing else distinguishes it.
#:
#: भाई is "brother" and it is also how you hail a stranger, and the rule that
#: raises the second to साहब was rewriting the first: "मेरा भाई डॉक्टर है" (my
#: brother is a doctor) came out as "मेरा साहब डॉक्टर है", which is not a
#: politeness change but a different sentence. Requiring an adjacent comma
#: gives up the comma-less vocative — "भाई ज़रा सुनो" is left alone — and that
#: is the right way round to be wrong: failing to add an honorific leaves the
#: sentence intact, while adding one to a kinship term destroys it.
_VOCATIVE_COMMA = r"[,،]\s*|\s*[,،]"

#: A bare stem before an auxiliary is not an imperative: Hindi builds its
#: progressives, modals and compound verbs on the same form the तू imperative
#: takes, so "कर सकता है" and "चल रही है" look like commands to a matcher that
#: stops at the word.
#: The same collision in the imperative. "सो जाओ" is one command — go to
#: sleep — built from the stem सो and the light verb जाओ, and only the light
#: verb carries the politeness. Treating both halves as commands produced
#: "सोइए जाइए", which is not Hindi; the correct Polite form is "सो जाइए".
#: Listed in every level's imperative, because the compound has to stay
#: unbroken whichever direction it is being moved in.
_HI_LIGHT_VERB_AFTER = (
    r"\s+(?:जा|जाओ|जाइए"                        # go: सो जाओ, बैठ जाओ
    r"|ले|लो|लीजिए"                             # take: खा लो, कर लो
    r"|दे|दो|दीजिए"                             # give: कर दो, रख दो
    r"|आ|आओ|आइए"                                # come: ले आओ
    r"|डाल|डालो|डालिए|रख|रखो|रखिए)"             # put, keep
    rf"{RIGHT}"
)

_HI_AUX_AFTER = (
    r"\s+(?:रहा|रही|रहे"                        # progressive
    r"|सकता|सकती|सकते|सको|सके|सकें"             # modal: can
    r"|पाता|पाती|पाते|चुका|चुकी|चुके"           # manage to, have already
    r"|गया|गयी|गई|गये|गए|लिया|ली|लिए|दिया|दी|दिए)"  # compound verbs
    rf"|{_HI_LIGHT_VERB_AFTER}"
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
        Rule("voc.sir", ("", "भाई", "साहब", "महोदय"), "sir",
             require_adjacent=_VOCATIVE_COMMA),
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

#: A bare stem before an auxiliary is not a command.
#:
#: Punjabi builds its progressives, modals and compound verbs on exactly the
#: form the ਤੂੰ imperative takes — the same collision Hindi and Urdu were
#: guarded against and this table never was. Unguarded it was worse here than
#: a clumsy rewrite: "ਮੈਂ ਜਾ ਰਿਹਾ ਹਾਂ" (I am going) became "ਮੈਂ ਜਾਓ ਰਿਹਾ ਹਾਂ"
#: and read as Casual at full confidence — a sentence about the speaker,
#: addressed to nobody, reported as evidence of how the listener is being
#: spoken to. In Auto mode that is a confident wrong mirror.
_PA_AUX_AFTER = (
    r"\s+(?:ਰਿਹਾ|ਰਹੀ|ਰਹੇ"                       # progressive
    r"|ਸਕਦਾ|ਸਕਦੀ|ਸਕਦੇ|ਸਕੋ|ਸਕੇ"                  # modal: can
    r"|ਚੁੱਕਾ|ਚੁੱਕੀ|ਚੁੱਕੇ"                        # have already
    r"|ਗਿਆ|ਗਈ|ਗਏ|ਲਿਆ|ਲਈ|ਲਏ|ਦਿੱਤਾ|ਦਿੱਤੀ|ਦਿੱਤੇ"    # compound perfectives
    # …and the light verbs a compound imperative is built on: "ਬੈਠ ਜਾ" is one
    # command, and only ਜਾ carries the politeness.
    r"|ਜਾ|ਜਾਓ|ਲੈ|ਲਵੋ|ਦੇ|ਦਿਓ|ਆ|ਆਓ|ਰੱਖ|ਰੱਖੋ)"
    rf"{RIGHT}"
)


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
                Rule(f"v.{verb}.{tense}", (tu, tu, tusi, tusi), f"{verb} · {tense}",
                     guard_after=_PA_AUX_AFTER if tense == "imp" else "")
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
#: Urdu builds compound verbs the same way Hindi does, on the same bare stem:
#: "سو جاؤ" is one command and only جاؤ carries the politeness.
_UR_LIGHT_VERB_AFTER = (
    r"\s+(?:جا|جاؤ|جائیے"                       # go
    r"|لے|لو|لیجیے"                             # take
    r"|دے|دو|دیجیے"                             # give
    r"|آ|آؤ|آئیے"                               # come
    r"|ڈال|ڈالو|ڈالیے|رکھ|رکھو|رکھیے)"          # put, keep
    rf"{RIGHT}"
)

_UR_AUX_AFTER = (
    r"\s+(?:رہا|رہی|رہے"                        # progressive
    r"|سکتا|سکتی|سکتے|سکو|سکے|سکیں"             # modal: can
    r"|پاتا|پاتی|پاتے|چکا|چکی|چکے"              # manage to, have already
    r"|گیا|گئی|گئے|لیا|لی|لیے|دیا|دی|دیے)"      # compound verbs
    rf"|{_UR_LIGHT_VERB_AFTER}"
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
        Rule("voc.sir", ("", "بھائی", "صاحب", "جناب"), "sir",
             require_adjacent=_VOCATIVE_COMMA),
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

