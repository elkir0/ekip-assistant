import asyncio
import logging
import tempfile
from pathlib import Path

from config import OPENAI_API_KEY
from audio.output import play_audio_file

logger = logging.getLogger(__name__)

try:
    from openai import AsyncOpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    logger.warning("[TTS] openai non disponible")


class TTSEngine:
    def __init__(self):
        self._client = None

    async def start(self):
        if not HAS_OPENAI or not OPENAI_API_KEY:
            logger.info("[TTS] Mode mock (pas de cle API)")
            return
        self._client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        logger.info("[TTS] Client OpenAI initialise")

    async def speak(self, text: str, duck_callback=None):
        if not self._client:
            logger.info("[TTS] Mock: '%s'", text[:60])
            return

        try:
            # Duck music volume if callback provided
            if duck_callback:
                await duck_callback(20)

            response = await self._client.audio.speech.create(
                model="tts-1",
                voice="nova",
                input=text,
                response_format="wav",
                speed=0.95,
            )

            # Write to temp file and play
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(response.content)
                tmp_path = f.name

            logger.info("[TTS] Lecture audio (%d bytes)", len(response.content))
            await play_audio_file(tmp_path)
            Path(tmp_path).unlink(missing_ok=True)

            # Restore music volume
            if duck_callback:
                await duck_callback(100)

        except Exception as e:
            logger.error("[TTS] Erreur: %s", e)
            if duck_callback:
                await duck_callback(100)
