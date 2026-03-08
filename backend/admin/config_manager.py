"""Runtime config manager — loads/saves backend/admin/config.json."""

import json
import copy
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent / "config.json"

DEFAULT_CONFIG = {
    "audio": {
        "sample_rate": 16000,
        "channels": 1,
        "chunk_size": 1024,
        "error_threshold": 5,
        "pipewire_volume": 32768,
    },
    "wakeword": {
        "model": "hey_jarvis",
        "threshold": 0.2,
        "cooldown_s": 10.0,
    },
    "stt": {
        "language": "fr",
        "duration_s": 8.0,
        "rms_threshold": 500,
        "drain_s": 0.5,
    },
    "tts": {
        "model": "tts-1",
        "voice": "nova",
        "speed": 0.95,
        "duck_volume": 20,
    },
    "llm": {
        "model": "gpt-4o-mini",
        "max_tokens": 200,
        "system_prompt": (
            "Tu es PI-Board, un assistant vocal familial. "
            "Reponds en francais, de maniere concise (2-3 phrases max)."
        ),
    },
    "spotify": {
        "market": "FR",
        "search_limit": 10,
        "queue_display_limit": 10,
        "playlists_limit": 50,
        "device_watch_attempts": 30,
        "device_watch_interval_s": 30,
    },
    "youtube": {
        "format": "bestvideo[height<=480][vcodec^=avc]+bestaudio/best[height<=480]",
        "search_limit": 5,
        "search_timeout_s": 15,
        "vlc_volume": 256,
        "network_cache_ms": 3000,
        "stop_timeout_s": 3,
    },
    "weather": {
        "timezone": "America/Guadeloupe",
        "forecast_days": 4,
        "fetch_timeout_s": 10,
    },
    "cameras": {
        "snapshot_width": 640,
        "snapshot_height": 360,
        "stream_width": 1280,
        "stream_height": 720,
        "stream_refresh_s": 0.1,
        "grid_refresh_ms": 1500,
        "auth_timeout_s": 3600,
    },
    "screen": {
        "sleep_hour_start": 22,
        "sleep_hour_end": 6,
        "quiet_hour_start": 20,
        "quiet_hour_end": 8,
        "night_volume": 30,
        "day_volume": 50,
        "brightness_max": 255,
    },
    "ui": {
        "accent_color": "#6c63ff",
        "bg_color": "#0a0a0f",
        "swipe_threshold_px": 60,
        "page_transition_ms": 400,
        "clock_update_ms": 10000,
    },
    "system": {
        "backend_port": 8000,
        "ws_reconnect_ms": 3000,
    },
}


class ConfigManager:
    """Manages runtime config with disk persistence."""

    def __init__(self):
        self._config: dict = {}
        self._load()

    # --- Public API ---

    def get_all(self) -> dict:
        """Return full config (deep copy)."""
        return copy.deepcopy(self._config)

    def get_section(self, section: str) -> dict:
        """Return one section or empty dict."""
        return copy.deepcopy(self._config.get(section, {}))

    def get(self, section: str, key: str, default=None):
        """Return a single value."""
        return self._config.get(section, {}).get(key, default)

    def set_section(self, section: str, values: dict):
        """Merge values into a section, preserving keys not in `values`."""
        if section not in self._config:
            self._config[section] = {}
        self._config[section].update(values)
        self._save()
        logger.info("[CONFIG] Section '%s' mise a jour: %s", section, list(values.keys()))

    def set(self, section: str, key: str, value):
        """Set a single key and save."""
        if section not in self._config:
            self._config[section] = {}
        self._config[section][key] = value
        self._save()
        logger.info("[CONFIG] %s.%s = %s", section, key, value)

    # --- Internal ---

    def _load(self):
        """Load from disk, fill missing keys from defaults."""
        saved = {}
        if CONFIG_PATH.exists():
            try:
                saved = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("[CONFIG] Erreur lecture %s: %s — utilisation defaults", CONFIG_PATH, e)

        # Deep-merge: defaults + saved (saved wins)
        merged = copy.deepcopy(DEFAULT_CONFIG)
        for section, defaults in DEFAULT_CONFIG.items():
            if section in saved and isinstance(saved[section], dict):
                merged[section].update(saved[section])

        # Keep any extra sections from saved that are not in defaults (e.g. auth)
        for section in saved:
            if section not in merged:
                merged[section] = saved[section]

        self._config = merged
        logger.info("[CONFIG] Charge depuis %s", CONFIG_PATH)

    def _save(self):
        """Persist to disk."""
        try:
            CONFIG_PATH.write_text(
                json.dumps(self._config, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except OSError as e:
            logger.error("[CONFIG] Erreur ecriture %s: %s", CONFIG_PATH, e)


# Singleton
config = ConfigManager()
