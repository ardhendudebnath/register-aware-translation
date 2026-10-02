"""
European: German, French, Spanish, Italian, Portuguese, English.

A T/V distinction in five of them and none at all in English, where
register is carried by word choice instead — which is why the English
rules are ``rewrite_only`` and never vote.
"""

from __future__ import annotations

from typing import Tuple

from .model import FormGuard, LanguageTable, Rule


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
             # Only the extra guard here: the rule's own applies to this form
             # as well, since blocking guards accumulate.
             form_guards=(("Sie", "", _DE_THIRD_SINGULAR, "", "", ""),)),
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

#: The same list without "que", for the subject reading. After a preposition
#: "vous" is tonic; after "que" it may be either, and only what follows says
#: which — so the subject rule stays available there and the tonic rule steps
#: aside when a verb comes next.
_FR_PREP_NOT_QUE = (
    r"\b(?:pour|avec|chez|sans|à|de|comme|sur|sous|vers|entre|contre)\s+"
)

# A French verb rule must not fire when the subject is not second person:
# "je vois" and "tu vois" are spelled identically, so upgrading "je te vois"
# would otherwise produce "je vous voyez". Clitics may sit between the subject
# and the verb, so the pattern skips over them.
_FR_NON_2P_SUBJECT = (
    r"(?:\bje\b|\bj'|\bil\b|\belle\b|\bon\b|\bnous\b|\bils\b|\belles\b|\bqui\b)"
    r"(?:\s+(?:me|te|se|nous|vous|le|la|les|lui|leur|y|en))*\s+"
)

#: The same, minus "vous", for the *vous form* of a verb.
#:
#: "vous" in front of a tu-form verb is an object — "je vous vois", where vois
#: is the first person and only looks like the tu form — so the rule-level
#: pattern above steps over it. In front of a vous *form* it cannot be an
#: object, because nothing else is left to be the subject: "ni sur qui vous
#: êtes" is "who you are". Treating it as a clitic there blocked the verb
#: while the pronoun still went down, leaving "qui tu êtes".
_FR_NON_2P_SUBJECT_VOUS_FORM = (
    r"(?:\bje\b|\bj'|\bil\b|\belle\b|\bon\b|\bnous\b|\bils\b|\belles\b|\bqui\b)"
    r"(?:\s+(?:me|te|se|nous|le|la|les|lui|leur|y|en))*\s+"
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


#: A conjugated second-person verb immediately after the pronoun, which is
#: what tells "que vous êtes" (a clause) from "plus grand que vous" (a
#: comparison). Built from this table's own forms so it cannot drift from
#: them, plus the -ez ending, which marks a vous form in verbs the table does
#: not carry.
_FR_VERB_AFTER = (
    r"\s+(?:"
    # Longest first so no alternative is shadowed by a prefix of itself, then
    # alphabetically — a set has no order, and sorting on length alone left
    # equal-length forms to fall wherever the run's hash seed put them. The
    # pattern meant the same thing either way, but it was different text on
    # every run, which is the kind of thing that makes a diff lie.
    + "|".join(sorted(
        {form for _s, tu, vous, _g in _FR_VERBS for form in (tu, vous)},
        key=lambda form: (-len(form), form),
    ))
    + r"|\w+ez)\b"
)


def _fr_verb_rules() -> Tuple[Rule, ...]:
    return tuple(
        Rule(f"v.{stem}", (tu_form, tu_form, vous_form, vous_form), gloss,
             guard_before=_FR_NON_2P_SUBJECT,
             # The one place in the project where a form wants a *weaker*
             # guard than its rule, so it has to say so: the rule steps over
             # "vous" as a clitic, and in front of a vous form it cannot be
             # one. Accumulating the two would put the clitic back.
             form_guards=(FormGuard(vous_form,
                                    guard_before=_FR_NON_2P_SUBJECT_VOUS_FORM,
                                    replace=True),))
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
        # The two narrow readings are declared first, so each takes the span
        # where its own context holds and the subject rule gets the rest.
        #
        # Object "vous": only in a clitic slot, where it becomes "te".
        Rule("pron.2sg.obj", ("te", "te", "vous", "vous"), "you (obj)",
             require_before=_FR_CLITIC_CONTEXT),
        # After a relative "qui", vous is whichever the verb says it is:
        # an object in "qui vous a dit cela" (who told you), the subject in
        # "qui vous êtes" (who you are). Only the first becomes "te", so this
        # stands aside when a second-person verb follows and lets the subject
        # rule below take it.
        Rule("pron.2sg.obj.rel", ("te", "te", "vous", "vous"), "you (obj)",
             require_before=r"\bqui\s+",
             guard_after=_FR_VERB_AFTER),
        # Tonic "vous": after a preposition, where it becomes "toi" — but not
        # when a verb follows. "que" is on that list for the comparative
        # ("plus grand que vous"), and it also introduces a subordinate clause,
        # where vous is the subject: "cela signifie que vous êtes" was coming
        # out as "que toi es".
        Rule("pron.2sg.tonic", ("toi", "toi", "vous", "vous"), "you (tonic)",
             require_before=_FR_PREP_CONTEXT,
             guard_after=_FR_VERB_AFTER),
        # Subject "vous": neither in a clitic slot nor after a preposition.
        # "que" is missing from that list on purpose — see the tonic rule.
        Rule("pron.2sg.nom", ("tu", "tu", "vous", "vous"), "you",
             guard_before=f"(?:{_FR_CLITIC_CONTEXT}|{_FR_PREP_NOT_QUE})"),
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

#: Words that put a finite verb after them, not a command.
#:
#: Several tú imperatives are homographs of some other verb's third person,
#: and "ve" is the worst: the imperative of *ir* and the 3sg of *ver*, which
#: for usted is the polite form. FAME-MT fired that rule 42 times and was
#: wrong half of them — "se ve", "lo que ve", "porque ve", "¿Cómo ve el
#: futuro?" all read as somebody being told to go somewhere.
#:
#: A proclitic or a subordinator is the cheap signal: Spanish does not put one
#: in front of an affirmative imperative, and the negative imperative takes
#: the subjunctive ("no vayas") rather than this form.
_ES_NOT_IMPERATIVE_BEFORE = (
    r"\b(?:se|me|te|nos|os|lo|la|los|las|le|les|"
    r"que|porque|cuando|donde|dónde|quien|quién|como|cómo|si|no|cual|cuál)\s+"
)

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
    # A named third-person subject rules it out for the same reason an adjacent
    # usted does: "Él habla español" is about him. It was read as Casual at full
    # confidence off the tú imperative, which in Auto mode mirrors a register
    # nobody used.
    out += [
        Rule(f"v.{stem}.imp", (tu, tu, usted, usted), gloss,
             guard_before=(rf"{_ES_USTED}\s+|{_ES_NOT_IMPERATIVE_BEFORE}"
                           rf"|{_ES_3P_SUBJECT}"),
             guard_after=rf"\s+{_ES_USTED}")
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

# Third-person subjects.
#
# Only "lei" is case-sensitive here, and for a real reason: capitalised "Lei"
# is the polite pronoun, lowercase "lei" is "she". Every other word on this
# list is third person whatever its case — and because Italian rules are
# ``cased``, their guards compile case-sensitively too, so writing the whole
# list in lower case quietly exempted the position these words actually occupy.
# A subject leads its sentence, which means it is capitalised: "Lui è
# italiano" was conjugated to "Lui sei italiano" and read as Polite, while the
# identical "lui è italiano" was handled correctly.
_IT_3P_SUBJECT = r"\b(?:(?i:lui|egli|ella|esso|essa|chi)|lei)\s+"

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
#: The same list plus "che", and the same rule about case: everything except
#: "lei" matches capitalised too.
_IT_3P_SUBJECT_FULL = r"\b(?:(?i:lui|egli|ella|esso|essa|chi|che)|lei)\s+"

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

#: The impersonal "si" — "si mangia bene qui", one eats well here. It is not
#: addressed to anybody, and the verb after it is third person. (A reflexive
#: rule whose own form starts with "si" is unaffected: the si is inside the
#: match, so it is never in the prefix this is tested against.)
_IT_IMPERSONAL_SI = r"\b(?i:si)\s+"

_IT_3P_BEFORE = (
    f"{_IT_3P_SUBJECT_FULL}|{_IT_NP_BEFORE}|{_IT_DEM_BEFORE}|{_IT_IMPERSONAL_SI}"
)
_IT_3P_AFTER = f"{_IT_NP_AFTER}|{_IT_GERUND}"

#: Prepositions that take the tonic pronoun rather than the nominative.
_IT_PREPOSITION = r"\b(?i:per|con|da|a|di|su|tra|fra|come)\s+"

# --------------------------------------------------------------------------
# An -are verb's two rules are exact mirror images of each other.
#
#     parlare   indicative  tu parli    Lei parla
#               imperative  tu parla!   Lei parli!
#
# So "parli" is the polite command *and* the familiar statement, and "parla"
# is the familiar command *and* the polite statement — the register runs in
# opposite directions depending on which reading is meant. The indicative was
# declared first and took every span, which made a polite imperative come back
# casual, in the wrong direction, at full confidence:
#
#     Aspetti un momento.  ->  Aspetta un momento.   read as Casual (1.00)
#
# A command heads its clause and a question is not a command, and between them
# those settle it. The imperative is declared first now so that it wins the
# span when both could match, and carries the positional constraints; when the
# sentence is a question it steps aside and the indicative takes it, which is
# what "Parli italiano?" needs.
# --------------------------------------------------------------------------

#: Clitics can sit in front of a command without it ceasing to head its
#: clause: "Mi dica", "Lo faccia". Not "si": "Si mangia bene qui" is the
#: impersonal — one eats well here — and no one is being told anything.
_IT_PROCLITIC = r"(?:(?i:mi|ti|ci|vi|lo|la|li|le|ne|gli|me|te)\s+){0,2}"

_IT_CLAUSE_INITIAL = rf"(?:^|[.!?…;:,–—\"“«»]|(?:^|\s)-)\s*{_IT_PROCLITIC}"

#: A question with a dropped subject is asking, not ordering.
_IT_QUESTION_AFTER = r"[^.!?]*\?"

#: The stems whose imperative and indicative are mirror images — every -are
#: verb in the table.
_IT_MIRRORED = {
    stem for stem, tu, lei, _g in _IT_IMPERATIVES
    if any(s == stem and t == lei for s, t, _l, _g2 in _IT_VERBS)
}


def _it_verb_rules() -> Tuple[Rule, ...]:
    # Imperatives first: where both readings match the same word, the command
    # is the one carrying the positional constraints, so it must be the one
    # offered the span first.
    out = []
    for stem, tu, lei, gloss in _IT_IMPERATIVES:
        mirrored = stem in _IT_MIRRORED
        out.append(
            Rule(f"v.{stem}.imp", (tu, tu, lei, lei), gloss, cased=True,
                 # The third-person blocklist the indicatives already carry:
                 # "Lui parla italiano" is not a command either.
                 # Not _IT_3P_AFTER on either form: a noun phrase after a
                 # command is its object — "Aspetti un momento", "Prenda un
                 # caffè" — where after an indicative it is the subject of a
                 # question about something else. Borrowing that guard from
                 # the indicative blocked every imperative that takes an
                 # object, which is most of them.
                 form_guards=(
                     (tu, _IT_3P_BEFORE,
                      _IT_QUESTION_AFTER if mirrored else "",
                      _IT_CLAUSE_INITIAL if mirrored else "", ""),
                     (lei, _IT_3P_BEFORE,
                      _IT_QUESTION_AFTER if mirrored else "",
                      _IT_CLAUSE_INITIAL if mirrored else "", ""),
                 ))
        )
    out += [
        # The guards sit on the Lei form alone. On the rule they also
        # constrained the tu form, which is unambiguous and needs no
        # constraining.
        Rule(f"v.{stem}", (tu, tu, lei, lei), gloss, cased=True,
             form_guards=((lei, _IT_3P_BEFORE, _IT_3P_AFTER, "", ""),))
        for stem, tu, lei, gloss in _IT_VERBS
    ]
    out += [
        Rule(f"v.{stem}.refl", (tu, tu, lei, lei), gloss, cased=True,
             form_guards=((lei, _IT_3P_BEFORE, _IT_3P_AFTER, "", ""),))
        for stem, tu, lei, gloss in _IT_REFLEXIVES
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
#:
#: Named subjects count as well as pronouns. With pronouns alone, "O trem vai
#: para o centro" — the train goes to the centre — was conjugated down to "O
#: trem vais", because nothing said the subject was not the listener. The
#: exception for "o senhor" is the same one :data:`_PT_IMPERSONAL` carries:
#: it has exactly the shape of a determiner and a noun, and it is the polite
#: second person.
#: Up to two clitic pronouns between a subject and its verb.
#:
#: Brazilian Portuguese puts them in front of the verb — "Ele me diz a
#: verdade", "O João nos faz rir" — and every subject guard below was anchored
#: to the word immediately before the verb, so a clitic in between hid the
#: subject completely. "He tells me the truth" came out as "Ele me dizes a
#: verdade". Every guard that looks for a subject has to look past these.
_PT_CLITICS = r"(?:(?:me|te|se|nos|vos|lhe|lhes|o|a|os|as)\s+){0,2}"

_PT_3P_SUBJECT = (
    r"\b(?:ele|ela|eles|elas|quem|que|isto|isso|aquilo|tudo|nada)\s+"
    rf"{_PT_CLITICS}"
    r"|\b(?:o|a|os|as|um|uma|uns|umas|este|esta|esse|essa|aquele|aquela)\s+"
    rf"(?!senhor(?:a|es|as)?\b)\w+\s+{_PT_CLITICS}"
)

#: The syncretic forms of ser and estar are also the third-person forms, and
#: Portuguese drops subjects freely, so they need far more than a pronoun list:
#: a determiner and noun ("A loja está"), a fronted adverb ("Hoje está"), or
#: nothing at all ("Está a chover"). Only these two verbs are this ambiguous
#: — and only in their polite form, which is why this is a per-form guard.
_PT_IMPERSONAL = (
    rf"\b(?:ele|ela|eles|elas|quem|que|isto|isso|aquilo|tudo|nada)\s+{_PT_CLITICS}"
    # A possessive and a noun is a subject like any other — "minha irmã é
    # cabeleireira" is about her sister. Without these, v.ser was the single
    # largest source of disagreement in the corpus: 2,892 firings, 30% wrong,
    # and the examples were overwhelmingly this shape.
    r"|\b(?:meu|minha|meus|minhas|teu|tua|teus|tuas|seu|sua|seus|suas"
    rf"|nosso|nossa|nossos|nossas|dele|dela|deles|delas)\s+\w+\s+{_PT_CLITICS}"
    # A conjunction resets the clause, and the subject of the new one is
    # rarely the listener: "…, e é por isso que…".
    r"|\b(?:e|mas|ou|porque|pois|portanto|então|também)\s+"
    # "o senhor" looks exactly like a determiner and a noun, and it is the
    # polite *second* person — the one subject in this shape that must not be
    # blocked. Without the exception "O senhor é muito simpático" kept its
    # third-person verb all the way down to "Tu é muito simpático".
    r"|\b(?:o|a|os|as|um|uma|uns|umas|este|esta|esse|essa|aquele|aquela)\s+"
    rf"(?!senhor(?:a|es|as)?\b)\w+\s+{_PT_CLITICS}"
    r"|\b(?:hoje|ontem|amanhã|aqui|ali|lá|agora|ainda|já|também)\s*"
    # A clause boundary, not just the start of the string. This was `^\s*`,
    # which covers "É uma péssima ideia" and misses "É, é uma péssima ideia" —
    # and after a comma is where a Portuguese copula most often turns up with a
    # subject that is not the listener: "é claro", "Sim, é o Bill", "Bem, é
    # fascinante". FAME-MT scored 1,011 firings of this rule at 36% wrong and
    # every example was that shape.
    #
    # Anchored at the end of the prefix, so it only blocks a copula sitting
    # *immediately* after the boundary. "Sim, você é simpático" is unaffected,
    # because the prefix there ends with "você ".
    r"|(?:^|[.!?…;:,])\s*"
)

#: A subject in front of the verb means the verb is not a command.
#:
#: Every Portuguese tu imperative is spelled like the third-person present —
#: fala, come, vai, tem, faz — so unguarded, "O trem vai para o centro" was
#: conjugated to "O trem vais" and "Ele fala português" read as Close at full
#: confidence. An imperative takes no subject, so any subject sitting in front
#: of the verb rules the reading out: a third-person pronoun, a determiner
#: and a noun, or a second-person subject, which takes the indicative too
#: ("Você fala português" is a statement, not an order).
_PT_NOT_IMPERATIVE_BEFORE = (
    r"\b(?:ele|ela|eles|elas|quem|que|isto|isso|aquilo|tudo|nada"
    rf"|eu|nós|você|vocês|tu)\s+{_PT_CLITICS}"
    r"|\b(?:o|a|os|as|um|uma|uns|umas|este|esta|esse|essa|aquele|aquela)\s+\w+\s+"
    rf"{_PT_CLITICS}"
)

#: Ten Portuguese verbs spell the tu imperative exactly like the você present:
#: faz, diz, vai, tem, vem, dá, fala, come, espera, abre. So "Faz isso agora"
#: is both "do it now" and "you do it now", and the indicative reading won —
#: asking for Close conjugated the command into a statement, "Fazes isso
#: agora", which changes the mood rather than the register.
#:
#: An imperative heads its clause and an indicative with a dropped subject
#: does not, so position settles most of it. A dialogue dash opens a clause
#: as surely as a full stop — "- Vai." is a line of speech, and without the
#: dash here it read as a statement. A connective and proclitics can sit in
#: front and the verb still heads its clause: "Então me diz como consertar
#: isso" is an instruction.
_PT_CLAUSE_INITIAL = (
    r"(?:^|[.!?…;:,–—\"“«]|(?:^|\s)-)\s*"
    r"(?:(?:então|agora|depois|e|mas|só|já|pois|por favor|faz favor)\s+)?"
    rf"{_PT_CLITICS}"
)

#: "ter que" and "ter de" are the obligation modal — "tem que largar essa
#: arma" is *you have to* drop that gun. There is no command reading, and
#: without this one the polite rewrite produced "Tenha que largar essa arma",
#: which asks the listener to possess an obligation.
_PT_OBLIGATION_AFTER = r"\s+(?:que|de)\s+\w"

#: The polite imperative is the present subjunctive — faça, diga, tenha, dê —
#: so after a subordinator in the same clause it is not a command at all, and
#: often not even second person. "O que quer que eu te diga?" is "whatever you
#: want me to say" and "Para que Ele te dê o rei" is "so that He gives you the
#: king"; both were rewritten into tu imperatives ("que eu te diz", "Ele te
#: dá"), and "que sua mensagem não tenha sido entregue" — the message's verb —
#: became "não tem sido". Anything up to the nearest clause boundary counts,
#: because a subject, a negation or a clitic usually sits in between.
_PT_SUBJUNCTIVE_BEFORE = (
    r"\b(?:que|caso|se|embora|quando|talvez|onde|quem|enquanto|contanto"
    r"|desde|até|conforme|ainda)\b[^.!?;:,–—]*"
)

#: The negative imperative is built from the subjunctive in both registers:
#: "não faça" politely and "não faças" to a friend. Rewriting only the verb
#: turned "E não faça isso" into "E não faz isso", which is Brazilian
#: colloquial at best and was then read as a statement and conjugated again.
_PT_NEGATIVE_TU = {
    "falar": "fales", "comer": "comas", "abrir": "abras", "ir": "vás",
    "ser": "sejas", "ter": "tenhas", "fazer": "faças", "dizer": "digas",
    "vir": "venhas", "dar": "dês", "esperar": "esperes",
    "aguardar": "aguardes", "ouvir": "ouças", "seguir": "sigas",
    "entrar": "entres", "sentar": "sentes", "olhar": "olhes",
}

#: …except in a question, where a clause-initial verb with a dropped subject
#: is asking rather than ordering: "Faz isso?" is "do you do that?". Matched
#: against the rest of the sentence, so it stops at the next full stop.
#:
#: …and except before an infinitive, which is Portuguese's periphrastic
#: future rather than a command: in "Quando ouvir os aplausos, vai tocar a
#: música" the music will play, nobody is being told to play it. The corpus
#: caught that one — it read Close at full confidence against a formal label.
_PT_QUESTION_AFTER = r"[^.!?]*\?|\s+\w+(?:ar|er|ir)\b"

#: The tu imperative of every verb that also has an indicative rule.
_PT_IMPERATIVE_TU = {stem: tu for stem, tu, _polite, _gloss in _PT_IMPERATIVES}

_PT_SYNCRETIC = {"ser": "é", "estar": "está"}

#: Prepositions taking the tonic pronoun rather than the nominative. "a" is
#: absent: it contracts with o senhor and is handled by its own rule.
_PT_PREPOSITION = (
    r"\b(?:para|por|de|em|com|sem|sobre|até|desde|entre|contra|após)\s+"
)


def _pt_verb_rules() -> Tuple[Rule, ...]:
    out = []
    for stem, tu, polite, gloss in _PT_VERBS:
        guards = []
        if stem in _PT_SYNCRETIC:
            guards.append((_PT_SYNCRETIC[stem], _PT_IMPERSONAL, "", "", ""))
        if _PT_IMPERATIVE_TU.get(stem) == polite:
            # Leading its clause, this form is a command, not a statement.
            # The imperative rule below picks it up instead — a guarded-out
            # pattern leaves the span free rather than consuming it.
            # The rule's third-person guard still applies here; blocking
            # guards accumulate.
            guards.append((polite, _PT_CLAUSE_INITIAL, "", "", ""))
        out.append(
            Rule(f"v.{stem}", (tu, polite, polite, polite), gloss,
                 guard_before=_PT_3P_SUBJECT,
                 form_guards=tuple(guards))
        )
    indicative_forms = {v[2] for v in _PT_VERBS}
    # Negatives first and longer, so "não faça" is taken whole before the
    # affirmative rule can see "faça" inside it.
    out += [
        Rule(f"v.{stem}.imp.neg",
             (f"não {_PT_NEGATIVE_TU[stem]}", f"não {_PT_NEGATIVE_TU[stem]}",
              f"não {polite}", f"não {polite}"),
             f"don't {gloss.rstrip('!')}!",
             guard_before=_PT_SUBJUNCTIVE_BEFORE)
        for stem, tu, polite, gloss in _PT_IMPERATIVES
        if stem in _PT_NEGATIVE_TU
    ]
    out += [
        Rule(f"v.{stem}.imp", (tu, polite, polite, polite), gloss,
             guard_before=_PT_NOT_IMPERATIVE_BEFORE,
             guard_after=_PT_OBLIGATION_AFTER if stem == "ter" else "",
             form_guards=(
                 # The polite form is also the subjunctive, so a subordinator
                 # in its clause means it is not a command. The rule's own
                 # "a subject in front of it" guard still applies as well.
                 ((polite, _PT_SUBJUNCTIVE_BEFORE, "", "", ""),)
                 # …and in a question the ambiguous tu form is the statement,
                 # so it hands the span back.
                 + (((tu, "", _PT_QUESTION_AFTER, "", ""),)
                    if tu in indicative_forms else ())
             ))
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

