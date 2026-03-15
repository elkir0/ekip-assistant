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
from services.devialet import DevialetService
from services.domotique import DomotiqueService
from services.llm import LLMHandler
from services.tts import TTSEngine
from intent.router import route, extract_volume_value, extract_timer_minutes
from memory.context import memory

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
devialet = DevialetService()
domotique = DomotiqueService()
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
    memory.add("MUSIC_PLAY", query, result)
    if result.get("playing"):
        await asyncio.sleep(1)
        await devialet.ensure_volume()  # Prevent AirPlay volume reset
        queue = await music.get_queue()
        await broadcast({"type": "music_queue", "data": queue})
        await speak(f"Je lance {result['title']} de {result['artist']}")
    else:
        await speak(f"Je n'ai pas trouve de musique pour {query}")


async def handle_music_pause(_query: str):
    await music.pause()
    await broadcast({"type": "music", "data": {"playing": False}})
    memory.add("MUSIC_PAUSE", "")


async def handle_music_resume(_query: str):
    await music.resume()
    current = await music.get_current()
    await broadcast({"type": "music", "data": current})
    memory.add("MUSIC_RESUME", "")
    if current.get("title"):
        await speak(f"Je reprends {current['title']}")


async def handle_music_next(_query: str):
    result = await music.next_track()
    await broadcast({"type": "music", "data": result})
    await devialet.ensure_volume()  # Prevent AirPlay volume reset
    memory.add("MUSIC_NEXT", "", result)
    if result.get("title"):
        await speak(f"Morceau suivant: {result['title']}")


async def handle_music_prev(_query: str):
    result = await music.previous_track()
    current = await music.get_current()
    await broadcast({"type": "music", "data": current})
    memory.add("MUSIC_PREV", "")


async def handle_music_volume_up(_query: str):
    ok = await devialet.volume_up()
    if ok:
        status = await devialet.get_status()
        vol = status.get("volume")
        await broadcast({"type": "volume", "data": vol})
        memory.add("MUSIC_VOLUME_UP", str(vol))


async def handle_music_volume_down(_query: str):
    ok = await devialet.volume_down()
    if ok:
        status = await devialet.get_status()
        vol = status.get("volume")
        await broadcast({"type": "volume", "data": vol})
        memory.add("MUSIC_VOLUME_DOWN", str(vol))


async def handle_music_volume_set(query: str):
    val = extract_volume_value(query)
    if val is not None:
        await devialet.set_volume(val)
        await broadcast({"type": "volume", "data": val})
        memory.add("MUSIC_VOLUME_SET", str(val))
        await speak(f"Volume a {val} pourcent")
    else:
        await speak("Je n'ai pas compris le volume souhaite")


async def handle_music_what(_query: str):
    current = await music.get_current()
    if current.get("title"):
        artist = current.get("artist", "")
        title = current.get("title", "")
        album = current.get("album", "")
        response = f"C'est {title} de {artist}"
        if album:
            response += f", album {album}"
        await speak(response)
    else:
        await speak("Il n'y a pas de musique en cours")


async def handle_music_playlist(query: str):
    if query:
        # Search for a specific playlist
        playlists = await music.get_playlists()
        for pl in playlists:
            if query.lower() in pl["name"].lower():
                result = await music.play_playlist(pl["uri"])
                await broadcast({"type": "music", "data": result})
                memory.add("MUSIC_PLAYLIST", pl["name"], result)
                await speak(f"Je lance la playlist {pl['name']}")
                return
        await speak(f"Je n'ai pas trouve de playlist {query}")
    else:
        await speak("Dis-moi quelle playlist tu veux")


async def handle_music_find(query: str):
    """Find a song by lyrics or description using LLM, then play it."""
    await speak("Je cherche cette chanson...")
    identified = await llm.identify_song(query)
    if identified:
        logger.info("[PIPELINE] Chanson identifiee: %s", identified)
        result = await music.search_and_play(identified)
        await broadcast({"type": "music", "data": result})
        memory.add("MUSIC_FIND", query, result)
        if result.get("playing"):
            await speak(f"C'est {result['title']} de {result['artist']}")
        else:
            await speak(f"J'ai identifie {identified} mais je ne la trouve pas sur Spotify")
    else:
        await speak("Desole, je n'ai pas reussi a identifier cette chanson")


async def handle_ai_mix(query: str):
    """Generate a playlist with AI and play it on Spotify."""
    await speak(f"Je prepare une selection pour toi...")
    songs = await llm.generate_playlist(query)
    if not songs:
        await speak("Desole, je n'ai pas reussi a creer la playlist")
        return

    # Search each song on Spotify and collect URIs
    uris = []
    first_info = None
    loop = asyncio.get_event_loop()
    for song in songs:
        try:
            results = await loop.run_in_executor(
                None, lambda s=song: music._sp.search(q=s, type="track", limit=1, market="FR")
            )
            tracks = results.get("tracks", {}).get("items", [])
            if tracks:
                uris.append(tracks[0]["uri"])
                if not first_info:
                    first_info = {
                        "title": tracks[0]["name"],
                        "artist": ", ".join(a["name"] for a in tracks[0]["artists"]),
                    }
        except Exception:
            pass

    if not uris:
        await speak("Je n'ai trouve aucun morceau sur Spotify")
        return

    # Play all at once
    try:
        await music._find_device()
        await loop.run_in_executor(
            None, lambda: music._sp.start_playback(device_id=music._device_id, uris=uris)
        )
        current = await music.get_current()
        await broadcast({"type": "music", "data": current})
        await asyncio.sleep(1)
        queue = await music.get_queue()
        await broadcast({"type": "music_queue", "data": queue})
        memory.add("MUSIC_AI_MIX", query, current)
        await speak(f"C'est parti! {len(uris)} morceaux, en commencant par {first_info['title']} de {first_info['artist']}")
    except Exception as e:
        logger.error("[PIPELINE] AI mix play error: %s", e)
        await speak("Erreur lors du lancement de la playlist")


async def handle_time(_query: str):
    from datetime import datetime
    now = datetime.now()
    h, m = now.hour, now.minute
    if m == 0:
        await speak(f"Il est {h} heures pile")
    else:
        await speak(f"Il est {h} heures {m}")


async def handle_repeat(_query: str):
    last = memory.last_tts
    if last:
        await speak(last)
    else:
        await speak("Je n'ai rien a repeter")


async def handle_cancel(_query: str):
    await speak("D'accord, j'annule")


async def handle_volets_open(_query: str):
    await domotique.open_all_rollers()
    await speak("J'ouvre les volets")


async def handle_volets_close(_query: str):
    await domotique.close_all_rollers()
    await speak("Je ferme les volets")


async def handle_portail(_query: str):
    await domotique.trigger_portail()
    await speak("Portail actionne")


async def handle_guinguette_on(_query: str):
    await domotique.plug_on("guinguette")
    await speak("Guinguette allumee")


async def handle_guinguette_off(_query: str):
    await domotique.plug_off("guinguette")
    await speak("Guinguette eteinte")


async def handle_greeting(_query: str):
    from datetime import datetime
    h = datetime.now().hour
    if h < 12:
        await speak("Bonjour! Comment je peux t'aider?")
    elif h < 18:
        await speak("Salut! Qu'est-ce que je peux faire pour toi?")
    else:
        await speak("Bonsoir! Je t'ecoute")


async def handle_thanks(_query: str):
    import random
    responses = ["De rien!", "Avec plaisir!", "A ton service!", "Pas de souci!"]
    await speak(random.choice(responses))


async def handle_mute(_query: str):
    await devialet.mute()
    memory.add("MUSIC_MUTE", "")


async def handle_unmute(_query: str):
    await devialet.unmute()
    memory.add("MUSIC_UNMUTE", "")


async def handle_timer(query: str):
    minutes = extract_timer_minutes(query)
    if minutes and minutes > 0:
        await speak(f"Minuteur de {minutes} minutes lance")

        async def _timer_alert():
            await asyncio.sleep(minutes * 60)
            await speak(f"Le minuteur de {minutes} minutes est termine!")

        asyncio.create_task(_timer_alert())
        memory.add("TIMER", str(minutes))
    else:
        await speak("Combien de minutes pour le minuteur?")


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
    context = memory.format_for_llm()
    response = await llm.ask(text, context=context) if context else await llm.ask(text)
    memory.add("GENERAL", text, {"response": response})
    await broadcast({"type": "llm_response", "data": response})
    await speak(response)


async def speak(text: str):
    memory.set_tts(text)
    await set_state("SPEAKING")
    await broadcast({"type": "speaking", "data": text})
    # No ducking — TTS and music share the same AirPlay output
    await tts.speak(text)
    await set_state("IDLE")


INTENT_HANDLERS = {
    "MUSIC_PLAY": handle_music_play,
    "MUSIC_PAUSE": handle_music_pause,
    "MUSIC_RESUME": handle_music_resume,
    "MUSIC_NEXT": handle_music_next,
    "MUSIC_PREV": handle_music_prev,
    "MUSIC_VOLUME_UP": handle_music_volume_up,
    "MUSIC_VOLUME_DOWN": handle_music_volume_down,
    "MUSIC_VOLUME_SET": handle_music_volume_set,
    "MUSIC_WHAT": handle_music_what,
    "MUSIC_PLAYLIST": handle_music_playlist,
    "MUSIC_FIND": handle_music_find,
    "MUSIC_AI_MIX": handle_ai_mix,
    "YOUTUBE_PLAY": handle_youtube_play,
    "YOUTUBE_STOP": handle_youtube_stop,
    "WEATHER": handle_weather,
    "SLEEP": handle_sleep,
    "WAKE": handle_wake,
    "TIME": handle_time,
    "REPEAT": handle_repeat,
    "CANCEL": handle_cancel,
    "TIMER": handle_timer,
    "DOMOTIQUE_VOLETS_OPEN": handle_volets_open,
    "DOMOTIQUE_VOLETS_CLOSE": handle_volets_close,
    "DOMOTIQUE_PORTAIL": handle_portail,
    "DOMOTIQUE_GUINGUETTE_ON": handle_guinguette_on,
    "DOMOTIQUE_GUINGUETTE_OFF": handle_guinguette_off,
    "GREETING": handle_greeting,
    "THANKS": handle_thanks,
    "MUSIC_MUTE": handle_mute,
    "MUSIC_UNMUTE": handle_unmute,
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
        # Pass active context so "stop" routes correctly (youtube vs music)
        try:
            is_yt = youtube.is_playing()
        except Exception:
            is_yt = False
        active_ctx = "youtube" if is_yt else memory.domain
        intent, query = route(text, active_context=active_ctx)
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

    # No volume ducking — causes more problems than it solves
    _wake_saved_vol = None

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

    # Volume not ducked — nothing to restore

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

        # Volume transitions via Devialet (skip if user overrode manually)
        if not volume_manual_override:
            if in_quiet and not was_quiet:
                await devialet.set_volume(30)
                await broadcast({"type": "volume", "data": 30})
                logger.info("[VOLUME] Mode nuit 30%%")
            elif not in_quiet and was_quiet:
                await devialet.set_volume(50)
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


# --- Audio sinks ---

async def _get_audio_sinks() -> dict:
    """List PipeWire/PulseAudio sinks with current default."""
    import subprocess
    loop = asyncio.get_event_loop()
    try:
        def _query():
            default = subprocess.run(
                ['pactl', 'get-default-sink'],
                capture_output=True, text=True, timeout=5,
            ).stdout.strip()

            raw = subprocess.run(
                ['pactl', 'list', 'sinks'],
                capture_output=True, text=True, timeout=5,
            ).stdout

            sinks = []
            current = {}
            for line in raw.splitlines():
                line = line.strip()
                if line.startswith('Sink #'):
                    if current:
                        sinks.append(current)
                    current = {'id': line.split('#')[1]}
                elif line.startswith('Name:'):
                    current['name'] = line.split(':', 1)[1].strip()
                elif line.startswith('Description:'):
                    current['description'] = line.split(':', 1)[1].strip()
                elif line.startswith('State:'):
                    current['state'] = line.split(':', 1)[1].strip()
            if current:
                sinks.append(current)

            return {
                'default': default,
                'sinks': [
                    {
                        'name': s.get('name', ''),
                        'description': s.get('description', s.get('name', '')),
                        'state': s.get('state', ''),
                        'is_default': s.get('name', '') == default,
                    }
                    for s in sinks
                ],
            }

        return await loop.run_in_executor(None, _query)
    except Exception as e:
        logger.error("[AUDIO] Erreur liste sinks: %s", e)
        return {'default': '', 'sinks': [], 'error': str(e)}


async def _set_audio_sink(sink_name: str) -> dict:
    """Set default PipeWire/PulseAudio sink and move all active streams to it."""
    import subprocess
    loop = asyncio.get_event_loop()
    try:
        def _apply():
            # 1. Set default sink
            subprocess.run(
                ['pactl', 'set-default-sink', sink_name],
                check=True, timeout=5,
            )
            # 2. Move ALL active sink-inputs (playing streams) to the new sink
            inputs_raw = subprocess.run(
                ['pactl', 'list', 'sink-inputs', 'short'],
                capture_output=True, text=True, timeout=5,
            ).stdout
            moved = 0
            for line in inputs_raw.strip().splitlines():
                if not line.strip():
                    continue
                input_id = line.split()[0]
                try:
                    subprocess.run(
                        ['pactl', 'move-sink-input', input_id, sink_name],
                        check=True, timeout=5,
                    )
                    moved += 1
                except Exception:
                    pass
            return sink_name, moved

        result_name, moved = await loop.run_in_executor(None, _apply)
        logger.info("[AUDIO] Sink par defaut: %s (%d flux deplaces)", result_name, moved)
        return {'success': True, 'default': result_name, 'moved': moved}
    except Exception as e:
        logger.error("[AUDIO] Erreur set sink: %s", e)
        return {'success': False, 'error': str(e)}


# --- App lifecycle ---

async def _delayed_shutdown():
    """Shutdown the Pi after a short delay."""
    await asyncio.sleep(2)
    proc = await asyncio.create_subprocess_exec(
        "sudo", "shutdown", "-h", "now",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    await proc.wait()


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
    await devialet.start()
    await domotique.start()
    await llm.start()
    await tts.start()
    # Connect YouTube ↔ Spotify: pause music when video plays, resume when stops
    youtube.set_music_callbacks(
        pause_fn=music.pause,
        resume_fn=music.resume,
    )
    # Pause wake word during video to free CPU for smooth AirPlay audio
    youtube.set_wakeword_callbacks(
        pause_fn=lambda: setattr(wake_detector, 'paused', True),
        resume_fn=lambda: setattr(wake_detector, 'paused', False),
    )
    pipeline_task = asyncio.create_task(voice_pipeline())
    scheduler_task = asyncio.create_task(screen_scheduler())
    watchdog_task = asyncio.create_task(music.token_watchdog())
    # Port 8888 redirect for Spotify OAuth callback (registered as http://127.0.0.1:8888/callback)
    proxy_server = await _start_oauth_proxy()
    logger.info("[PI-BOARD] Tous les services demarres")
    yield
    logger.info("[PI-BOARD] Arret...")
    await audio_capture.stop()
    pipeline_task.cancel()
    scheduler_task.cancel()
    watchdog_task.cancel()
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
        dev_status = await asyncio.wait_for(devialet.get_status(), timeout=3)
        vol = dev_status.get("volume") or 50
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
                await devialet.set_volume(vol)
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
                    dev_s = await devialet.get_status()
                    await broadcast({"type": "volume", "data": dev_s.get("volume") or 50})
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
            elif msg.get("type") == "system_shutdown":
                logger.info("[SYSTEM] Shutdown demande par l'utilisateur")
                await ws.send_json({"type": "speaking", "data": "Extinction en cours..."})
                asyncio.create_task(_delayed_shutdown())
            elif msg.get("type") == "domotique_status":
                status = await domotique.get_status()
                await ws.send_json({"type": "domotique_status", "data": status})
            elif msg.get("type") == "domotique_roller":
                d = msg.get("data", {})
                dev_id = d.get("id", "")
                action = d.get("action", "")
                if action == "open":
                    await domotique.roller_open(dev_id)
                elif action == "close":
                    await domotique.roller_close(dev_id)
                elif action == "stop":
                    await domotique.roller_stop(dev_id)
                status = await domotique.get_status()
                await broadcast({"type": "domotique_status", "data": status})
            elif msg.get("type") == "domotique_roller_all":
                action = msg.get("data", "")
                if action == "open":
                    await domotique.open_all_rollers()
                elif action == "close":
                    await domotique.close_all_rollers()
                status = await domotique.get_status()
                await broadcast({"type": "domotique_status", "data": status})
            elif msg.get("type") == "domotique_portail":
                await domotique.trigger_portail()
            elif msg.get("type") == "domotique_plug":
                d = msg.get("data", {})
                dev_id = d.get("id", "")
                action = d.get("action", "")
                if action == "on":
                    await domotique.plug_on(dev_id)
                elif action == "off":
                    await domotique.plug_off(dev_id)
                elif action == "toggle":
                    await domotique.plug_toggle(dev_id)
                status = await domotique.get_status()
                await broadcast({"type": "domotique_status", "data": status})
            elif msg.get("type") == "devialet_status":
                status = await devialet.get_status()
                await ws.send_json({"type": "devialet_status", "data": status})
            elif msg.get("type") == "devialet_volume":
                vol = int(msg.get("data", 50))
                await devialet.set_volume(vol)
                status = await devialet.get_status()
                await broadcast({"type": "devialet_status", "data": status})
            elif msg.get("type") == "devialet_volume_up":
                await devialet.volume_up()
                status = await devialet.get_status()
                await broadcast({"type": "devialet_status", "data": status})
            elif msg.get("type") == "devialet_volume_down":
                await devialet.volume_down()
                status = await devialet.get_status()
                await broadcast({"type": "devialet_status", "data": status})
            elif msg.get("type") == "devialet_play":
                await devialet.play()
            elif msg.get("type") == "devialet_pause":
                await devialet.pause()
            elif msg.get("type") == "devialet_next":
                await devialet.next_track()
            elif msg.get("type") == "devialet_prev":
                await devialet.previous_track()
            elif msg.get("type") == "devialet_mute":
                await devialet.mute()
            elif msg.get("type") == "devialet_unmute":
                await devialet.unmute()
            elif msg.get("type") == "devialet_night_mode":
                on = bool(msg.get("data", False))
                await devialet.set_night_mode(on)
                status = await devialet.get_status()
                await broadcast({"type": "devialet_status", "data": status})
            elif msg.get("type") == "devialet_eq_preset":
                preset = msg.get("data", "flat")
                await devialet.set_equalizer_preset(preset)
                status = await devialet.get_status()
                await broadcast({"type": "devialet_status", "data": status})
            elif msg.get("type") == "audio_sinks":
                sinks = await _get_audio_sinks()
                await ws.send_json({"type": "audio_sinks", "data": sinks})
            elif msg.get("type") == "audio_set_sink":
                sink_name = msg.get("data", "")
                if sink_name:
                    result = await _set_audio_sink(sink_name)
                    await ws.send_json({"type": "audio_sink_changed", "data": result})
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
    """Show a styled intermediate page that redirects to Spotify auth."""
    url = music.get_auth_url()
    if not url:
        return JSONResponse({"error": "Spotify non configure"}, status_code=400)
    from fastapi.responses import HTMLResponse
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<style>
body {{ background: #0a0a0f; color: #f0f0f0; font-family: Inter, sans-serif;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  height: 100vh; margin: 0; gap: 20px; }}
.spinner {{ width: 40px; height: 40px; border: 3px solid #333; border-top-color: #1DB954;
  border-radius: 50%; animation: spin 1s linear infinite; }}
@keyframes spin {{ to {{ transform: rotate(360deg); }} }}
h2 {{ font-size: 18px; color: #1DB954; margin: 0; }}
p {{ font-size: 13px; color: #888; margin: 0; }}
a {{ color: #6c63ff; font-size: 13px; margin-top: 20px; }}
</style>
</head><body>
<div class="spinner"></div>
<h2>Connexion a Spotify...</h2>
<p>Vous allez etre redirige</p>
<a href="/">Annuler et revenir</a>
<script>setTimeout(function() {{ window.location.href = "{url}"; }}, 1500);</script>
</body></html>"""
    return HTMLResponse(html)


@app.get("/api/spotify/callback")
async def api_spotify_callback(code: str = ""):
    """Handle Spotify OAuth callback with styled result page."""
    from fastapi.responses import HTMLResponse
    if not code:
        return JSONResponse({"error": "Code manquant"}, status_code=400)
    success = await music.handle_callback(code)
    if success:
        icon = "&#10004;"
        color = "#1DB954"
        title = "Spotify connecte !"
        detail = "Retour a l'interface..."
    else:
        icon = "&#10008;"
        color = "#ff6b6b"
        title = "Echec de connexion"
        detail = "Retour automatique dans 3 secondes"
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<style>
body {{ background: #0a0a0f; color: #f0f0f0; font-family: Inter, sans-serif;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  height: 100vh; margin: 0; gap: 16px; }}
.icon {{ font-size: 48px; color: {color}; }}
h2 {{ font-size: 20px; color: {color}; margin: 0; }}
p {{ font-size: 13px; color: #888; margin: 0; }}
</style>
</head><body>
<span class="icon">{icon}</span>
<h2>{title}</h2>
<p>{detail}</p>
<script>setTimeout(function() {{ window.location.href = "/"; }}, 2000);</script>
</body></html>"""
    return HTMLResponse(html)


@app.get("/callback")
async def legacy_spotify_callback(code: str = ""):
    """Legacy redirect URI (http://127.0.0.1:8888/callback -> port 8000) — forward to real handler."""
    return await api_spotify_callback(code=code)


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


@app.api_route("/api/youtube/audio-proxy", methods=["GET", "HEAD"])
async def api_youtube_audio_proxy():
    """Proxy YouTube audio stream for UPnP playback (Devialet can't access HTTPS googlevideo)."""
    from starlette.requests import Request
    proxy_url = getattr(youtube, '_current_audio_proxy_url', None)
    if not proxy_url:
        return JSONResponse({"error": "No audio stream"}, status_code=404)

    import httpx

    async def _stream():
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", proxy_url, timeout=120) as resp:
                async for chunk in resp.aiter_bytes(chunk_size=65536):
                    yield chunk

    return StreamingResponse(_stream(), media_type="audio/ogg")


# Serve UPnP audio files (TTS, etc.)
upnp_audio_dir = Path(__file__).parent / ".." / "frontend" / "dist" / "upnp_audio"
upnp_audio_dir.mkdir(exist_ok=True)
app.mount("/upnp_audio", StaticFiles(directory=upnp_audio_dir), name="upnp-audio")


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
