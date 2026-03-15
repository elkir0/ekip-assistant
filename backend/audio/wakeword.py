import asyncio
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)

# Try to import EfficientWord-Net (preferred)
try:
    from eff_word_net.engine import HotwordDetector
    from eff_word_net.audio_processing import Resnet50_Arc_loss
    HAS_EWN = True
except ImportError:
    HAS_EWN = False
    logger.warning("[WAKEWORD] EfficientWord-Net non disponible")

# Fallback: openWakeWord
try:
    from openwakeword.model import Model as OWWModel
    HAS_OWW = True
except ImportError:
    HAS_OWW = False

# Admin config (runtime settings)
try:
    from admin.config_manager import config as admin_config
except ImportError:
    admin_config = None

def _cfg(key, default):
    """Read from admin config, fallback to default."""
    if admin_config:
        return admin_config.get("wakeword", key, default)
    return default

# Defaults (overridden by admin config at runtime)
COOLDOWN_S_DEFAULT = 15.0
THRESHOLD_DEFAULT = 0.5

# EfficientWord-Net paths
REFS_DIR = os.path.join(os.path.dirname(__file__), "hotword_refs")
WAKEWORD_NAME = "terminator"
WAKEWORD_REF = os.path.join(REFS_DIR, f"{WAKEWORD_NAME}_ref.json")

# openWakeWord fallback
OWW_CHUNK_SIZE = 1280
MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
CUSTOM_MODEL = os.path.join(MODELS_DIR, "Terminator!.onnx")

# EWN expects 24000 samples (1.5 seconds at 16kHz)
EWN_FRAME_SIZE = 24000


class WakeWordDetector:
    def __init__(self, on_wake: Callable[[], Awaitable[None]] | None = None):
        self.on_wake = on_wake
        self._detector = None
        self._last_trigger = 0.0
        self._debug_counter = 0
        self.running = False
        self.paused = False
        self._needs_reset = False
        self._use_ewn = False
        # openWakeWord fallback state
        self._oww_model = None
        self._buffer = np.array([], dtype=np.int16)

    async def start(self):
        # Read config from admin panel (live values)
        self._threshold = float(_cfg("threshold", THRESHOLD_DEFAULT))
        self._cooldown = float(_cfg("cooldown_s", COOLDOWN_S_DEFAULT))
        engine_pref = _cfg("engine", "ewn")

        if engine_pref == "ewn" and HAS_EWN and os.path.exists(WAKEWORD_REF):
            try:
                base_model = Resnet50_Arc_loss()
                self._detector = HotwordDetector(
                    hotword=WAKEWORD_NAME,
                    model=base_model,
                    reference_file=WAKEWORD_REF,
                    threshold=self._threshold,
                    relaxation_time=2,
                    continuous=True,
                )
                self._use_ewn = True
                logger.info("[WAKEWORD] EfficientWord-Net charge (%s, threshold=%.2f, cooldown=%.0fs)",
                           WAKEWORD_NAME, self._threshold, self._cooldown)
            except Exception as e:
                logger.error("[WAKEWORD] Erreur init EfficientWord-Net: %s", e)
                self._use_ewn = False

        if not self._use_ewn:
            if HAS_OWW:
                if os.path.exists(CUSTOM_MODEL):
                    self._oww_model = OWWModel(
                        wakeword_models=[CUSTOM_MODEL],
                        inference_framework="onnx",
                    )
                    logger.info("[WAKEWORD] openWakeWord (Terminator!, threshold=%.2f, cooldown=%.0fs)",
                               self._threshold, self._cooldown)
                else:
                    self._oww_model = OWWModel(
                        wakeword_models=["hey_jarvis"],
                        inference_framework="onnx",
                    )
                    logger.info("[WAKEWORD] openWakeWord (hey_jarvis, threshold=%.2f, cooldown=%.0fs)",
                               self._threshold, self._cooldown)
            else:
                logger.info("[WAKEWORD] Mode mock actif")

        self.running = True

    async def process(self, audio_queue: asyncio.Queue):
        if self._use_ewn:
            await self._process_ewn(audio_queue)
        else:
            await self._process_oww(audio_queue)

    async def _process_ewn(self, audio_queue: asyncio.Queue):
        """Process audio with EfficientWord-Net detector.

        Key optimizations vs naive approach:
        - scoreFrame runs in executor (doesn't block asyncio event loop)
        - Full frame slide (1.5s) instead of half (0.75s) = 2x fewer inferences
        - Small sleep after each inference to yield CPU to PipeWire/AirPlay
        """
        buffer = np.array([], dtype=np.int16)
        loop = asyncio.get_event_loop()
        # Single-thread pool — prevents EWN from eating all CPU cores
        ewn_pool = ThreadPoolExecutor(max_workers=1)

        while self.running:
            try:
                chunk = await asyncio.wait_for(audio_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            if self.paused:
                buffer = np.array([], dtype=np.int16)
                self._needs_reset = True
                continue

            if self._needs_reset:
                self._needs_reset = False
                buffer = np.array([], dtype=np.int16)
                continue

            buffer = np.concatenate([buffer, chunk])

            # Process ONE frame at a time, skip excess buffer to save CPU
            if len(buffer) >= EWN_FRAME_SIZE:
                # If buffer is way too full, skip to latest frame (drop old audio)
                if len(buffer) > EWN_FRAME_SIZE * 3:
                    buffer = buffer[-(EWN_FRAME_SIZE):]

                frame = buffer[:EWN_FRAME_SIZE]
                buffer = buffer[EWN_FRAME_SIZE:]

                rms = int(np.sqrt(np.mean(frame.astype(np.float32)**2)))

                try:
                    # Run inference in thread pool — don't block event loop
                    result = await loop.run_in_executor(
                        ewn_pool, lambda f=frame: self._detector.scoreFrame(f, unsafe=True)
                    )

                    self._debug_counter += 1
                    if result is not None:
                        confidence = result.get("confidence", 0)
                        matched = result.get("match", False)
                        if self._debug_counter % 10 == 0 or confidence > 0.3:
                            logger.info("[WAKEWORD] %s conf=%.3f match=%s (rms=%d)",
                                       WAKEWORD_NAME, confidence, matched, rms)

                        if matched:
                            now = time.monotonic()
                            if now - self._last_trigger < self._cooldown:
                                pass
                            else:
                                self._last_trigger = now
                                logger.info("[WAKEWORD] Detecte! (EWN conf=%.2f)", confidence)
                                if self.on_wake:
                                    await self.on_wake()
                    else:
                        if self._debug_counter % 25 == 0:
                            logger.info("[WAKEWORD] %s (silence, rms=%d)", WAKEWORD_NAME, rms)

                    # Long pause after inference — 500ms gives CPU ~40% instead of ~95%
                    await asyncio.sleep(0.5)

                except Exception as e:
                    if self._debug_counter % 100 == 0:
                        logger.warning("[WAKEWORD] EWN error: %s", e)

    async def _process_oww(self, audio_queue: asyncio.Queue):
        """Fallback: process audio with openWakeWord."""
        while self.running:
            try:
                chunk = await asyncio.wait_for(audio_queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            if not self._oww_model:
                continue

            if self.paused:
                self._buffer = np.array([], dtype=np.int16)
                self._needs_reset = True
                continue

            if self._needs_reset:
                self._needs_reset = False
                self._buffer = np.array([], dtype=np.int16)
                silence = np.zeros(OWW_CHUNK_SIZE * 10, dtype=np.int16)
                for i in range(10):
                    self._oww_model.predict(silence[i*OWW_CHUNK_SIZE:(i+1)*OWW_CHUNK_SIZE])
                logger.info("[WAKEWORD] Model flushed after pause")
                continue

            self._buffer = np.concatenate([self._buffer, chunk])

            while len(self._buffer) >= OWW_CHUNK_SIZE:
                frame = self._buffer[:OWW_CHUNK_SIZE]
                self._buffer = self._buffer[OWW_CHUNK_SIZE:]

                prediction = self._oww_model.predict(frame)

                for model_name, score in prediction.items():
                    self._debug_counter += 1
                    if self._debug_counter % 25 == 0 or score > 0.02:
                        logger.info("[WAKEWORD] %s score=%.3f (rms=%d)", model_name, score,
                                   np.sqrt(np.mean(frame.astype(np.float32)**2)))

                    if score >= self._threshold:
                        now = time.monotonic()
                        if now - self._last_trigger < COOLDOWN_S:
                            continue
                        self._last_trigger = now
                        logger.info("[WAKEWORD] Detecte! (score=%.2f)", score)
                        if self.on_wake:
                            await self.on_wake()

    def reset_cooldown(self):
        """Reset cooldown timer."""
        self._last_trigger = time.monotonic()
        logger.info("[WAKEWORD] Cooldown reset")

    async def stop(self):
        self.running = False
        logger.info("[WAKEWORD] Arrete")
