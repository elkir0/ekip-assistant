"""Home automation service — Shelly rollers, Shelly relay, Kasa plug."""

import asyncio
import functools
import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)
_TIMEOUT = 3


def _prefix(msg: str) -> str:
    return f"[DOMOTIQUE] {msg}"


class DomotiqueService:
    """Async controller for home automation devices."""

    DEVICES = {
        "volet_gauche": {"ip": "192.168.1.52", "type": "shelly_roller", "name": "Volet Gauche"},
        "volet_milieu": {"ip": "192.168.1.20", "type": "shelly_roller", "name": "Volet Milieu"},
        "portail": {"ip": "192.168.1.55", "type": "shelly_relay_g3", "name": "Portail"},
        "guinguette": {"ip": "192.168.1.102", "type": "kasa_plug", "name": "Guinguette"},
    }

    def __init__(self):
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._kasa_plug = None  # lazy-loaded SmartPlug instance

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.get_event_loop()
        return self._loop

    async def _http_get(self, url: str) -> Optional[dict]:
        try:
            resp = await self._get_loop().run_in_executor(
                None, functools.partial(requests.get, url, timeout=_TIMEOUT)
            )
            resp.raise_for_status()
            try:
                return resp.json()
            except ValueError:
                return {"ok": True, "text": resp.text}
        except Exception as exc:
            logger.warning(_prefix(f"GET {url} failed: {exc}"))
            return None

    def _dev(self, device_id: str) -> Optional[dict]:
        dev = self.DEVICES.get(device_id)
        if not dev:
            logger.warning(_prefix(f"Unknown device: {device_id}"))
        return dev

    # ------------------------------------------------------------------
    # Kasa helper
    # ------------------------------------------------------------------

    async def _get_kasa(self):
        """Return a connected SmartPlug instance (lazy init)."""
        if self._kasa_plug is None:
            try:
                from kasa import SmartPlug
                dev = self.DEVICES["guinguette"]
                self._kasa_plug = SmartPlug(dev["ip"])
            except ImportError:
                logger.error(_prefix("python-kasa not installed"))
                return None
        try:
            await self._kasa_plug.update()
        except Exception as exc:
            logger.warning(_prefix(f"Kasa update failed: {exc}"))
            return None
        return self._kasa_plug

    # ------------------------------------------------------------------
    # Start / connectivity
    # ------------------------------------------------------------------

    async def start(self):
        """Test connectivity to all devices at startup."""
        for did, dev in self.DEVICES.items():
            ip = dev["ip"]
            dtype = dev["type"]
            try:
                if dtype == "shelly_roller":
                    r = await self._http_get(f"http://{ip}/status")
                    ok = r is not None
                elif dtype == "shelly_relay_g3":
                    r = await self._http_get(f"http://{ip}/rpc/Shelly.GetDeviceInfo")
                    ok = r is not None
                elif dtype == "kasa_plug":
                    plug = await self._get_kasa()
                    ok = plug is not None
                else:
                    ok = False
                status = "OK" if ok else "UNREACHABLE"
                logger.info(_prefix(f"{dev['name']} ({ip}) — {status}"))
            except Exception as exc:
                logger.warning(_prefix(f"{dev['name']} ({ip}) — error: {exc}"))

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    async def get_status(self) -> dict:
        """Return a dict with all device states."""
        result = {}
        for did, dev in self.DEVICES.items():
            ip = dev["ip"]
            dtype = dev["type"]
            try:
                if dtype == "shelly_roller":
                    data = await self._http_get(f"http://{ip}/roller/0")
                    result[did] = {
                        "name": dev["name"], "type": dtype, "online": data is not None,
                        "state": (data or {}).get("state"),
                        "position": (data or {}).get("current_pos"),
                    }
                elif dtype == "shelly_relay_g3":
                    data = await self._http_get(f"http://{ip}/rpc/Switch.GetStatus?id=0")
                    result[did] = {
                        "name": dev["name"], "type": dtype, "online": data is not None,
                        "output": (data or {}).get("output"),
                    }
                elif dtype == "kasa_plug":
                    plug = await self._get_kasa()
                    if plug:
                        result[did] = {
                            "name": dev["name"], "type": dtype, "online": True,
                            "is_on": plug.is_on,
                        }
                    else:
                        result[did] = {"name": dev["name"], "type": dtype, "online": False}
            except Exception as exc:
                logger.warning(_prefix(f"Status {did} failed: {exc}"))
                result[did] = {"name": dev["name"], "type": dtype, "online": False}
        return result

    # ------------------------------------------------------------------
    # Shelly rollers (Gen1 API)
    # ------------------------------------------------------------------

    async def roller_open(self, device_id: str) -> bool:
        dev = self._dev(device_id)
        if not dev or dev["type"] != "shelly_roller":
            return False
        r = await self._http_get(f"http://{dev['ip']}/roller/0?go=open")
        logger.info(_prefix(f"{dev['name']} — open"))
        return r is not None

    async def roller_close(self, device_id: str) -> bool:
        dev = self._dev(device_id)
        if not dev or dev["type"] != "shelly_roller":
            return False
        r = await self._http_get(f"http://{dev['ip']}/roller/0?go=close")
        logger.info(_prefix(f"{dev['name']} — close"))
        return r is not None

    async def roller_stop(self, device_id: str) -> bool:
        dev = self._dev(device_id)
        if not dev or dev["type"] != "shelly_roller":
            return False
        r = await self._http_get(f"http://{dev['ip']}/roller/0?go=stop")
        logger.info(_prefix(f"{dev['name']} — stop"))
        return r is not None

    async def roller_position(self, device_id: str, pos: int) -> bool:
        dev = self._dev(device_id)
        if not dev or dev["type"] != "shelly_roller":
            return False
        pos = max(0, min(100, pos))
        r = await self._http_get(f"http://{dev['ip']}/roller/0?go=to_pos&roller_pos={pos}")
        logger.info(_prefix(f"{dev['name']} — position {pos}%"))
        return r is not None

    # ------------------------------------------------------------------
    # Convenience: all rollers
    # ------------------------------------------------------------------

    async def open_all_rollers(self) -> bool:
        results = await asyncio.gather(
            self.roller_open("volet_gauche"),
            self.roller_open("volet_milieu"),
        )
        return all(results)

    async def close_all_rollers(self) -> bool:
        results = await asyncio.gather(
            self.roller_close("volet_gauche"),
            self.roller_close("volet_milieu"),
        )
        return all(results)

    # ------------------------------------------------------------------
    # Shelly relay Gen3 — Portail (impulse)
    # ------------------------------------------------------------------

    async def trigger_portail(self) -> bool:
        dev = self.DEVICES["portail"]
        r = await self._http_get(f"http://{dev['ip']}/rpc/Switch.Set?id=0&on=true")
        logger.info(_prefix("Portail — triggered (impulse)"))
        return r is not None

    # ------------------------------------------------------------------
    # Kasa smart plug
    # ------------------------------------------------------------------

    async def plug_on(self, device_id: str = "guinguette") -> bool:
        dev = self._dev(device_id)
        if not dev or dev["type"] != "kasa_plug":
            return False
        try:
            plug = await self._get_kasa()
            if plug:
                await plug.turn_on()
                logger.info(_prefix(f"{dev['name']} — ON"))
                return True
        except Exception as exc:
            logger.warning(_prefix(f"plug_on failed: {exc}"))
        return False

    async def plug_off(self, device_id: str = "guinguette") -> bool:
        dev = self._dev(device_id)
        if not dev or dev["type"] != "kasa_plug":
            return False
        try:
            plug = await self._get_kasa()
            if plug:
                await plug.turn_off()
                logger.info(_prefix(f"{dev['name']} — OFF"))
                return True
        except Exception as exc:
            logger.warning(_prefix(f"plug_off failed: {exc}"))
        return False

    async def plug_toggle(self, device_id: str = "guinguette") -> bool:
        dev = self._dev(device_id)
        if not dev or dev["type"] != "kasa_plug":
            return False
        try:
            plug = await self._get_kasa()
            if plug:
                if plug.is_on:
                    await plug.turn_off()
                    logger.info(_prefix(f"{dev['name']} — toggled OFF"))
                else:
                    await plug.turn_on()
                    logger.info(_prefix(f"{dev['name']} — toggled ON"))
                return True
        except Exception as exc:
            logger.warning(_prefix(f"plug_toggle failed: {exc}"))
        return False
