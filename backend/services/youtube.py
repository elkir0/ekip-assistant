import asyncio
import logging
import os
import signal
import subprocess
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)

YT_FORMAT_DEFAULT = "bestvideo[height<=720][vcodec^=avc]+bestaudio/bestvideo[height<=720]+bestaudio/best[height<=720]/best"
YT_COOKIES = os.path.join(os.path.dirname(__file__), '..', '..', 'yt-cookies.txt')


def _get_yt_config() -> dict:
    """Read YouTube config from admin config manager (lazy import)."""
    try:
        from admin.config_manager import config
        return config.get_section("youtube")
    except Exception:
        return {}


def _get_raop_sink() -> str:
    """Find the best Devialet RAOP sink from PipeWire.

    Priority: 1) manual devialet_ipv4, 2) auto-discovered IPv4, 3) any Phantom, 4) default sink.
    """
    try:
        result = subprocess.run(
            ["pactl", "list", "sinks", "short"],
            capture_output=True, text=True, timeout=5,
        )
        manual_ipv4 = None
        auto_ipv4 = None
        any_devialet = None
        for line in result.stdout.strip().split("\n"):
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            name = parts[1]
            if "devialet_ipv4" in name:
                manual_ipv4 = name
            elif "phantom" in name.lower() and "fe80" not in name:
                auto_ipv4 = name
            elif "phantom" in name.lower():
                any_devialet = name

        if manual_ipv4:
            return manual_ipv4
        if auto_ipv4:
            return auto_ipv4
        if any_devialet:
            return any_devialet
    except Exception:
        pass

    # Fallback: use default sink
    try:
        result = subprocess.run(
            ["pactl", "get-default-sink"],
            capture_output=True, text=True, timeout=5,
        )
        sink = result.stdout.strip()
        if sink:
            return sink
    except Exception:
        pass
    return "@DEFAULT_SINK@"


class YouTubeController:
    def __init__(self):
        self._vlc_process: asyncio.subprocess.Process | None = None
        self._on_music_pause: Callable | None = None
        self._on_music_resume: Callable | None = None
        self._on_wakeword_pause: Callable | None = None
        self._on_wakeword_resume: Callable | None = None
        self._queue: list[dict] = []
        self._queue_index: int = 0
        self._on_finish_callback = None
        self._on_next_callback: Callable | None = None
        self._stopped = False

    def set_music_callbacks(self, pause_fn, resume_fn):
        """Set callbacks to pause/resume Spotify when YouTube plays/stops."""
        self._on_music_pause = pause_fn
        self._on_music_resume = resume_fn

    def set_wakeword_callbacks(self, pause_fn, resume_fn):
        """Set callbacks to pause/resume wake word during video playback (saves CPU)."""
        self._on_wakeword_pause = pause_fn
        self._on_wakeword_resume = resume_fn

    def set_queue(self, results: list[dict], on_next=None):
        """Set the video queue from search results."""
        self._queue = results
        self._queue_index = 0
        self._on_next_callback = on_next
        self._stopped = False
        logger.info("[YOUTUBE] Queue: %d videos", len(results))

    def get_queue(self) -> list[dict]:
        """Return remaining videos in queue."""
        if self._queue_index + 1 < len(self._queue):
            return self._queue[self._queue_index + 1:]
        return []

    def _base_args(self) -> list[str]:
        """Return common yt-dlp arguments (cookies + JS solver)."""
        args = ["--remote-components", "ejs:github"]
        if os.path.exists(YT_COOKIES):
            args.extend(["--cookies", YT_COOKIES])
        return args

    async def search(self, query: str, limit: int = 0) -> list[dict[str, Any]]:
        cfg = _get_yt_config()
        if limit <= 0:
            limit = cfg.get("search_limit", 5)
        timeout = cfg.get("search_timeout_s", 15)
        try:
            proc = await asyncio.create_subprocess_exec(
                "yt-dlp",
                *self._base_args(),
                f"ytsearch{limit}:{query}",
                "--dump-json",
                "--flat-playlist",
                "--no-download",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)

            import json
            results = []
            for line in stdout.decode().strip().split("\n"):
                if not line:
                    continue
                data = json.loads(line)
                results.append({
                    "id": data.get("id", ""),
                    "title": data.get("title", ""),
                    "channel": data.get("channel", data.get("uploader", "")),
                    "duration": data.get("duration_string", ""),
                    "thumbnail": data.get("thumbnail", ""),
                    "url": f"https://www.youtube.com/watch?v={data.get('id', '')}",
                })

            logger.info("[YOUTUBE] Recherche '%s': %d resultats", query, len(results))
            return results

        except asyncio.TimeoutError:
            logger.error("[YOUTUBE] Timeout recherche")
            return []
        except FileNotFoundError:
            logger.error("[YOUTUBE] yt-dlp non installe")
            return []
        except Exception as e:
            logger.error("[YOUTUBE] Erreur recherche: %s", e)
            return []

    async def play(self, url: str, on_finish=None) -> dict:
        # Stop any existing playback (but don't clear queue)
        await self._stop_vlc()

        self._on_finish_callback = on_finish

        try:
            # Pause wake word to free CPU for video playback
            if self._on_wakeword_pause:
                try:
                    self._on_wakeword_pause()
                except Exception:
                    pass

            # Pause Spotify before playing YouTube (timeout to avoid rate limit block)
            if self._on_music_pause:
                try:
                    await asyncio.wait_for(self._on_music_pause(), timeout=3)
                    logger.info("[YOUTUBE] Spotify mis en pause")
                except (asyncio.TimeoutError, Exception) as e:
                    logger.warning("[YOUTUBE] Pause Spotify skip: %s", e)

            return await self._launch_vlc(url)

        except asyncio.TimeoutError:
            logger.error("[YOUTUBE] Timeout yt-dlp")
            return {"playing": False, "error": "Timeout"}
        except FileNotFoundError as e:
            logger.error("[YOUTUBE] Programme manquant: %s", e)
            return {"playing": False, "error": "vlc ou yt-dlp non installe"}
        except Exception as e:
            logger.error("[YOUTUBE] Erreur lecture: %s", e)
            return {"playing": False, "error": str(e)}

    async def _launch_vlc(self, url: str) -> dict:
        """Get stream URLs and launch VLC for a single video."""
        cfg = _get_yt_config()
        yt_format = cfg.get("format", YT_FORMAT_DEFAULT)
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "-f", yt_format,
            "--get-url",
            *self._base_args(),
            url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        stderr_text = stderr.decode().strip() if stderr else ""
        if stderr_text:
            for line in stderr_text.split("\n"):
                if "WARNING" not in line and line.strip():
                    logger.warning("[YOUTUBE] yt-dlp: %s", line[:200])

        if proc.returncode != 0:
            logger.error("[YOUTUBE] yt-dlp echoue (code %d) pour %s: %s", proc.returncode, url, stderr_text[:300])
            return {"playing": False, "error": f"yt-dlp erreur (code {proc.returncode})"}

        stream_urls = [u for u in stdout.decode().strip().split("\n") if u.startswith("http")]

        if not stream_urls:
            logger.error("[YOUTUBE] yt-dlp n'a retourne aucune URL pour %s", url)
            return {"playing": False, "error": "Impossible d'obtenir l'URL"}

        sink_name = _get_raop_sink()
        logger.info("[YOUTUBE] Sink audio: %s, %d stream URLs", sink_name, len(stream_urls))
        env = {**os.environ, "PULSE_SINK": sink_name}
        cache_ms = cfg.get("network_cache_ms", 5000)

        # Use mpv (VLC 3.0.23 broken with HTTPS streams on Pi)
        player_args = [
            "mpv",
            "--fullscreen",
            "--ao=pulse",
            "--no-terminal",
            f"--cache-secs={cache_ms // 1000}",
            "--demuxer-max-bytes=50M",
            "--hwdec=auto",
        ]
        if len(stream_urls) >= 2 and stream_urls[1]:
            player_args.append(f"--audio-file={stream_urls[1]}")
        player_args.append(stream_urls[0])

        logger.info("[YOUTUBE] Lancement mpv: %d args, video=%s", len(player_args), url)
        self._vlc_process = await asyncio.create_subprocess_exec(
            *player_args,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        # Wait briefly to check player didn't die immediately
        await asyncio.sleep(2)
        if self._vlc_process.returncode is not None:
            exit_code = self._vlc_process.returncode
            player_err = ""
            try:
                stderr_data = await asyncio.wait_for(self._vlc_process.stderr.read(2000), timeout=1)
                player_err = stderr_data.decode().strip()[:300]
            except Exception:
                pass
            logger.error("[YOUTUBE] mpv mort immediatement (code %d): %s", exit_code, player_err)
            self._vlc_process = None
            return {"playing": False, "error": f"mpv echoue (code {exit_code})"}

        logger.info("[YOUTUBE] mpv demarre OK (PID %d)", self._vlc_process.pid)

        # Watch for natural VLC exit → play next in queue
        asyncio.create_task(self._watch_vlc())

        return {"playing": True, "url": url}

    async def _watch_vlc(self):
        try:
            if self._vlc_process:
                start_time = asyncio.get_event_loop().time()
                await self._vlc_process.wait()
                duration = asyncio.get_event_loop().time() - start_time
                exit_code = self._vlc_process.returncode
                self._vlc_process = None

                # If VLC died very fast, it's an error not a natural end
                if duration < 5:
                    logger.warning("[YOUTUBE] mpv termine trop vite (%.1fs, code %s) — skip", duration, exit_code)
                    # Don't chain next, just clean up
                    if self._on_wakeword_resume:
                        try:
                            self._on_wakeword_resume()
                        except Exception:
                            pass
                    if self._on_music_resume:
                        try:
                            await asyncio.wait_for(self._on_music_resume(), timeout=3)
                        except Exception:
                            pass
                    if self._on_finish_callback:
                        await self._on_finish_callback()
                    return

                logger.info("[YOUTUBE] mpv termine naturellement (%.0fs)", duration)

                # If stopped manually, don't play next
                if self._stopped:
                    return

                # Try to play next in queue
                if self._queue_index + 1 < len(self._queue):
                    self._queue_index += 1
                    next_video = self._queue[self._queue_index]
                    logger.info("[YOUTUBE] Enchainement: %s (%d/%d)",
                                next_video["title"][:50], self._queue_index + 1, len(self._queue))

                    # Notify frontend of new video
                    if self._on_next_callback:
                        try:
                            await self._on_next_callback(next_video)
                        except Exception:
                            pass

                    try:
                        await self._launch_vlc(next_video["url"])
                        return  # _watch_vlc will be called again by _launch_vlc
                    except Exception as e:
                        logger.error("[YOUTUBE] Erreur enchainement: %s", e)

                # Queue exhausted or error — resume wake word + Spotify
                logger.info("[YOUTUBE] Queue terminee")
                if self._on_wakeword_resume:
                    try:
                        self._on_wakeword_resume()
                    except Exception:
                        pass
                if self._on_music_resume:
                    try:
                        await asyncio.wait_for(self._on_music_resume(), timeout=3)
                        logger.info("[YOUTUBE] Spotify repris")
                    except (asyncio.TimeoutError, Exception) as e:
                        logger.warning("[YOUTUBE] Reprise Spotify skip: %s", e)
                if self._on_finish_callback:
                    await self._on_finish_callback()
        except Exception as e:
            logger.error("[YOUTUBE] Erreur watcher mpv: %s", e)

    async def _stop_vlc(self):
        """Stop VLC without resuming Spotify or clearing queue."""
        if self._vlc_process and self._vlc_process.returncode is None:
            try:
                self._vlc_process.send_signal(signal.SIGTERM)
                await asyncio.wait_for(self._vlc_process.wait(), timeout=3)
                logger.info("[YOUTUBE] mpv arrete")
            except (asyncio.TimeoutError, ProcessLookupError):
                self._vlc_process.kill()
            self._vlc_process = None

    async def stop(self) -> dict:
        """Full stop: kill VLC, clear queue, resume wake word + Spotify."""
        self._stopped = True
        self._queue = []
        self._queue_index = 0
        await self._stop_vlc()
        # Resume wake word (frees CPU constraint)
        if self._on_wakeword_resume:
            try:
                self._on_wakeword_resume()
            except Exception:
                pass
        # Resume Spotify after stop (timeout to avoid rate limit block)
        if self._on_music_resume:
            try:
                await asyncio.wait_for(self._on_music_resume(), timeout=3)
                logger.info("[YOUTUBE] Spotify repris")
            except (asyncio.TimeoutError, Exception) as e:
                logger.warning("[YOUTUBE] Reprise Spotify skip: %s", e)
        return {"stopped": True}

    @property
    def is_playing(self) -> bool:
        return self._vlc_process is not None and self._vlc_process.returncode is None
