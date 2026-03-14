import asyncio
import logging
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


async def _get_sink_volume() -> int:
    """Read current PipeWire default sink volume percent."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "pactl", "get-sink-volume", "@DEFAULT_SINK@",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await proc.communicate()
        for part in stdout.decode().split('/'):
            part = part.strip()
            if part.endswith('%'):
                return int(part[:-1].strip())
    except Exception:
        pass
    return 50


async def _set_sink_volume(percent: int):
    """Set PipeWire default sink volume."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{percent}%",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.communicate()
    except Exception:
        pass


async def play_audio_file(file_path: str | Path):
    """Play an audio file via PipeWire (paplay) at the current Devialet volume level."""
    try:
        # paplay volume: 65536 = 100%. Scale to match Devialet volume
        # so TTS isn't louder than music. Default to 50% if can't read.
        devialet_vol = 50
        try:
            import requests
            from config import DEVIALET_IP
            r = requests.get(
                f"http://{DEVIALET_IP}/ipcontrol/v1/systems/current/sources/current/soundControl/volume",
                timeout=1,
            )
            devialet_vol = r.json().get("volume", 50)
        except Exception:
            pass

        # Scale paplay volume: 65536 = 100%
        # TTS should be at the same perceived level as music
        paplay_vol = int(65536 * devialet_vol / 100)
        paplay_vol = max(6554, min(65536, paplay_vol))  # 10%-100% range

        proc = await asyncio.create_subprocess_exec(
            "paplay", f"--volume={paplay_vol}", str(file_path),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        logger.info("[OUTPUT] TTS joue (vol=%d, devialet=%d%%)", paplay_vol, devialet_vol)
    except FileNotFoundError:
        logger.warning("[OUTPUT] paplay non disponible — audio non joue")
    except Exception as e:
        logger.error("[OUTPUT] Erreur lecture: %s", e)


async def play_audio_bytes(data: bytes, suffix: str = ".wav"):
    """Write audio bytes to temp file and play."""
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(data)
        tmp_path = f.name
    await play_audio_file(tmp_path)
    Path(tmp_path).unlink(missing_ok=True)
