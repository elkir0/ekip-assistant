import asyncio
import logging
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse, RedirectResponse
from pathlib import Path

from config import BACKEND_PORT, FRONTEND_BUILD_DIR
from admin.routes import admin_router
from audio.capture import AudioCapture
from audio.wakeword import WakeWordDetector
from services.stt import STTEngine
from services.spotify import MusicController
from services.weather import WeatherService
from services.youtube import YouTubeController
from services.cameras import CameraService
from services.llm import LLMHandler
from services.tts import TTSEngine
from intent.router import route

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

# --- Shared state ---
connected_clients: list[WebSocket] = []
assistant_state = "IDLE"

# --- Core components ---
audio_capture = AudioCapture(device_name="AI-Voice")
music = MusicController()
weather = WeatherService()
youtube = YouTubeController()
cameras = CameraService()
llm = LLMHandler()
tts = TTSEngine()


async def broadcast(message: dict):
    for client in list(connected_clients):
        try:
            await client.send_json(message)
        except Exception:
            pass


async def set_state(new_state: str):
    global assistant_state
    assistant_state = new_state
    logger.info("[STATE] %s", new_state)
    await broadcast({"type": "state", "data": new_state})


# --- Intent handlers ---

async def handle_music_play(query: str):
    # Use LLM to normalize artist/track names from STT transcription
    cleaned = await llm.normalize_music_query(query)
    if cleaned and cleaned != query:
        logger.info("[PIPELINE] Query normalisee: '%s' -> '%s'", query, cleaned)
        query = cleaned
    result = await music.search_and_play(query)
    await broadcast({"type": "music", "data": result})
    if result.get("playing"):
        await asyncio.sleep(1)
        queue = await music.get_queue()
        await broadcast({"type": "music_queue", "data": queue})
        await speak(f"Je lance {result['title']} de {result['artist']}")
    else:
        await speak(f"Je n'ai pas trouve de musique pour {query}")


async def handle_music_pause(_query: str):
    await music.pause()
    await broadcast({"type": "music", "data": {"playing": False}})


async def handle_music_next(_query: str):
    result = await music.next_track()
    await broadcast({"type": "music", "data": result})
    if result.get("title"):
        await speak(f"Morceau suivant: {result['title']}")


async def handle_music_volume(direction: str, _query: str):
    current = await music.get_current()
    delta = 20 if direction == "up" else -20
    new_vol = max(0, min(100, 50 + delta))  # simplified
    await music.set_volume(new_vol)


async def handle_weather(_query: str):
    await broadcast({"type": "page", "data": 1})
    data = await weather.get_current()
    await broadcast({"type": "weather", "data": data})
    spoken = weather.format_spoken(data)
    await speak(spoken)


async def handle_youtube_play(query: str):
    await broadcast({"type": "page", "data": 2})
    results = await youtube.search(query, limit=5)
    await broadcast({"type": "youtube_results", "data": results})
    if results:
        async def on_finish():
            await broadcast({"type": "youtube_stopped", "data": {}})
            await asyncio.sleep(1)
            current = await music.get_current()
            if current.get("playing"):
                await broadcast({"type": "music", "data": current})

        async def on_next(video):
            await broadcast({"type": "youtube_playing", "data": {
                "title": video.get("title", ""),
                "channel": video.get("channel", ""),
                "thumbnail": video.get("thumbnail", ""),
                "url": video.get("url", ""),
            }})

        # Set queue with all results, auto-play next on finish
        youtube.set_queue(results, on_next=on_next)
        play_result = await youtube.play(results[0]["url"], on_finish=on_finish)
        if play_result.get("playing"):
            await broadcast({"type": "youtube_playing", "data": {**results[0], **play_result}})
            remaining = len(results) - 1
            title = results[0]['title']
            if remaining > 0:
                await speak(f"Je lance {title}, plus {remaining} videos a suivre")
            else:
                await speak(f"Je lance {title}")
        else:
            error_msg = play_result.get("error", "Erreur inconnue")
            logger.warning("[PIPELINE] YouTube play echoue: %s", error_msg)
            await broadcast({"type": "youtube_stopped", "data": {"error": error_msg}})
            await speak("Desole, je n'ai pas pu lancer la video")
    else:
        await speak(f"Je n'ai rien trouve pour {query} sur YouTube")


async def handle_youtube_stop(_query: str):
    await youtube.stop()
    await broadcast({"type": "youtube_stopped", "data": {}})
    await asyncio.sleep(1)
    current = await music.get_current()
    if current.get("playing"):
        await broadcast({"type": "music", "data": current})


async def handle_sleep(_query: str):
    global screen_sleeping
    await speak("Bonne nuit")
    await screen_off()
    screen_sleeping = True


async def handle_wake(_query: str):
    global screen_sleeping
    await screen_on()
    screen_sleeping = False
    await speak("Bonjour!")


BACKLIGHT = "/sys/class/backlight/10-0045/brightness"


async def screen_off():
    proc = await asyncio.create_subprocess_shell(
        f"echo 0 | sudo tee {BACKLIGHT}"
    )
    await proc.wait()
    logger.info("[SCREEN] Ecran eteint")
    await broadcast({"type": "screen", "data": "off"})


async def screen_on():
    proc = await asyncio.create_subprocess_shell(
        f"echo 255 | sudo tee {BACKLIGHT}"
    )
    await proc.wait()
    logger.info("[SCREEN] Ecran allume")
    await broadcast({"type": "screen", "data": "on"})


async def handle_general(text: str):
    response = await llm.ask(text)
    await broadcast({"type": "llm_response", "data": response})
    await speak(response)


async def speak(text: str):
    await set_state("SPEAKING")
    await broadcast({"type": "speaking", "data": text})

    # Duck Spotify volume via API (not PipeWire — TTS uses PipeWire)
    # Save current volume to restore after TTS (timeout to avoid rate limit block)
    saved_spotify_vol = None
    try:
        current = await asyncio.wait_for(music.get_current(), timeout=2)
        if current.get("playing"):
            saved_spotify_vol = await asyncio.wait_for(music.get_spotify_volume(), timeout=2)
    except (asyncio.TimeoutError, Exception):
        pass

    async def duck(vol):
        nonlocal saved_spotify_vol
        try:
            if vol == 100:
                restore_vol = saved_spotify_vol if saved_spotify_vol is not None else 70
                await asyncio.wait_for(music.spotify_volume(restore_vol), timeout=2)
            else:
                await asyncio.wait_for(music.spotify_volume(vol), timeout=2)
        except (asyncio.TimeoutError, Exception):
            pass

    await tts.speak(text, duck_callback=duck)
    await set_state("IDLE")


INTENT_HANDLERS = {
    "MUSIC_PLAY": handle_music_play,
    "MUSIC_PAUSE": handle_music_pause,
    "MUSIC_NEXT": handle_music_next,
    "MUSIC_VOLUME_UP": lambda q: handle_music_volume("up", q),
    "MUSIC_VOLUME_DOWN": lambda q: handle_music_volume("down", q),
    "YOUTUBE_PLAY": handle_youtube_play,
    "YOUTUBE_STOP": handle_youtube_stop,
    "WEATHER": handle_weather,
    "SLEEP": handle_sleep,
    "WAKE": handle_wake,
    "GENERAL": handle_general,
}


# --- Voice pipeline ---

_pending_handler = None

async def on_transcript(text: str, is_final: bool):
    global _pending_handler
    await broadcast({"type": "transcript", "data": {"text": text, "final": is_final}})

    if is_final and text.strip():
        logger.info("[PIPELINE] Transcription: %s", text)
        # Don't run handler here (recv_loop gets cancelled by send_audio)
        # Instead, store it and run after send_audio completes
        intent, query = route(text)
        await broadcast({"type": "intent", "data": {"intent": intent, "query": query}})
        _pending_handler = (intent, query)


async def on_wake():
    global assistant_state
    # Don't trigger if already busy
    if assistant_state != "IDLE":
        return

    logger.info("[PIPELINE] Wake word detecte!")
    # Pause wake word detection during interaction
    if wake_detector:
        wake_detector.paused = True

    # Duck music immediately so the mic hears the user clearly (timeout to avoid rate limit block)
    _wake_saved_vol = None
    try:
        current = await asyncio.wait_for(music.get_current(), timeout=2)
        if current.get("playing"):
            _wake_saved_vol = await asyncio.wait_for(music.get_spotify_volume(), timeout=2)
            duck_vol = max(10, (_wake_saved_vol or 50) // 2)
            await asyncio.wait_for(music.spotify_volume(duck_vol), timeout=2)
            logger.info("[PIPELINE] Musique duckee %d%% -> %d%%", _wake_saved_vol or 50, duck_vol)
    except (asyncio.TimeoutError, Exception):
        pass

    await set_state("LISTENING")

    audio_queue = audio_capture.subscribe()

    # Drain ~0.5s of audio to skip the tail end of the wake word
    drain_end = asyncio.get_event_loop().time() + 0.5
    while asyncio.get_event_loop().time() < drain_end:
        try:
            audio_queue.get_nowait()
        except asyncio.QueueEmpty:
            await asyncio.sleep(0.05)

    try:
        global _pending_handler
        _pending_handler = None

        stt = STTEngine(on_transcript=on_transcript)
        await stt.start()
        await stt.send_audio(audio_queue, duration_s=8.0)
    except Exception as e:
        logger.error("[PIPELINE] Erreur STT: %s", e)
    finally:
        audio_capture.unsubscribe(audio_queue)

    # Run the handler AFTER send_audio (not inside recv_loop)
    if _pending_handler:
        intent, query = _pending_handler
        _pending_handler = None
        await set_state("PROCESSING")
        handler = INTENT_HANDLERS.get(intent, handle_general)
        try:
            await handler(query)
        except Exception as e:
            logger.error("[PIPELINE] Erreur handler %s: %s", intent, e)

    # Restore music volume if we ducked it at wake
    if _wake_saved_vol is not None:
        try:
            await asyncio.wait_for(music.spotify_volume(_wake_saved_vol), timeout=2)
            logger.info("[PIPELINE] Volume restaure %d%%", _wake_saved_vol)
        except (asyncio.TimeoutError, Exception):
            pass

    # Return to IDLE
    await set_state("IDLE")

    # Re-enable wake word after a delay (avoid self-trigger from TTS)
    await asyncio.sleep(6.0)
    if wake_detector:
        wake_detector.reset_cooldown()  # Reset cooldown so music doesn't re-trigger immediately
        wake_detector.paused = False
        logger.info("[PIPELINE] Wake word reactif")


async def voice_pipeline():
    global wake_detector
    wake_detector = WakeWordDetector(on_wake=on_wake)
    await wake_detector.start()
    audio_queue = audio_capture.subscribe()
    asyncio.create_task(audio_capture.start())
    await wake_detector.process(audio_queue)

wake_detector = None

screen_sleeping = False
volume_manual_override = False  # True when user changes volume manually

async def screen_scheduler():
    """Auto sleep 22h-6h, night volume 30% 20h-8h. Each action fires once per transition."""
    from datetime import datetime
    global screen_sleeping, volume_manual_override

    # Initialize state based on current time (avoid re-triggering on restart)
    hour = datetime.now().hour
    was_sleep = hour >= 22 or hour < 6
    was_quiet = hour >= 20 or hour < 8

    # Apply initial state (only volume hint, don't force — user may have set it)
    if was_sleep:
        await screen_off()
        screen_sleeping = True
        logger.info("[SCREEN] Demarrage en mode dodo")

    while True:
        await asyncio.sleep(60)
        hour = datetime.now().hour
        in_sleep = hour >= 22 or hour < 6
        in_quiet = hour >= 20 or hour < 8

        # Volume transitions (skip if user overrode manually)
        if not volume_manual_override:
            if in_quiet and not was_quiet:
                await music.set_volume(30)
                await broadcast({"type": "volume", "data": 30})
                logger.info("[VOLUME] Mode nuit 30%%")
            elif not in_quiet and was_quiet:
                await music.set_volume(50)
                await broadcast({"type": "volume", "data": 50})
                logger.info("[VOLUME] Mode jour 50%%")
        # Reset override on period transition so next auto-change works
        if in_quiet != was_quiet:
            volume_manual_override = False
        was_quiet = in_quiet

        # Screen transitions
        if in_sleep and not was_sleep:
            await screen_off()
            screen_sleeping = True
            logger.info("[SCREEN] Auto dodo (22h)")
        elif not in_sleep and was_sleep:
            await screen_on()
            screen_sleeping = False
            logger.info("[SCREEN] Auto reveil (6h)")
        was_sleep = in_sleep


# --- App lifecycle ---

async def _start_spotify():
    """Start Spotify in background so rate limits don't block server startup."""
    try:
        await music.start()
    except Exception as e:
        logger.error("[SPOTIFY] Erreur au demarrage: %s", e)


async def _start_oauth_proxy():
    """Tiny HTTP server on port 8888 that redirects to port 8000.

    Spotify OAuth redirect URI is http://127.0.0.1:8888/callback but
    FastAPI runs on port 8000. This proxy catches the callback and redirects.
    """
    async def handle_client(reader, writer):
        try:
            request_line = await asyncio.wait_for(reader.readline(), timeout=5)
            # Read remaining headers (discard)
            while True:
                line = await asyncio.wait_for(reader.readline(), timeout=2)
                if line == b'\r\n' or not line:
                    break
            # Extract path from "GET /callback?code=xxx HTTP/1.1"
            parts = request_line.decode().split()
            path = parts[1] if len(parts) >= 2 else "/"
            redirect_url = f"http://127.0.0.1:8000{path}"
            response = (
                f"HTTP/1.1 302 Found\r\n"
                f"Location: {redirect_url}\r\n"
                f"Connection: close\r\n\r\n"
            )
            writer.write(response.encode())
            await writer.drain()
        except Exception:
            pass
        finally:
            writer.close()

    try:
        server = await asyncio.start_server(handle_client, "127.0.0.1", 8888)
        logger.info("[OAUTH] Proxy port 8888 -> 8000 actif")
        return server
    except OSError as e:
        logger.warning("[OAUTH] Port 8888 indisponible: %s", e)
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[PI-BOARD] Demarrage des services...")
    # Wire broadcast so Spotify can push status changes to frontend
    music.set_broadcast(broadcast)
    # Start Spotify in background — don't block server startup on rate limits
    asyncio.create_task(_start_spotify())
    await cameras.start()
    await llm.start()
    await tts.start()
    # Connect YouTube ↔ Spotify: pause music when video plays, resume when stops
    youtube.set_music_callbacks(
        pause_fn=music.pause,
        resume_fn=music.resume,
    )
    pipeline_task = asyncio.create_task(voice_pipeline())
    scheduler_task = asyncio.create_task(screen_scheduler())
    # Port 8888 redirect for Spotify OAuth callback (registered as http://127.0.0.1:8888/callback)
    proxy_server = await _start_oauth_proxy()
    logger.info("[PI-BOARD] Tous les services demarres")
    yield
    logger.info("[PI-BOARD] Arret...")
    await audio_capture.stop()
    pipeline_task.cancel()
    scheduler_task.cancel()
    if proxy_server:
        proxy_server.close()
        await proxy_server.wait_closed()


app = FastAPI(title="PI-Board", lifespan=lifespan)

# Expose audio_capture for admin routes (hotword recording)
app.state.audio_capture = audio_capture

# --- Admin panel ---
app.include_router(admin_router)


# --- WebSocket ---

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connected_clients.append(ws)
    logger.info("[WS] Client connecte (%d total)", len(connected_clients))
    await ws.send_json({"type": "state", "data": assistant_state})
    # Send Spotify status on connect (with timeout — don't block WS on rate limits)
    try:
        spotify_status = music.status
        await ws.send_json({"type": "spotify_status", "data": spotify_status})
        vol = await asyncio.wait_for(music.get_volume(), timeout=3)
        await ws.send_json({"type": "volume", "data": vol})
        current = await asyncio.wait_for(music.get_current(), timeout=3)
        if current.get("playing"):
            await ws.send_json({"type": "music", "data": current})
            queue = await asyncio.wait_for(music.get_queue(), timeout=3)
            await ws.send_json({"type": "music_queue", "data": queue})
    except (asyncio.TimeoutError, Exception) as e:
        logger.warning("[WS] Spotify status indisponible: %s", e)

    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            logger.info("[WS] Recu: %s", msg)

            if msg.get("type") == "navigate":
                page = int(msg.get("data", 0))
                await broadcast({"type": "page", "data": page})
            elif msg.get("type") == "simulate_wake":
                asyncio.create_task(on_wake())
            elif msg.get("type") == "simulate_command":
                text = msg.get("data", "")
                asyncio.create_task(on_transcript(text, True))
            elif msg.get("type") == "music_play_pause":
                if (await music.get_current()).get("playing"):
                    await music.pause()
                    await broadcast({"type": "music", "data": {"playing": False}})
                else:
                    await music.resume()
                    current = await music.get_current()
                    await broadcast({"type": "music", "data": current})
            elif msg.get("type") == "music_next":
                result = await music.next_track()
                await broadcast({"type": "music", "data": result})
            elif msg.get("type") == "music_prev":
                await music.previous_track()
                current = await music.get_current()
                await broadcast({"type": "music", "data": current})
            elif msg.get("type") == "music_volume":
                global volume_manual_override
                vol = int(msg.get("data", 50))
                await music.set_volume(vol)
                await broadcast({"type": "volume", "data": vol})
                volume_manual_override = True
            elif msg.get("type") == "music_search":
                query = msg.get("data", "")
                results = await music.search_tracks(query)
                await ws.send_json({"type": "music_search_results", "data": results})
            elif msg.get("type") == "music_play_uri":
                uri = msg.get("data", "")
                result = await music.play_uri(uri)
                await broadcast({"type": "music", "data": result})
                await asyncio.sleep(1)
                queue = await music.get_queue()
                await broadcast({"type": "music_queue", "data": queue})
            elif msg.get("type") == "music_queue":
                queue = await music.get_queue()
                await ws.send_json({"type": "music_queue", "data": queue})
            elif msg.get("type") == "music_progress":
                current = await music.get_current()
                await ws.send_json({"type": "music", "data": current})
            elif msg.get("type") == "music_playlists":
                playlists = await music.get_playlists()
                await ws.send_json({"type": "music_playlists", "data": playlists})
            elif msg.get("type") == "music_play_playlist":
                uri = msg.get("data", "")
                result = await music.play_playlist(uri)
                await broadcast({"type": "music", "data": result})
                await asyncio.sleep(1)
                queue = await music.get_queue()
                await broadcast({"type": "music_queue", "data": queue})
            elif msg.get("type") == "spotify_reauth":
                url = music.get_auth_url()
                if url:
                    await ws.send_json({"type": "spotify_reauth_url", "data": url})
            elif msg.get("type") == "spotify_retry":
                # Retry Spotify connection (e.g. after network issue, no full re-auth)
                await music.start()
                status = music.status
                await broadcast({"type": "spotify_status", "data": status})
                if status == "ok":
                    vol = await music.get_volume()
                    await broadcast({"type": "volume", "data": vol})
            elif msg.get("type") == "youtube_search":
                query = msg.get("data", "")
                if query and len(query) >= 2:
                    results = await youtube.search(query, limit=5)
                    await ws.send_json({"type": "youtube_results", "data": results})
            elif msg.get("type") == "youtube_select":
                video = msg.get("data", {})
                url = video.get("url", "")
                if url:
                    async def _play_and_notify(v, u):
                        async def on_finish():
                            await broadcast({"type": "youtube_stopped", "data": {}})
                            await asyncio.sleep(1)
                            current = await music.get_current()
                            if current.get("playing"):
                                await broadcast({"type": "music", "data": current})
                        result = await youtube.play(u, on_finish=on_finish)
                        if result.get("playing"):
                            await broadcast({"type": "youtube_playing", "data": {
                                "title": v.get("title", ""),
                                "channel": v.get("channel", ""),
                                "thumbnail": v.get("thumbnail", ""),
                                "url": u,
                            }})
                        else:
                            await broadcast({"type": "youtube_stopped", "data": {"error": result.get("error", "")}})
                    asyncio.create_task(_play_and_notify(video, url))
            elif msg.get("type") == "youtube_stop":
                await youtube.stop()
                await broadcast({"type": "youtube_stopped", "data": {}})
                # Refresh music state after Spotify resumes
                await asyncio.sleep(1)
                current = await music.get_current()
                if current.get("playing"):
                    await broadcast({"type": "music", "data": current})
            elif msg.get("type") == "weather_refresh":
                data = await weather.get_current()
                await ws.send_json({"type": "weather", "data": data})
            elif msg.get("type") == "cameras_list":
                cams = await cameras.get_cameras()
                await ws.send_json({"type": "cameras_list", "data": cams})
            elif msg.get("type") == "cameras_snapshots":
                snaps = await cameras.get_all_snapshots()
                await ws.send_json({"type": "cameras_snapshots", "data": snaps})
            elif msg.get("type") == "camera_snapshot":
                cam_id = msg.get("data", "")
                snap = await cameras.get_snapshot(cam_id)
                await ws.send_json({"type": "camera_snapshot", "data": {"id": cam_id, "snapshot": snap}})

    except WebSocketDisconnect:
        connected_clients.remove(ws)
        logger.info("[WS] Client deconnecte (%d restants)", len(connected_clients))


# --- REST endpoints ---

@app.get("/api/weather")
async def api_weather():
    return await weather.get_current()


@app.get("/api/spotify/current")
async def api_spotify_current():
    return await music.get_current()


@app.get("/api/spotify/reauth")
async def api_spotify_reauth():
    """Generate Spotify OAuth URL and redirect the browser to it."""
    url = music.get_auth_url()
    if not url:
        return JSONResponse({"error": "Spotify non configure"}, status_code=400)
    return RedirectResponse(url)


@app.get("/api/spotify/callback")
async def api_spotify_callback(code: str = ""):
    """Handle Spotify OAuth callback, then redirect back to the app."""
    if not code:
        return JSONResponse({"error": "Code manquant"}, status_code=400)
    success = await music.handle_callback(code)
    if success:
        return RedirectResponse("/")
    return JSONResponse({"error": "Echec authentification Spotify"}, status_code=500)


@app.get("/callback")
async def legacy_spotify_callback(code: str = ""):
    """Legacy redirect URI (http://127.0.0.1:8888/callback) — forward to real handler."""
    return await api_spotify_callback(code)


@app.get("/api/youtube/login")
async def api_youtube_login():
    """Redirect kiosk to YouTube for login, auto-return after 90s."""
    async def _auto_return():
        await asyncio.sleep(90)
        logger.info("[YOUTUBE] Auto-retour kiosk apres login")
        proc = await asyncio.create_subprocess_exec(
            "sudo", "systemctl", "restart", "piboard-kiosk",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()

    asyncio.create_task(_auto_return())
    return RedirectResponse("https://www.youtube.com")


@app.get("/api/cameras/{camera_id}/stream")
async def api_camera_stream(camera_id: str):
    return StreamingResponse(
        cameras.stream_mjpeg(camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


# --- Serve admin frontend ---

admin_static = Path(__file__).parent / "admin" / "static"
if admin_static.exists() and (admin_static / "assets").exists():
    app.mount("/admin/assets", StaticFiles(directory=admin_static / "assets"), name="admin-assets")


@app.get("/admin/{full_path:path}")
async def serve_admin(full_path: str):
    # Don't intercept API or asset routes
    if full_path.startswith("api/") or full_path.startswith("assets/"):
        raise HTTPException(status_code=404, detail="Not found")
    if admin_static.exists():
        file = admin_static / full_path
        if file.exists() and file.is_file():
            return FileResponse(file)
        index = admin_static / "index.html"
        if index.exists():
            return FileResponse(index)
    return JSONResponse({"error": "Admin UI not built"}, status_code=404)


# --- Serve main frontend (MUST be last — catch-all route) ---

frontend_path = Path(FRONTEND_BUILD_DIR)
if frontend_path.exists():
    if (frontend_path / "assets").exists():
        app.mount("/assets", StaticFiles(directory=frontend_path / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        file = frontend_path / full_path
        if file.exists() and file.is_file():
            return FileResponse(file)
        return FileResponse(frontend_path / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=BACKEND_PORT, reload=True)
