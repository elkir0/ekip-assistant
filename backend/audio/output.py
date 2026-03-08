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
    """Play an audio file via PipeWire (paplay). Uses high paplay volume to compensate sink level."""
    try:
        # Use paplay volume above 100% to compensate for sink being at 50%
        # 65536 = 100%, 98304 = 150% — enough to be heard clearly without blasting
        proc = await asyncio.create_subprocess_exec(
            "paplay", "--volume=98304", str(file_path),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        logger.info("[OUTPUT] Lecture terminee: %s", file_path)
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
