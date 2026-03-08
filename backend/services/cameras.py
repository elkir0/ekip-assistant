import asyncio
import base64
import logging
import ssl
import time
from typing import Any

import requests

from config import UNIFI_HOST, UNIFI_USER, UNIFI_PASS

logger = logging.getLogger(__name__)

# Disable SSL warnings for self-signed certs
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class CameraService:
    def __init__(self):
        self._session = requests.Session()
        self._session.verify = False
        self._base_url = f"https://{UNIFI_HOST}"
        self._cameras: list[dict] = []
        self._authenticated = False
        self._last_auth = 0

    async def start(self):
        if not UNIFI_USER or not UNIFI_PASS:
            logger.info("[CAMERAS] Pas de credentials UniFi — mode desactive")
            return
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, self._authenticate)
            await loop.run_in_executor(None, self._fetch_cameras)
            logger.info("[CAMERAS] %d cameras detectees", len(self._cameras))
        except Exception as e:
            logger.error("[CAMERAS] Erreur init: %s", e)

    def _authenticate(self):
        try:
            resp = self._session.post(
                f"{self._base_url}/api/auth/login",
                json={"username": UNIFI_USER, "password": UNIFI_PASS},
                timeout=10,
            )
            if resp.status_code == 200:
                self._authenticated = True
                self._last_auth = time.time()
                logger.info("[CAMERAS] Authentification reussie")
            else:
                logger.error("[CAMERAS] Auth echouee: %d", resp.status_code)
                self._authenticated = False
        except Exception as e:
            logger.error("[CAMERAS] Erreur auth: %s", e)
            self._authenticated = False

    def _ensure_auth(self):
        """Re-authenticate if session is older than 1 hour."""
        if not self._authenticated or (time.time() - self._last_auth > 3600):
            self._authenticate()

    def _fetch_cameras(self):
        self._ensure_auth()
        if not self._authenticated:
            return
        try:
            resp = self._session.get(
                f"{self._base_url}/proxy/protect/api/cameras",
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                self._cameras = [
                    {
                        "id": cam["id"],
                        "name": cam.get("name", "Camera"),
                        "type": cam.get("type", ""),
                        "state": cam.get("state", ""),
                        "mac": cam.get("mac", ""),
                    }
                    for cam in data
                    if cam.get("state") == "CONNECTED"
                ]
            else:
                logger.error("[CAMERAS] Erreur liste: %d", resp.status_code)
        except Exception as e:
            logger.error("[CAMERAS] Erreur fetch cameras: %s", e)

    async def get_cameras(self) -> list[dict]:
        if not self._cameras:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._fetch_cameras)
        return self._cameras

    async def get_snapshot(self, camera_id: str) -> str | None:
        """Get a JPEG snapshot as base64 string."""
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(None, self._fetch_snapshot, camera_id)
        except Exception as e:
            logger.error("[CAMERAS] Erreur snapshot %s: %s", camera_id, e)
            return None

    def _fetch_snapshot(self, camera_id: str) -> str | None:
        self._ensure_auth()
        if not self._authenticated:
            return None
        try:
            resp = self._session.get(
                f"{self._base_url}/proxy/protect/api/cameras/{camera_id}/snapshot",
                params={"force": "true", "w": 640, "h": 360},
                timeout=10,
            )
            if resp.status_code == 200 and resp.content:
                return base64.b64encode(resp.content).decode("ascii")
            logger.warning("[CAMERAS] Snapshot %s: status %d", camera_id, resp.status_code)
            return None
        except Exception as e:
            logger.error("[CAMERAS] Erreur snapshot fetch: %s", e)
            return None

    async def get_all_snapshots(self) -> list[dict]:
        """Get snapshots for all cameras in parallel."""
        cameras = await self.get_cameras()
        snapshots = await asyncio.gather(
            *[self.get_snapshot(cam["id"]) for cam in cameras]
        )
        return [{**cam, "snapshot": snap} for cam, snap in zip(cameras, snapshots)]

    def _fetch_snapshot_raw(self, camera_id: str) -> bytes | None:
        """Get raw JPEG bytes (for MJPEG stream)."""
        self._ensure_auth()
        if not self._authenticated:
            return None
        try:
            resp = self._session.get(
                f"{self._base_url}/proxy/protect/api/cameras/{camera_id}/snapshot",
                params={"force": "true", "w": 1280, "h": 720},
                timeout=10,
            )
            if resp.status_code == 200 and resp.content:
                return resp.content
            return None
        except Exception:
            return None

    async def stream_mjpeg(self, camera_id: str):
        """Async generator yielding MJPEG frames."""
        loop = asyncio.get_event_loop()
        while True:
            frame = await loop.run_in_executor(None, self._fetch_snapshot_raw, camera_id)
            if frame:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Content-Length: " + str(len(frame)).encode() + b"\r\n\r\n"
                    + frame + b"\r\n"
                )
            await asyncio.sleep(0.1)  # Small pause between fetches

    @property
    def available(self) -> bool:
        return bool(UNIFI_USER and UNIFI_PASS)
