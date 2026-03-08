import asyncio
import logging
import os
import signal
import subprocess
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)

YT_FORMAT = "bestvideo[height<=480][vcodec^=avc]+bestaudio/best[height<=480]"


def _get_raop_sink() -> str:
    """Find the Devialet RAOP sink name from PipeWire."""
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
        self._queue: list[dict] = []
        self._queue_index: int = 0
        self._on_finish_callback = None
        self._on_next_callback: Callable | None = None
        self._stopped = False

    def set_music_callbacks(self, pause_fn, resume_fn):
        """Set callbacks to pause/resume Spotify when YouTube plays/stops."""
        self._on_music_pause = pause_fn
        self._on_music_resume = resume_fn

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

    async def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        try:
            proc = await asyncio.create_subprocess_exec(
                "yt-dlp",
                f"ytsearch{limit}:{query}",
                "--dump-json",
                "--flat-playlist",
                "--no-download",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)

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
            # Pause Spotify before playing YouTube
            if self._on_music_pause:
                try:
                    await self._on_music_pause()
                    logger.info("[YOUTUBE] Spotify mis en pause")
                except Exception as e:
                    logger.warning("[YOUTUBE] Erreur pause Spotify: %s", e)

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
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "-f", YT_FORMAT,
            "--get-url",
            url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=20)
        if stderr:
            stderr_text = stderr.decode().strip()
            if stderr_text and "WARNING" not in stderr_text:
                logger.warning("[YOUTUBE] yt-dlp stderr: %s", stderr_text[:200])
        stream_urls = stdout.decode().strip().split("\n")

        if not stream_urls or not stream_urls[0]:
            logger.error("[YOUTUBE] yt-dlp n'a retourne aucune URL pour %s", url)
            return {"playing": False, "error": "Impossible d'obtenir l'URL"}

        sink_name = _get_raop_sink()
        logger.info("[YOUTUBE] Sink audio: %s, %d stream URLs", sink_name, len(stream_urls))
        env = {**os.environ, "PULSE_SINK": sink_name}
        vlc_args = [
            "vlc",
            "--fullscreen",
            "--play-and-exit",
            "--aout=pulse",
            "--volume=256",
            "--no-video-title-show",
            "--quiet",
            "--network-caching=3000",
            "--file-caching=3000",
            "--live-caching=3000",
            "--clock-jitter=0",
            "--avcodec-skiploopfilter=4",
        ]
        if len(stream_urls) >= 2 and stream_urls[1]:
            vlc_args.append(f"--input-slave={stream_urls[1]}")
        vlc_args.append(stream_urls[0])
        self._vlc_process = await asyncio.create_subprocess_exec(
            *vlc_args,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            env=env,
        )

        logger.info("[YOUTUBE] Lecture VLC: %s", url)

        # Watch for natural VLC exit → play next in queue
        asyncio.create_task(self._watch_vlc())

        return {"playing": True, "url": url}

    async def _watch_vlc(self):
        try:
            if self._vlc_process:
                await self._vlc_process.wait()
                self._vlc_process = None
                logger.info("[YOUTUBE] VLC termine naturellement")

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

                # Queue exhausted or error — resume Spotify
                logger.info("[YOUTUBE] Queue terminee")
                if self._on_music_resume:
                    try:
                        await self._on_music_resume()
                        logger.info("[YOUTUBE] Spotify repris")
                    except Exception as e:
                        logger.warning("[YOUTUBE] Erreur reprise Spotify: %s", e)
                if self._on_finish_callback:
                    await self._on_finish_callback()
        except Exception as e:
            logger.error("[YOUTUBE] Erreur watcher VLC: %s", e)

    async def _stop_vlc(self):
        """Stop VLC without resuming Spotify or clearing queue."""
        if self._vlc_process and self._vlc_process.returncode is None:
            try:
                self._vlc_process.send_signal(signal.SIGTERM)
                await asyncio.wait_for(self._vlc_process.wait(), timeout=3)
                logger.info("[YOUTUBE] VLC arrete")
            except (asyncio.TimeoutError, ProcessLookupError):
                self._vlc_process.kill()
            self._vlc_process = None

    async def stop(self) -> dict:
        """Full stop: kill VLC, clear queue, resume Spotify."""
        self._stopped = True
        self._queue = []
        self._queue_index = 0
        await self._stop_vlc()
        # Resume Spotify after stop
        if self._on_music_resume:
            try:
                await self._on_music_resume()
                logger.info("[YOUTUBE] Spotify repris")
            except Exception as e:
                logger.warning("[YOUTUBE] Erreur reprise Spotify: %s", e)
        return {"stopped": True}

    @property
    def is_playing(self) -> bool:
        return self._vlc_process is not None and self._vlc_process.returncode is None
