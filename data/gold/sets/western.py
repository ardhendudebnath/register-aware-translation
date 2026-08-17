"""
European and East Asian register sets: German, French, Spanish, Italian,
Portuguese, Japanese, English.

These are the languages that *do* have prior art — CoCoA-MT covers French,
German, Italian, Japanese and Spanish, and DeepL exposes a formality flag for
several. So the value here is not novelty but regression cover: these are the
tables with the trickiest disambiguation rules in the engine, and the sets
below deliberately target the cases that have broken before.

Specifically:

* German ``Sie`` is *you* before a plural verb and *she* before a singular one,
  and ``Ihr``/``ihr`` differ only by case.
* French ``vous`` is a subject, an object clitic or a tonic pronoun depending
  entirely on what precedes it, and ``votre`` is gender-neutral where ``ton`` /
  ``ta`` are not.
* Italian ``Lei`` is capitalised even mid-sentence, which is the only thing
  distinguishing it from ``lei`` (she) — and sentence-initially that cue is
  gone, which the engine documents as a known limitation.
* Portuguese runs three ways: ``tu`` / ``você`` / ``o senhor``.
* Japanese has three genuine levels and no word boundaries at all.

The ``hard`` rows in each are where the interesting failures live.
"""

from __future__ import annotations

from ..common import LanguageSet

# ==========================================================================
# German — du / Sie
# ==========================================================================

GERMAN = LanguageSet(
    code="de",
    name="German",
    columns=(1, 2, 2),
    confidence="high",
    note="Binary pronoun system; the extra formality at level 3 is lexical "
         "(Herzlichen Dank, Sehr geehrte).",
    triads=[
        ("pronouns", [
            ("Wie geht es dir?", "Wie geht es Ihnen?", "Wie geht es Ihnen?",
             "greeting", "friend", "pron.dat"),
            ("Wie heißt du?", "Wie heißen Sie?", "Wie heißen Sie?",
             "greeting", "stranger", "pron.nom + v.agree"),
            ("Wo wohnst du?", "Wo wohnen Sie?", "Wo wohnen Sie?",
             "smalltalk", "stranger", "pron.nom + v.agree"),
            ("Das ist für dich.", "Das ist für Sie.", "Das ist für Sie.",
             "everyday", "family", "pron.acc after preposition"),
            ("Ich sehe dich morgen.", "Ich sehe Sie morgen.", "Ich sehe Sie morgen.",
             "planning", "colleague", "pron.acc as object"),
            ("Ist das dein Buch?", "Ist das Ihr Buch?", "Ist das Ihr Buch?",
             "everyday", "colleague", "poss.nom"),
            ("Ich brauche deine Hilfe.", "Ich brauche Ihre Hilfe.",
             "Ich brauche Ihre Hilfe.", "request", "colleague", "poss.acc.f"),
        ]),
        ("verbs", [
            ("Du bist sehr nett.", "Sie sind sehr nett.", "Sie sind sehr nett.",
             "compliment", "acquaintance", "v.sein"),
            ("Du hast dein Buch vergessen.", "Sie haben Ihr Buch vergessen.",
             "Sie haben Ihr Buch vergessen.", "everyday", "colleague", "v.haben + poss"),
            ("Kannst du mir helfen?", "Können Sie mir helfen?",
             "Können Sie mir helfen?", "request", "stranger", "v.koennen.inv"),
            ("Verstehst du mich?", "Verstehen Sie mich?", "Verstehen Sie mich?",
             "smalltalk", "colleague", "v.verstehen.inv"),
            ("Wann kommst du?", "Wann kommen Sie?", "Wann kommen Sie?",
             "planning", "colleague", "v.kommen"),
            ("Was machst du?", "Was machen Sie?", "Was machen Sie?",
             "smalltalk", "stranger", "v.machen"),
            ("Sprichst du Deutsch?", "Sprechen Sie Deutsch?", "Sprechen Sie Deutsch?",
             "smalltalk", "stranger", "v.sprechen.inv"),
            ("Möchtest du einen Kaffee?", "Möchten Sie einen Kaffee?",
             "Möchten Sie einen Kaffee?", "hospitality", "guest", "v.moechten.inv"),
        ]),
        ("courtesy", [
            ("Entschuldige bitte.", "Entschuldigen Sie bitte.",
             "Entschuldigen Sie bitte.", "apology", "stranger", "v.imp"),
            ("Danke dir.", "Danke Ihnen.", "Danke Ihnen.",
             "greeting", "acquaintance", "pron.dat"),
        ]),
        ("transit", [
            ("Wohin fährst du?", "Wohin fahren Sie?", "Wohin fahren Sie?",
             "transit", "fellow traveller", "v.fahren"),
            ("Hast du eine Fahrkarte?", "Haben Sie eine Fahrkarte?",
             "Haben Sie eine Fahrkarte?", "transit", "conductor", "v.haben.inv"),
        ]),
    ],
    formal=[
        ("Sehr geehrte Damen und Herren,", "correspondence", "official"),
        ("Herzlichen Dank für Ihre Unterstützung.", "workplace", "official"),
        ("Ich bedanke mich vielmals.", "greeting", "official"),
        ("Mit freundlichen Grüßen", "correspondence", "official"),
        ("Bitte nehmen Sie Platz.", "admin", "official"),
    ],
    no_marker=[
        ("Das Wetter ist heute gut.", "weather"),
        ("Was kostet das?", "shopping"),
        ("Der Zug hat Verspätung.", "transit"),
        ("Ich wohne in Berlin.", "smalltalk"),
        ("Es regnet.", "weather"),
        ("Das Geschäft ist geschlossen.", "shopping"),
        ("Keine Zeit.", "smalltalk"),
    ],
    hard=[
        # These are the exact strings the engine has regressed on before.
        ("Sie ist nett und sie hat ihr Buch.", None, "she vs you",
         "sentence-initial Sie before a singular verb is 'she' — must not be "
         "rewritten, and lowercase sie/ihr never are"),
        ("Sie kommt morgen.", None, "she vs you",
         "3sg verb settles it: this is 'she comes tomorrow'"),
        ("Sie sind sehr nett.", 2, "you",
         "plural verb settles it the other way"),
        ("Ich sehe Sie morgen.", 2, "accusative",
         "object position — downgrades to dich, not du"),
        ("Wo wohnen Sie?", 2, "inversion",
         "verb-first question; the pronoun follows the verb"),
        ("Ihr Buch liegt hier.", 2, "poss vs her",
         "capitalised Ihr is 'your'; lowercase ihr would be 'her'"),
    ],
)


# ==========================================================================
# French — tu / vous
# ==========================================================================

FRENCH = LanguageSet(
    code="fr",
    name="French",
    columns=(1, 2, 2),
    confidence="high",
    triads=[
        ("pronouns", [
            ("Comment vas-tu ?", "Comment allez-vous ?", "Comment allez-vous ?",
             "greeting", "friend", "v.aller.inv"),
            ("Comment t'appelles-tu ?", "Comment vous appelez-vous ?",
             "Comment vous appelez-vous ?", "greeting", "stranger", "v.reflexive"),
            ("Où habites-tu ?", "Où habitez-vous ?", "Où habitez-vous ?",
             "smalltalk", "stranger", "v.habiter.inv"),
            ("C'est pour toi.", "C'est pour vous.", "C'est pour vous.",
             "everyday", "family", "pron.tonic"),
            ("Je te vois demain.", "Je vous vois demain.", "Je vous vois demain.",
             "planning", "colleague", "pron.clitic"),
            ("Il t'attend.", "Il vous attend.", "Il vous attend.",
             "everyday", "colleague", "pron.clitic + elision"),
        ]),
        ("possessives", [
            # The gender cases: votre is neutral, ton/ta are not.
            ("C'est ta maison ?", "C'est votre maison ?", "C'est votre maison ?",
             "everyday", "acquaintance", "poss.f"),
            ("C'est ton livre ?", "C'est votre livre ?", "C'est votre livre ?",
             "everyday", "colleague", "poss.m"),
            ("Voici ton adresse.", "Voici votre adresse.", "Voici votre adresse.",
             "admin", "official", "poss before vowel"),
            ("J'ai vu tes amis.", "J'ai vu vos amis.", "J'ai vu vos amis.",
             "smalltalk", "friend", "poss.pl"),
        ]),
        ("verbs", [
            ("Tu es très gentil.", "Vous êtes très gentil.", "Vous êtes très gentil.",
             "compliment", "acquaintance", "v.etre"),
            ("Tu as raison.", "Vous avez raison.", "Vous avez raison.",
             "smalltalk", "colleague", "v.avoir"),
            ("Peux-tu m'aider ?", "Pouvez-vous m'aider ?", "Pouvez-vous m'aider ?",
             "request", "stranger", "v.pouvoir.inv"),
            ("Tu parles anglais ?", "Vous parlez anglais ?", "Vous parlez anglais ?",
             "smalltalk", "stranger", "v.parler"),
            ("Que fais-tu ?", "Que faites-vous ?", "Que faites-vous ?",
             "smalltalk", "stranger", "v.faire.inv"),
            ("Quand viens-tu ?", "Quand venez-vous ?", "Quand venez-vous ?",
             "planning", "colleague", "v.venir.inv"),
        ]),
        ("courtesy", [
            ("Excuse-moi.", "Excusez-moi.", "Excusez-moi.",
             "apology", "stranger", "v.imp"),
            ("Merci à toi.", "Merci à vous.", "Merci à vous.",
             "greeting", "acquaintance", "pron.tonic"),
            ("S'il te plaît.", "S'il vous plaît.", "S'il vous plaît.",
             "request", "stranger", "fixed phrase"),
        ]),
    ],
    formal=[
        ("Je vous prie de m'excuser.", "apology", "official"),
        ("Je vous remercie de votre aide.", "greeting", "official"),
        ("Veuillez patienter un instant.", "request", "official"),
        ("Veuillez signer ici.", "admin", "official"),
        ("Cordialement,", "correspondence", "official"),
    ],
    no_marker=[
        ("Il fait beau aujourd'hui.", "weather"),
        ("Combien ça coûte ?", "shopping"),
        ("Le train a du retard.", "transit"),
        ("J'habite à Paris.", "smalltalk"),
        ("Il pleut.", "weather"),
        ("Le magasin est fermé.", "shopping"),
        ("Pas le temps.", "smalltalk"),
    ],
    hard=[
        ("Je vous vois demain.", 2, "clitic",
         "object clitic — downgrades to te, not tu"),
        ("C'est pour vous.", 2, "tonic",
         "after a preposition — downgrades to toi, not tu"),
        ("Vous êtes très gentil.", 2, "subject",
         "subject position — downgrades to tu"),
        ("Il vous attend.", 2, "clitic + elision",
         "downgrades to t'attend, with the elision restored"),
        ("Je vois le train.", None, "1sg homograph",
         "vois is both 'I see' and 'you see'; the subject is je, so no "
         "second-person marker is present"),
        ("Il est très gentil.", None, "third person", "no second-person marker"),
    ],
)


# ==========================================================================
# Spanish — tú / usted
# ==========================================================================

SPANISH = LanguageSet(
    code="es",
    name="Spanish",
    columns=(1, 2, 2),
    confidence="high",
    note="Peninsular usage. Latin American vos and ustedes differ and are not "
         "covered here — worth a separate set.",
    triads=[
        ("pronouns", [
            ("¿Cómo estás?", "¿Cómo está usted?", "¿Cómo está usted?",
             "greeting", "friend", "v.estar"),
            ("¿Cómo te llamas?", "¿Cómo se llama usted?", "¿Cómo se llama usted?",
             "greeting", "stranger", "v.reflexive"),
            ("¿Dónde vives?", "¿Dónde vive usted?", "¿Dónde vive usted?",
             "smalltalk", "stranger", "v.vivir"),
            ("Esto es para ti.", "Esto es para usted.", "Esto es para usted.",
             "everyday", "family", "pron.prep"),
            ("¿Es tu libro?", "¿Es su libro?", "¿Es su libro?",
             "everyday", "colleague", "poss"),
        ]),
        ("verbs", [
            ("Eres muy amable.", "Es usted muy amable.", "Es usted muy amable.",
             "compliment", "acquaintance", "v.ser"),
            ("¿Tienes tiempo?", "¿Tiene usted tiempo?", "¿Tiene usted tiempo?",
             "request", "colleague", "v.tener"),
            ("¿Puedes ayudarme?", "¿Puede usted ayudarme?", "¿Puede usted ayudarme?",
             "request", "stranger", "v.poder"),
            ("¿Hablas inglés?", "¿Habla usted inglés?", "¿Habla usted inglés?",
             "smalltalk", "stranger", "v.hablar"),
            ("¿Qué quieres?", "¿Qué quiere usted?", "¿Qué quiere usted?",
             "shopping", "shopkeeper", "v.querer"),
        ]),
        ("imperative", [
            ("Ven aquí.", "Venga aquí.", "Venga aquí.", "everyday", "guest", "v.imp.venir"),
            ("Dime.", "Dígame.", "Dígame.", "everyday", "colleague", "v.imp.decir"),
            ("Espera un momento.", "Espere un momento.", "Espere un momento.",
             "everyday", "stranger", "v.imp.esperar"),
        ]),
        ("courtesy", [
            ("Perdona.", "Perdone.", "Perdone.", "apology", "stranger", "v.imp"),
            ("Gracias a ti.", "Gracias a usted.", "Gracias a usted.",
             "greeting", "acquaintance", "pron.prep"),
        ]),
    ],
    formal=[
        ("Le agradezco mucho su ayuda.", "greeting", "official"),
        ("Le pido disculpas.", "apology", "official"),
        ("Por favor, espere un momento.", "request", "official"),
        ("Atentamente,", "correspondence", "official"),
        ("Que tenga un buen día.", "greeting", "official"),
    ],
    no_marker=[
        ("Hoy hace buen tiempo.", "weather"),
        ("¿Cuánto cuesta?", "shopping"),
        ("El tren llega tarde.", "transit"),
        ("Vivo en Madrid.", "smalltalk"),
        ("Está lloviendo.", "weather"),
        ("La tienda está cerrada.", "shopping"),
        ("No hay tiempo.", "smalltalk"),
    ],
    hard=[
        ("Él es muy amable.", None, "third person",
         "es is both 'he is' and 'you are' (usted); él settles it"),
        ("¿Es usted muy amable?", 2, "explicit pronoun",
         "usted present, so unambiguous"),
        ("Su libro está aquí.", 2, "poss ambiguity",
         "su is 'your' (usted) but also 'his/her/their'"),
    ],
)


# ==========================================================================
# Italian — tu / Lei
# ==========================================================================

ITALIAN = LanguageSet(
    code="it",
    name="Italian",
    columns=(1, 2, 2),
    confidence="high",
    triads=[
        ("pronouns", [
            ("Come stai?", "Come sta?", "Come sta?",
             "greeting", "friend", "v.stare"),
            ("Come ti chiami?", "Come si chiama?", "Come si chiama?",
             "greeting", "stranger", "v.reflexive"),
            ("Dove abiti?", "Dove abita?", "Dove abita?",
             "smalltalk", "stranger", "v.abitare"),
            ("Questo è per te.", "Questo è per Lei.", "Questo è per Lei.",
             "everyday", "family", "pron.tonic"),
            ("È il tuo libro?", "È il Suo libro?", "È il Suo libro?",
             "everyday", "colleague", "poss"),
        ]),
        ("verbs", [
            ("Sei molto gentile.", "È molto gentile.", "È molto gentile.",
             "compliment", "acquaintance", "v.essere"),
            ("Hai tempo?", "Ha tempo?", "Ha tempo?", "request", "colleague", "v.avere"),
            ("Puoi aiutarmi?", "Può aiutarmi?", "Può aiutarmi?",
             "request", "stranger", "v.potere"),
            ("Parli inglese?", "Parla inglese?", "Parla inglese?",
             "smalltalk", "stranger", "v.parlare"),
        ]),
        ("courtesy", [
            ("Scusa.", "Mi scusi.", "Mi scusi.", "apology", "stranger", "v.imp"),
            ("Grazie a te.", "Grazie a Lei.", "Grazie a Lei.",
             "greeting", "acquaintance", "pron.tonic"),
        ]),
    ],
    formal=[
        ("La ringrazio molto.", "greeting", "official"),
        ("Le chiedo scusa.", "apology", "official"),
        ("La prego di attendere.", "request", "official"),
        ("Distinti saluti,", "correspondence", "official"),
    ],
    no_marker=[
        ("Oggi il tempo è bello.", "weather"),
        ("Quanto costa?", "shopping"),
        ("Il treno è in ritardo.", "transit"),
        ("Abito a Roma.", "smalltalk"),
        ("Sta piovendo.", "weather"),
        ("Il negozio è chiuso.", "shopping"),
    ],
    hard=[
        ("Ho visto lei e le sue amiche.", None, "lowercase lei",
         "lowercase lei is 'her'; le and sue are not the polite forms"),
        ("Anche lei ha la sua ragione.", None, "lowercase lei",
         "third person — ha must not downgrade to hai"),
        ("Lei è molto gentile.", 2, "known limitation",
         "sentence-initial Lei is ambiguous between polite 'you' and 'she'; "
         "both take a third-person verb. The engine reads it as polite"),
        ("Questo è per Lei.", 2, "mid-sentence capital",
         "capitalisation mid-sentence is unambiguous"),
    ],
)


# ==========================================================================
# Portuguese — tu / você / o senhor
# ==========================================================================

PORTUGUESE = LanguageSet(
    code="pt",
    name="Portuguese",
    columns=(0, 1, 2),
    confidence="medium",
    note="Three-way, but usage splits by region: tu is everyday in Portugal "
         "and regional in Brazil, where você is the default. Drafted toward "
         "European Portuguese.",
    triads=[
        ("pronouns", [
            ("Como estás?", "Como está?", "Como está o senhor?",
             "greeting", "friend", "v.estar"),
            ("Onde moras?", "Onde mora?", "Onde mora o senhor?",
             "smalltalk", "stranger", "v.morar"),
            ("Isto é para ti.", "Isto é para si.", "Isto é para o senhor.",
             "everyday", "family", "pron.prep"),
            ("É o teu livro?", "É o seu livro?", "É o seu livro?",
             "everyday", "colleague", "poss"),
        ]),
        ("verbs", [
            ("És muito simpático.", "É muito simpático.",
             "O senhor é muito simpático.", "compliment", "acquaintance", "v.ser"),
            ("Tens tempo?", "Tem tempo?", "O senhor tem tempo?",
             "request", "colleague", "v.ter"),
            ("Podes ajudar-me?", "Pode ajudar-me?", "O senhor pode ajudar-me?",
             "request", "stranger", "v.poder"),
            ("Falas inglês?", "Fala inglês?", "O senhor fala inglês?",
             "smalltalk", "stranger", "v.falar"),
        ]),
        ("courtesy", [
            ("Desculpa.", "Desculpe.", "Desculpe.", "apology", "stranger", "v.imp"),
            ("Obrigado a ti.", "Obrigado a si.", "Obrigado ao senhor.",
             "greeting", "acquaintance", "pron.prep"),
        ]),
    ],
    formal=[
        ("Agradeço muito a sua ajuda.", "greeting", "official"),
        ("Peço desculpa pelo incómodo.", "apology", "official"),
        ("Por favor, aguarde um momento.", "request", "official"),
        ("Com os melhores cumprimentos,", "correspondence", "official"),
    ],
    no_marker=[
        ("Hoje está bom tempo.", "weather"),
        ("Quanto custa?", "shopping"),
        ("O comboio está atrasado.", "transit"),
        ("Moro em Lisboa.", "smalltalk"),
        ("Está a chover.", "weather"),
        ("A loja está fechada.", "shopping"),
    ],
    hard=[
        ("Ele é muito simpático.", None, "third person",
         "é is both 'he is' and 'you are' (você); ele settles it"),
        ("Você é muito simpático.", 1, "explicit pronoun", "você present"),
    ],
)


# ==========================================================================
# Japanese — plain / です・ます / 敬語
# ==========================================================================

JAPANESE = LanguageSet(
    code="ja",
    name="Japanese",
    columns=(1, 2, 3),
    confidence="medium",
    note="Three genuine levels, and no word boundaries at all — matching is "
         "substring-ordered, so longer forms must win over the copulas nested "
         "inside them. Real keigo needs morphological analysis; the sentence-"
         "final politeness spine is what the engine actually covers.",
    triads=[
        ("copula", [
            ("これをする。", "これをします。", "これをいたします。",
             "everyday", "colleague", "v.suru"),
            ("明日行く。", "明日行きます。", "明日まいります。",
             "planning", "colleague", "v.iku"),
            ("すぐ来る。", "すぐ来ます。", "すぐまいります。",
             "planning", "colleague", "v.kuru"),
            ("それを見る。", "それを見ます。", "それを拝見します。",
             "workplace", "senior", "v.miru"),
            ("お茶を飲む。", "お茶を飲みます。", "お茶をいただきます。",
             "hospitality", "guest", "v.nomu"),
        ]),
        ("courtesy", [
            ("ありがとう。", "ありがとうございます。", "誠にありがとうございます。",
             "greeting", "acquaintance", "thanks"),
            ("ごめんね。", "すみません。", "申し訳ございません。",
             "apology", "stranger", "apology"),
        ]),
        ("existential", [
            ("時間がある。", "時間があります。", "時間がございます。",
             "planning", "colleague", "v.aru"),
            ("ここにいる。", "ここにいます。", "ここにおります。",
             "everyday", "colleague", "v.iru"),
        ]),
    ],
    formal=[
        ("お世話になっております。", "correspondence", "official"),
        ("よろしくお願いいたします。", "correspondence", "official"),
        ("恐れ入りますが、少々お待ちください。", "request", "official"),
    ],
    no_marker=[
        ("今日はいい天気です。", "weather"),
        ("これはいくらですか。", "shopping"),
        ("電車が遅れています。", "transit"),
        ("東京に住んでいます。", "smalltalk"),
        ("雨が降っています。", "weather"),
    ],
    hard=[
        ("する。", 1, "bare plain form", "no politeness spine at all"),
        ("します。", 2, "masu form", "the sentence-final spine is the whole signal"),
        ("いたします。", 3, "humble form", "keigo"),
    ],
)


# ==========================================================================
# English — weak register, but the contrast is real
# ==========================================================================

ENGLISH = LanguageSet(
    code="en",
    name="English",
    columns=(1, 2, 3),
    confidence="high",
    note="No grammatical T/V distinction, so register here is entirely lexical "
         "and hedging. Included because the dial has to do *something* when "
         "English is the target, and because English is usually the pivot.",
    triads=[
        ("requests", [
            ("Can you help me?", "Could you help me?", "Could you kindly help me?",
             "request", "stranger", "modal hedging"),
            ("Give me a hand.", "Could you give me a hand?",
             "Could you kindly give me a hand?", "request", "colleague", "imperative → hedge"),
            ("Send it over.", "Please send it over.", "Kindly send it over.",
             "workplace", "colleague", "imperative + politeness marker"),
        ]),
        ("greetings", [
            ("Hi.", "Hello.", "Good day.", "greeting", "stranger", "greeting"),
            ("Thanks.", "Thank you.", "Thank you very much.",
             "greeting", "acquaintance", "thanks"),
            ("Sorry.", "I apologise.", "I sincerely apologise.",
             "apology", "stranger", "apology"),
            ("Bye.", "Goodbye.", "I bid you goodbye.", "greeting", "stranger", "farewell"),
        ]),
        ("lexis", [
            ("I wanna go.", "I want to go.", "I should like to go.",
             "smalltalk", "friend", "contraction → full form"),
            ("Yeah.", "Yes.", "Certainly.", "smalltalk", "colleague", "assent"),
            ("Loads of people came.", "Many people came.",
             "A great deal of people came.", "smalltalk", "colleague", "quantifier"),
        ]),
    ],
    formal=[
        ("I am writing to enquire about the position advertised.", "correspondence", "official"),
        ("Please find the requested documents attached.", "correspondence", "official"),
        ("I would be grateful for your assistance in this matter.", "request", "official"),
        ("Yours sincerely,", "correspondence", "official"),
    ],
    no_marker=[
        ("The weather is nice today.", "weather"),
        ("How much does this cost?", "shopping"),
        ("The train is delayed.", "transit"),
        ("I live in London.", "smalltalk"),
        ("It is raining.", "weather"),
        ("The shop is closed.", "shopping"),
    ],
    hard=[
        ("He is very kind.", None, "third person", "no second-person marker"),
        ("Thanks.", 1, "bare token", "single-word register signal"),
    ],
)


ALL = [GERMAN, FRENCH, SPANISH, ITALIAN, PORTUGUESE, JAPANESE, ENGLISH]
