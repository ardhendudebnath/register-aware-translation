"""
Dravidian register sets: Tamil, Telugu, Kannada, Malayalam.

None of these has any published register benchmark at all — this is the group
the blueprint singles out as completely unserved.

Tamil, Telugu and Kannada share a two-pronoun system (நீ/நீங்கள்,
నువ్వు/మీరు, ನೀನು/ನೀವು), so their triads use columns ``(1, 2, 2)``: the third
column repeats the second and the extra deference is carried lexically in
``formal``. Malayalam genuinely has three (നീ / നിങ്ങൾ / താങ്കൾ) and gets
``(1, 2, 3)``.

The verb morphology in all four is where the risk is. Pronouns are easy to get
right from a grammar; agreement suffixes are not, and these are drafted rather
than spoken.
"""

from __future__ import annotations

from ..common import LanguageSet

# ==========================================================================
# Tamil — நீ / நீங்கள்
# ==========================================================================

TAMIL = LanguageSet(
    code="ta",
    name="Tamil",
    columns=(1, 2, 2),
    confidence="medium",
    note="நீங்கள் covers Polite and Formal; தயவுசெய்து and சார்/மேடம் carry "
         "the extra deference. Spoken Tamil differs sharply from the written "
         "forms drafted here.",
    triads=[
        ("pronouns", [
            ("நீ எப்படி இருக்கிறாய்?", "நீங்கள் எப்படி இருக்கிறீர்கள்?",
             "நீங்கள் எப்படி இருக்கிறீர்கள்?",
             "greeting", "friend", "pron.nom + v.pres"),
            ("உன் பெயர் என்ன?", "உங்கள் பெயர் என்ன?", "உங்கள் பெயர் என்ன?",
             "greeting", "stranger", "pron.gen"),
            ("உன் வீடு எங்கே?", "உங்கள் வீடு எங்கே?", "உங்கள் வீடு எங்கே?",
             "smalltalk", "stranger", "pron.gen"),
            ("இது உனக்கு.", "இது உங்களுக்கு.", "இது உங்களுக்கு.",
             "everyday", "family", "pron.dat"),
            ("எனக்கு உன் உதவி வேண்டும்.", "எனக்கு உங்கள் உதவி வேண்டும்.",
             "எனக்கு உங்கள் உதவி வேண்டும்.", "request", "colleague", "pron.gen"),
        ]),
        ("tense", [
            ("நீ என்ன செய்கிறாய்?", "நீங்கள் என்ன செய்கிறீர்கள்?",
             "நீங்கள் என்ன செய்கிறீர்கள்?", "smalltalk", "stranger", "v.pres"),
            ("நீ எங்கே இருக்கிறாய்?", "நீங்கள் எங்கே இருக்கிறீர்கள்?",
             "நீங்கள் எங்கே இருக்கிறீர்கள்?", "smalltalk", "friend", "v.pres"),
            ("நீ எப்போது வருவாய்?", "நீங்கள் எப்போது வருவீர்கள்?",
             "நீங்கள் எப்போது வருவீர்கள்?", "planning", "colleague", "v.future"),
            ("நீ சாப்பிட்டாயா?", "நீங்கள் சாப்பிட்டீர்களா?",
             "நீங்கள் சாப்பிட்டீர்களா?", "food", "family", "v.past"),
        ]),
        ("imperative", [
            ("இங்கே வா.", "இங்கே வாருங்கள்.", "இங்கே வாருங்கள்.",
             "everyday", "guest", "v.imp.varu"),
            ("இங்கே உட்கார்.", "இங்கே உட்காருங்கள்.", "இங்கே உட்காருங்கள்.",
             "everyday", "guest", "v.imp.utkaar"),
            ("என்னிடம் சொல்.", "என்னிடம் சொல்லுங்கள்.", "என்னிடம் சொல்லுங்கள்.",
             "everyday", "colleague", "v.imp.sollu"),
            ("கொஞ்சம் இரு.", "கொஞ்சம் இருங்கள்.", "கொஞ்சம் இருங்கள்.",
             "everyday", "stranger", "v.imp.iru"),
            ("இதை பார்.", "இதை பாருங்கள்.", "இதை பாருங்கள்.",
             "everyday", "colleague", "v.imp.paar"),
        ]),
        ("courtesy", [
            ("என்னை மன்னி.", "என்னை மன்னியுங்கள்.", "என்னை மன்னியுங்கள்.",
             "apology", "stranger", "v.imp.manni"),
            ("உனக்கு நன்றி.", "உங்களுக்கு நன்றி.", "உங்களுக்கு நன்றி.",
             "greeting", "acquaintance", "pron.dat"),
        ]),
        ("transit", [
            ("நீ எங்கே போகிறாய்?", "நீங்கள் எங்கே போகிறீர்கள்?",
             "நீங்கள் எங்கே போகிறீர்கள்?", "transit", "fellow traveller", "v.pres"),
            ("இங்கே இறங்கு.", "இங்கே இறங்குங்கள்.", "இங்கே இறங்குங்கள்.",
             "transit", "driver", "v.imp.irangu"),
        ]),
    ],
    formal_lexical_groups=("courtesy",),
    formal=[
        ("தயவுசெய்து கொஞ்சம் காத்திருங்கள்.", "request", "official"),
        ("தயவுசெய்து இங்கே கையெழுத்திடுங்கள்.", "admin", "official"),
        ("உங்களுக்கு மிக்க நன்றி.", "greeting", "official"),
    ],
    no_marker=[
        ("இன்று வானிலை நன்றாக இருக்கிறது.", "weather"),
        ("இதன் விலை என்ன?", "shopping"),
        ("ரயில் தாமதமாக இருக்கிறது.", "transit"),
        ("நான் சென்னையில் இருக்கிறேன்.", "smalltalk"),
        ("மழை பெய்கிறது.", "weather"),
        ("கடை மூடப்பட்டுள்ளது.", "shopping"),
        ("நேரம் இல்லை.", "smalltalk"),
    ],
    hard=[
        ("வா.", 1, "imperative", "நீ imperative"),
        ("வாருங்கள்.", 2, "imperative", "நீங்கள் imperative"),
        ("அவன் என்ன செய்கிறான்?", None, "third person", "no second-person marker"),
        # These were filed as Formal because they are things you say to an
        # official. That is a fact about the context, not about the sentence:
        # both are bare honorific forms carrying no Formal marker, and both are
        # equally at home with a stranger. Formal in Tamil is reached
        # lexically — தயவுசெய்து, மிக்க — and neither has it.
        ("மன்னிக்கவும்.", 2, "honorific, no lexical Formal",
         "honorific form; Formal needs தயவுசெய்து or மிக்க"),
        ("உங்கள் ஒத்துழைப்புக்கு நன்றி.", 2, "honorific, no lexical Formal",
         "உங்கள் is honorific; plain நன்றி does not reach Formal"),
    ],
)


# ==========================================================================
# Telugu — నువ్వు / మీరు
# ==========================================================================

TELUGU = LanguageSet(
    code="te",
    name="Telugu",
    columns=(1, 2, 2),
    confidence="medium",
    triads=[
        ("pronouns", [
            ("నువ్వు ఎలా ఉన్నావు?", "మీరు ఎలా ఉన్నారు?", "మీరు ఎలా ఉన్నారు?",
             "greeting", "friend", "pron.nom + v.pres"),
            ("నీ పేరు ఏమిటి?", "మీ పేరు ఏమిటి?", "మీ పేరు ఏమిటి?",
             "greeting", "stranger", "pron.gen"),
            ("నీ ఇల్లు ఎక్కడ?", "మీ ఇల్లు ఎక్కడ?", "మీ ఇల్లు ఎక్కడ?",
             "smalltalk", "stranger", "pron.gen"),
            ("ఇది నీ కోసం.", "ఇది మీ కోసం.", "ఇది మీ కోసం.",
             "everyday", "family", "pron.gen"),
        ]),
        ("tense", [
            ("నువ్వు ఏమి చేస్తున్నావు?", "మీరు ఏమి చేస్తున్నారు?",
             "మీరు ఏమి చేస్తున్నారు?", "smalltalk", "friend", "v.pres.cont"),
            ("నువ్వు ఎక్కడ ఉంటావు?", "మీరు ఎక్కడ ఉంటారు?", "మీరు ఎక్కడ ఉంటారు?",
             "smalltalk", "stranger", "v.pres.habitual"),
            ("నువ్వు ఎప్పుడు వస్తావు?", "మీరు ఎప్పుడు వస్తారు?",
             "మీరు ఎప్పుడు వస్తారు?", "planning", "colleague", "v.future"),
            ("నువ్వు తిన్నావా?", "మీరు తిన్నారా?", "మీరు తిన్నారా?",
             "food", "family", "v.past"),
        ]),
        ("imperative", [
            ("ఇక్కడికి రా.", "ఇక్కడికి రండి.", "ఇక్కడికి రండి.",
             "everyday", "guest", "v.imp.raa"),
            ("ఇక్కడ కూర్చో.", "ఇక్కడ కూర్చోండి.", "ఇక్కడ కూర్చోండి.",
             "everyday", "guest", "v.imp.kurcho"),
            ("నాకు చెప్పు.", "నాకు చెప్పండి.", "నాకు చెప్పండి.",
             "everyday", "colleague", "v.imp.cheppu"),
            ("కొంచెం ఆగు.", "కొంచెం ఆగండి.", "కొంచెం ఆగండి.",
             "everyday", "stranger", "v.imp.aagu"),
        ]),
        ("courtesy", [
            ("నన్ను క్షమించు.", "నన్ను క్షమించండి.", "నన్ను క్షమించండి.",
             "apology", "stranger", "v.imp.kshaminchu"),
            ("నీకు ధన్యవాదాలు.", "మీకు ధన్యవాదాలు.", "మీకు ధన్యవాదాలు.",
             "greeting", "acquaintance", "pron.dat"),
        ]),
    ],
    formal_lexical_groups=("courtesy",),
    formal=[
        ("దయచేసి కొంచెం వేచి ఉండండి.", "request", "official"),
        ("దయచేసి ఇక్కడ సంతకం చేయండి.", "admin", "official"),
        ("మీకు చాలా ధన్యవాదాలు.", "greeting", "official"),
    ],
    no_marker=[
        ("ఈరోజు వాతావరణం బాగుంది.", "weather"),
        ("దీని ధర ఎంత?", "shopping"),
        ("రైలు ఆలస్యంగా ఉంది.", "transit"),
        ("నేను హైదరాబాద్‌లో ఉంటాను.", "smalltalk"),
        ("వర్షం పడుతోంది.", "weather"),
        ("సమయం లేదు.", "smalltalk"),
    ],
    hard=[
        ("చెప్పు.", 1, "imperative", "నువ్వు imperative"),
        ("చెప్పండి.", 2, "imperative", "మీరు imperative"),
        ("అతను ఏమి చేస్తాడు?", None, "third person", "no second-person marker"),
        # Filed as Formal for its context rather than its content: a bare
        # honorific with no Formal marker. Formal needs దయచేసి or చాలా.
        ("క్షమించండి.", 2, "honorific, no lexical Formal",
         "honorific form; Formal needs దయచేసి or చాలా"),
    ],
)


# ==========================================================================
# Kannada — ನೀನು / ನೀವು
# ==========================================================================

KANNADA = LanguageSet(
    code="kn",
    name="Kannada",
    columns=(1, 2, 2),
    confidence="medium",
    triads=[
        ("pronouns", [
            ("ನೀನು ಹೇಗಿದ್ದೀಯ?", "ನೀವು ಹೇಗಿದ್ದೀರಿ?", "ನೀವು ಹೇಗಿದ್ದೀರಿ?",
             "greeting", "friend", "pron.nom + v.pres"),
            ("ನಿನ್ನ ಹೆಸರು ಏನು?", "ನಿಮ್ಮ ಹೆಸರು ಏನು?", "ನಿಮ್ಮ ಹೆಸರು ಏನು?",
             "greeting", "stranger", "pron.gen"),
            ("ನಿನ್ನ ಮನೆ ಎಲ್ಲಿ?", "ನಿಮ್ಮ ಮನೆ ಎಲ್ಲಿ?", "ನಿಮ್ಮ ಮನೆ ಎಲ್ಲಿ?",
             "smalltalk", "stranger", "pron.gen"),
            ("ಇದು ನಿನಗೆ.", "ಇದು ನಿಮಗೆ.", "ಇದು ನಿಮಗೆ.",
             "everyday", "family", "pron.dat"),
        ]),
        ("tense", [
            ("ನೀನು ಏನು ಮಾಡುತ್ತಿದ್ದೀಯ?", "ನೀವು ಏನು ಮಾಡುತ್ತಿದ್ದೀರಿ?",
             "ನೀವು ಏನು ಮಾಡುತ್ತಿದ್ದೀರಿ?", "smalltalk", "friend", "v.pres.cont"),
            ("ನೀನು ಎಲ್ಲಿ ಇರುತ್ತೀಯ?", "ನೀವು ಎಲ್ಲಿ ಇರುತ್ತೀರಿ?",
             "ನೀವು ಎಲ್ಲಿ ಇರುತ್ತೀರಿ?", "smalltalk", "stranger", "v.pres.habitual"),
            ("ನೀನು ಯಾವಾಗ ಬರುತ್ತೀಯ?", "ನೀವು ಯಾವಾಗ ಬರುತ್ತೀರಿ?",
             "ನೀವು ಯಾವಾಗ ಬರುತ್ತೀರಿ?", "planning", "colleague", "v.future"),
        ]),
        ("imperative", [
            ("ಇಲ್ಲಿ ಬಾ.", "ಇಲ್ಲಿ ಬನ್ನಿ.", "ಇಲ್ಲಿ ಬನ್ನಿ.", "everyday", "guest", "v.imp.baa"),
            ("ಇಲ್ಲಿ ಕುಳಿತುಕೋ.", "ಇಲ್ಲಿ ಕುಳಿತುಕೊಳ್ಳಿ.", "ಇಲ್ಲಿ ಕುಳಿತುಕೊಳ್ಳಿ.",
             "everyday", "guest", "v.imp.kulitu"),
            ("ನನಗೆ ಹೇಳು.", "ನನಗೆ ಹೇಳಿ.", "ನನಗೆ ಹೇಳಿ.",
             "everyday", "colleague", "v.imp.helu"),
            ("ಸ್ವಲ್ಪ ನಿಲ್ಲು.", "ಸ್ವಲ್ಪ ನಿಲ್ಲಿ.", "ಸ್ವಲ್ಪ ನಿಲ್ಲಿ.",
             "everyday", "stranger", "v.imp.nillu"),
        ]),
        ("courtesy", [
            ("ನನ್ನನ್ನು ಕ್ಷಮಿಸು.", "ನನ್ನನ್ನು ಕ್ಷಮಿಸಿ.", "ನನ್ನನ್ನು ಕ್ಷಮಿಸಿ.",
             "apology", "stranger", "v.imp.kshamisu"),
            ("ನಿನಗೆ ಧನ್ಯವಾದ.", "ನಿಮಗೆ ಧನ್ಯವಾದ.", "ನಿಮಗೆ ಧನ್ಯವಾದ.",
             "greeting", "acquaintance", "pron.dat"),
        ]),
    ],
    formal_lexical_groups=("courtesy",),
    formal=[
        ("ದಯವಿಟ್ಟು ಸ್ವಲ್ಪ ಕಾಯಿರಿ.", "request", "official"),
        ("ದಯವಿಟ್ಟು ಇಲ್ಲಿ ಸಹಿ ಮಾಡಿ.", "admin", "official"),
        ("ನಿಮಗೆ ಅನಂತ ಧನ್ಯವಾದಗಳು.", "greeting", "official"),
    ],
    no_marker=[
        ("ಇಂದು ಹವಾಮಾನ ಚೆನ್ನಾಗಿದೆ.", "weather"),
        ("ಇದರ ಬೆಲೆ ಎಷ್ಟು?", "shopping"),
        ("ರೈಲು ತಡವಾಗಿದೆ.", "transit"),
        ("ನಾನು ಬೆಂಗಳೂರಿನಲ್ಲಿ ಇದ್ದೇನೆ.", "smalltalk"),
        ("ಮಳೆ ಬರುತ್ತಿದೆ.", "weather"),
        ("ಸಮಯ ಇಲ್ಲ.", "smalltalk"),
    ],
    hard=[
        ("ಹೇಳು.", 1, "imperative", "ನೀನು imperative"),
        ("ಹೇಳಿ.", 2, "imperative", "ನೀವು imperative"),
        ("ಅವನು ಏನು ಮಾಡುತ್ತಾನೆ?", None, "third person", "no second-person marker"),
        # Filed as Formal for its context rather than its content: a bare
        # honorific with no Formal marker. Formal needs ದಯವಿಟ್ಟು or ಅನಂತ.
        ("ಕ್ಷಮಿಸಿ.", 2, "honorific, no lexical Formal",
         "honorific form; Formal needs ದಯವಿಟ್ಟು or ಅನಂತ"),
    ],
)


# ==========================================================================
# Malayalam — നീ / നിങ്ങൾ / താങ്കൾ  (three genuine levels)
# ==========================================================================

MALAYALAM = LanguageSet(
    code="ml",
    name="Malayalam",
    columns=(1, 2, 3),
    confidence="medium",
    note="One of the few Dravidian languages with a genuine third level: "
         "താങ്കൾ sits above നിങ്ങൾ.",
    triads=[
        ("pronouns", [
            ("നീ എങ്ങനെ ഉണ്ട്?", "നിങ്ങൾ എങ്ങനെ ഉണ്ട്?", "താങ്കൾ എങ്ങനെ ഉണ്ട്?",
             "greeting", "friend", "pron.nom"),
            ("നിന്റെ പേര് എന്താണ്?", "നിങ്ങളുടെ പേര് എന്താണ്?",
             "താങ്കളുടെ പേര് എന്താണ്?", "greeting", "stranger", "pron.gen"),
            ("നിന്റെ വീട് എവിടെ?", "നിങ്ങളുടെ വീട് എവിടെ?",
             "താങ്കളുടെ വീട് എവിടെ?", "smalltalk", "stranger", "pron.gen"),
            ("ഇത് നിനക്ക്.", "ഇത് നിങ്ങൾക്ക്.", "ഇത് താങ്കൾക്ക്.",
             "everyday", "family", "pron.dat"),
        ]),
        ("tense", [
            ("നീ എന്ത് ചെയ്യുന്നു?", "നിങ്ങൾ എന്ത് ചെയ്യുന്നു?",
             "താങ്കൾ എന്ത് ചെയ്യുന്നു?", "smalltalk", "friend", "v.pres"),
            ("നീ എവിടെ താമസിക്കുന്നു?", "നിങ്ങൾ എവിടെ താമസിക്കുന്നു?",
             "താങ്കൾ എവിടെ താമസിക്കുന്നു?", "smalltalk", "stranger", "v.pres"),
            ("നീ എപ്പോൾ വരും?", "നിങ്ങൾ എപ്പോൾ വരും?", "താങ്കൾ എപ്പോൾ വരും?",
             "planning", "colleague", "v.future"),
        ]),
        ("imperative", [
            ("ഇവിടെ വാ.", "ഇവിടെ വരൂ.", "ഇവിടെ വരണം.", "everyday", "guest", "v.imp.varu"),
            ("ഇവിടെ ഇരി.", "ഇവിടെ ഇരിക്കൂ.", "ഇവിടെ ഇരിക്കണം.",
             "everyday", "guest", "v.imp.irikkuka"),
            ("എന്നോട് പറ.", "എന്നോട് പറയൂ.", "എന്നോട് പറയണം.",
             "everyday", "colleague", "v.imp.parayuka"),
        ]),
        ("courtesy", [
            ("എന്നോട് ക്ഷമിക്ക്.", "എന്നോട് ക്ഷമിക്കൂ.", "എന്നോട് ക്ഷമിക്കണം.",
             "apology", "stranger", "v.imp.kshamikkuka"),
            ("നിനക്ക് നന്ദി.", "നിങ്ങൾക്ക് നന്ദി.", "താങ്കൾക്ക് നന്ദി.",
             "greeting", "acquaintance", "pron.dat"),
        ]),
    ],
    formal=[
        ("ദയവായി അല്പം കാത്തിരിക്കൂ.", "request", "official"),
        ("ദയവായി ഇവിടെ ഒപ്പിടൂ.", "admin", "official"),
        ("താങ്കൾക്ക് വളരെ നന്ദി.", "greeting", "official"),
        ("ക്ഷമിക്കണം.", "apology", "official"),
    ],
    no_marker=[
        ("ഇന്ന് കാലാവസ്ഥ നല്ലതാണ്.", "weather"),
        ("ഇതിന്റെ വില എത്ര?", "shopping"),
        ("ട്രെയിൻ വൈകിയിരിക്കുന്നു.", "transit"),
        ("ഞാൻ കൊച്ചിയിൽ താമസിക്കുന്നു.", "smalltalk"),
        ("മഴ പെയ്യുന്നു.", "weather"),
        ("സമയമില്ല.", "smalltalk"),
    ],
    hard=[
        ("പറ.", 1, "imperative", "നീ imperative"),
        ("പറയൂ.", 2, "imperative", "നിങ്ങൾ imperative"),
        ("അവൻ എന്ത് ചെയ്യുന്നു?", None, "third person", "no second-person marker"),
    ],
)


ALL = [TAMIL, TELUGU, KANNADA, MALAYALAM]
