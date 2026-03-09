
<p align="center">

```
 ____  _ ____                      _
|  _ \(_) __ )  ___   __ _ _ __ __| |
| |_) | |  _ \ / _ \ / _` | '__/ _` |
|  __/| | |_) | (_) | (_| | | | (_| |
|_|   |_|____/ \___/ \__,_|_|  \__,_|
```

**Your home deserves a voice. Build it yourself.**

</p>

<p align="center">
  <a href="#"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue.svg"></a>
  <a href="#"><img alt="Python 3.11" src="https://img.shields.io/badge/python-3.11-3776AB.svg"></a>
  <a href="#"><img alt="Svelte 4" src="https://img.shields.io/badge/svelte-4-FF3E00.svg"></a>
  <a href="#"><img alt="Raspberry Pi 4" src="https://img.shields.io/badge/raspberry%20pi-4-C51A4A.svg"></a>
  <a href="#"><img alt="FastAPI" src="https://img.shields.io/badge/fastapi-0.115-009688.svg"></a>
</p>

<p align="center">
  <strong>English</strong> |
  <a href="README_FR.md">Francais</a> |
  <a href="README_ES.md">Espanol</a>
</p>

---

**Piboard** is an open-source smart display that turns a Raspberry Pi into a fully voice-controlled home assistant. Think Amazon Echo Show — but one you own, understand, and can customize however you want.

Say *"Hey Piboard, mets du jazz"* and it plays jazz on your Devialet. Ask for the weather and it reads the forecast while switching to the weather page. Tell it to play a YouTube video and it streams fullscreen with audio routed wirelessly to your speakers via AirPlay.

No cloud lock-in. No subscription. Just a Pi, a screen, and your voice.

Born in **Guadeloupe**, designed to run 24/7 on your nightstand or kitchen counter.

## Why Piboard?

- **Wireless hi-fi audio** — Music and video audio stream to any AirPlay or Spotify Connect speaker (Devialet, Sonos, HomePod, etc.) via PipeWire's RAOP sink. The Pi never touches the audio — your speakers do.
- **Spotify Connect integration** — Search by voice, control playback, browse playlists. Audio goes directly from Spotify servers to your speaker — zero quality loss.
- **YouTube on your TV/speaker** — Voice or touch search, fullscreen VLC playback, audio routed to your hi-fi speakers over AirPlay. Queue management with auto-chaining.
- **Real voice interaction** — Custom wake word trained on YOUR voice. STT via OpenAI, natural TTS responses, smart audio ducking that lowers music when the assistant speaks.
- **4-page touch interface** — Swipe between Music, Weather, YouTube, and Security Cameras. Dark theme optimized for always-on 7" displays.
- **Security cameras** — Live snapshots from UniFi Protect cameras right on your nightstand.
- **Full admin panel** — Configure everything from your phone: wake word sensitivity, audio routing, Spotify settings, YouTube cookies, screen schedule, and more.
- **Auto sleep/wake** — Screen off at 22h, back on at 6h. Night volume mode from 20h. Smart brightness control.
- **100% open source** — MIT licensed, no proprietary firmware, no vendor lock-in.

## Screenshots

| Music | Weather | YouTube |
|:-----:|:-------:|:-------:|
| ![Music](docs/screenshots/music.png) | ![Weather](docs/screenshots/weather.png) | ![YouTube](docs/screenshots/youtube.png) |

## How It Works

```
Raspberry Pi 4 + 7" Touchscreen
  |
  +-- Chromium Kiosk (fullscreen Svelte app)
  |    +-- WebSocket <--> FastAPI Backend
  |
  +-- USB Microphone (ReSpeaker 2-Mic Array)
  |    +-- Wake Word Detection (EfficientWord-Net / openWakeWord)
  |    +-- Speech-to-Text (OpenAI GPT-4o-transcribe)
  |    +-- Intent Router (keyword matching, zero-cost for common commands)
  |         |
  |         +-- "mets du jazz"     --> Spotify API --> Devialet (Spotify Connect)
  |         +-- "meteo demain"     --> Open-Meteo --> TTS --> AirPlay --> Speaker
  |         +-- "YouTube Stromae"  --> yt-dlp --> VLC --> AirPlay --> Speaker
  |         +-- "montre les cameras" --> UniFi Protect --> Live snapshots
  |         +-- anything else      --> LLM (GPT-4o-mini) --> TTS --> Speaker
  |
  +-- PipeWire Audio Engine
       +-- RAOP sink (AirPlay) --> Devialet / Sonos / HomePod
       +-- Spotify Connect (direct stream, Pi not in the audio path)
```

### Audio Architecture

This is what makes Piboard special:

| Source | Path | Quality |
|--------|------|---------|
| **Spotify** | Spotify servers --> Spotify Connect --> your speaker | Lossless (OGG 320kbps) |
| **YouTube video** | yt-dlp --> VLC --> PipeWire --> AirPlay (RAOP) --> your speaker | Up to 720p video + AAC audio |
| **Voice responses** | OpenAI TTS --> PipeWire --> AirPlay --> your speaker | Natural voice |
| **Ducking** | Spotify volume lowered via API while TTS plays, then restored | Seamless |

The Pi acts as a **controller and router**, never as a DAC. Your expensive speakers get the best quality audio the source can provide.

## Hardware Requirements

| Component | Model | Notes |
|-----------|-------|-------|
| **SBC** | Raspberry Pi 4 (4GB RAM) | ARM64, Raspberry Pi OS Bookworm 64-bit |
| **Display** | Raspberry Pi Touch Display 2 (7") | 720x1280, capacitive, DSI connector |
| **Microphone** | ReSpeaker Lite USB 2-Mic Array | Hardware AEC, or any USB mic |
| **Speakers** | Any AirPlay or Spotify Connect speaker | Devialet, Sonos, HomePod, etc. |
| **Storage** | microSD 32GB+ (class A2 recommended) | |
| **Network** | WiFi or Ethernet | Pi and speakers on same LAN |

**Total cost:** ~$120 (Pi + screen + mic), plus whatever speakers you already own.

## Quick Start

### 1. Clone and Install

```bash
git clone https://github.com/elkir0/ekip-assistant.git piboard
cd piboard
chmod +x scripts/*.sh
./scripts/setup.sh
```

### 2. Configure

```bash
cp .env.example .env
nano .env
```

Fill in your API keys (see [Configuration](#configuration) below).

### 3. Run

```bash
./scripts/start.sh
```

Backend starts on port 8000, Chromium opens in kiosk mode. You're live.

### 4. Auto-start on Boot

```bash
sudo cp systemd/piboard-backend.service /etc/systemd/system/
sudo cp systemd/piboard-kiosk.service /etc/systemd/system/
sudo systemctl enable piboard-backend piboard-kiosk
sudo systemctl start piboard-backend piboard-kiosk
```

## Configuration

Create a `.env` file from the example:

```bash
# Speech-to-Text + Text-to-Speech + LLM
OPENAI_API_KEY=sk-...              # openai.com — STT, TTS, and LLM

# Spotify
SPOTIFY_CLIENT_ID=...              # developer.spotify.com
SPOTIFY_CLIENT_SECRET=...
SPOTIFY_REDIRECT_URI=http://localhost:8000/api/spotify/callback
SPOTIFY_DEVICE_NAME=Devialet       # Exact name of your Spotify Connect speaker

# Weather (Open-Meteo is free, no key needed)
WEATHER_CITY=Guadeloupe
WEATHER_LAT=16.25
WEATHER_LON=-61.58

# UniFi Protect (optional — for security cameras)
UNIFI_HOST=192.168.1.18
UNIFI_USER=admin
UNIFI_PASS=...

# Audio
PIPEWIRE_AIRPLAY_SINK=Devialet     # Name of your PipeWire AirPlay sink
RESPEAKER_DEVICE=hw:ReSpeaker,0    # ALSA device name for your USB mic

# Server
BACKEND_PORT=8000
```

### API Keys

| Service | Where to get it | Cost |
|---------|----------------|------|
| **OpenAI** | [platform.openai.com](https://platform.openai.com) | Pay-as-you-go (~$0.01/day for voice assistant use) |
| **Spotify** | [developer.spotify.com](https://developer.spotify.com) | Free (requires Spotify Premium for playback) |
| **Open-Meteo** | No key needed | Free |
| **UniFi Protect** | Local Cloud Key | Free (requires UniFi hardware) |

## Voice Commands

Piboard understands French voice commands out of the box:

| Command | What it does |
|---------|-------------|
| *"Hey Piboard, mets du jazz"* | Searches and plays jazz on Spotify via your speakers |
| *"Hey Piboard, joue Stromae"* | Plays Stromae on Spotify Connect |
| *"Hey Piboard, pause"* | Pauses the current track |
| *"Hey Piboard, suivant"* | Skips to the next track |
| *"Hey Piboard, plus fort"* | Increases volume on your speakers |
| *"Hey Piboard, moins fort"* | Decreases volume |
| *"Hey Piboard, meteo"* | Reads the weather aloud and switches to the weather page |
| *"Hey Piboard, mets la video Stromae"* | Searches YouTube, plays fullscreen with audio on your speakers |
| *"Hey Piboard, stop video"* | Stops YouTube playback, resumes Spotify |
| *"Hey Piboard, dodo"* | Turns off the screen (sleep mode) |
| *"Hey Piboard, debout"* | Turns the screen back on |
| *"Hey Piboard, c'est quoi la capitale du Japon?"* | General question answered by LLM |

> The wake word is customizable. Train your own via the admin panel or `scripts/record_wakeword.py`.

## Touch Controls

- **Swipe up/down** to navigate between pages (Music > Weather > YouTube > Cameras)
- **Tap** play/pause, next/previous on the Music page
- **Volume slider** on the Music page
- **On-screen keyboard** for YouTube search
- **Tap** a camera for fullscreen snapshot

## Admin Panel

Access at `http://your-pi-ip:8000/admin` from any device on your network.

| Section | What you can configure |
|---------|----------------------|
| **Dashboard** | System status, service health, uptime, CPU/RAM |
| **Voice** | Wake word model, sensitivity threshold, cooldown |
| **Audio** | Microphone gain, PipeWire sink selection |
| **Music** | Spotify connection, device selection, search limits |
| **YouTube** | Video format/quality, VLC buffer size (AirPlay stability), cookie management for YouTube authentication |
| **Weather** | Location, timezone, forecast days |
| **Cameras** | UniFi Protect host, snapshot resolution, grid layout |
| **Screen** | Brightness, sleep/wake schedule, night volume |
| **System** | Live logs, service restart, system info |
| **Interface** | Accent color, transition speed, swipe sensitivity |

## Project Structure

```
piboard/
+-- backend/
|   +-- main.py                  # FastAPI app, WebSocket, voice pipeline
|   +-- config.py                # Environment variables
|   +-- audio/
|   |   +-- capture.py           # USB mic audio stream (PyAudio, 44.1kHz -> 16kHz)
|   |   +-- wakeword.py          # Wake word detection
|   |   +-- output.py            # PipeWire audio output (AirPlay routing)
|   +-- services/
|   |   +-- stt.py               # Speech-to-Text (OpenAI)
|   |   +-- tts.py               # Text-to-Speech (OpenAI TTS)
|   |   +-- llm.py               # LLM for complex intents (GPT-4o-mini)
|   |   +-- spotify.py           # Spotify Web API + Connect + auto-recovery
|   |   +-- weather.py           # Weather data (Open-Meteo)
|   |   +-- youtube.py           # YouTube search + VLC + AirPlay audio routing
|   |   +-- cameras.py           # UniFi Protect camera snapshots
|   +-- intent/
|   |   +-- router.py            # Intent classification (keyword + LLM fallback)
|   +-- admin/
|       +-- routes.py            # Admin API (config, cookies, system)
|       +-- config_manager.py    # Runtime config with disk persistence
|       +-- static/              # Admin panel (built Svelte app)
+-- frontend/
|   +-- src/                     # Main kiosk UI (Svelte)
|   +-- admin/                   # Admin panel (separate Svelte app)
+-- scripts/
|   +-- setup.sh                 # Full installation
|   +-- start.sh                 # Launch backend + kiosk
|   +-- deploy-pi.sh             # Deploy from Mac to Pi via scp
+-- systemd/
|   +-- piboard-backend.service  # Backend auto-start
|   +-- piboard-kiosk.service    # Chromium kiosk auto-start
+-- requirements.txt
+-- LICENSE
```

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend | Python 3.11, FastAPI, asyncio | Async everything, real-time WebSocket |
| Frontend | Svelte 4, Vite 5 | Fast, lightweight, perfect for embedded |
| Audio capture | PyAudio + scipy resampling | 44.1kHz USB mic -> 16kHz for STT |
| Wake word | EfficientWord-Net + openWakeWord | Custom voice training + reliable fallback |
| STT | OpenAI GPT-4o-transcribe | Best French accuracy available |
| TTS | OpenAI TTS | Natural, expressive voice |
| LLM | OpenAI GPT-4o-mini | Fast, cheap, smart enough for intents |
| Music | Spotipy + Spotify Connect | Direct hi-fi streaming to speakers |
| Video | yt-dlp + VLC + deno (JS solver) | Reliable YouTube extraction + playback |
| Weather | Open-Meteo | Free, no API key, accurate |
| Cameras | UniFi Protect REST API | Local network, no cloud dependency |
| Audio routing | PipeWire + RAOP (AirPlay) | Wireless hi-fi to any AirPlay speaker |
| Display | Chromium kiosk (Wayland) | Fullscreen, touch-optimized |

## Development

### Dev on Mac, Deploy to Pi

```bash
# On your Mac — edit code, build frontend, then deploy
./scripts/deploy-pi.sh

# On the Pi — restart the service
sudo systemctl restart piboard-backend
```

> **Note:** Node.js/npm are NOT installed on the Pi. Always build frontends on your Mac.

### Running Locally (Mac)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..
cd backend && uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Audio capture and wake word detection run in mock mode on macOS.

## Troubleshooting

**No audio on speakers:**
```bash
pactl list sinks short          # Check AirPlay sink is visible
wpctl status                    # PipeWire/WirePlumber status
```

**Spotify won't connect:**
- Spotify Premium required
- `SPOTIFY_DEVICE_NAME` must exactly match your speaker name in the Spotify app
- If disconnected, the Music page shows a "Reconnect" button for OAuth re-auth
- Register `http://localhost:8000/api/spotify/callback` in your Spotify Developer Dashboard

**YouTube videos won't play:**
- YouTube blocks unauthenticated requests — install cookies via Admin > YouTube
- Export cookies from a browser logged into YouTube (use "Get cookies.txt LOCALLY" extension)
- `deno` is required for yt-dlp's JS solver: `curl -fsSL https://deno.land/install.sh | sh`
- Check logs: `journalctl -u piboard-backend -f`

**Wake word not triggering:**
- Check microphone levels in the admin panel
- Lower the threshold or re-record wake word samples

**Screen control:**
```bash
cat /sys/class/backlight/10-0045/brightness      # Read current
echo 255 | sudo tee /sys/class/backlight/10-0045/brightness  # Max
echo 0 | sudo tee /sys/class/backlight/10-0045/brightness    # Off
```

## Contributing

Contributions welcome! Fork, branch, PR.

Ideas:
- Multi-language support (English, Spanish, Creole)
- Home Assistant / MQTT integration
- Alarm clock and timers
- Radio/podcast streaming
- Better wake word models

## Credits

- Built by **Anthony D.** in Guadeloupe
- Powered by [FastAPI](https://fastapi.tiangolo.com/), [Svelte](https://svelte.dev/), [Spotipy](https://spotipy.readthedocs.io/), [yt-dlp](https://github.com/yt-dlp/yt-dlp), [openWakeWord](https://github.com/dscripka/openWakeWord)
- Weather by [Open-Meteo](https://open-meteo.com/) | Speech by [OpenAI](https://openai.com/)

## License

MIT License — see [LICENSE](LICENSE).

---

<p align="center">
  Made with care in Guadeloupe
  <br>
  <em>Un projet du soleil pour votre maison</em>
</p>
