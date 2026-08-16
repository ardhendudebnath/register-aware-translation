"""
Noun gender, for the information that register rewriting throws away.

French ``votre`` carries no gender. Downgrading it has to become ``ton`` or
``ta`` depending on the noun that follows, and a table alone cannot know which —
so the old behaviour was to always guess masculine, turning *votre maison* into
the wrong *ton maison* (blueprint 3.4, first row).

Two sources, cheapest first:

1. **Suffix morphology.** French gender is highly predictable from the ending:
   ``-tion``, ``-té``, ``-ance`` are feminine; ``-ment``, ``-age``, ``-eau`` are
   masculine. This covers a large share of the vocabulary for a few dozen rules
   and generalises to words no lexicon lists.
2. **A lexicon of common and irregular nouns**, consulted first, because the
   frequent words are exactly the ones whose endings lie (``page`` is feminine
   despite ``-age``; ``musée`` is masculine despite ``-ée``).

Returns None when it does not know, and callers fall back to the masculine
default rather than inventing an answer.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Optional

__all__ = ["french_gender", "french_possessive", "FR_VOWEL_START"]

MASCULINE = "m"
FEMININE = "f"

#: A word beginning with a vowel sound. French takes the *masculine* possessive
#: before these even when the noun is feminine — "ton amie", never "ta amie" —
#: because "ta amie" is unpronounceable. Silent h behaves like a vowel.
FR_VOWEL_START = re.compile(r"^[aeiouéèêàâîïôöûùüh]", re.IGNORECASE)

# Endings that decide gender. Longest suffix wins, so -ation beats -ion.
_FEMININE_SUFFIXES = (
    "ation", "ition", "ution", "ction", "xion", "sion", "tion",
    "ance", "ence", "ande", "aison", "aille", "eille", "ouille",
    "esse", "ette", "elle", "erie", "ie", "ée", "té", "tié",
    "ude", "ure", "eur",   # -eur abstract: la couleur, la douleur
    "ise", "ade", "ine", "ienne", "onne", "euse", "trice", "iere", "ière",
)

_MASCULINE_SUFFIXES = (
    "ment", "age", "isme", "iste", "eau", "eu", "ou", "oir", "ier", "er",
    "on", "an", "in", "ain", "ein", "at", "et", "ot", "as", "is", "os", "us",
    "acle", "ege", "ège", "phone", "scope", "gramme",
)

#: Common nouns and the irregulars whose endings mislead. The frequent words
#: matter most: a lexicon that misses "maison" is useless however large it is.
_LEXICON = {
    # feminine
    "maison": FEMININE, "voiture": FEMININE, "porte": FEMININE, "table": FEMININE,
    "chaise": FEMININE, "fenetre": FEMININE, "fenêtre": FEMININE, "chambre": FEMININE,
    "cuisine": FEMININE, "salle": FEMININE, "ville": FEMININE, "rue": FEMININE,
    "route": FEMININE, "place": FEMININE, "gare": FEMININE, "école": FEMININE,
    "ecole": FEMININE, "eglise": FEMININE, "église": FEMININE, "banque": FEMININE,
    "poste": FEMININE, "carte": FEMININE, "lettre": FEMININE, "page": FEMININE,
    "image": FEMININE, "plage": FEMININE, "cage": FEMININE, "nage": FEMININE,
    "main": FEMININE, "tete": FEMININE, "tête": FEMININE, "jambe": FEMININE,
    "bouche": FEMININE, "dent": FEMININE, "langue": FEMININE, "peau": FEMININE,
    "voix": FEMININE, "eau": FEMININE, "mer": FEMININE, "terre": FEMININE,
    "fleur": FEMININE, "feuille": FEMININE, "montagne": FEMININE, "riviere": FEMININE,
    "rivière": FEMININE, "famille": FEMININE, "mere": FEMININE, "mère": FEMININE,
    "soeur": FEMININE, "sœur": FEMININE, "fille": FEMININE, "femme": FEMININE,
    "amie": FEMININE, "personne": FEMININE, "vie": FEMININE, "mort": FEMININE,
    "sante": FEMININE, "santé": FEMININE, "douleur": FEMININE, "chance": FEMININE,
    "heure": FEMININE, "minute": FEMININE, "seconde": FEMININE, "semaine": FEMININE,
    "annee": FEMININE, "année": FEMININE, "journee": FEMININE, "journée": FEMININE,
    "nuit": FEMININE, "matinee": FEMININE, "matinée": FEMININE, "saison": FEMININE,
    "question": FEMININE, "reponse": FEMININE, "réponse": FEMININE, "idee": FEMININE,
    "idée": FEMININE, "raison": FEMININE, "chose": FEMININE, "partie": FEMININE,
    "fois": FEMININE, "facon": FEMININE, "façon": FEMININE, "maniere": FEMININE,
    "manière": FEMININE, "photo": FEMININE, "video": FEMININE, "vidéo": FEMININE,
    "radio": FEMININE, "télé": FEMININE, "tele": FEMININE, "cle": FEMININE,
    "clé": FEMININE, "valise": FEMININE, "chemise": FEMININE, "jupe": FEMININE,
    "robe": FEMININE, "veste": FEMININE, "chaussure": FEMININE, "monnaie": FEMININE,
    "piece": FEMININE, "pièce": FEMININE, "boisson": FEMININE, "viande": FEMININE,
    "salade": FEMININE, "soupe": FEMININE, "pomme": FEMININE, "orange": FEMININE,
    "banane": FEMININE, "boite": FEMININE, "boîte": FEMININE, "bouteille": FEMININE,
    "tasse": FEMININE, "assiette": FEMININE, "cuillere": FEMININE, "cuillère": FEMININE,
    "fourchette": FEMININE, "serviette": FEMININE, "adresse": FEMININE,
    "signature": FEMININE, "facture": FEMININE, "commande": FEMININE,
    "reunion": FEMININE, "réunion": FEMININE, "entreprise": FEMININE,
    "societe": FEMININE, "société": FEMININE, "equipe": FEMININE, "équipe": FEMININE,
    "reservation": FEMININE, "réservation": FEMININE, "chambre_hotel": FEMININE,

    # masculine
    "livre": MASCULINE, "stylo": MASCULINE, "papier": MASCULINE, "cahier": MASCULINE,
    "sac": MASCULINE, "telephone": MASCULINE, "téléphone": MASCULINE,
    "ordinateur": MASCULINE, "bureau": MASCULINE, "travail": MASCULINE,
    "metier": MASCULINE, "métier": MASCULINE, "argent": MASCULINE, "prix": MASCULINE,
    "temps": MASCULINE, "jour": MASCULINE, "mois": MASCULINE, "matin": MASCULINE,
    "soir": MASCULINE, "an": MASCULINE, "moment": MASCULINE, "siecle": MASCULINE,
    "siècle": MASCULINE, "pere": MASCULINE, "père": MASCULINE, "frere": MASCULINE,
    "frère": MASCULINE, "fils": MASCULINE, "homme": MASCULINE, "ami": MASCULINE,
    "enfant": MASCULINE, "garcon": MASCULINE, "garçon": MASCULINE,
    "monsieur": MASCULINE, "corps": MASCULINE, "bras": MASCULINE, "pied": MASCULINE,
    "doigt": MASCULINE, "oeil": MASCULINE, "œil": MASCULINE, "nez": MASCULINE,
    "dos": MASCULINE, "coeur": MASCULINE, "cœur": MASCULINE, "pays": MASCULINE,
    "monde": MASCULINE, "ciel": MASCULINE, "soleil": MASCULINE, "vent": MASCULINE,
    "feu": MASCULINE, "arbre": MASCULINE, "jardin": MASCULINE, "chemin": MASCULINE,
    "pont": MASCULINE, "train": MASCULINE, "avion": MASCULINE, "bateau": MASCULINE,
    "velo": MASCULINE, "vélo": MASCULINE, "billet": MASCULINE, "passeport": MASCULINE,
    "hotel": MASCULINE, "hôtel": MASCULINE, "restaurant": MASCULINE,
    "magasin": MASCULINE, "marche": MASCULINE, "marché": MASCULINE,
    "musee": MASCULINE, "musée": MASCULINE, "lycee": MASCULINE, "lycée": MASCULINE,
    "cafe": MASCULINE, "café": MASCULINE, "the": MASCULINE, "thé": MASCULINE,
    "pain": MASCULINE, "fromage": MASCULINE, "repas": MASCULINE, "plat": MASCULINE,
    "verre": MASCULINE, "couteau": MASCULINE, "lit": MASCULINE, "mur": MASCULINE,
    "toit": MASCULINE, "sol": MASCULINE, "nom": MASCULINE, "prenom": MASCULINE,
    "prénom": MASCULINE, "numero": MASCULINE, "numéro": MASCULINE,
    "probleme": MASCULINE, "problème": MASCULINE, "projet": MASCULINE,
    "document": MASCULINE, "dossier": MASCULINE, "rendez-vous": MASCULINE,
    "medecin": MASCULINE, "médecin": MASCULINE, "docteur": MASCULINE,
    "chien": MASCULINE, "chat": MASCULINE, "groupe": MASCULINE, "message": MASCULINE,
    "compte": MASCULINE, "service": MASCULINE, "site": MASCULINE, "mot": MASCULINE,
}


def _normalise(word: str) -> str:
    return word.strip().lower().strip(".,!?;:\"'()[]{}«»")


def _strip_accents(word: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", word)
        if unicodedata.category(c) != "Mn"
    )


def french_gender(word: str) -> Optional[str]:
    """
    ``"m"``, ``"f"``, or None when unknown.

    The lexicon is consulted before the suffix rules, because the common words
    are disproportionately the irregular ones — *page* is feminine despite the
    masculine ``-age`` ending, *musée* masculine despite the feminine ``-ée``.
    """
    if not isinstance(word, str):
        return None

    key = _normalise(word)
    if not key:
        return None

    if key in _LEXICON:
        return _LEXICON[key]

    # Try again without accents, so "reponse" finds "réponse".
    bare = _strip_accents(key)
    for candidate, gender in _LEXICON.items():
        if _strip_accents(candidate) == bare:
            return gender

    for suffix in sorted(_FEMININE_SUFFIXES, key=len, reverse=True):
        if key.endswith(suffix):
            return FEMININE
    for suffix in sorted(_MASCULINE_SUFFIXES, key=len, reverse=True):
        if key.endswith(suffix):
            return MASCULINE

    return None


def french_possessive(following: str, plural: bool = False) -> str:
    """
    The singular possessive to use before ``following``.

    Three-way, not two: French uses the masculine form before any vowel-initial
    noun regardless of gender, because "ta amie" cannot be pronounced. So
    "votre amie" downgrades to "ton amie", not "ta amie".
    """
    if plural:
        return "tes"

    word = _normalise(following)
    if not word:
        return "ton"

    if FR_VOWEL_START.match(word):
        return "ton"

    return "ta" if french_gender(word) == FEMININE else "ton"
