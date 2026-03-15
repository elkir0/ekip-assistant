import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

INTENT_KEYWORDS = {
    # Music playback
    "MUSIC_PLAY": ["mets", "joue", "lance", "musique", "ecouter", "écouter"],
    "MUSIC_PAUSE": ["pause", "stop", "arrete", "arrête", "stoppe", "tais-toi", "tais toi",
                     "chut", "silence", "la ferme", "suffit", "ca suffit", "ça suffit"],
    "MUSIC_RESUME": ["reprends", "continue", "relance", "remets", "remet", "encore", "repart"],
    "MUSIC_NEXT": ["suivant", "suivante", "passe", "skip", "prochaine", "change",
                    "autre chose", "j'aime pas", "c'est nul", "pas ca", "pas ça"],
    "MUSIC_PREV": ["precedent", "précédent", "precedente", "précédente", "reviens",
                    "avant", "d'avant", "la derniere", "la dernière"],
    # Volume
    "MUSIC_VOLUME_UP": ["plus fort", "monte le son", "augmente", "monte le volume",
                         "plus haut", "plus de son", "monte"],
    "MUSIC_VOLUME_DOWN": ["moins fort", "baisse le son", "diminue", "baisse le volume",
                           "baisser le son", "baisser", "plus bas", "plus doucement",
                           "plus doux", "doucement", "trop fort"],
    "MUSIC_VOLUME_SET": ["volume a", "volume à", "volume au", "son a", "son à",
                          "mets le volume", "mets le son", "pourcent", "%"],
    "MUSIC_MUTE": ["coupe le son", "mute", "muet", "couper le son"],
    "MUSIC_UNMUTE": ["remet le son", "remets le son", "unmute", "du son"],
    # Music info / search
    "MUSIC_WHAT": ["c'est quoi", "c'est qui", "quel morceau", "quelle chanson",
                    "qui chante", "quel artiste", "quel titre", "c'est quel"],
    "MUSIC_FIND": ["trouve moi", "trouve-moi", "cherche moi", "cherche-moi",
                    "la chanson qui dit", "la musique qui dit", "qui fait", "le morceau qui", "le son qui",
                    "je recherche", "je me souviens plus", "je me rappelle plus", "ça fait", "ça dit",
                    "comment s'appelle", "comment elle s'appelle"],
    "MUSIC_PLAYLIST": ["playlist", "ma playlist", "mes playlists"],
    "MUSIC_AI_MIX": ["fais moi", "fais-moi", "cree moi", "crée moi", "genere", "génère",
                      "fabrique", "fabriquer", "compose", "concocte",
                      "ambiance", "mix de", "selection de", "sélection de",
                      "compile", "propose moi", "propose-moi",
                      "prepare", "prépare", "liste de lecture",
                      "les meilleur", "qui ont marqué", "pour se motiver",
                      "top", "classement", "les plus",
                      "playlist de", "playlist pour"],
    # YouTube
    "YOUTUBE_PLAY": ["youtube", "video", "vidéo", "regarde", "montre", "clip",
                      "dessin anime", "dessin animé", "épisode", "episode"],
    "YOUTUBE_STOP": ["ferme la video", "ferme la vidéo", "quitte", "stop video",
                      "stop vidéo", "arrete la video", "arrête la vidéo"],
    # Weather
    "WEATHER": ["meteo", "météo", "temps qu'il fait", "temperature", "température",
                 "pluie", "soleil", "temps dehors", "quel temps", "fait il beau",
                 "fait-il beau", "pleut", "il pleut"],
    # System
    "SLEEP": ["dodo", "dort", "dors", "eteins", "éteins", "bonne nuit", "nuit",
              "au revoir", "a demain", "à demain"],
    "WAKE": ["reveille", "réveille", "allume", "debout", "leve", "lève", "bonjour"],
    "TIME": ["heure", "quelle heure"],
    "REPEAT": ["repete", "répète", "redis", "repeter", "répéter", "redit"],
    "CANCEL": ["annule", "non merci", "rien", "laisse tomber", "oublie"],
    "TIMER": ["minuteur", "timer", "chrono", "rappelle moi dans", "dans minutes"],
    # Social
    "GREETING": ["bonjour", "salut", "coucou", "hello", "hey"],
    "THANKS": ["merci", "super", "genial", "génial", "parfait", "cool", "top"],
}

# Control intents have priority over content intents when both match
PRIORITY_INTENTS = {
    "MUSIC_VOLUME_DOWN", "MUSIC_VOLUME_UP", "MUSIC_VOLUME_SET",
    "MUSIC_MUTE", "MUSIC_UNMUTE",
    "MUSIC_NEXT", "MUSIC_PREV", "MUSIC_PAUSE", "MUSIC_RESUME",
    "MUSIC_WHAT", "YOUTUBE_STOP", "CANCEL", "REPEAT", "TIME",
    "GREETING", "THANKS",
}

# Keywords that should NEVER trigger MUSIC_PLAY (they have "mets" or "musique" but mean something else)
ANTI_PLAY_WORDS = ["plus fort", "moins fort", "monte", "baisse", "volume", "mets le son",
                    "mets le volume", "mets plus fort"]


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
    m = re.search(r'(\d+)\s*%?', text)
    if m:
        val = int(m.group(1))
        if 0 <= val <= 100:
            return val
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


def route(text: str, active_context: str | None = None) -> tuple[str, str]:
    """Route a transcript to an intent.

    Args:
        text: The transcribed text
        active_context: Current active domain (music/youtube/None) for contextual routing

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

    # --- Anti-confusion rules ---

    # "mets plus fort" → VOLUME_UP, not MUSIC_PLAY
    if "MUSIC_PLAY" in scores and any(w in lower for w in ANTI_PLAY_WORDS):
        del scores["MUSIC_PLAY"]

    # "volume" alone without a number → could be VOLUME_UP context, don't match VOLUME_SET
    if "MUSIC_VOLUME_SET" in scores and extract_volume_value(lower) is None:
        del scores["MUSIC_VOLUME_SET"]

    if not scores:
        return "GENERAL", text

    # --- Special cases ---

    # Number + volume keyword → VOLUME_SET
    if extract_volume_value(lower) is not None and any(k in lower for k in ["volume", "son", "pourcent", "%"]):
        logger.info("[INTENT] '%s' -> MUSIC_VOLUME_SET", text[:50])
        return "MUSIC_VOLUME_SET", text

    # "stop" when YouTube is playing → YOUTUBE_STOP instead of MUSIC_PAUSE
    if "MUSIC_PAUSE" in scores and active_context == "youtube":
        logger.info("[INTENT] '%s' -> YOUTUBE_STOP (context=youtube)", text[:50])
        return "YOUTUBE_STOP", text

    # --- Priority-based routing ---

    # Priority intents (volume, next, pause) beat content intents
    priority_matches = {k: v for k, v in scores.items() if k in PRIORITY_INTENTS}
    if priority_matches:
        best_intent = max(priority_matches, key=priority_matches.get)
    else:
        # MUSIC_FIND beats everything
        if "MUSIC_FIND" in scores:
            best_intent = "MUSIC_FIND"
        # AI_MIX beats MUSIC_PLAY and MUSIC_PLAYLIST
        elif "MUSIC_AI_MIX" in scores and ("MUSIC_PLAY" in scores or "MUSIC_PLAYLIST" in scores):
            best_intent = "MUSIC_AI_MIX"
        # YOUTUBE_PLAY beats MUSIC_PLAY
        elif "YOUTUBE_PLAY" in scores and "MUSIC_PLAY" in scores:
            best_intent = "YOUTUBE_PLAY"
        else:
            best_intent = max(scores, key=scores.get)

    query = extract_query(text, best_intent)
    logger.info("[INTENT] '%s' -> %s (query='%s')", text[:50], best_intent, query)
    return best_intent, query
