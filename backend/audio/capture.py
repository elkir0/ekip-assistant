import asyncio
import logging
import numpy as np

logger = logging.getLogger(__name__)

TARGET_RATE = 16000
CHANNELS = 1
CHUNK = 1024
FORMAT_WIDTH = 2  # 16-bit

try:
    import pyaudio
    HAS_PYAUDIO = True
except ImportError:
    HAS_PYAUDIO = False
    logger.warning("[AUDIO] PyAudio non disponible — mode mock actif")


def resample(data: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    if src_rate == dst_rate:
        return data
    from math import gcd
    from scipy.signal import resample_poly
    # resample_poly does proper anti-aliasing filter before decimation
    g = gcd(src_rate, dst_rate)
    up = dst_rate // g
    down = src_rate // g
    resampled = resample_poly(data.astype(np.float32), up, down)
    return np.clip(resampled, -32768, 32767).astype(np.int16)


class AudioCapture:
    def __init__(self, device_name: str = "AI-Voice"):
        self.device_name = device_name
        self.running = False
        self._stream = None
        self._pa = None
        self._device_index = None
        self._device_rate = TARGET_RATE
        self._listeners: list[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._listeners.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        if q in self._listeners:
            self._listeners.remove(q)

    def _find_device(self) -> int | None:
        if not HAS_PYAUDIO:
            return None
        self._pa = pyaudio.PyAudio()

        # Try exact match first, then partial match
        for i in range(self._pa.get_device_count()):
            info = self._pa.get_device_info_by_index(i)
            if info["maxInputChannels"] > 0:
                name = info["name"]
                if self.device_name.lower() in name.lower():
                    self._device_rate = int(info["defaultSampleRate"])
                    logger.info("[AUDIO] Trouve: %s (index %d, rate=%d)", name, i, self._device_rate)
                    return i

        # Fallback: first USB input device
        for i in range(self._pa.get_device_count()):
            info = self._pa.get_device_info_by_index(i)
            if info["maxInputChannels"] > 0 and "usb" in info["name"].lower():
                self._device_rate = int(info["defaultSampleRate"])
                logger.info("[AUDIO] Fallback USB: %s (index %d, rate=%d)", info["name"], i, self._device_rate)
                return i

        logger.warning("[AUDIO] Aucun micro USB trouve, utilise default")
        return None

    async def start(self):
        self.running = True

        # Retry finding mic up to 5 times (USB mic may not be ready at boot)
        for attempt in range(5):
            self._device_index = self._find_device()
            if HAS_PYAUDIO and self._pa:
                # Try opening at 16kHz first (no resampling needed)
                opened = False
                for try_rate in [TARGET_RATE, self._device_rate]:
                    try:
                        self._stream = self._pa.open(
                            format=pyaudio.paInt16,
                            channels=CHANNELS,
                            rate=try_rate,
                            input=True,
                            input_device_index=self._device_index,
                            frames_per_buffer=CHUNK,
                        )
                        self._device_rate = try_rate
                        opened = True
                        break
                    except Exception as e:
                        if try_rate == TARGET_RATE:
                            logger.info("[AUDIO] 16kHz non supporte, essai %dHz", self._device_rate)
                        else:
                            raise e
                if opened:
                    logger.info("[AUDIO] Capture demarree (device=%s, rate=%d, resample=%s)",
                               self._device_index, self._device_rate,
                               "oui" if self._device_rate != TARGET_RATE else "non")
                    await self._read_loop()
                    return
            else:
                if attempt < 4:
                    logger.info("[AUDIO] Micro non trouve, retry dans 5s (tentative %d/5)", attempt + 1)
                    await asyncio.sleep(5)
                    continue

            # Cleanup before retry
            if self._pa:
                try:
                    self._pa.terminate()
                except Exception:
                    pass
                self._pa = None
            if attempt < 4:
                logger.error("[AUDIO] Erreur ouverture stream (tentative %d/5)", attempt + 1)
                await asyncio.sleep(5)

        logger.warning("[AUDIO] Micro introuvable apres 5 tentatives — mode mock")
        await self._mock_loop()

    async def _read_loop(self):
        loop = asyncio.get_event_loop()
        error_count = 0
        while self.running:
            try:
                data = await loop.run_in_executor(
                    None, self._stream.read, CHUNK, False
                )
                chunk = np.frombuffer(data, dtype=np.int16)
                error_count = 0

                # Resample to 16kHz if needed
                if self._device_rate != TARGET_RATE:
                    chunk = resample(chunk, self._device_rate, TARGET_RATE)

                for q in self._listeners:
                    try:
                        q.put_nowait(chunk)
                    except asyncio.QueueFull:
                        pass
            except Exception as e:
                error_count += 1
                logger.error("[AUDIO] Erreur lecture: %s", e)
                if error_count > 5:
                    logger.warning("[AUDIO] Trop d'erreurs, bascule en mode mock")
                    try:
                        self._stream.stop_stream()
                        self._stream.close()
                    except Exception:
                        pass
                    await self._mock_loop()
                    return
                await asyncio.sleep(0.5)

    async def _mock_loop(self):
        while self.running:
            chunk = np.zeros(512, dtype=np.int16)
            for q in self._listeners:
                try:
                    q.put_nowait(chunk)
                except asyncio.QueueFull:
                    pass
            await asyncio.sleep(512 / TARGET_RATE)

    async def stop(self):
        self.running = False
        if self._stream:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:
                pass
        if self._pa:
            self._pa.terminate()
        logger.info("[AUDIO] Capture arretee")
