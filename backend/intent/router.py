import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

INTENT_KEYWORDS = {
    # Music
    "MUSIC_PLAY": ["mets", "joue", "lance", "musique", "ecouter", "écouter"],
    "MUSIC_PAUSE": ["pause", "stop", "arrete", "arrête"],
    "MUSIC_RESUME": ["reprends", "continue", "relance"],
    "MUSIC_NEXT": ["suivant", "suivante", "passe", "skip", "prochaine", "change"],
    "MUSIC_PREV": ["precedent", "précédent", "precedente", "précédente", "reviens", "avant"],
    "MUSIC_VOLUME_UP": ["plus fort", "monte le son", "augmente", "monte le volume"],
    "MUSIC_VOLUME_DOWN": ["moins fort", "baisse le son", "diminue", "baisse le volume", "baisser le son", "baisser"],
    "MUSIC_VOLUME_SET": ["volume a", "volume à", "volume au", "son a", "son à", "mets le volume", "mets le son", "volume", "pourcent", "%"],
    "MUSIC_WHAT": ["c'est quoi", "c'est qui", "quel morceau", "quelle chanson", "qui chante", "quel artiste"],
    "MUSIC_PLAYLIST": ["playlist", "ma playlist", "mes playlists"],
    "MUSIC_AI_MIX": ["fais moi", "cree moi", "crée moi", "genere", "génère", "ambiance",
                      "mix de", "selection de", "sélection de", "compile", "propose moi",
                      "prepare", "prépare", "liste de lecture", "les meilleur", "qui ont marqué",
                      "top", "classement", "les plus"],
    # YouTube
    "YOUTUBE_PLAY": ["youtube", "video", "vidéo", "regarde", "montre", "clip", "dessin anime", "dessin animé", "épisode", "episode"],
    "YOUTUBE_STOP": ["ferme", "quitte", "stop video", "stop vidéo"],
    # Weather
    "WEATHER": ["meteo", "météo", "temps qu'il fait", "temperature", "température", "pluie", "soleil", "temps dehors"],
    # System
    "SLEEP": ["dodo", "dort", "dors", "eteins", "éteins", "bonne nuit", "nuit"],
    "WAKE": ["reveille", "réveille", "allume", "debout", "leve", "lève"],
    "TIME": ["heure", "quelle heure"],
    "REPEAT": ["repete", "répète", "redis", "repeter", "répéter", "redit"],
    "CANCEL": ["annule", "non merci", "rien", "laisse tomber", "oublie"],
    "TIMER": ["minuteur", "timer", "chrono", "rappelle moi dans", "dans minutes"],
}

# Control intents have priority over content intents when both match
PRIORITY_INTENTS = {
    "MUSIC_VOLUME_DOWN", "MUSIC_VOLUME_UP", "MUSIC_VOLUME_SET",
    "MUSIC_NEXT", "MUSIC_PREV", "MUSIC_PAUSE", "MUSIC_RESUME",
    "MUSIC_WHAT", "YOUTUBE_STOP", "CANCEL", "REPEAT", "TIME",
}


def extract_query(text: str, intent: str) -> str:
    """Extract the search query from the transcript after removing intent keywords."""
    cleaned = text.lower().strip().rstrip(".")

    # Remove wake word
    for wake in ["hey pi", "pi board", "piboard", "terminator"]:
        cleaned = cleaned.replace(wake, "")

    # Remove intent trigger words (longest first to avoid partial matches)
    keywords = sorted(INTENT_KEYWORDS.get(intent, []), key=len, reverse=True)
    for kw in keywords:
        cleaned = cleaned.replace(kw, " ")

    # Only remove leading filler words (don't touch the actual query content)
    cleaned = re.sub(r"^\s*(?:de la|du|des|de|le|la|les|un|une|sur|moi)\s+", "", cleaned.strip())

    # Normalize whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned


_FRENCH_NUMBERS = {
    "zero": 0, "cinq": 5, "dix": 10, "quinze": 15, "vingt": 20,
    "vingt-cinq": 25, "trente": 30, "trente-cinq": 35, "quarante": 40,
    "quarante-cinq": 45, "cinquante": 50, "cinquante-cinq": 55,
    "soixante": 60, "soixante-cinq": 65, "soixante-dix": 70,
    "soixante-quinze": 75, "quatre-vingt": 80, "quatre-vingts": 80,
    "quatre-vingt-cinq": 85, "quatre-vingt-dix": 90, "cent": 100,
}


def extract_volume_value(text: str) -> int | None:
    """Extract a volume percentage from text like 'volume a 30%' or 'volume a soixante'."""
    # Try digits first
    m = re.search(r'(\d+)\s*%?', text)
    if m:
        val = int(m.group(1))
        if 0 <= val <= 100:
            return val
    # Try French number words
    lower = text.lower()
    for word, val in sorted(_FRENCH_NUMBERS.items(), key=lambda x: -len(x[0])):
        if word in lower:
            return val
    return None


def extract_timer_minutes(text: str) -> int | None:
    """Extract timer duration from text like 'minuteur 10 minutes'."""
    m = re.search(r'(\d+)\s*(?:minute|min)', text)
    if m:
        return int(m.group(1))
    return None


def route(text: str) -> tuple[str, str]:
    """Route a transcript to an intent.

    Returns (intent, query) tuple.
    """
    lower = text.lower().strip()

    # Score each intent by keyword matches
    scores: dict[str, int] = {}
    for intent, keywords in INTENT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in lower)
        if score > 0:
            scores[intent] = score

    if not scores:
        return "GENERAL", text

    # Special case: if there's a number + volume keywords → VOLUME_SET takes over
    if extract_volume_value(lower) is not None and any(k in lower for k in ["volume", "son", "pourcent", "%"]):
        query = extract_query(text, "MUSIC_VOLUME_SET")
        logger.info("[INTENT] '%s' -> MUSIC_VOLUME_SET (query='%s')", text[:50], query)
        return "MUSIC_VOLUME_SET", text  # pass full text for number extraction

    # If a priority intent (volume, next, pause) matches, prefer it over content intents
    priority_matches = {k: v for k, v in scores.items() if k in PRIORITY_INTENTS}
    if priority_matches:
        best_intent = max(priority_matches, key=priority_matches.get)
    else:
        # AI_MIX beats MUSIC_PLAY — complex requests are AI playlists
        if "MUSIC_AI_MIX" in scores and "MUSIC_PLAY" in scores:
            best_intent = "MUSIC_AI_MIX"
        # YOUTUBE_PLAY beats MUSIC_PLAY when both match
        elif "YOUTUBE_PLAY" in scores and "MUSIC_PLAY" in scores:
            best_intent = "YOUTUBE_PLAY"
        else:
            best_intent = max(scores, key=scores.get)
    query = extract_query(text, best_intent)

    logger.info("[INTENT] '%s' -> %s (query='%s')", text[:50], best_intent, query)
    return best_intent, query
