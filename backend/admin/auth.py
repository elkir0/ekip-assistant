"""Simple session-based auth for the admin panel."""

import hashlib
import secrets
import logging
from datetime import datetime, timedelta

from admin.config_manager import config

logger = logging.getLogger(__name__)

SESSION_COOKIE = "piboard_session"
SESSION_MAX_AGE = 86400  # 24h


def _hash(password: str) -> str:
    """SHA-256 hash a password."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


# Default credentials — stored hashed in config.json under "auth" section
_DEFAULT_HASH = _hash("piboard")

# Active sessions: token -> expiry
_sessions: dict[str, datetime] = {}


def _ensure_auth_config():
    """Make sure config has auth section with hashed password."""
    stored = config.get("auth", "password_hash")
    if not stored:
        config.set("auth", "password_hash", _DEFAULT_HASH)
        config.set("auth", "username", "admin")


def verify_login(username: str, password: str) -> str | None:
    """Check credentials, return session token or None."""
    _ensure_auth_config()
    stored_user = config.get("auth", "username", "admin")
    stored_hash = config.get("auth", "password_hash", _DEFAULT_HASH)

    if username == stored_user and _hash(password) == stored_hash:
        token = secrets.token_hex(32)
        _sessions[token] = datetime.now() + timedelta(seconds=SESSION_MAX_AGE)
        logger.info("[AUTH] Login reussi pour %s", username)
        return token

    logger.warning("[AUTH] Login echoue pour %s", username)
    return None


def verify_session(token: str | None) -> bool:
    """Check if a session token is valid."""
    if not token:
        return False
    expiry = _sessions.get(token)
    if not expiry:
        return False
    if datetime.now() > expiry:
        _sessions.pop(token, None)
        return False
    return True


def logout(token: str | None):
    """Invalidate a session."""
    if token:
        _sessions.pop(token, None)


def change_password(current: str, new_password: str) -> bool:
    """Change the admin password. Returns True on success."""
    _ensure_auth_config()
    stored_hash = config.get("auth", "password_hash", _DEFAULT_HASH)

    if _hash(current) != stored_hash:
        return False

    config.set("auth", "password_hash", _hash(new_password))
    logger.info("[AUTH] Mot de passe modifie")
    return True
