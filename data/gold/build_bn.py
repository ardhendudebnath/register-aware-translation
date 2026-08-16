"""
Bengali register gold set — source data and builder.

    python data/gold/build_bn.py          # writes data/gold/bn.jsonl
    python data/gold/build_bn.py --stats  # coverage report only

STATUS: MACHINE-DRAFTED, NOT YET VERIFIED
========================================
Every row is written out with ``"status": "draft"``. This is **not** a gold set
until a native speaker has been through it, and the evaluation harness refuses
to call it one. What it is: a scaffold that converts the job from *writing* 500
Bengali sentences into *checking* 500 Bengali sentences, which is perhaps five
times faster and much less error-prone.

Review it with::

    python -m evaluation.review bn

Why triads
----------
Most rows come in contrastive sets of three — the same sentence at তুই, তুমি and
আপনি — because that is the shape a register benchmark actually needs. CoCoA-MT
is contrastive for the same reason: it is far more informative to know that a
system turns *তুমি কি করছ?* into *আপনি কি করছেন?* than that it classified one
sentence correctly.

Triads also give each row an ``expected`` map of the exact surface form at every
level, which lets the harness grade the *rewriter* against a gold rendering
rather than round-tripping through its own detector. A rewrite that produces
something the detector happens to like is not the same as a rewrite that
produces what a Bengali speaker would actually say.

Coverage aims
-------------
* the pronoun paradigm — nominative, genitive, accusative
* eight tense/aspect constructions, not just the present
* imperatives, which carry register most sharply in Bengali
* the domains a traveller actually needs: transit, shopping, medical, emergency
* social contexts, including the case a one-dimensional dial gets wrong — the
  family elder you address as তুমি, who is high power *and* high solidarity
* negatives: sentences with no register marker at all, which must detect as None
* ambiguities the engine has to resolve, like বলো as statement vs imperative

Bengali levels
--------------
    0 Close   তুই   younger sibling, childhood friend, a child
    1 Casual  তুমি  friend, spouse, younger colleague, an elder in the family
    2 Polite  আপনি  stranger, elder outside the family, customer, official
    3 Formal  আপনি  + দয়া করে / অনুগ্রহ করে and Sanskritised vocabulary

Level 3 shares আপনি with level 2; what separates them is lexical, so formal rows
are listed separately rather than as a fourth column.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

HERE = Path(__file__).resolve().parent
OUT = HERE / "bn.jsonl"

# (close, casual, polite, domain, context, construction)
Triad = Tuple[str, str, str, str, str, str]

# --------------------------------------------------------------------------
# 1. Pronoun paradigm
# --------------------------------------------------------------------------

PRONOUNS: List[Triad] = [
    ("তুই কেমন আছিস?", "তুমি কেমন আছ?", "আপনি কেমন আছেন?",
     "greeting", "friend", "pron.nom + cop.pres"),
    ("তোর নাম কী?", "তোমার নাম কী?", "আপনার নাম কী?",
     "greeting", "stranger", "pron.gen"),
    ("তোকে দেখে ভালো লাগল।", "তোমাকে দেখে ভালো লাগল।", "আপনাকে দেখে ভালো লাগল।",
     "greeting", "acquaintance", "pron.acc"),
    ("তোর বাড়ি কোথায়?", "তোমার বাড়ি কোথায়?", "আপনার বাড়ি কোথায়?",
     "smalltalk", "stranger", "pron.gen"),
    ("তোকে একটা কথা বলব।", "তোমাকে একটা কথা বলব।", "আপনাকে একটা কথা বলব।",
     "smalltalk", "colleague", "pron.acc"),
    ("এটা তোর জন্য।", "এটা তোমার জন্য।", "এটা আপনার জন্য।",
     "domestic", "family", "pron.gen + postposition"),
    ("তোর সঙ্গে যাব।", "তোমার সঙ্গে যাব।", "আপনার সঙ্গে যাব।",
     "travel", "companion", "pron.gen + postposition"),
    ("তোর কাছে সময় আছে?", "তোমার কাছে সময় আছে?", "আপনার কাছে সময় আছে?",
     "smalltalk", "colleague", "pron.gen + existential"),
    ("আমি তোকে চিনি।", "আমি তোমাকে চিনি।", "আমি আপনাকে চিনি।",
     "smalltalk", "acquaintance", "pron.acc"),
    ("তোর সাহায্য দরকার।", "তোমার সাহায্য দরকার।", "আপনার সাহায্য দরকার।",
     "request", "colleague", "pron.gen"),
]

# --------------------------------------------------------------------------
# 2. Tense and aspect — the register marking runs through the whole paradigm,
#    not just the present, and a table that only covers the present will look
#    fine in a demo and fail on real speech.
# --------------------------------------------------------------------------

TENSES: List[Triad] = [
    # present simple
    ("তুই কী করিস?", "তুমি কী করো?", "আপনি কী করেন?",
     "smalltalk", "stranger", "v.pres.simple"),
    ("তুই কোথায় থাকিস?", "তুমি কোথায় থাকো?", "আপনি কোথায় থাকেন?",
     "smalltalk", "stranger", "v.pres.simple"),
    ("তুই বাংলা বলিস?", "তুমি বাংলা বলো?", "আপনি বাংলা বলেন?",
     "smalltalk", "stranger", "v.pres.simple"),
    # present continuous
    ("তুই কী করছিস?", "তুমি কী করছ?", "আপনি কী করছেন?",
     "smalltalk", "friend", "v.pres.cont"),
    ("তুই কোথায় যাচ্ছিস?", "তুমি কোথায় যাচ্ছ?", "আপনি কোথায় যাচ্ছেন?",
     "travel", "acquaintance", "v.pres.cont"),
    ("তুই কী খাচ্ছিস?", "তুমি কী খাচ্ছ?", "আপনি কী খাচ্ছেন?",
     "food", "friend", "v.pres.cont"),
    # present perfect
    ("তুই খেয়েছিস?", "তুমি খেয়েছ?", "আপনি খেয়েছেন?",
     "food", "family", "v.pres.perf"),
    ("তুই কাজটা করেছিস?", "তুমি কাজটা করেছ?", "আপনি কাজটা করেছেন?",
     "workplace", "colleague", "v.pres.perf"),
    ("তুই কি চিঠিটা পড়েছিস?", "তুমি কি চিঠিটা পড়েছ?", "আপনি কি চিঠিটা পড়েছেন?",
     "workplace", "colleague", "v.pres.perf"),
    # simple past
    ("তুই কখন এলি?", "তুমি কখন এলে?", "আপনি কখন এলেন?",
     "greeting", "guest", "v.past.simple"),
    ("তুই কী বললি?", "তুমি কী বললে?", "আপনি কী বললেন?",
     "smalltalk", "friend", "v.past.simple"),
    ("তুই ওখানে গেলি কেন?", "তুমি ওখানে গেলে কেন?", "আপনি ওখানে গেলেন কেন?",
     "smalltalk", "friend", "v.past.simple"),
    # past continuous
    ("তুই কী করছিলি?", "তুমি কী করছিলে?", "আপনি কী করছিলেন?",
     "smalltalk", "friend", "v.past.cont"),
    ("তুই কোথায় ছিলি?", "তুমি কোথায় ছিলে?", "আপনি কোথায় ছিলেন?",
     "smalltalk", "family", "v.past.cont"),
    # habitual past
    ("তুই আগে এখানে আসতিস।", "তুমি আগে এখানে আসতে।", "আপনি আগে এখানে আসতেন।",
     "smalltalk", "acquaintance", "v.past.habitual"),
    # future
    ("তুই কখন আসবি?", "তুমি কখন আসবে?", "আপনি কখন আসবেন?",
     "planning", "colleague", "v.future"),
    ("তুই কী খাবি?", "তুমি কী খাবে?", "আপনি কী খাবেন?",
     "food", "guest", "v.future"),
    ("তুই কি আমাকে সাহায্য করবি?", "তুমি কি আমাকে সাহায্য করবে?",
     "আপনি কি আমাকে সাহায্য করবেন?",
     "request", "stranger", "v.future"),
    ("তুই কবে ফিরবি?", "তুমি কবে ফিরবে?", "আপনি কবে ফিরবেন?",
     "planning", "family", "v.future"),
]

# --------------------------------------------------------------------------
# 3. Imperatives — where Bengali register is sharpest, and where getting it
#    wrong is most audible.
# --------------------------------------------------------------------------

IMPERATIVES: List[Triad] = [
    ("এখানে আয়।", "এখানে এসো।", "এখানে আসুন।", "everyday", "guest", "v.imp.asa"),
    ("এখানে বোস।", "এখানে বসো।", "এখানে বসুন।", "everyday", "guest", "v.imp.bosa"),
    ("একটু শোন।", "একটু শোনো।", "একটু শুনুন।", "everyday", "stranger", "v.imp.suna"),
    ("এটা দেখ।", "এটা দেখো।", "এটা দেখুন।", "everyday", "colleague", "v.imp.dekha"),
    ("আমাকে বল।", "আমাকে বলো।", "আমাকে বলুন।", "everyday", "colleague", "v.imp.bola"),
    ("দরজাটা খোল।", "দরজাটা খোলো।", "দরজাটা খুলুন।", "everyday", "family", "v.imp.khola"),
    ("একটু অপেক্ষা কর।", "একটু অপেক্ষা করো।", "একটু অপেক্ষা করুন।",
     "everyday", "stranger", "v.imp.kora"),
    ("আমাকে একটা দে।", "আমাকে একটা দাও।", "আমাকে একটা দিন।",
     "shopping", "shopkeeper", "v.imp.deoa"),
    ("এটা নে।", "এটা নাও।", "এটা নিন।", "shopping", "shopkeeper", "v.imp.neoa"),
    ("তাড়াতাড়ি চল।", "তাড়াতাড়ি চলো।", "তাড়াতাড়ি চলুন।",
     "travel", "companion", "v.imp.chala"),
    ("ভেতরে আয়।", "ভেতরে এসো।", "ভেতরে আসুন।", "everyday", "guest", "v.imp.asa"),
    ("খেয়ে নে।", "খেয়ে নাও।", "খেয়ে নিন।", "food", "guest", "v.imp.neoa"),
    ("আমাকে ফোন কর।", "আমাকে ফোন করো।", "আমাকে ফোন করুন।",
     "phone", "colleague", "v.imp.kora"),
    ("এখানে লেখ।", "এখানে লেখো।", "এখানে লিখুন।", "admin", "official", "v.imp.lekha"),
    ("একটু সরে যা।", "একটু সরে যাও।", "একটু সরে যান।",
     "transit", "stranger", "v.imp.jaoa"),
]

# --------------------------------------------------------------------------
# 4. Modals — পারা (can) is the most common request frame in Bengali, and the
#    one machine translation most often gets stuck at the polite form.
# --------------------------------------------------------------------------

MODALS: List[Triad] = [
    ("তুই কি আমাকে সাহায্য করতে পারিস?", "তুমি কি আমাকে সাহায্য করতে পারো?",
     "আপনি কি আমাকে সাহায্য করতে পারেন?",
     "request", "stranger", "v.para"),
    ("তুই কি একটু অপেক্ষা করতে পারিস?", "তুমি কি একটু অপেক্ষা করতে পারো?",
     "আপনি কি একটু অপেক্ষা করতে পারেন?",
     "request", "stranger", "v.para"),
    ("তুই কি আমাকে তোর বই দিতে পারিস?", "তুমি কি আমাকে তোমার বই দিতে পারো?",
     "আপনি কি আমাকে আপনার বই দিতে পারেন?",
     "request", "colleague", "v.para + pron.gen"),
    ("তুই কী চাস?", "তুমি কী চাও?", "আপনি কী চান?",
     "shopping", "shopkeeper", "v.chaoa"),
    ("তুই কি জানিস?", "তুমি কি জানো?", "আপনি কি জানেন?",
     "smalltalk", "stranger", "v.jana"),
    ("তুই কি বুঝিস?", "তুমি কি বোঝো?", "আপনি কি বোঝেন?",
     "smalltalk", "colleague", "v.bojha"),
]

# --------------------------------------------------------------------------
# 5. Domains a traveller actually hits
# --------------------------------------------------------------------------

TRANSIT: List[Triad] = [
    ("তুই স্টেশনে যাস?", "তুমি স্টেশনে যাও?", "আপনি স্টেশনে যান?",
     "transit", "driver", "v.pres.simple"),
    ("তোর কাছে টিকিট আছে?", "তোমার কাছে টিকিট আছে?", "আপনার কাছে টিকিট আছে?",
     "transit", "conductor", "pron.gen + existential"),
    ("তুই কোন ট্রেনে যাবি?", "তুমি কোন ট্রেনে যাবে?", "আপনি কোন ট্রেনে যাবেন?",
     "transit", "fellow traveller", "v.future"),
    ("এখানে নাম।", "এখানে নামো।", "এখানে নামুন।", "transit", "driver", "v.imp.nama"),
    ("তুই আমাকে রাস্তাটা দেখাতে পারিস?", "তুমি আমাকে রাস্তাটা দেখাতে পারো?",
     "আপনি আমাকে রাস্তাটা দেখাতে পারেন?",
     "transit", "stranger", "v.para"),
    ("তুই কতক্ষণ লাগবে বলতে পারিস?", "তুমি কতক্ষণ লাগবে বলতে পারো?",
     "আপনি কতক্ষণ লাগবে বলতে পারেন?",
     "transit", "driver", "v.para"),
]

SHOPPING: List[Triad] = [
    ("তুই কত নিবি?", "তুমি কত নেবে?", "আপনি কত নেবেন?",
     "shopping", "shopkeeper", "v.future"),
    ("তোর কাছে খুচরো আছে?", "তোমার কাছে খুচরো আছে?", "আপনার কাছে খুচরো আছে?",
     "shopping", "shopkeeper", "pron.gen + existential"),
    ("একটু কমা।", "একটু কমাও।", "একটু কমান।", "shopping", "shopkeeper", "v.imp.kamano"),
    ("তুই কি এটা বদলে দিতে পারিস?", "তুমি কি এটা বদলে দিতে পারো?",
     "আপনি কি এটা বদলে দিতে পারেন?",
     "shopping", "shopkeeper", "v.para"),
    ("আমাকে রসিদটা দে।", "আমাকে রসিদটা দাও।", "আমাকে রসিদটা দিন।",
     "shopping", "shopkeeper", "v.imp.deoa"),
]

MEDICAL: List[Triad] = [
    ("তোর কী হয়েছে?", "তোমার কী হয়েছে?", "আপনার কী হয়েছে?",
     "medical", "patient", "pron.gen + v.pres.perf"),
    ("তুই ওষুধ খেয়েছিস?", "তুমি ওষুধ খেয়েছ?", "আপনি ওষুধ খেয়েছেন?",
     "medical", "patient", "v.pres.perf"),
    ("তোর কোথায় ব্যথা?", "তোমার কোথায় ব্যথা?", "আপনার কোথায় ব্যথা?",
     "medical", "patient", "pron.gen"),
    ("তুই কতদিন ধরে ভুগছিস?", "তুমি কতদিন ধরে ভুগছ?", "আপনি কতদিন ধরে ভুগছেন?",
     "medical", "patient", "v.pres.cont"),
    ("এখানে শো।", "এখানে শোও।", "এখানে শুয়ে পড়ুন।",
     "medical", "patient", "v.imp.soa"),
    ("তোর কি অ্যালার্জি আছে?", "তোমার কি অ্যালার্জি আছে?", "আপনার কি অ্যালার্জি আছে?",
     "medical", "patient", "pron.gen + existential"),
]

EMERGENCY: List[Triad] = [
    ("তাড়াতাড়ি আয়!", "তাড়াতাড়ি এসো!", "তাড়াতাড়ি আসুন!",
     "emergency", "bystander", "v.imp.asa"),
    ("আমাকে সাহায্য কর!", "আমাকে সাহায্য করো!", "আমাকে সাহায্য করুন!",
     "emergency", "bystander", "v.imp.kora"),
    ("ডাক্তার ডাক!", "ডাক্তার ডাকো!", "ডাক্তার ডাকুন!",
     "emergency", "bystander", "v.imp.daka"),
    ("তুই পুলিশে ফোন কর।", "তুমি পুলিশে ফোন করো।", "আপনি পুলিশে ফোন করুন।",
     "emergency", "bystander", "v.imp.kora"),
    ("এখান থেকে সর!", "এখান থেকে সরো!", "এখান থেকে সরুন!",
     "emergency", "bystander", "v.imp.sara"),
]

DOMESTIC: List[Triad] = [
    ("তুই কি ঘুমিয়েছিস?", "তুমি কি ঘুমিয়েছ?", "আপনি কি ঘুমিয়েছেন?",
     "domestic", "family", "v.pres.perf"),
    ("মা তোকে ডাকছে।", "মা তোমাকে ডাকছে।", "মা আপনাকে ডাকছেন।",
     "domestic", "family", "pron.acc + 3sg honorific"),
    ("তুই চা খাবি?", "তুমি চা খাবে?", "আপনি চা খাবেন?",
     "domestic", "guest", "v.future"),
    ("দরজাটা বন্ধ কর।", "দরজাটা বন্ধ করো।", "দরজাটা বন্ধ করুন।",
     "domestic", "family", "v.imp.kora"),
    ("তোর জামা কোথায়?", "তোমার জামা কোথায়?", "আপনার জামা কোথায়?",
     "domestic", "family", "pron.gen"),
]

WORKPLACE: List[Triad] = [
    ("তুই মিটিংয়ে আসবি?", "তুমি মিটিংয়ে আসবে?", "আপনি মিটিংয়ে আসবেন?",
     "workplace", "colleague", "v.future"),
    ("তুই রিপোর্টটা পাঠিয়েছিস?", "তুমি রিপোর্টটা পাঠিয়েছ?",
     "আপনি রিপোর্টটা পাঠিয়েছেন?",
     "workplace", "colleague", "v.pres.perf"),
    ("এটা একটু দেখে দে।", "এটা একটু দেখে দাও।", "এটা একটু দেখে দিন।",
     "workplace", "colleague", "v.imp.deoa"),
    ("তোর মতামত কী?", "তোমার মতামত কী?", "আপনার মতামত কী?",
     "workplace", "colleague", "pron.gen"),
    ("তুই কি ফাইলটা পেয়েছিস?", "তুমি কি ফাইলটা পেয়েছ?", "আপনি কি ফাইলটা পেয়েছেন?",
     "workplace", "colleague", "v.pres.perf"),
]

EDUCATION: List[Triad] = [
    ("তুই পড়াশোনা করেছিস?", "তুমি পড়াশোনা করেছ?", "আপনি পড়াশোনা করেছেন?",
     "education", "student", "v.pres.perf"),
    ("বইটা আন।", "বইটা আনো।", "বইটা আনুন।", "education", "student", "v.imp.ana"),
    ("তুই কোন ক্লাসে পড়িস?", "তুমি কোন ক্লাসে পড়ো?", "আপনি কোন ক্লাসে পড়েন?",
     "education", "student", "v.pres.simple"),
    ("তুই কি প্রশ্নটা বুঝেছিস?", "তুমি কি প্রশ্নটা বুঝেছ?", "আপনি কি প্রশ্নটা বুঝেছেন?",
     "education", "student", "v.pres.perf"),
]

HOSPITALITY: List[Triad] = [
    ("তুই কোথায় উঠেছিস?", "তুমি কোথায় উঠেছ?", "আপনি কোথায় উঠেছেন?",
     "hospitality", "traveller", "v.pres.perf"),
    ("তোর ঘর তৈরি।", "তোমার ঘর তৈরি।", "আপনার ঘর তৈরি।",
     "hospitality", "guest", "pron.gen"),
    ("তুই কদিন থাকবি?", "তুমি কদিন থাকবে?", "আপনি কদিন থাকবেন?",
     "hospitality", "guest", "v.future"),
    ("চাবিটা নে।", "চাবিটা নাও।", "চাবিটা নিন।",
     "hospitality", "guest", "v.imp.neoa"),
]

PHONE: List[Triad] = [
    ("তোর নম্বরটা দে।", "তোমার নম্বরটা দাও।", "আপনার নম্বরটা দিন।",
     "phone", "acquaintance", "v.imp.deoa + pron.gen"),
    ("তুই পরে ফোন করিস।", "তুমি পরে ফোন করো।", "আপনি পরে ফোন করবেন।",
     "phone", "colleague", "v.imp / v.future"),
    ("তুই কি শুনতে পাচ্ছিস?", "তুমি কি শুনতে পাচ্ছ?", "আপনি কি শুনতে পাচ্ছেন?",
     "phone", "caller", "v.pres.cont"),
]

# --------------------------------------------------------------------------
# 6. The case a single dial gets wrong.
#
# Blueprint 13.2 #1: register is at least two axes, power and solidarity. The
# family elder is high power AND high solidarity, so Bengali uses তুমি — the
# same form as a friend, for an entirely different reason. A stranger of the
# same age gets আপনি. On one scale those two sit far apart; socially they are
# not on the same line at all. These rows exist so that a future two-axis model
# has something to be measured against.
# --------------------------------------------------------------------------

SOLIDARITY: List[Triad] = [
    ("তুই কেমন আছিস, দিদা?", "তুমি কেমন আছ, দিদা?", "আপনি কেমন আছেন, দিদা?",
     "family", "grandmother — high power, high solidarity → তুমি is correct",
     "pron.nom + vocative"),
    ("তুই খেয়েছিস, দাদু?", "তুমি খেয়েছ, দাদু?", "আপনি খেয়েছেন, দাদু?",
     "family", "grandfather — তুমি expected despite seniority", "v.pres.perf + vocative"),
    ("তুই আসবি, কাকু?", "তুমি আসবে, কাকু?", "আপনি আসবেন, কাকু?",
     "family", "uncle — তুমি within the family", "v.future + vocative"),
    ("তুই কোথায় যাচ্ছিস, মা?", "তুমি কোথায় যাচ্ছ, মা?", "আপনি কোথায় যাচ্ছেন, মা?",
     "family", "mother — তুমি", "v.pres.cont + vocative"),
]

# --------------------------------------------------------------------------
# 6b. Negation — Bengali negates differently by tense, and the prohibitive
#     (যেও না) is not the same shape as the indicative negative (যাও না).
#     A table that only handles affirmatives breaks on half of real speech.
# --------------------------------------------------------------------------

NEGATION: List[Triad] = [
    ("তুই ওখানে যাস না।", "তুমি ওখানে যেও না।", "আপনি ওখানে যাবেন না।",
     "everyday", "friend", "v.prohibitive"),
    ("তুই এটা করিস না।", "তুমি এটা কোরো না।", "আপনি এটা করবেন না।",
     "everyday", "colleague", "v.prohibitive"),
    ("তুই চিন্তা করিস না।", "তুমি চিন্তা কোরো না।", "আপনি চিন্তা করবেন না।",
     "reassurance", "friend", "v.prohibitive"),
    ("তুই কিছু বলিস না।", "তুমি কিছু বোলো না।", "আপনি কিছু বলবেন না।",
     "everyday", "friend", "v.prohibitive"),
    ("তুই জানিস না?", "তুমি জানো না?", "আপনি জানেন না?",
     "smalltalk", "acquaintance", "v.pres.negative"),
    ("তুই আসিসনি কেন?", "তুমি আসোনি কেন?", "আপনি আসেননি কেন?",
     "smalltalk", "friend", "v.perf.negative"),
    ("তুই কিছু খাসনি।", "তুমি কিছু খাওনি।", "আপনি কিছু খাননি।",
     "food", "guest", "v.perf.negative"),
    ("তুই তো কিছু বলছিস না।", "তুমি তো কিছু বলছ না।", "আপনি তো কিছু বলছেন না।",
     "smalltalk", "friend", "v.cont.negative"),
]

# --------------------------------------------------------------------------
# 6c. Question forms beyond the plain yes/no
# --------------------------------------------------------------------------

QUESTIONS: List[Triad] = [
    ("তুই কেন এসেছিস?", "তুমি কেন এসেছ?", "আপনি কেন এসেছেন?",
     "smalltalk", "visitor", "wh.why + v.pres.perf"),
    ("তুই কার সঙ্গে এসেছিস?", "তুমি কার সঙ্গে এসেছ?", "আপনি কার সঙ্গে এসেছেন?",
     "smalltalk", "visitor", "wh.who"),
    ("তুই কীভাবে এলি?", "তুমি কীভাবে এলে?", "আপনি কীভাবে এলেন?",
     "transit", "visitor", "wh.how + v.past"),
    ("তোর কোনটা পছন্দ?", "তোমার কোনটা পছন্দ?", "আপনার কোনটা পছন্দ?",
     "shopping", "customer", "wh.which + pron.gen"),
    ("তুই কতক্ষণ থাকবি?", "তুমি কতক্ষণ থাকবে?", "আপনি কতক্ষণ থাকবেন?",
     "hospitality", "guest", "wh.how-long + v.future"),
    ("তুই কি রাজি?", "তুমি কি রাজি?", "আপনি কি রাজি?",
     "workplace", "colleague", "yes-no + adjective"),
    ("তোর কী মনে হয়?", "তোমার কী মনে হয়?", "আপনার কী মনে হয়?",
     "workplace", "colleague", "wh.what + idiom"),
    ("তুই কাকে খুঁজছিস?", "তুমি কাকে খুঁজছ?", "আপনি কাকে খুঁজছেন?",
     "everyday", "stranger", "wh.whom + v.pres.cont"),
]

# --------------------------------------------------------------------------
# 6d. Courtesy — thanks, apology, compliment, condolence
# --------------------------------------------------------------------------

COURTESY: List[Triad] = [
    ("আমাকে মাফ কর।", "আমাকে মাফ করো।", "আমাকে মাফ করুন।",
     "apology", "stranger", "v.imp.kora"),
    ("তোকে ধন্যবাদ।", "তোমাকে ধন্যবাদ।", "আপনাকে ধন্যবাদ।",
     "greeting", "acquaintance", "pron.acc"),
    ("তুই ভালো করেছিস।", "তুমি ভালো করেছ।", "আপনি ভালো করেছেন।",
     "compliment", "colleague", "v.pres.perf"),
    ("তোকে খুব ভালো লাগছে।", "তোমাকে খুব ভালো লাগছে।", "আপনাকে খুব ভালো লাগছে।",
     "compliment", "acquaintance", "pron.acc + v.pres.cont"),
    ("তুই কিছু মনে করিস না।", "তুমি কিছু মনে কোরো না।", "আপনি কিছু মনে করবেন না।",
     "apology", "colleague", "v.prohibitive"),
    ("তোর জন্য খারাপ লাগছে।", "তোমার জন্য খারাপ লাগছে।", "আপনার জন্য খারাপ লাগছে।",
     "condolence", "acquaintance", "pron.gen"),
    ("তুই একটু কষ্ট করে আয়।", "তুমি একটু কষ্ট করে এসো।", "আপনি একটু কষ্ট করে আসুন।",
     "request", "colleague", "v.imp.asa + softener"),
    ("তোর অনেক উপকার হল।", "তোমার অনেক উপকার হল।", "আপনার অনেক উপকার হল।",
     "greeting", "acquaintance", "pron.gen"),
]

# --------------------------------------------------------------------------
# 6e. Invitations and offers
# --------------------------------------------------------------------------

INVITATION: List[Triad] = [
    ("তুই আমাদের বাড়ি আয়।", "তুমি আমাদের বাড়ি এসো।", "আপনি আমাদের বাড়ি আসুন।",
     "invitation", "friend", "v.imp.asa"),
    ("তুই কি আমার সঙ্গে যাবি?", "তুমি কি আমার সঙ্গে যাবে?",
     "আপনি কি আমার সঙ্গে যাবেন?",
     "invitation", "colleague", "v.future"),
    ("তুই বসে খা।", "তুমি বসে খাও।", "আপনি বসে খান।",
     "invitation", "guest", "v.imp.khaoa"),
    ("তোর জন্য চা এনেছি।", "তোমার জন্য চা এনেছি।", "আপনার জন্য চা এনেছি।",
     "invitation", "guest", "pron.gen"),
    ("তুই কাল আসতে পারবি?", "তুমি কাল আসতে পারবে?", "আপনি কাল আসতে পারবেন?",
     "invitation", "colleague", "v.para.future"),
]

# --------------------------------------------------------------------------
# 6f. Money and banking
# --------------------------------------------------------------------------

MONEY: List[Triad] = [
    ("তুই কত টাকা দিবি?", "তুমি কত টাকা দেবে?", "আপনি কত টাকা দেবেন?",
     "money", "customer", "v.future"),
    ("তোর অ্যাকাউন্ট নম্বর কী?", "তোমার অ্যাকাউন্ট নম্বর কী?",
     "আপনার অ্যাকাউন্ট নম্বর কী?",
     "money", "bank clerk", "pron.gen"),
    ("তুই কি কার্ডে দিবি?", "তুমি কি কার্ডে দেবে?", "আপনি কি কার্ডে দেবেন?",
     "money", "customer", "v.future"),
    ("টাকাটা এখানে জমা দে।", "টাকাটা এখানে জমা দাও।", "টাকাটা এখানে জমা দিন।",
     "money", "bank clerk", "v.imp.deoa"),
    ("তোর কাছে ভাঙতি আছে?", "তোমার কাছে ভাঙতি আছে?", "আপনার কাছে ভাঙতি আছে?",
     "money", "shopkeeper", "pron.gen + existential"),
    ("তুই পরে শোধ করিস।", "তুমি পরে শোধ কোরো।", "আপনি পরে শোধ করবেন।",
     "money", "acquaintance", "v.imp / v.future"),
]

# --------------------------------------------------------------------------
# 6g. Directions
# --------------------------------------------------------------------------

DIRECTIONS: List[Triad] = [
    ("তুই সোজা যা।", "তুমি সোজা যাও।", "আপনি সোজা যান।",
     "directions", "stranger", "v.imp.jaoa"),
    ("তুই ডানদিকে ঘোর।", "তুমি ডানদিকে ঘোরো।", "আপনি ডানদিকে ঘুরুন।",
     "directions", "stranger", "v.imp.ghora"),
    ("তুই ওই মোড়ে নাম।", "তুমি ওই মোড়ে নামো।", "আপনি ওই মোড়ে নামুন।",
     "directions", "stranger", "v.imp.nama"),
    ("তুই কি রাস্তাটা চিনিস?", "তুমি কি রাস্তাটা চেনো?", "আপনি কি রাস্তাটা চেনেন?",
     "directions", "stranger", "v.chena"),
    ("তুই আমার পিছনে আয়।", "তুমি আমার পিছনে এসো।", "আপনি আমার পিছনে আসুন।",
     "directions", "stranger", "v.imp.asa"),
    ("তুই এখানে দাঁড়া।", "তুমি এখানে দাঁড়াও।", "আপনি এখানে দাঁড়ান।",
     "directions", "stranger", "v.imp.darano"),
]

# --------------------------------------------------------------------------
# 6h. Everyday verbs not covered above
# --------------------------------------------------------------------------

MORE_VERBS: List[Triad] = [
    ("তুই কি ঘুমাস?", "তুমি কি ঘুমাও?", "আপনি কি ঘুমান?",
     "domestic", "family", "v.ghumano"),
    ("তুই গানটা শুনিস।", "তুমি গানটা শোনো।", "আপনি গানটা শোনেন।",
     "leisure", "friend", "v.suna"),
    ("তুই ছবিটা দেখিস।", "তুমি ছবিটা দেখো।", "আপনি ছবিটা দেখেন।",
     "leisure", "friend", "v.dekha"),
    ("তুই কি লিখিস?", "তুমি কি লেখো?", "আপনি কি লেখেন?",
     "education", "student", "v.lekha"),
    ("তুই কি রান্না করিস?", "তুমি কি রান্না করো?", "আপনি কি রান্না করেন?",
     "domestic", "acquaintance", "v.kora"),
    ("তুই আমাকে শেখা।", "তুমি আমাকে শেখাও।", "আপনি আমাকে শেখান।",
     "education", "teacher", "v.imp.sekhano"),
    ("তুই একটু ভাব।", "তুমি একটু ভাবো।", "আপনি একটু ভাবুন।",
     "workplace", "colleague", "v.imp.bhaba"),
    ("তুই কি বিশ্বাস করিস?", "তুমি কি বিশ্বাস করো?", "আপনি কি বিশ্বাস করেন?",
     "smalltalk", "acquaintance", "v.kora"),
    ("তুই কাগজটা রাখ।", "তুমি কাগজটা রাখো।", "আপনি কাগজটা রাখুন।",
     "workplace", "colleague", "v.imp.rakha"),
    ("তুই আমাকে ডাক।", "তুমি আমাকে ডাকো।", "আপনি আমাকে ডাকুন।",
     "everyday", "colleague", "v.imp.daka"),
]

TRIAD_GROUPS: List[Tuple[str, List[Triad]]] = [
    ("pronouns", PRONOUNS),
    ("tense", TENSES),
    ("imperative", IMPERATIVES),
    ("modal", MODALS),
    ("negation", NEGATION),
    ("questions", QUESTIONS),
    ("courtesy", COURTESY),
    ("invitation", INVITATION),
    ("money", MONEY),
    ("directions", DIRECTIONS),
    ("more_verbs", MORE_VERBS),
    ("transit", TRANSIT),
    ("shopping", SHOPPING),
    ("medical", MEDICAL),
    ("emergency", EMERGENCY),
    ("domestic", DOMESTIC),
    ("workplace", WORKPLACE),
    ("education", EDUCATION),
    ("hospitality", HOSPITALITY),
    ("phone", PHONE),
    ("solidarity", SOLIDARITY),
]

# --------------------------------------------------------------------------
# 7. Level 3 — Formal shares আপনি with Polite, so what marks it is lexical:
#    দয়া করে / অনুগ্রহ করে, Sanskritised vocabulary, and elaborated closings.
# --------------------------------------------------------------------------

FORMAL: List[Tuple[str, str, str]] = [
    ("দয়া করে একটু অপেক্ষা করুন।", "request", "official"),
    ("অনুগ্রহ করে এখানে স্বাক্ষর করুন।", "admin", "official"),
    ("দয়া করে আমাকে সাহায্য করুন।", "request", "official"),
    ("অনুগ্রহ করে একটু বসুন।", "admin", "official"),
    ("আপনাকে অসংখ্য ধন্যবাদ।", "greeting", "official"),
    ("আমি আপনার কাছে কৃতজ্ঞ।", "greeting", "official"),
    ("আমি ক্ষমাপ্রার্থী।", "apology", "official"),
    ("দয়া করে বিষয়টি বিবেচনা করুন।", "admin", "official"),
    ("অনুগ্রহ করে আপনার পরিচয়পত্র দেখান।", "admin", "official"),
    ("আপনার সহযোগিতার জন্য ধন্যবাদ।", "workplace", "official"),
    ("দয়া করে লাইনে দাঁড়ান।", "admin", "official"),
    ("অনুগ্রহ করে নথিপত্র জমা দিন।", "admin", "official"),
    ("আপনার আবেদন গৃহীত হয়েছে।", "admin", "official"),
    ("দয়া করে অপেক্ষা করুন, আপনার নাম ডাকা হবে।", "admin", "official"),
    ("মহোদয়, আপনার সময়ের জন্য ধন্যবাদ।", "workplace", "official"),
]

# --------------------------------------------------------------------------
# 8. Negatives — no second-person marker anywhere, so detection must return
#    None rather than inventing a level. A detector that guesses on these is
#    worse than one that abstains, because Auto mode would then mirror noise.
# --------------------------------------------------------------------------

NO_MARKER: List[Tuple[str, str]] = [
    ("আজ আবহাওয়া খুব ভালো।", "weather"),
    ("এটার দাম কত?", "shopping"),
    ("ট্রেনটা দেরিতে চলছে।", "transit"),
    ("আমি কলকাতায় থাকি।", "smalltalk"),
    ("বৃষ্টি হচ্ছে।", "weather"),
    ("দোকানটা বন্ধ।", "shopping"),
    ("আমার নাম রাহুল।", "greeting"),
    ("এখানে খুব ভিড়।", "transit"),
    ("খাবারটা সুস্বাদু ছিল।", "food"),
    ("আমি বাংলা শিখছি।", "education"),
    ("বাসটা এখনও আসেনি।", "transit"),
    ("ঘরটা পরিষ্কার।", "domestic"),
    ("সে কাল এসেছিল।", "smalltalk"),
    ("আমার মাথা ব্যথা করছে।", "medical"),
    ("হাসপাতালটা কাছেই।", "medical"),
    ("দাম অনেক বেড়ে গেছে।", "shopping"),
    ("রাস্তাটা বন্ধ আছে।", "transit"),
    ("আমরা কাল যাব।", "planning"),
    ("সময় নেই।", "smalltalk"),
    ("ব্যাগটা ভারী।", "travel"),
]

# --------------------------------------------------------------------------
# 9. Hard cases — genuine ambiguities the engine has to resolve, and the rows
#    most worth a native speaker's attention.
# --------------------------------------------------------------------------

HARD: List[Tuple[str, Optional[int], str, str]] = [
    ("বলো।", 1, "imperative", "bare imperative — তুমি level, no pronoun to lean on"),
    ("তুমি বলো।", 1, "statement", "same verb form as the imperative above; the "
                                  "pronoun is what makes it a statement"),
    ("বল।", 0, "imperative", "তুই imperative"),
    ("বলুন।", 2, "imperative", "আপনি imperative"),
    ("করো।", 1, "imperative", "তুমি imperative, identical to the present tense"),
    ("তুমি করো।", 1, "statement", "present tense reading"),
    ("যান।", 2, "imperative", "আপনি imperative — also the 3rd person plural form"),
    ("আপনি যান।", 2, "statement", "unambiguous with the pronoun present"),
    ("খাও।", 1, "imperative", "তুমি"),
    ("তুমি খাও।", 1, "statement", "present tense"),
    ("আপনারা কেমন আছেন?", 2, "plural", "2nd person plural honorific"),
    ("তোরা কোথায় যাস?", 0, "plural", "তুই plural — তোরা"),
    ("তোমরা কী করছ?", 1, "plural", "তুমি plural — তোমরা"),
    ("তুই আর আমি যাব।", 0, "coordination", "pronoun inside a coordinated subject"),
    ("আপনি এবং আপনার পরিবার আমন্ত্রিত।", 2, "coordination",
     "honorific repeated across a conjunction"),
]


def triad_rows() -> Iterator[dict]:
    """Expand each triad into three rows, each carrying the full gold rendering."""
    for group, triads in TRIAD_GROUPS:
        for close, casual, polite, domain, context, construction in triads:
            expected = {"0": close, "1": casual, "2": polite, "3": polite}
            for level, text in ((0, close), (1, casual), (2, polite)):
                yield {
                    "text": text,
                    "level": level,
                    "expected": expected,
                    "domain": domain,
                    "context": context,
                    "construction": construction,
                    "group": group,
                    "status": "draft",
                    "note": f"{construction} · {context}",
                }


def formal_rows() -> Iterator[dict]:
    for text, domain, context in FORMAL:
        yield {
            "text": text, "level": 3, "domain": domain, "context": context,
            "construction": "lexical formality", "group": "formal",
            "status": "draft",
            "note": "Formal is lexical in Bengali — আপনি plus দয়া করে / অনুগ্রহ করে",
        }


def no_marker_rows() -> Iterator[dict]:
    for text, domain in NO_MARKER:
        yield {
            "text": text, "level": None, "domain": domain, "context": "n/a",
            "construction": "no second-person marker", "group": "negative",
            "status": "draft",
            "note": "detection must return None; abstaining beats guessing",
        }


def hard_rows() -> Iterator[dict]:
    for text, level, construction, note in HARD:
        yield {
            "text": text, "level": level, "domain": "ambiguity", "context": "n/a",
            "construction": construction, "group": "hard",
            "status": "draft", "note": note,
        }


def all_rows() -> List[dict]:
    rows = list(triad_rows()) + list(formal_rows()) + list(no_marker_rows()) + list(hard_rows())
    for index, row in enumerate(rows, 1):
        row["id"] = f"bn-{index:04d}"
        row["language"] = "bn"
    return rows


def report(rows: List[dict]) -> None:
    levels = Counter(str(r["level"]) for r in rows)
    groups = Counter(r["group"] for r in rows)
    domains = Counter(r["domain"] for r in rows)
    constructions = Counter(r["construction"] for r in rows)

    print(f"Bengali gold set — {len(rows)} rows  (ALL DRAFT, unverified)\n")
    print("by level")
    for key in ("0", "1", "2", "3", "None"):
        if key in levels:
            name = {"0": "Close", "1": "Casual", "2": "Polite",
                    "3": "Formal", "None": "no marker"}[key]
            print(f"  {name:<10} {levels[key]:>4}")
    print("\nby group")
    for name, count in groups.most_common():
        print(f"  {name:<14} {count:>4}")
    print(f"\ndomains: {len(domains)}   constructions: {len(constructions)}")
    print(f"contrastive triads: {sum(len(t) for _, t in TRIAD_GROUPS)}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build the Bengali gold set draft")
    parser.add_argument("--stats", action="store_true", help="report coverage only")
    parser.add_argument("--out", default=str(OUT))
    args = parser.parse_args(argv)

    rows = all_rows()
    report(rows)

    if args.stats:
        return 0

    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"\nwrote {path}")
    print("Every row is status=draft. Review with:  python -m evaluation.review bn")
    return 0


if __name__ == "__main__":
    sys.exit(main())
