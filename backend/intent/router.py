import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

INTENT_KEYWORDS = {
    "MUSIC_PLAY": ["mets", "joue", "lance", "musique", "ecouter"],
    "MUSIC_PAUSE": ["pause", "stop", "arrete", "arrête"],
    "MUSIC_NEXT": ["suivant", "suivante", "passe", "skip", "prochaine", "change"],
    "MUSIC_VOLUME_UP": ["plus fort", "monte le son", "augmente", "monte le volume"],
    "MUSIC_VOLUME_DOWN": ["moins fort", "baisse le son", "diminue", "baisse le volume", "baisser le son", "baisser"],
    "YOUTUBE_PLAY": ["youtube", "video", "vidéo", "regarde", "montre", "clip"],
    "YOUTUBE_STOP": ["ferme", "quitte", "stop video", "stop vidéo"],
    "WEATHER": ["meteo", "météo", "temps", "temperature", "température", "pluie", "soleil"],
    "SLEEP": ["dodo", "dort", "dors", "eteins", "éteins", "bonne nuit", "nuit"],
    "WAKE": ["reveille", "réveille", "allume", "debout", "leve", "lève"],
}

# Control intents have priority over content intents when both match
PRIORITY_INTENTS = {"MUSIC_VOLUME_DOWN", "MUSIC_VOLUME_UP", "MUSIC_NEXT", "MUSIC_PAUSE", "YOUTUBE_STOP"}


def extract_query(text: str, intent: str) -> str:
    """Extract the search query from the transcript after removing intent keywords."""
    cleaned = text.lower().strip()

    # Remove wake word
    for wake in ["hey pi", "pi board", "piboard"]:
        cleaned = cleaned.replace(wake, "")

    # Remove intent trigger words
    keywords = INTENT_KEYWORDS.get(intent, [])
    for kw in keywords:
        cleaned = cleaned.replace(kw, "")

    # Remove filler words
    for filler in ["de la", "du", "des", "de", "le", "la", "les", "un", "une", "sur", "moi"]:
        cleaned = re.sub(rf"\b{filler}\b", "", cleaned)

    return cleaned.strip()


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

    # If a priority intent (volume, next, pause) matches, prefer it over content intents
    priority_matches = {k: v for k, v in scores.items() if k in PRIORITY_INTENTS}
    if priority_matches:
        best_intent = max(priority_matches, key=priority_matches.get)
    else:
        best_intent = max(scores, key=scores.get)
    query = extract_query(text, best_intent)

    logger.info("[INTENT] '%s' -> %s (query='%s')", text[:50], best_intent, query)
    return best_intent, query
