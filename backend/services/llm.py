import logging

from config import OPENAI_API_KEY

logger = logging.getLogger(__name__)

try:
    from openai import AsyncOpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    logger.warning("[LLM] openai non disponible")

SYSTEM_PROMPT = """Tu es PI-Board, un assistant vocal intelligent installe sur un Raspberry Pi en Guadeloupe.
Tu reponds de maniere concise et naturelle en francais.
Tes reponses sont courtes (1-2 phrases max) car elles seront lues a voix haute.
Tu es sympathique et utile. Tu tutoies l'utilisateur."""


class LLMHandler:
    def __init__(self):
        self._client = None

    async def start(self):
        if not HAS_OPENAI or not OPENAI_API_KEY:
            logger.info("[LLM] Mode mock (pas de cle API)")
            return
        self._client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        logger.info("[LLM] Client OpenAI initialise")

    async def normalize_music_query(self, raw_query: str) -> str:
        """Use LLM to clean up a music query from STT transcription."""
        if not self._client:
            return raw_query

        try:
            response = await self._client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=50,
                temperature=0,
                messages=[
                    {"role": "system", "content": (
                        "Tu recois une transcription vocale approximative d'une demande de musique. "
                        "Extrais et corrige le nom de l'artiste et/ou du morceau. "
                        "Reponds UNIQUEMENT avec la requete corrigee pour Spotify, rien d'autre. "
                        "Exemples:\n"
                        "- 'mais de la musique par singuina' -> 'Singuila'\n"
                        "- 'joue du jazz' -> 'jazz'\n"
                        "- 'mets un son de dadou' -> 'Dadju'\n"
                        "- 'lance singula rossignol' -> 'Singuila Rossignol'\n"
                        "- 'mais par fin d'hier' -> 'Singuila'\n"
                        "- 'mis de la musique a Henri Salvador' -> 'Henri Salvador'\n"
                    )},
                    {"role": "user", "content": raw_query},
                ],
            )
            cleaned = response.choices[0].message.content.strip().strip('"\'')
            logger.info("[LLM] Normalize: '%s' -> '%s'", raw_query, cleaned)
            return cleaned
        except Exception as e:
            logger.error("[LLM] Normalize error: %s", e)
            return raw_query

    async def generate_playlist(self, prompt: str) -> list[str]:
        """Ask the LLM to generate a playlist of song titles for a given mood/theme."""
        if not self._client:
            return []
        try:
            response = await self._client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=500,
                temperature=0.8,
                messages=[
                    {"role": "system", "content": (
                        "Tu es un DJ expert. L'utilisateur te demande une playlist. "
                        "Reponds UNIQUEMENT avec une liste JSON de 12 morceaux. "
                        "Chaque element est une string 'Artiste - Titre'. "
                        "Choisis des morceaux varies, connus, qui correspondent parfaitement a la demande. "
                        "Pas de commentaires, pas d'explication, juste le JSON.\n"
                        "Exemple de reponse:\n"
                        '[\"Marvin Gaye - Let\'s Get It On\", \"Barry White - Can\'t Get Enough\"]'
                    )},
                    {"role": "user", "content": prompt},
                ],
            )
            text = response.choices[0].message.content.strip()
            # Parse JSON list
            import json
            # Handle markdown code blocks
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            songs = json.loads(text)
            if isinstance(songs, list):
                logger.info("[LLM] Playlist: %d morceaux pour '%s'", len(songs), prompt[:40])
                return songs[:15]
        except Exception as e:
            logger.error("[LLM] Playlist error: %s", e)
        return []

    async def ask(self, user_message: str, context: str = "") -> str:
        if not self._client:
            return "Je suis en mode test, je ne peux pas repondre pour le moment."

        system = SYSTEM_PROMPT
        if context:
            system += "\n\n" + context

        try:
            response = await self._client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=200,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_message},
                ],
            )
            text = response.choices[0].message.content
            logger.info("[LLM] Reponse: %s", text[:80])
            return text
        except Exception as e:
            logger.error("[LLM] Erreur: %s", e)
            return "Desole, je n'ai pas pu traiter ta demande."
