"""Devialet IP Control API wrapper — async, zero-crash."""

import asyncio
import functools
import logging
from typing import Optional

import requests

from config import DEVIALET_IP

logger = logging.getLogger(__name__)
_TIMEOUT = 2


def _prefix(msg: str) -> str:
    return f"[DEVIALET] {msg}"


class DevialetService:
    """Async wrapper around the Devialet IP Control REST API."""

    def __init__(self, ip: Optional[str] = None):
        self.ip = ip or DEVIALET_IP
        self.base = f"http://{self.ip}/ipcontrol/v1"
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._last_volume: Optional[int] = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.get_event_loop()
        return self._loop

    async def _get(self, path: str) -> Optional[dict]:
        url = f"{self.base}{path}"
        try:
            resp = await self._get_loop().run_in_executor(
                None, functools.partial(requests.get, url, timeout=_TIMEOUT)
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning(_prefix(f"GET {path} failed: {exc}"))
            return None

    async def _post(self, path: str, body: Optional[dict] = None) -> bool:
        url = f"{self.base}{path}"
        try:
            resp = await self._get_loop().run_in_executor(
                None,
                functools.partial(
                    requests.post, url, json=body or {}, timeout=_TIMEOUT
                ),
            )
            resp.raise_for_status()
            return True
        except Exception as exc:
            logger.warning(_prefix(f"POST {path} failed: {exc}"))
            return False

    # ------------------------------------------------------------------
    # 1. Start / connectivity
    # ------------------------------------------------------------------

    async def start(self) -> bool:
        """Test connectivity and cache current volume."""
        info = await self._get("/devices/current")
        if info:
            name = info.get("deviceName", "?")
            model = info.get("model", "?")
            logger.info(_prefix(f"Connected — {model} '{name}' at {self.ip}"))
            # Cache current Devialet volume so ensure_volume works from start
            vol_data = await self._get("/systems/current/sources/current/soundControl/volume")
            if vol_data and vol_data.get("volume") is not None:
                self._last_volume = vol_data["volume"]
                logger.info(_prefix(f"Volume initial: {self._last_volume}%"))
            else:
                self._last_volume = 40  # Safe default
                logger.info(_prefix("Pas de source active, volume par defaut: 40%"))
            return True
        logger.error(_prefix(f"Cannot reach Devialet at {self.ip}"))
        return False

    # ------------------------------------------------------------------
    # 2. Status (aggregate)
    # ------------------------------------------------------------------

    async def get_status(self) -> dict:
        """Return a combined status dict (device, source, volume, etc.)."""
        device, system, source, vol, night, eq = await asyncio.gather(
            self._get("/devices/current"),
            self._get("/systems/current"),
            self._get("/groups/current/sources/current"),
            self._get("/systems/current/sources/current/soundControl/volume"),
            self._get("/systems/current/settings/audio/nightMode"),
            self._get("/systems/current/settings/audio/equalizer"),
        )
        connected = device is not None
        fw = (device or {}).get("release", {})
        return {
            "connected": connected,
            "model": (device or {}).get("model", ""),
            "systemName": (system or {}).get("systemName", "Devialet"),
            "firmware": fw.get("version", "") if isinstance(fw, dict) else str(fw),
            "volume": (vol or {}).get("volume") if vol else None,
            "nightMode": (night or {}).get("nightMode") == "on" if night else False,
            "eqPreset": (eq or {}).get("preset", "flat"),
            "currentSource": (source or {}).get("source", {}).get("type") if source and source.get("source") else None,
            "playingState": (source or {}).get("playingState"),
            "muteState": (source or {}).get("muteState"),
            "metadata": (source or {}).get("metadata"),
            "sources": [s.get("type") for s in ((await self.get_sources()) or [])],
            "devices": [
                {
                    "name": d.get("deviceName", ""),
                    "role": d.get("role", ""),
                    "serial": d.get("serial", ""),
                    "isLeader": d.get("isSystemLeader", False),
                }
                for d in (system or {}).get("devices", [])
            ],
        }

    # ------------------------------------------------------------------
    # 3-4. Volume
    # ------------------------------------------------------------------

    async def set_volume(self, percent: int) -> bool:
        """Set volume (0-100) on Devialet only. PipeWire stays at 100%."""
        percent = max(0, min(100, percent))
        self._last_volume = percent
        return await self._post(
            "/systems/current/sources/current/soundControl/volume",
            {"volume": percent},
        )

    async def ensure_volume(self):
        """Re-apply last known volume (call after track change to prevent AirPlay reset)."""
        if self._last_volume is not None:
            logger.info(_prefix(f"ensure_volume: {self._last_volume}%"))
            await self._post(
                "/systems/current/sources/current/soundControl/volume",
                {"volume": self._last_volume},
            )
            # Also cap PipeWire so AirPlay doesn't override
            try:
                import subprocess
                subprocess.run(
                    ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{self._last_volume}%"],
                    timeout=2, capture_output=True,
                )
            except Exception:
                pass

    async def volume_up(self) -> bool:
        return await self._post(
            "/systems/current/sources/current/soundControl/volumeUp"
        )

    async def volume_down(self) -> bool:
        return await self._post(
            "/systems/current/sources/current/soundControl/volumeDown"
        )

    # ------------------------------------------------------------------
    # 5. Playback
    # ------------------------------------------------------------------

    async def play(self) -> bool:
        return await self._post("/groups/current/sources/current/playback/play")

    async def pause(self) -> bool:
        return await self._post("/groups/current/sources/current/playback/pause")

    async def next_track(self) -> bool:
        return await self._post("/groups/current/sources/current/playback/next")

    async def previous_track(self) -> bool:
        return await self._post(
            "/groups/current/sources/current/playback/previous"
        )

    # ------------------------------------------------------------------
    # 6. Mute
    # ------------------------------------------------------------------

    async def mute(self) -> bool:
        return await self._post("/groups/current/sources/current/playback/mute")

    async def unmute(self) -> bool:
        return await self._post(
            "/groups/current/sources/current/playback/unmute"
        )

    # ------------------------------------------------------------------
    # 7. Night mode
    # ------------------------------------------------------------------

    async def set_night_mode(self, on: bool) -> bool:
        return await self._post(
            "/systems/current/settings/audio/nightMode",
            {"nightMode": "on" if on else "off"},
        )

    # ------------------------------------------------------------------
    # 8-9. Equalizer
    # ------------------------------------------------------------------

    async def get_equalizer(self) -> Optional[dict]:
        return await self._get("/systems/current/settings/audio/equalizer")

    async def set_equalizer_preset(self, preset: str) -> bool:
        """Set EQ preset: flat, custom, voice, etc."""
        return await self._post(
            "/systems/current/settings/audio/equalizer",
            {"preset": preset},
        )

    # ------------------------------------------------------------------
    # 10-11. Sources
    # ------------------------------------------------------------------

    async def get_sources(self) -> Optional[list]:
        data = await self._get("/groups/current/sources")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("sources", [])
        return None

    async def get_current_source(self) -> Optional[dict]:
        return await self._get("/groups/current/sources/current")
