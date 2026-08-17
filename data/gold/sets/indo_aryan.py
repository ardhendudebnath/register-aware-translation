"""
Indo-Aryan register sets: Hindi, Urdu, Marathi, Gujarati, Punjabi, Nepali,
Odia, Assamese.

All machine-drafted, all ``status: "draft"``. See ``common.py`` for why that
distinction is load-bearing.

Hindi is the fullest set here on purpose. CoCoA-MT gave Hindi a *binary*
formality benchmark in 2022 — formal vs informal — and Hindi has three
grammatical levels (तू / तुम / आप), so a three-level set is new rather than a
re-run of existing work. Every other language in this file has nothing at all
to compare against.

Column mappings are read off the shipped tables, not assumed. Where a language
uses one pronoun for both Polite and Formal (Punjabi ਤੁਸੀਂ), the triad's third
column repeats the second and Formal is carried lexically in ``formal``
instead — inventing a distinct third pronoun would fake a contrast the language
does not draw.
"""

from __future__ import annotations

from ..common import LanguageSet

# ==========================================================================
# Hindi — तू / तुम / आप
# ==========================================================================

HINDI = LanguageSet(
    code="hi",
    name="Hindi",
    columns=(0, 1, 2),
    confidence="high",
    note="तू is intimate or rude depending entirely on relationship; "
         "तुम is the everyday default among equals; आप is polite and plural.",
    triads=[
        ("pronouns", [
            ("तू कैसा है?", "तुम कैसे हो?", "आप कैसे हैं?",
             "greeting", "friend", "pron.nom + cop.pres"),
            ("तेरा नाम क्या है?", "तुम्हारा नाम क्या है?", "आपका नाम क्या है?",
             "greeting", "stranger", "pron.gen"),
            ("तुझे देखकर अच्छा लगा।", "तुम्हें देखकर अच्छा लगा।",
             "आपको देखकर अच्छा लगा।", "greeting", "acquaintance", "pron.dat"),
            ("तेरा घर कहाँ है?", "तुम्हारा घर कहाँ है?", "आपका घर कहाँ है?",
             "smalltalk", "stranger", "pron.gen"),
            ("यह तेरे लिए है।", "यह तुम्हारे लिए है।", "यह आपके लिए है।",
             "everyday", "family", "pron.gen.obl"),
            ("मैं तुझे जानता हूँ।", "मैं तुम्हें जानता हूँ।", "मैं आपको जानता हूँ।",
             "smalltalk", "acquaintance", "pron.dat"),
            ("तेरे पास समय है?", "तुम्हारे पास समय है?", "आपके पास समय है?",
             "smalltalk", "colleague", "pron.gen + existential"),
            ("मुझे तेरी मदद चाहिए।", "मुझे तुम्हारी मदद चाहिए।",
             "मुझे आपकी मदद चाहिए।", "request", "colleague", "pron.gen.f"),
        ]),
        ("tense", [
            ("तू क्या करता है?", "तुम क्या करते हो?", "आप क्या करते हैं?",
             "smalltalk", "stranger", "v.pres.habitual"),
            ("तू कहाँ रहता है?", "तुम कहाँ रहते हो?", "आप कहाँ रहते हैं?",
             "smalltalk", "stranger", "v.pres.habitual"),
            ("तू हिंदी बोलता है?", "तुम हिंदी बोलते हो?", "आप हिंदी बोलते हैं?",
             "smalltalk", "stranger", "v.pres.habitual"),
            ("तू क्या कर रहा है?", "तुम क्या कर रहे हो?", "आप क्या कर रहे हैं?",
             "smalltalk", "friend", "v.pres.cont"),
            ("तू कहाँ जा रहा है?", "तुम कहाँ जा रहे हो?", "आप कहाँ जा रहे हैं?",
             "travel", "acquaintance", "v.pres.cont"),
            ("तूने खाना खाया?", "तुमने खाना खाया?", "आपने खाना खाया?",
             "food", "family", "v.past.perfective"),
            ("तूने काम कर लिया?", "तुमने काम कर लिया?", "आपने काम कर लिया?",
             "workplace", "colleague", "v.past.perfective"),
            ("तू कहाँ था?", "तुम कहाँ थे?", "आप कहाँ थे?",
             "smalltalk", "friend", "v.past.cop"),
            ("तू कब आएगा?", "तुम कब आओगे?", "आप कब आएँगे?",
             "planning", "colleague", "v.future"),
            ("तू क्या खाएगा?", "तुम क्या खाओगे?", "आप क्या खाएँगे?",
             "food", "guest", "v.future"),
            ("तू कब लौटेगा?", "तुम कब लौटोगे?", "आप कब लौटेंगे?",
             "planning", "family", "v.future"),
        ]),
        ("imperative", [
            ("यहाँ आ।", "यहाँ आओ।", "यहाँ आइए।", "everyday", "guest", "v.imp.ana"),
            ("यहाँ बैठ।", "यहाँ बैठो।", "यहाँ बैठिए।", "everyday", "guest", "v.imp.baithna"),
            ("ज़रा सुन।", "ज़रा सुनो।", "ज़रा सुनिए।", "everyday", "stranger", "v.imp.sunna"),
            ("यह देख।", "यह देखो।", "यह देखिए।", "everyday", "colleague", "v.imp.dekhna"),
            ("मुझे बता।", "मुझे बताओ।", "मुझे बताइए।", "everyday", "colleague", "v.imp.batana"),
            ("दरवाज़ा खोल।", "दरवाज़ा खोलो।", "दरवाज़ा खोलिए।",
             "everyday", "family", "v.imp.kholna"),
            ("थोड़ा रुक।", "थोड़ा रुको।", "थोड़ा रुकिए।",
             "everyday", "stranger", "v.imp.rukna"),
            ("मुझे एक दे।", "मुझे एक दो।", "मुझे एक दीजिए।",
             "shopping", "shopkeeper", "v.imp.dena"),
            ("यह ले।", "यह लो।", "यह लीजिए।", "shopping", "shopkeeper", "v.imp.lena"),
            ("जल्दी चल।", "जल्दी चलो।", "जल्दी चलिए।", "travel", "companion", "v.imp.chalna"),
            ("मुझे फ़ोन कर।", "मुझे फ़ोन करो।", "मुझे फ़ोन कीजिए।",
             "phone", "colleague", "v.imp.karna"),
            ("यहाँ लिख।", "यहाँ लिखो।", "यहाँ लिखिए।", "admin", "official", "v.imp.likhna"),
        ]),
        ("modal", [
            ("तू मेरी मदद कर सकता है?", "तुम मेरी मदद कर सकते हो?",
             "आप मेरी मदद कर सकते हैं?", "request", "stranger", "v.sakna"),
            ("तू थोड़ा रुक सकता है?", "तुम थोड़ा रुक सकते हो?",
             "आप थोड़ा रुक सकते हैं?", "request", "stranger", "v.sakna"),
            ("तुझे क्या चाहिए?", "तुम्हें क्या चाहिए?", "आपको क्या चाहिए?",
             "shopping", "shopkeeper", "v.chahiye"),
            ("तू जानता है?", "तुम जानते हो?", "आप जानते हैं?",
             "smalltalk", "stranger", "v.janna"),
            ("तू समझता है?", "तुम समझते हो?", "आप समझते हैं?",
             "smalltalk", "colleague", "v.samajhna"),
        ]),
        ("negation", [
            ("तू वहाँ मत जा।", "तुम वहाँ मत जाओ।", "आप वहाँ मत जाइए।",
             "everyday", "friend", "v.prohibitive"),
            ("तू चिंता मत कर।", "तुम चिंता मत करो।", "आप चिंता मत कीजिए।",
             "reassurance", "friend", "v.prohibitive"),
            ("तू कुछ मत बोल।", "तुम कुछ मत बोलो।", "आप कुछ मत बोलिए।",
             "everyday", "friend", "v.prohibitive"),
            ("तू नहीं जानता?", "तुम नहीं जानते?", "आप नहीं जानते?",
             "smalltalk", "acquaintance", "v.pres.negative"),
            ("तू क्यों नहीं आया?", "तुम क्यों नहीं आए?", "आप क्यों नहीं आए?",
             "smalltalk", "friend", "v.past.negative"),
        ]),
        ("questions", [
            ("तू क्यों आया है?", "तुम क्यों आए हो?", "आप क्यों आए हैं?",
             "smalltalk", "visitor", "wh.why + v.perf"),
            ("तू किसके साथ आया?", "तुम किसके साथ आए?", "आप किसके साथ आए?",
             "smalltalk", "visitor", "wh.who"),
            ("तू कैसे आया?", "तुम कैसे आए?", "आप कैसे आए?",
             "transit", "visitor", "wh.how"),
            ("तुझे कौन सा पसंद है?", "तुम्हें कौन सा पसंद है?", "आपको कौन सा पसंद है?",
             "shopping", "customer", "wh.which + pron.dat"),
            ("तू कितनी देर रुकेगा?", "तुम कितनी देर रुकोगे?", "आप कितनी देर रुकेंगे?",
             "hospitality", "guest", "wh.how-long + v.future"),
        ]),
        ("courtesy", [
            ("मुझे माफ़ कर।", "मुझे माफ़ करो।", "मुझे माफ़ कीजिए।",
             "apology", "stranger", "v.imp.karna"),
            ("तुझे धन्यवाद।", "तुम्हें धन्यवाद।", "आपको धन्यवाद।",
             "greeting", "acquaintance", "pron.dat"),
            ("तूने अच्छा किया।", "तुमने अच्छा किया।", "आपने अच्छा किया।",
             "compliment", "colleague", "v.past.perfective"),
            ("तू बुरा मत मान।", "तुम बुरा मत मानो।", "आप बुरा मत मानिए।",
             "apology", "colleague", "v.prohibitive"),
        ]),
        ("transit", [
            ("तू स्टेशन जाता है?", "तुम स्टेशन जाते हो?", "आप स्टेशन जाते हैं?",
             "transit", "driver", "v.pres.habitual"),
            ("तेरे पास टिकट है?", "तुम्हारे पास टिकट है?", "आपके पास टिकट है?",
             "transit", "conductor", "pron.gen + existential"),
            ("तू किस ट्रेन से जाएगा?", "तुम किस ट्रेन से जाओगे?",
             "आप किस ट्रेन से जाएँगे?", "transit", "fellow traveller", "v.future"),
            ("यहाँ उतर।", "यहाँ उतरो।", "यहाँ उतरिए।", "transit", "driver", "v.imp.utarna"),
            ("तू मुझे रास्ता दिखा सकता है?", "तुम मुझे रास्ता दिखा सकते हो?",
             "आप मुझे रास्ता दिखा सकते हैं?", "directions", "stranger", "v.sakna"),
        ]),
        ("shopping", [
            ("तू कितने का देगा?", "तुम कितने का दोगे?", "आप कितने का देंगे?",
             "shopping", "shopkeeper", "v.future"),
            ("तेरे पास छुट्टा है?", "तुम्हारे पास छुट्टा है?", "आपके पास छुट्टा है?",
             "shopping", "shopkeeper", "pron.gen + existential"),
            ("थोड़ा कम कर।", "थोड़ा कम करो।", "थोड़ा कम कीजिए।",
             "shopping", "shopkeeper", "v.imp.karna"),
            ("मुझे रसीद दे।", "मुझे रसीद दो।", "मुझे रसीद दीजिए।",
             "shopping", "shopkeeper", "v.imp.dena"),
        ]),
        ("medical", [
            ("तुझे क्या हुआ?", "तुम्हें क्या हुआ?", "आपको क्या हुआ?",
             "medical", "patient", "pron.dat + v.past"),
            ("तूने दवा ली?", "तुमने दवा ली?", "आपने दवा ली?",
             "medical", "patient", "v.past.perfective"),
            ("तुझे कहाँ दर्द है?", "तुम्हें कहाँ दर्द है?", "आपको कहाँ दर्द है?",
             "medical", "patient", "pron.dat"),
            ("यहाँ लेट।", "यहाँ लेटो।", "यहाँ लेटिए।", "medical", "patient", "v.imp.letna"),
        ]),
        ("emergency", [
            ("जल्दी आ!", "जल्दी आओ!", "जल्दी आइए!", "emergency", "bystander", "v.imp.ana"),
            ("मेरी मदद कर!", "मेरी मदद करो!", "मेरी मदद कीजिए!",
             "emergency", "bystander", "v.imp.karna"),
            ("डॉक्टर बुला!", "डॉक्टर बुलाओ!", "डॉक्टर बुलाइए!",
             "emergency", "bystander", "v.imp.bulana"),
            ("यहाँ से हट!", "यहाँ से हटो!", "यहाँ से हटिए!",
             "emergency", "bystander", "v.imp.hatna"),
        ]),
        ("solidarity", [
            # Blueprint 13.2 #1: the family elder is high power AND high
            # solidarity. Hindi families commonly use तुम with grandparents,
            # where a stranger of the same age would get आप.
            ("तू कैसा है, दादा?", "तुम कैसे हो, दादा?", "आप कैसे हैं, दादा?",
             "family", "grandfather — तुम is normal within the family",
             "pron.nom + vocative"),
            ("तूने खाया, दादी?", "तुमने खाया, दादी?", "आपने खाया, दादी?",
             "family", "grandmother — तुम despite seniority", "v.past + vocative"),
            ("तू आएगा, चाचा?", "तुम आओगे, चाचा?", "आप आएँगे, चाचा?",
             "family", "uncle", "v.future + vocative"),
        ]),
    ],
    formal=[
        ("कृपया थोड़ा प्रतीक्षा कीजिए।", "request", "official"),
        ("कृपया यहाँ हस्ताक्षर कीजिए।", "admin", "official"),
        ("कृपया मेरी सहायता कीजिए।", "request", "official"),
        ("आपका हार्दिक धन्यवाद।", "greeting", "official"),
        ("मैं आपका आभारी हूँ।", "greeting", "official"),
        ("मुझे खेद है।", "apology", "official"),
        ("कृपया इस विषय पर विचार कीजिए।", "admin", "official"),
        ("कृपया अपना परिचय पत्र दिखाइए।", "admin", "official"),
        ("आपके सहयोग के लिए धन्यवाद।", "workplace", "official"),
        ("कृपया पंक्ति में खड़े रहिए।", "admin", "official"),
        ("आपका आवेदन स्वीकार कर लिया गया है।", "admin", "official"),
        ("महोदय, आपके समय के लिए धन्यवाद।", "workplace", "official"),
    ],
    no_marker=[
        ("आज मौसम बहुत अच्छा है।", "weather"),
        ("इसकी कीमत क्या है?", "shopping"),
        ("ट्रेन देर से चल रही है।", "transit"),
        ("मैं दिल्ली में रहता हूँ।", "smalltalk"),
        ("बारिश हो रही है।", "weather"),
        ("दुकान बंद है।", "shopping"),
        ("मेरा नाम राहुल है।", "greeting"),
        ("यहाँ बहुत भीड़ है।", "transit"),
        ("खाना स्वादिष्ट था।", "food"),
        ("मैं हिंदी सीख रहा हूँ।", "education"),
        ("बस अभी तक नहीं आई।", "transit"),
        ("मेरे सिर में दर्द है।", "medical"),
        ("अस्पताल पास ही है।", "medical"),
        ("रास्ता बंद है।", "transit"),
        ("हम कल जाएँगे।", "planning"),
        ("समय नहीं है।", "smalltalk"),
    ],
    hard=[
        ("बोलो।", 1, "imperative", "bare तुम imperative, no pronoun to lean on"),
        ("तुम बोलो।", 1, "statement", "same verb form; the pronoun makes it a statement"),
        ("बोल।", 0, "imperative", "तू imperative"),
        ("बोलिए।", 2, "imperative", "आप imperative"),
        ("जाओ।", 1, "imperative", "तुम"),
        ("जाइए।", 2, "imperative", "आप"),
        ("आप लोग कैसे हैं?", 2, "plural", "आप + लोग for explicit plural"),
        ("तुम लोग क्या कर रहे हो?", 1, "plural", "तुम + लोग"),
        ("तू और मैं जाएँगे।", 0, "coordination", "pronoun inside a coordinated subject"),
        ("आप और आपका परिवार आमंत्रित हैं।", 2, "coordination",
         "honorific repeated across a conjunction"),
        ("वह क्या करता है?", None, "third person",
         "वह is third person — no second-person marker, detection must abstain"),
    ],
)


# ==========================================================================
# Urdu — تو / تم / آپ  (same system as Hindi, different script)
# ==========================================================================

URDU = LanguageSet(
    code="ur",
    name="Urdu",
    columns=(0, 1, 2),
    confidence="medium",
    note="Grammatically parallel to Hindi; the lexicon leans Perso-Arabic and "
         "the script is right-to-left, which the boundary matcher has to handle.",
    triads=[
        ("pronouns", [
            ("تو کیسا ہے؟", "تم کیسے ہو؟", "آپ کیسے ہیں؟",
             "greeting", "friend", "pron.nom + cop.pres"),
            ("تیرا نام کیا ہے؟", "تمہارا نام کیا ہے؟", "آپ کا نام کیا ہے؟",
             "greeting", "stranger", "pron.gen"),
            ("تیرا گھر کہاں ہے؟", "تمہارا گھر کہاں ہے؟", "آپ کا گھر کہاں ہے؟",
             "smalltalk", "stranger", "pron.gen"),
            ("یہ تیرے لیے ہے۔", "یہ تمہارے لیے ہے۔", "یہ آپ کے لیے ہے۔",
             "everyday", "family", "pron.gen.obl"),
            ("مجھے تیری مدد چاہیے۔", "مجھے تمہاری مدد چاہیے۔", "مجھے آپ کی مدد چاہیے۔",
             "request", "colleague", "pron.gen.f"),
        ]),
        ("tense", [
            ("تو کیا کرتا ہے؟", "تم کیا کرتے ہو؟", "آپ کیا کرتے ہیں؟",
             "smalltalk", "stranger", "v.pres.habitual"),
            ("تو کہاں رہتا ہے؟", "تم کہاں رہتے ہو؟", "آپ کہاں رہتے ہیں؟",
             "smalltalk", "stranger", "v.pres.habitual"),
            ("تو کیا کر رہا ہے؟", "تم کیا کر رہے ہو؟", "آپ کیا کر رہے ہیں؟",
             "smalltalk", "friend", "v.pres.cont"),
            ("تو کب آئے گا؟", "تم کب آؤ گے؟", "آپ کب آئیں گے؟",
             "planning", "colleague", "v.future"),
            ("تو کہاں تھا؟", "تم کہاں تھے؟", "آپ کہاں تھے؟",
             "smalltalk", "friend", "v.past.cop"),
        ]),
        ("imperative", [
            ("یہاں آ۔", "یہاں آؤ۔", "یہاں آئیے۔", "everyday", "guest", "v.imp.ana"),
            ("یہاں بیٹھ۔", "یہاں بیٹھو۔", "یہاں بیٹھیے۔", "everyday", "guest", "v.imp.baithna"),
            ("ذرا سن۔", "ذرا سنو۔", "ذرا سنیے۔", "everyday", "stranger", "v.imp.sunna"),
            ("مجھے بتا۔", "مجھے بتاؤ۔", "مجھے بتائیے۔", "everyday", "colleague", "v.imp.batana"),
            ("تھوڑا رک۔", "تھوڑا رکو۔", "تھوڑا رکیے۔", "everyday", "stranger", "v.imp.rukna"),
        ]),
        ("modal", [
            ("تو میری مدد کر سکتا ہے؟", "تم میری مدد کر سکتے ہو؟",
             "آپ میری مدد کر سکتے ہیں؟", "request", "stranger", "v.sakna"),
            ("تجھے کیا چاہیے؟", "تمہیں کیا چاہیے؟", "آپ کو کیا چاہیے؟",
             "shopping", "shopkeeper", "v.chahiye"),
        ]),
        ("courtesy", [
            ("مجھے معاف کر۔", "مجھے معاف کرو۔", "مجھے معاف کیجیے۔",
             "apology", "stranger", "v.imp.karna"),
            ("تیرا شکریہ۔", "تمہارا شکریہ۔", "آپ کا شکریہ۔",
             "greeting", "acquaintance", "pron.gen"),
        ]),
    ],
    formal_lexical_groups=("courtesy",),
    formal=[
        ("براہ کرم تھوڑا انتظار کیجیے۔", "request", "official"),
        ("براہ کرم یہاں دستخط کیجیے۔", "admin", "official"),
        ("آپ کا بہت بہت شکریہ۔", "greeting", "official"),
        ("مجھے افسوس ہے۔", "apology", "official"),
        ("جناب، آپ کے وقت کا شکریہ۔", "workplace", "official"),
    ],
    no_marker=[
        ("آج موسم بہت اچھا ہے۔", "weather"),
        ("اس کی قیمت کیا ہے؟", "shopping"),
        ("ٹرین دیر سے چل رہی ہے۔", "transit"),
        ("میں لاہور میں رہتا ہوں۔", "smalltalk"),
        ("بارش ہو رہی ہے۔", "weather"),
        ("دکان بند ہے۔", "shopping"),
        ("وقت نہیں ہے۔", "smalltalk"),
    ],
    hard=[
        ("بول۔", 0, "imperative", "تو imperative"),
        ("بولو۔", 1, "imperative", "تم imperative"),
        ("بولیے۔", 2, "imperative", "آپ imperative"),
        ("وہ کیا کرتا ہے؟", None, "third person", "no second-person marker"),
    ],
)


# ==========================================================================
# Marathi — तू / तुम्ही / आपण
# ==========================================================================

MARATHI = LanguageSet(
    code="mr",
    name="Marathi",
    columns=(1, 2, 3),
    confidence="medium",
    note="आपण is genuinely a third level above तुम्ही, and is also the "
         "inclusive 'we' — a real ambiguity worth reviewing.",
    triads=[
        ("pronouns", [
            ("तू कसा आहेस?", "तुम्ही कसे आहात?", "आपण कसे आहात?",
             "greeting", "friend", "pron.nom + cop.pres"),
            ("तुझं नाव काय आहे?", "तुमचं नाव काय आहे?", "आपलं नाव काय आहे?",
             "greeting", "stranger", "pron.gen"),
            ("तुझं घर कुठे आहे?", "तुमचं घर कुठे आहे?", "आपलं घर कुठे आहे?",
             "smalltalk", "stranger", "pron.gen"),
            ("हे तुझ्यासाठी आहे.", "हे तुमच्यासाठी आहे.", "हे आपल्यासाठी आहे.",
             "everyday", "family", "pron.gen.obl"),
            ("मला तुझी मदत हवी.", "मला तुमची मदत हवी.", "मला आपली मदत हवी.",
             "request", "colleague", "pron.gen.f"),
        ]),
        ("tense", [
            ("तू काय करतोस?", "तुम्ही काय करता?", "आपण काय करता?",
             "smalltalk", "stranger", "v.pres.habitual"),
            ("तू कुठे राहतोस?", "तुम्ही कुठे राहता?", "आपण कुठे राहता?",
             "smalltalk", "stranger", "v.pres.habitual"),
            ("तू काय करत आहेस?", "तुम्ही काय करत आहात?", "आपण काय करत आहात?",
             "smalltalk", "friend", "v.pres.cont"),
            ("तू कधी येशील?", "तुम्ही कधी याल?", "आपण कधी याल?",
             "planning", "colleague", "v.future"),
            ("तू कुठे होतास?", "तुम्ही कुठे होतात?", "आपण कुठे होतात?",
             "smalltalk", "friend", "v.past.cop"),
        ]),
        ("imperative", [
            ("इथे ये.", "इथे या.", "इथे या.", "everyday", "guest", "v.imp.yene"),
            ("इथे बस.", "इथे बसा.", "इथे बसा.", "everyday", "guest", "v.imp.basne"),
            ("जरा ऐक.", "जरा ऐका.", "जरा ऐका.", "everyday", "stranger", "v.imp.aikne"),
            ("मला सांग.", "मला सांगा.", "मला सांगा.", "everyday", "colleague", "v.imp.sangne"),
            ("थोडं थांब.", "थोडं थांबा.", "थोडं थांबा.", "everyday", "stranger", "v.imp.thambne"),
        ]),
        ("modal", [
            ("तू मला मदत करू शकतोस का?", "तुम्ही मला मदत करू शकता का?",
             "आपण मला मदत करू शकता का?", "request", "stranger", "v.shakne"),
            ("तुला काय हवं?", "तुम्हाला काय हवं?", "आपल्याला काय हवं?",
             "shopping", "shopkeeper", "pron.dat"),
        ]),
        ("courtesy", [
            ("मला माफ कर.", "मला माफ करा.", "मला माफ करा.",
             "apology", "stranger", "v.imp.karne"),
            ("तुझे आभार.", "तुमचे आभार.", "आपले आभार.",
             "greeting", "acquaintance", "pron.gen"),
        ]),
    ],
    formal=[
        ("कृपया थोडा वेळ थांबा.", "request", "official"),
        ("कृपया इथे सही करा.", "admin", "official"),
        ("आपले मनःपूर्वक आभार.", "greeting", "official"),
        ("मला क्षमा करा.", "apology", "official"),
        ("आपल्या सहकार्याबद्दल धन्यवाद.", "workplace", "official"),
    ],
    no_marker=[
        ("आज हवामान छान आहे.", "weather"),
        ("याची किंमत काय आहे?", "shopping"),
        ("ट्रेन उशिरा आहे.", "transit"),
        ("मी पुण्यात राहतो.", "smalltalk"),
        ("पाऊस पडत आहे.", "weather"),
        ("दुकान बंद आहे.", "shopping"),
        ("वेळ नाही.", "smalltalk"),
    ],
    hard=[
        ("बोल.", 1, "imperative", "तू imperative"),
        ("बोला.", 2, "imperative", "तुम्ही imperative"),
        ("आपण जाऊया.", None, "inclusive we",
         "आपण here is inclusive 'we', not the honorific 'you' — a real ambiguity"),
        ("तो काय करतो?", None, "third person", "no second-person marker"),
    ],
)


# ==========================================================================
# Gujarati — તું / તમે / આપ
# ==========================================================================

GUJARATI = LanguageSet(
    code="gu",
    name="Gujarati",
    columns=(1, 2, 3),
    confidence="medium",
    triads=[
        ("pronouns", [
            ("તું કેમ છે?", "તમે કેમ છો?", "આપ કેમ છો?",
             "greeting", "friend", "pron.nom + cop.pres"),
            ("તારું નામ શું છે?", "તમારું નામ શું છે?", "આપનું નામ શું છે?",
             "greeting", "stranger", "pron.gen"),
            ("તારું ઘર ક્યાં છે?", "તમારું ઘર ક્યાં છે?", "આપનું ઘર ક્યાં છે?",
             "smalltalk", "stranger", "pron.gen"),
            ("આ તારા માટે છે.", "આ તમારા માટે છે.", "આ આપના માટે છે.",
             "everyday", "family", "pron.gen.obl"),
        ]),
        ("tense", [
            ("તું શું કરે છે?", "તમે શું કરો છો?", "આપ શું કરો છો?",
             "smalltalk", "stranger", "v.pres.habitual"),
            ("તું ક્યાં રહે છે?", "તમે ક્યાં રહો છો?", "આપ ક્યાં રહો છો?",
             "smalltalk", "stranger", "v.pres.habitual"),
            ("તું ક્યારે આવીશ?", "તમે ક્યારે આવશો?", "આપ ક્યારે આવશો?",
             "planning", "colleague", "v.future"),
        ]),
        ("imperative", [
            ("અહીં આવ.", "અહીં આવો.", "અહીં આવજો.", "everyday", "guest", "v.imp.avvu"),
            ("અહીં બેસ.", "અહીં બેસો.", "અહીં બેસજો.", "everyday", "guest", "v.imp.besvu"),
            ("મને કહે.", "મને કહો.", "મને કહેજો.", "everyday", "colleague", "v.imp.kahevu"),
            ("થોડું થોભ.", "થોડું થોભો.", "થોડું થોભજો.", "everyday", "stranger", "v.imp.thobhvu"),
        ]),
        ("courtesy", [
            ("મને માફ કર.", "મને માફ કરો.", "મને માફ કરજો.",
             "apology", "stranger", "v.imp.karvu"),
            ("તારો આભાર.", "તમારો આભાર.", "આપનો આભાર.",
             "greeting", "acquaintance", "pron.gen"),
        ]),
    ],
    formal=[
        ("કૃપા કરીને થોડી રાહ જુઓ.", "request", "official"),
        ("કૃપા કરીને અહીં સહી કરો.", "admin", "official"),
        ("આપનો ખૂબ ખૂબ આભાર.", "greeting", "official"),
        ("મને ક્ષમા કરશો.", "apology", "official"),
    ],
    no_marker=[
        ("આજે હવામાન સરસ છે.", "weather"),
        ("આની કિંમત શું છે?", "shopping"),
        ("ટ્રેન મોડી છે.", "transit"),
        ("હું અમદાવાદમાં રહું છું.", "smalltalk"),
        ("વરસાદ પડે છે.", "weather"),
        ("સમય નથી.", "smalltalk"),
    ],
    hard=[
        ("આપ.", None, "homograph",
         "આપ is both the formal pronoun 'you' and the imperative 'give!' — "
         "bare, it is the verb"),
        ("તે શું કરે છે?", None, "third person", "no second-person marker"),
    ],
)


# ==========================================================================
# Punjabi — ਤੂੰ / ਤੁਸੀਂ  (one polite pronoun; Formal is lexical)
# ==========================================================================

PUNJABI = LanguageSet(
    code="pa",
    name="Punjabi",
    columns=(1, 2, 2),
    confidence="medium",
    note="ਤੁਸੀਂ covers both Polite and Formal; ਜੀ and ਕਿਰਪਾ ਕਰਕੇ carry the "
         "extra deference lexically.",
    triads=[
        ("pronouns", [
            ("ਤੂੰ ਕਿਵੇਂ ਹੈਂ?", "ਤੁਸੀਂ ਕਿਵੇਂ ਹੋ?", "ਤੁਸੀਂ ਕਿਵੇਂ ਹੋ?",
             "greeting", "friend", "pron.nom + cop.pres"),
            ("ਤੇਰਾ ਨਾਂ ਕੀ ਹੈ?", "ਤੁਹਾਡਾ ਨਾਂ ਕੀ ਹੈ?", "ਤੁਹਾਡਾ ਨਾਂ ਕੀ ਹੈ?",
             "greeting", "stranger", "pron.gen"),
            ("ਤੇਰਾ ਘਰ ਕਿੱਥੇ ਹੈ?", "ਤੁਹਾਡਾ ਘਰ ਕਿੱਥੇ ਹੈ?", "ਤੁਹਾਡਾ ਘਰ ਕਿੱਥੇ ਹੈ?",
             "smalltalk", "stranger", "pron.gen"),
            ("ਇਹ ਤੇਰੇ ਲਈ ਹੈ।", "ਇਹ ਤੁਹਾਡੇ ਲਈ ਹੈ।", "ਇਹ ਤੁਹਾਡੇ ਲਈ ਹੈ।",
             "everyday", "family", "pron.gen.obl"),
        ]),
        ("tense", [
            ("ਤੂੰ ਕੀ ਕਰਦਾ ਹੈਂ?", "ਤੁਸੀਂ ਕੀ ਕਰਦੇ ਹੋ?", "ਤੁਸੀਂ ਕੀ ਕਰਦੇ ਹੋ?",
             "smalltalk", "stranger", "v.pres.habitual"),
            ("ਤੂੰ ਕਿੱਥੇ ਰਹਿੰਦਾ ਹੈਂ?", "ਤੁਸੀਂ ਕਿੱਥੇ ਰਹਿੰਦੇ ਹੋ?", "ਤੁਸੀਂ ਕਿੱਥੇ ਰਹਿੰਦੇ ਹੋ?",
             "smalltalk", "stranger", "v.pres.habitual"),
            ("ਤੂੰ ਕਦੋਂ ਆਵੇਂਗਾ?", "ਤੁਸੀਂ ਕਦੋਂ ਆਓਗੇ?", "ਤੁਸੀਂ ਕਦੋਂ ਆਓਗੇ?",
             "planning", "colleague", "v.future"),
        ]),
        ("imperative", [
            ("ਇੱਥੇ ਆ।", "ਇੱਥੇ ਆਓ।", "ਇੱਥੇ ਆਓ।", "everyday", "guest", "v.imp.auna"),
            ("ਇੱਥੇ ਬੈਠ।", "ਇੱਥੇ ਬੈਠੋ।", "ਇੱਥੇ ਬੈਠੋ।", "everyday", "guest", "v.imp.baithna"),
            ("ਮੈਨੂੰ ਦੱਸ।", "ਮੈਨੂੰ ਦੱਸੋ।", "ਮੈਨੂੰ ਦੱਸੋ।", "everyday", "colleague", "v.imp.dassna"),
        ]),
        ("courtesy", [
            ("ਮੈਨੂੰ ਮਾਫ਼ ਕਰ।", "ਮੈਨੂੰ ਮਾਫ਼ ਕਰੋ।", "ਮੈਨੂੰ ਮਾਫ਼ ਕਰੋ।",
             "apology", "stranger", "v.imp.karna"),
            ("ਤੇਰਾ ਧੰਨਵਾਦ।", "ਤੁਹਾਡਾ ਧੰਨਵਾਦ।", "ਤੁਹਾਡਾ ਧੰਨਵਾਦ।",
             "greeting", "acquaintance", "pron.gen"),
        ]),
    ],
    formal=[
        ("ਕਿਰਪਾ ਕਰਕੇ ਥੋੜ੍ਹਾ ਇੰਤਜ਼ਾਰ ਕਰੋ।", "request", "official"),
        ("ਕਿਰਪਾ ਕਰਕੇ ਇੱਥੇ ਦਸਤਖਤ ਕਰੋ।", "admin", "official"),
        ("ਤੁਹਾਡਾ ਬਹੁਤ ਬਹੁਤ ਧੰਨਵਾਦ।", "greeting", "official"),
        ("ਮੈਨੂੰ ਅਫ਼ਸੋਸ ਹੈ।", "apology", "official"),
    ],
    no_marker=[
        ("ਅੱਜ ਮੌਸਮ ਬਹੁਤ ਵਧੀਆ ਹੈ।", "weather"),
        ("ਇਸ ਦੀ ਕੀਮਤ ਕੀ ਹੈ?", "shopping"),
        ("ਗੱਡੀ ਲੇਟ ਹੈ।", "transit"),
        ("ਮੈਂ ਅੰਮ੍ਰਿਤਸਰ ਵਿੱਚ ਰਹਿੰਦਾ ਹਾਂ।", "smalltalk"),
        ("ਮੀਂਹ ਪੈ ਰਿਹਾ ਹੈ।", "weather"),
    ],
    hard=[
        ("ਬੋਲ।", 1, "imperative", "ਤੂੰ imperative"),
        ("ਬੋਲੋ।", 2, "imperative", "ਤੁਸੀਂ imperative"),
        ("ਉਹ ਕੀ ਕਰਦਾ ਹੈ?", None, "third person", "no second-person marker"),
    ],
)


# ==========================================================================
# Nepali — तँ / तिमी / तपाईं  (हजुर above तपाईं)
# ==========================================================================

NEPALI = LanguageSet(
    code="ne",
    name="Nepali",
    columns=(0, 1, 2),
    confidence="low",
    formal_distinct=True,
    note="Four levels in practice: तँ / तिमी / तपाईं / हजुर. हजुर rows are in "
         "`formal`. Verb agreement is elaborate — review the endings closely.",
    triads=[
        ("pronouns", [
            ("तँ कस्तो छस्?", "तिमी कस्तो छौ?", "तपाईं कस्तो हुनुहुन्छ?",
             "greeting", "friend", "pron.nom + cop.pres"),
            ("तेरो नाम के हो?", "तिम्रो नाम के हो?", "तपाईंको नाम के हो?",
             "greeting", "stranger", "pron.gen"),
            ("तेरो घर कहाँ छ?", "तिम्रो घर कहाँ छ?", "तपाईंको घर कहाँ छ?",
             "smalltalk", "stranger", "pron.gen"),
        ]),
        ("tense", [
            ("तँ के गर्छस्?", "तिमी के गर्छौ?", "तपाईं के गर्नुहुन्छ?",
             "smalltalk", "stranger", "v.pres.habitual"),
            ("तँ कहाँ बस्छस्?", "तिमी कहाँ बस्छौ?", "तपाईं कहाँ बस्नुहुन्छ?",
             "smalltalk", "stranger", "v.pres.habitual"),
            ("तँ कहिले आउँछस्?", "तिमी कहिले आउँछौ?", "तपाईं कहिले आउनुहुन्छ?",
             "planning", "colleague", "v.future"),
        ]),
        ("imperative", [
            ("यहाँ आइज।", "यहाँ आऊ।", "यहाँ आउनुहोस्।", "everyday", "guest", "v.imp.aunu"),
            ("यहाँ बस्।", "यहाँ बस।", "यहाँ बस्नुहोस्।", "everyday", "guest", "v.imp.basnu"),
            ("मलाई भन्।", "मलाई भन।", "मलाई भन्नुहोस्।", "everyday", "colleague", "v.imp.bhannu"),
        ]),
        ("courtesy", [
            ("मलाई माफ गर्।", "मलाई माफ गर।", "मलाई माफ गर्नुहोस्।",
             "apology", "stranger", "v.imp.garnu"),
            ("तेरो धन्यवाद।", "तिम्रो धन्यवाद।", "तपाईंलाई धन्यवाद।",
             "greeting", "acquaintance", "pron.gen"),
        ]),
    ],
    formal=[
        ("कृपया एकछिन पर्खनुहोस्।", "request", "official"),
        ("कृपया यहाँ हस्ताक्षर गर्नुहोस्।", "admin", "official"),
        ("हजुरलाई धेरै धन्यवाद।", "greeting", "official"),
        ("म क्षमाप्रार्थी छु।", "apology", "official"),
    ],
    no_marker=[
        ("आज मौसम राम्रो छ।", "weather"),
        ("यसको मूल्य कति हो?", "shopping"),
        ("म काठमाडौंमा बस्छु।", "smalltalk"),
        ("पानी परिरहेको छ।", "weather"),
        ("समय छैन।", "smalltalk"),
    ],
    hard=[
        ("भन।", 1, "imperative", "तिमी imperative"),
        ("भन्नुहोस्।", 2, "imperative", "तपाईं imperative"),
        ("उसले के गर्छ?", None, "third person", "no second-person marker"),
    ],
)


# ==========================================================================
# Odia — ତୁ / ତୁମେ / ଆପଣ
# ==========================================================================

ODIA = LanguageSet(
    code="or",
    name="Odia",
    columns=(0, 1, 2),
    confidence="low",
    note="Three levels parallel to Bengali. Verb endings drafted from standard "
         "grammar; every row needs a speaker's eye.",
    triads=[
        ("pronouns", [
            ("ତୁ କେମିତି ଅଛୁ?", "ତୁମେ କେମିତି ଅଛ?", "ଆପଣ କେମିତି ଅଛନ୍ତି?",
             "greeting", "friend", "pron.nom + cop.pres"),
            ("ତୋର ନାଁ କଣ?", "ତୁମର ନାଁ କଣ?", "ଆପଣଙ୍କ ନାଁ କଣ?",
             "greeting", "stranger", "pron.gen"),
            ("ତୋର ଘର କେଉଁଠି?", "ତୁମର ଘର କେଉଁଠି?", "ଆପଣଙ୍କ ଘର କେଉଁଠି?",
             "smalltalk", "stranger", "pron.gen"),
        ]),
        ("tense", [
            ("ତୁ କଣ କରୁଛୁ?", "ତୁମେ କଣ କରୁଛ?", "ଆପଣ କଣ କରୁଛନ୍ତି?",
             "smalltalk", "friend", "v.pres.cont"),
            ("ତୁ କେଉଁଠି ରହୁଛୁ?", "ତୁମେ କେଉଁଠି ରହୁଛ?", "ଆପଣ କେଉଁଠି ରହୁଛନ୍ତି?",
             "smalltalk", "stranger", "v.pres.cont"),
            ("ତୁ କେବେ ଆସିବୁ?", "ତୁମେ କେବେ ଆସିବ?", "ଆପଣ କେବେ ଆସିବେ?",
             "planning", "colleague", "v.future"),
        ]),
        ("imperative", [
            ("ଏଠିକି ଆସ୍।", "ଏଠିକି ଆସ।", "ଏଠିକି ଆସନ୍ତୁ।", "everyday", "guest", "v.imp.asiba"),
            ("ଏଠି ବସ୍।", "ଏଠି ବସ।", "ଏଠି ବସନ୍ତୁ।", "everyday", "guest", "v.imp.basiba"),
            ("ମୋତେ କୁହ୍।", "ମୋତେ କୁହ।", "ମୋତେ କୁହନ୍ତୁ।", "everyday", "colleague", "v.imp.kahiba"),
        ]),
        ("courtesy", [
            ("ମୋତେ କ୍ଷମା କର୍।", "ମୋତେ କ୍ଷମା କର।", "ମୋତେ କ୍ଷମା କରନ୍ତୁ।",
             "apology", "stranger", "v.imp.kariba"),
            ("ତୋର ଧନ୍ୟବାଦ।", "ତୁମର ଧନ୍ୟବାଦ।", "ଆପଣଙ୍କୁ ଧନ୍ୟବାଦ।",
             "greeting", "acquaintance", "pron.gen"),
        ]),
    ],
    formal=[
        ("ଦୟାକରି ଟିକେ ଅପେକ୍ଷା କରନ୍ତୁ।", "request", "official"),
        ("ଦୟାକରି ଏଠାରେ ସ୍ୱାକ୍ଷର କରନ୍ତୁ।", "admin", "official"),
        ("ଆପଣଙ୍କୁ ବହୁତ ଧନ୍ୟବାଦ।", "greeting", "official"),
    ],
    no_marker=[
        ("ଆଜି ପାଗ ଭଲ ଅଛି।", "weather"),
        ("ଏହାର ଦାମ କେତେ?", "shopping"),
        ("ମୁଁ ଭୁବନେଶ୍ୱରରେ ରହେ।", "smalltalk"),
        ("ବର୍ଷା ହେଉଛି।", "weather"),
        ("ସମୟ ନାହିଁ।", "smalltalk"),
    ],
    hard=[
        ("କୁହ।", 1, "imperative", "ତୁମେ imperative"),
        ("କୁହନ୍ତୁ।", 2, "imperative", "ଆପଣ imperative"),
        ("ସେ କଣ କରୁଛି?", None, "third person", "no second-person marker"),
    ],
)


# ==========================================================================
# Assamese — তই / তুমি / আপুনি
# ==========================================================================

ASSAMESE = LanguageSet(
    code="as",
    name="Assamese",
    columns=(0, 1, 2),
    confidence="low",
    note="Shares the Bengali script but not the alphabet — ৰ and ৱ are "
         "Assamese-only, which is what the language detector keys on. Verb "
         "morphology differs from Bengali more than the script suggests.",
    triads=[
        ("pronouns", [
            ("তই কেনে আছ?", "তুমি কেনে আছা?", "আপুনি কেনে আছে?",
             "greeting", "friend", "pron.nom + cop.pres"),
            ("তোৰ নাম কি?", "তোমাৰ নাম কি?", "আপোনাৰ নাম কি?",
             "greeting", "stranger", "pron.gen"),
            ("তোৰ ঘৰ ক'ত?", "তোমাৰ ঘৰ ক'ত?", "আপোনাৰ ঘৰ ক'ত?",
             "smalltalk", "stranger", "pron.gen"),
        ]),
        ("tense", [
            ("তই কি কৰি আছ?", "তুমি কি কৰি আছা?", "আপুনি কি কৰি আছে?",
             "smalltalk", "friend", "v.pres.cont"),
            ("তই ক'ত থাক?", "তুমি ক'ত থাকা?", "আপুনি ক'ত থাকে?",
             "smalltalk", "stranger", "v.pres.habitual"),
            ("তই কেতিয়া আহিবি?", "তুমি কেতিয়া আহিবা?", "আপুনি কেতিয়া আহিব?",
             "planning", "colleague", "v.future"),
        ]),
        ("imperative", [
            ("ইয়ালৈ আহ।", "ইয়ালৈ আহা।", "ইয়ালৈ আহক।", "everyday", "guest", "v.imp.aha"),
            ("ইয়াত বহ।", "ইয়াত বহা।", "ইয়াত বহক।", "everyday", "guest", "v.imp.baha"),
            # The তই and তুমি columns were both কোৱা in an earlier draft, which
            # asked the detector to tell two identical strings apart.
            ("মোক ক।", "মোক কোৱা।", "মোক কওক।", "everyday", "colleague", "v.imp.koa"),
        ]),
        ("courtesy", [
            ("মোক ক্ষমা কৰ।", "মোক ক্ষমা কৰা।", "মোক ক্ষমা কৰক।",
             "apology", "stranger", "v.imp.kora"),
            ("তোক ধন্যবাদ।", "তোমাক ধন্যবাদ।", "আপোনাক ধন্যবাদ।",
             "greeting", "acquaintance", "pron.acc"),
        ]),
    ],
    formal=[
        ("অনুগ্ৰহ কৰি অলপ ৰ'ব।", "request", "official"),
        ("অনুগ্ৰহ কৰি ইয়াত স্বাক্ষৰ কৰক।", "admin", "official"),
        ("আপোনাক বহুত ধন্যবাদ।", "greeting", "official"),
    ],
    no_marker=[
        ("আজি বতৰ ভাল।", "weather"),
        ("ইয়াৰ দাম কিমান?", "shopping"),
        ("মই গুৱাহাটীত থাকোঁ।", "smalltalk"),
        ("বৰষুণ দি আছে।", "weather"),
        ("সময় নাই।", "smalltalk"),
    ],
    hard=[
        ("কোৱা।", 1, "imperative", "তুমি imperative"),
        ("কওক।", 2, "imperative", "আপুনি imperative"),
        ("তেওঁ কি কৰে?", None, "third person",
         "তেওঁ is third-person honorific — not a second-person marker"),
    ],
)


ALL = [HINDI, URDU, MARATHI, GUJARATI, PUNJABI, NEPALI, ODIA, ASSAMESE]
