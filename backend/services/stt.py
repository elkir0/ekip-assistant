import asyncio
import logging
import time
import io
import wave
from typing import Callable, Awaitable

from config import OPENAI_API_KEY

logger = logging.getLogger(__name__)

try:
    from openai import AsyncOpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    logger.warning("[STT] openai non disponible")


class STTEngine:
    def __init__(self, on_transcript: Callable[[str, bool], Awaitable[None]] | None = None):
        self.on_transcript = on_transcript
        self._client = None
        self.running = False
        self.got_final = False

    async def start(self):
        if not HAS_OPENAI or not OPENAI_API_KEY:
            logger.info("[STT] Mode mock (pas de cle OpenAI)")
            self.running = True
            return

        self._client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        logger.info("[STT] OpenAI Whisper pret")
        self.running = True

    async def send_audio(self, audio_queue: asyncio.Queue, duration_s: float = 6.0):
        import numpy as np
        start = time.monotonic()
        all_samples = []
        total_samples = 0

        try:
            # Collect audio for duration_s seconds
            while self.running and (time.monotonic() - start) < duration_s:
                try:
                    chunk = await asyncio.wait_for(audio_queue.get(), timeout=0.5)
                    all_samples.append(chunk)
                    total_samples += len(chunk)
                except asyncio.TimeoutError:
                    continue

            if not all_samples or not self._client:
                logger.info("[STT] Pas d'audio collecte")
                return

            # Concatenate all audio
            audio = np.concatenate(all_samples)
            rms = int(np.sqrt(np.mean(audio.astype(np.float32)**2)))
            logger.info("[STT] Audio collecte: %.1fs, %d samples, rms=%d",
                       time.monotonic() - start, len(audio), rms)

            # Skip if audio is too quiet (just noise)
            if rms < 500:
                logger.info("[STT] Audio trop faible (rms=%d), skip", rms)
                return

            # Detect if audio is just constant music (no voice peaks)
            # Split into 500ms chunks and check if any chunk is significantly louder
            chunk_size = 8000  # 500ms at 16kHz
            float_audio = audio.astype(np.float32)
            chunk_rms = []
            for i in range(0, len(float_audio) - chunk_size, chunk_size):
                c = float_audio[i:i+chunk_size]
                chunk_rms.append(np.sqrt(np.mean(c**2)))
            if chunk_rms:
                max_rms = max(chunk_rms)
                min_rms = min(chunk_rms) if min(chunk_rms) > 0 else 1
                ratio = max_rms / min_rms
                logger.info("[STT] Voice ratio: %.1f (max=%.0f, min=%.0f)", ratio, max_rms, min_rms)
                # If all chunks have similar volume = constant music, no voice
                if ratio < 1.5:
                    logger.info("[STT] Audio constant (musique sans voix), skip")
                    return

            # Convert to WAV in memory (16kHz mono 16-bit)
            wav_buf = io.BytesIO()
            with wave.open(wav_buf, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(audio.tobytes())
            wav_buf.seek(0)
            wav_buf.name = "audio.wav"

            # Send to GPT-4o transcribe (better French, fewer hallucinations)
            logger.info("[STT] Envoi a GPT-4o-transcribe...")
            transcript_result = await self._client.audio.transcriptions.create(
                model="gpt-4o-transcribe",
                file=wav_buf,
                language="fr",
            )

            text = transcript_result.text.strip()

            # Filter Whisper hallucinations (common when audio is noise/silence)
            HALLUCINATIONS = [
                "merci d'avoir regardé",
                "sous-titres",
                "sous-titrage",
                "merci d'avoir écouté",
                "merci de votre attention",
                "a bientôt",
                "à bientôt",
                "n'oubliez pas de vous abonner",
                "abonnez-vous",
                "like et abonnez",
                "merci à tous",
                "partager cette vidéo",
                "réseaux sociaux",
                "n'hésite pas à",
                "n'hésitez pas à",
                "laisser un commentaire",
                "laissez un commentaire",
                "ne manquer aucune",
                "nouvelles vidéos",
                "cliquez sur",
                "clique sur",
                "la cloche",
            ]
            if text and any(h in text.lower() for h in HALLUCINATIONS):
                logger.warning("[STT] Hallucination Whisper filtree: '%s'", text)
                return

            if text:
                logger.info("[STT] FINAL: %s", text)
                self.got_final = True
                if self.on_transcript:
                    await self.on_transcript(text, True)
            else:
                logger.info("[STT] Whisper: transcript vide")

        except Exception as e:
            logger.error("[STT] Erreur Whisper: %s", e)
        finally:
            logger.info("[STT] Termine (%.1fs, %d samples)",
                       time.monotonic() - start, total_samples)

    async def stop(self):
        self.running = False
        logger.info("[STT] Arrete")
