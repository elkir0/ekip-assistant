"""Admin API routes — mounted at /admin/api."""

import asyncio
import logging
import shutil
import subprocess
from pathlib import Path

from fastapi import APIRouter, Request, Response, HTTPException, Depends
from fastapi.responses import JSONResponse

from admin.config_manager import config
from admin.auth import (
    verify_login,
    verify_session,
    logout,
    change_password,
    SESSION_COOKIE,
    SESSION_MAX_AGE,
)

logger = logging.getLogger(__name__)

admin_router = APIRouter(prefix="/admin/api", tags=["admin"])

ENV_PATH = Path(__file__).parent.parent.parent / ".env"

# Secrets to mask when reading .env
_SECRET_PATTERNS = {
    "KEY", "SECRET", "PASS", "TOKEN", "PASSWORD",
}


# --- Auth dependency ---

def require_auth(request: Request):
    """Dependency that checks session cookie."""
    token = request.cookies.get(SESSION_COOKIE)
    if not verify_session(token):
        raise HTTPException(status_code=401, detail="Non authentifie")
    return token


# --- Auth endpoints ---

@admin_router.post("/login")
async def login(request: Request):
    body = await request.json()
    username = body.get("username", "")
    password = body.get("password", "")

    token = verify_login(username, password)
    if not token:
        raise HTTPException(status_code=401, detail="Identifiants invalides")

    response = JSONResponse({"ok": True})
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="strict",
        path="/",
    )
    return response


@admin_router.get("/auth-check")
async def auth_check(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    if not verify_session(token):
        raise HTTPException(status_code=401, detail="Non authentifie")
    return {"ok": True}


@admin_router.post("/logout")
async def api_logout(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    logout(token)
    response = JSONResponse({"ok": True})
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


# --- Config endpoints ---

@admin_router.get("/config")
async def get_config(_token: str = Depends(require_auth)):
    """Return all runtime config grouped by section."""
    all_cfg = config.get_all()
    # Don't leak auth section
    all_cfg.pop("auth", None)
    return all_cfg


@admin_router.put("/config/{section}")
async def update_section(section: str, request: Request, _token: str = Depends(require_auth)):
    """Update an entire section."""
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Body must be a JSON object")
    config.set_section(section, body)
    return {"ok": True, "section": section}


@admin_router.put("/config/{section}/{key}")
async def update_key(section: str, key: str, request: Request, _token: str = Depends(require_auth)):
    """Update a single config key."""
    body = await request.json()
    value = body.get("value")
    if value is None:
        raise HTTPException(status_code=400, detail="Missing 'value' in body")
    config.set(section, key, value)
    return {"ok": True, "section": section, "key": key, "value": value}


# --- System endpoints ---

@admin_router.get("/system")
async def system_info(_token: str = Depends(require_auth)):
    """Return system stats (CPU temp, memory, disk, uptime, IP)."""
    info = {}

    # CPU temperature
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            info["cpu_temp"] = round(int(f.read().strip()) / 1000, 1)
    except (FileNotFoundError, ValueError):
        info["cpu_temp"] = None

    # Memory
    try:
        with open("/proc/meminfo") as f:
            meminfo = {}
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    meminfo[parts[0].rstrip(":")] = int(parts[1])
            total = meminfo.get("MemTotal", 0)
            available = meminfo.get("MemAvailable", 0)
            info["memory"] = {
                "total_mb": round(total / 1024),
                "available_mb": round(available / 1024),
                "used_mb": round((total - available) / 1024),
                "percent": round((total - available) / total * 100, 1) if total else 0,
            }
    except (FileNotFoundError, ValueError):
        info["memory"] = None

    # Disk
    try:
        usage = shutil.disk_usage("/")
        info["disk"] = {
            "total_gb": round(usage.total / (1024**3), 1),
            "used_gb": round(usage.used / (1024**3), 1),
            "free_gb": round(usage.free / (1024**3), 1),
            "percent": round(usage.used / usage.total * 100, 1),
        }
    except OSError:
        info["disk"] = None

    # Uptime
    try:
        with open("/proc/uptime") as f:
            uptime_s = float(f.read().split()[0])
            hours = int(uptime_s // 3600)
            minutes = int((uptime_s % 3600) // 60)
            info["uptime"] = {"seconds": int(uptime_s), "display": f"{hours}h {minutes}m"}
    except (FileNotFoundError, ValueError):
        info["uptime"] = None

    # IP address
    try:
        result = subprocess.run(
            ["hostname", "-I"], capture_output=True, text=True, timeout=5
        )
        ips = result.stdout.strip().split()
        info["ip"] = ips[0] if ips else "unknown"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        info["ip"] = "unknown"

    # Hostname
    try:
        result = subprocess.run(
            ["hostname"], capture_output=True, text=True, timeout=5
        )
        info["hostname"] = result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        info["hostname"] = "unknown"

    return info


@admin_router.post("/system/reboot")
async def system_reboot(_token: str = Depends(require_auth)):
    """Reboot the Pi after a 3-second delay."""
    logger.warning("[ADMIN] Reboot demande!")

    async def _reboot():
        await asyncio.sleep(3)
        subprocess.Popen(["sudo", "reboot"])

    asyncio.create_task(_reboot())
    return {"ok": True, "message": "Reboot dans 3 secondes"}


@admin_router.post("/system/restart-backend")
async def restart_backend(_token: str = Depends(require_auth)):
    """Restart the ekip-backend systemd service."""
    logger.warning("[ADMIN] Restart backend demande!")

    async def _restart():
        await asyncio.sleep(1)
        subprocess.Popen(["sudo", "systemctl", "restart", "ekip-backend"])

    asyncio.create_task(_restart())
    return {"ok": True, "message": "Restart backend en cours"}


# --- Logs ---

@admin_router.get("/logs")
async def get_logs(_token: str = Depends(require_auth)):
    """Return last 100 lines of backend logs."""
    try:
        result = subprocess.run(
            ["journalctl", "-u", "ekip-backend", "-n", "100", "--no-pager", "-o", "short"],
            capture_output=True, text=True, timeout=10,
        )
        lines = result.stdout.strip().split("\n") if result.stdout else []
        return {"lines": lines}
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return {"lines": ["Impossible de lire les logs (journalctl non disponible)"]}


# --- Password ---

# --- Hotword training ---

HOTWORD_SAMPLES_DIR = Path(__file__).parent.parent / "audio" / "hotword_samples"
HOTWORD_REFS_DIR = Path(__file__).parent.parent / "audio" / "hotword_refs"


@admin_router.get("/hotword/samples")
async def get_hotword_samples(_token: str = Depends(require_auth)):
    """List recorded hotword samples with their audio levels."""
    wakeword = config.get("wakeword", "name", "terminator")
    samples_dir = HOTWORD_SAMPLES_DIR / wakeword
    ref_file = HOTWORD_REFS_DIR / f"{wakeword}_ref.json"

    samples = []
    if samples_dir.exists():
        import wave
        import numpy as np
        for f in sorted(samples_dir.iterdir()):
            if f.suffix == ".wav":
                try:
                    wf = wave.open(str(f), "rb")
                    data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
                    wf.close()
                    rms = int(np.sqrt(np.mean(data.astype(np.float32) ** 2)))
                    samples.append({
                        "name": f.name,
                        "rms": rms,
                        "max": int(np.max(np.abs(data))),
                        "duration_s": round(len(data) / wf.getframerate(), 1),
                        "good": rms > 500,
                    })
                except Exception:
                    samples.append({"name": f.name, "rms": 0, "max": 0, "duration_s": 0, "good": False})

    return {
        "wakeword": wakeword,
        "samples": samples,
        "has_reference": ref_file.exists(),
        "sample_count": len(samples),
        "good_count": sum(1 for s in samples if s.get("good")),
    }


@admin_router.post("/hotword/record")
async def record_hotword_sample(request: Request, _token: str = Depends(require_auth)):
    """Record a single hotword sample using the backend's audio capture."""
    import wave
    import numpy as np

    body = await request.json()
    duration = body.get("duration_s", 3)
    wakeword = config.get("wakeword", "name", "terminator")
    samples_dir = HOTWORD_SAMPLES_DIR / wakeword
    samples_dir.mkdir(parents=True, exist_ok=True)

    # Find next sample number
    existing = list(samples_dir.glob(f"{wakeword}_*.wav"))
    next_num = len(existing) + 1
    filepath = samples_dir / f"{wakeword}_{next_num}.wav"

    # Subscribe to the running audio capture
    audio_capture = request.app.state.audio_capture
    q = audio_capture.subscribe()

    try:
        all_samples = []
        import time
        start = time.monotonic()

        while (time.monotonic() - start) < duration:
            try:
                chunk = await asyncio.wait_for(q.get(), timeout=0.5)
                all_samples.append(chunk)
            except asyncio.TimeoutError:
                continue

        if not all_samples:
            raise HTTPException(status_code=500, detail="Pas d'audio capture")

        audio = np.concatenate(all_samples)
        rms = int(np.sqrt(np.mean(audio.astype(np.float32) ** 2)))

        # Save as WAV (16kHz mono 16-bit — already resampled by capture)
        with wave.open(str(filepath), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(audio.tobytes())

        return {
            "ok": True,
            "file": filepath.name,
            "rms": rms,
            "max": int(np.max(np.abs(audio))),
            "good": rms > 500,
            "duration_s": round(len(audio) / 16000, 1),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        audio_capture.unsubscribe(q)


@admin_router.delete("/hotword/samples")
async def delete_hotword_samples(_token: str = Depends(require_auth)):
    """Delete all hotword samples."""
    wakeword = config.get("wakeword", "name", "terminator")
    samples_dir = HOTWORD_SAMPLES_DIR / wakeword
    if samples_dir.exists():
        for f in samples_dir.glob("*.wav"):
            f.unlink()
    return {"ok": True}


@admin_router.delete("/hotword/sample/{filename}")
async def delete_hotword_sample(filename: str, _token: str = Depends(require_auth)):
    """Delete a single hotword sample."""
    wakeword = config.get("wakeword", "name", "terminator")
    filepath = HOTWORD_SAMPLES_DIR / wakeword / filename
    if filepath.exists() and filepath.suffix == ".wav":
        filepath.unlink()
        return {"ok": True}
    raise HTTPException(status_code=404, detail="Fichier non trouve")


@admin_router.post("/hotword/generate")
async def generate_hotword_reference(_token: str = Depends(require_auth)):
    """Generate EWN reference file from recorded samples."""
    wakeword = config.get("wakeword", "name", "terminator")
    samples_dir = HOTWORD_SAMPLES_DIR / wakeword
    HOTWORD_REFS_DIR.mkdir(parents=True, exist_ok=True)

    if not samples_dir.exists():
        raise HTTPException(status_code=400, detail="Pas d'echantillons enregistres")

    wav_files = sorted(samples_dir.glob("*.wav"))
    if len(wav_files) < 3:
        raise HTTPException(status_code=400, detail="Minimum 3 echantillons requis")

    try:
        import wave
        import json
        import numpy as np
        from math import gcd
        from scipy.signal import resample_poly
        from eff_word_net.audio_processing import Resnet50_Arc_loss

        model = Resnet50_Arc_loss()
        WINDOW = model.window_frames  # 24000

        embeddings = []
        details = []

        for wav_path in wav_files:
            wf = wave.open(str(wav_path), "rb")
            rate = wf.getframerate()
            data = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
            wf.close()

            # Resample to 16kHz
            if rate != 16000:
                g = gcd(rate, 16000)
                data = resample_poly(data.astype(np.float32), 16000 // g, rate // g)
                data = np.clip(data, -32768, 32767).astype(np.int16)

            rms = int(np.sqrt(np.mean(data.astype(np.float32) ** 2)))

            # Skip too quiet samples
            if rms < 500:
                details.append({"file": wav_path.name, "rms": rms, "status": "skip (trop faible)"})
                continue

            # Find loudest 1.5s window
            if len(data) < WINDOW:
                data = np.pad(data, (0, WINDOW - len(data)))

            best_rms = 0
            best_start = 0
            for start in range(0, len(data) - WINDOW, 800):
                chunk = data[start:start + WINDOW]
                chunk_rms = np.sqrt(np.mean(chunk.astype(np.float32) ** 2))
                if chunk_rms > best_rms:
                    best_rms = chunk_rms
                    best_start = start

            window = data[best_start:best_start + WINDOW]
            vec = model.audioToVector(window)
            embeddings.append(vec.tolist())
            details.append({
                "file": wav_path.name,
                "rms": rms,
                "best_window_rms": int(best_rms),
                "status": "ok",
            })

        if len(embeddings) < 3:
            raise HTTPException(
                status_code=400,
                detail=f"Seulement {len(embeddings)} echantillons valides (min 3). Details: {details}",
            )

        ref_data = {"embeddings": embeddings, "model_type": "resnet_50_arc"}
        ref_path = HOTWORD_REFS_DIR / f"{wakeword}_ref.json"
        with open(ref_path, "w") as f:
            json.dump(ref_data, f)

        return {
            "ok": True,
            "embeddings_count": len(embeddings),
            "details": details,
            "message": "Reference generee. Redemarrez le backend pour appliquer.",
        }

    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"EfficientWord-Net non disponible: {e}")
    except Exception as e:
        logger.error("[ADMIN] Erreur generation reference: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.post("/password")
async def api_change_password(request: Request, _token: str = Depends(require_auth)):
    body = await request.json()
    current = body.get("current", "")
    new_pwd = body.get("new", "")

    if len(new_pwd) < 4:
        raise HTTPException(status_code=400, detail="Mot de passe trop court (min 4)")

    if not change_password(current, new_pwd):
        raise HTTPException(status_code=401, detail="Mot de passe actuel incorrect")

    return {"ok": True}


# --- .env management ---

def _mask_value(key: str, value: str) -> str:
    """Mask secret values, showing only first/last 2 chars."""
    key_upper = key.upper()
    if any(p in key_upper for p in _SECRET_PATTERNS):
        if len(value) > 8:
            return value[:2] + "*" * (len(value) - 4) + value[-2:]
        elif len(value) > 2:
            return value[0] + "*" * (len(value) - 1)
        else:
            return "***"
    return value


@admin_router.get("/env")
async def get_env(_token: str = Depends(require_auth)):
    """Read .env and return key-value pairs with masked secrets."""
    if not ENV_PATH.exists():
        return {"entries": [], "raw": ""}

    raw = ENV_PATH.read_text(encoding="utf-8")
    entries = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            entries.append({"type": "comment", "line": line})
            continue
        if "=" in stripped:
            key, _, value = stripped.partition("=")
            key = key.strip()
            value = value.strip().strip("\"'")
            entries.append({
                "type": "var",
                "key": key,
                "value": value,
                "masked": _mask_value(key, value),
            })
        else:
            entries.append({"type": "comment", "line": line})

    return {"entries": entries}


@admin_router.put("/env")
async def update_env(request: Request, _token: str = Depends(require_auth)):
    """Update .env file. Body: {"entries": [{"key": "X", "value": "Y"}, ...]}"""
    body = await request.json()
    entries = body.get("entries", [])

    if not entries:
        raise HTTPException(status_code=400, detail="No entries provided")

    # Read current .env
    current_lines = []
    if ENV_PATH.exists():
        current_lines = ENV_PATH.read_text(encoding="utf-8").splitlines()

    # Build a map of existing keys -> line index
    key_map: dict[str, int] = {}
    for i, line in enumerate(current_lines):
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k = stripped.split("=", 1)[0].strip()
            key_map[k] = i

    # Apply updates
    for entry in entries:
        key = entry.get("key", "").strip()
        value = entry.get("value", "")
        if not key:
            continue

        new_line = f"{key}={value}"
        if key in key_map:
            current_lines[key_map[key]] = new_line
        else:
            current_lines.append(new_line)
            key_map[key] = len(current_lines) - 1

    ENV_PATH.write_text("\n".join(current_lines) + "\n", encoding="utf-8")
    logger.info("[ADMIN] .env mis a jour (%d entrees)", len(entries))
    return {"ok": True}
