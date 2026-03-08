
<p align="center">

```
 _____ _  _____ ____
| ____| |/ /_ _|  _ \
|  _| | ' / | || |_) |
| |___| . \ | ||  __/
|_____|_|\_\___|_|       ASSISTANT
```

**A DIY voice-controlled smart display built on Raspberry Pi**

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

Ekip Assistant is a **privacy-friendly, open-source alternative to Amazon Echo Show**. Built on a Raspberry Pi 4 with a 7" touchscreen, it responds to your voice and your touch. No cloud lock-in for core functionality — only targeted API calls for speech recognition, music, and weather.

Born in **Guadeloupe**, built with love, and designed to run 24/7 on your nightstand or kitchen counter.

## Features

- **Custom wake word** — Train a wake word on YOUR voice using EfficientWord-Net (fallback: openWakeWord)
- **Voice commands in French** — "Hey Ekip, mets du jazz" and it plays jazz on your speakers
- **4-page swipe interface** — Music, Weather, YouTube, Security Cameras
- **Spotify Connect** — Streams music directly to high-end speakers (Devialet, Sonos, etc.)
- **Weather forecasts** — Current conditions and 3-day forecast via Open-Meteo
- **YouTube playback** — Voice or touch search, plays via VLC with audio routed to your speakers
- **Security cameras** — Live snapshots from UniFi Protect cameras on your local network
- **Web admin panel** — Configure everything from your phone or laptop browser
- **Dark theme** — Optimized for always-on displays, easy on the eyes at night
- **Auto sleep/wake** — Screen dims at 22h, wakes at 6h, night volume mode from 20h
- **Speech-to-Text** — OpenAI GPT-4o-transcribe for accurate French transcription
- **Text-to-Speech** — OpenAI TTS for natural voice responses
- **Smart audio ducking** — Music volume drops when the assistant speaks, then restores

## Screenshots

| Music | Weather | YouTube |
|:-----:|:-------:|:-------:|
| ![Music](docs/screenshots/music.png) | ![Weather](docs/screenshots/weather.png) | ![YouTube](docs/screenshots/youtube.png) |

## Architecture

```
Chromium Kiosk (fullscreen, port 8000)
  +-- Svelte SPA <--> WebSocket <--> FastAPI Backend
       |
       +-- AudioCapture (USB mic, 44.1kHz -> 16kHz resampling)
       |    +-- WakeWordDetector (EfficientWord-Net / openWakeWord)
       |         +-- STT (OpenAI GPT-4o-transcribe)
       |              +-- IntentRouter (keyword matching + LLM fallback)
       |                   +-- MusicController (Spotify Connect)
       |                   +-- WeatherService (Open-Meteo)
       |                   +-- YouTubeController (yt-dlp + VLC)
       |                   +-- CameraService (UniFi Protect)
       |                   +-- LLMHandler -> TTS -> PipeWire -> AirPlay
       |
       +-- Admin Panel (/admin)
            +-- Wake word training, config, system monitoring
```

### Voice Pipeline Flow

1. USB microphone captures audio continuously (44.1kHz, resampled to 16kHz)
2. Wake word detector listens for your custom hotword
3. On detection, music is ducked and 8 seconds of audio is captured
4. Audio is sent to OpenAI GPT-4o-transcribe for French STT
5. Intent router matches keywords (zero cost) or falls back to LLM
6. The matched handler executes the action (play music, read weather, etc.)
7. TTS response is generated and played through PipeWire to your speakers
8. System returns to idle, wake word detection resumes after cooldown

## Hardware Requirements

| Component | Model | Notes |
|-----------|-------|-------|
| **SBC** | Raspberry Pi 4 (4GB RAM) | ARM64, Raspberry Pi OS Bookworm 64-bit |
| **Display** | Raspberry Pi Touch Display 2 (7") | 720x1280, capacitive, DSI connector |
| **Microphone** | ReSpeaker Lite USB 2-Mic Array | Or any USB microphone |
| **Speakers** | Devialet / Sonos / any AirPlay speaker | Spotify Connect + AirPlay via PipeWire |
| **Storage** | microSD 32GB+ (class A2 recommended) | |
| **Network** | WiFi or Ethernet | Pi and speakers on same LAN |

> **Note:** The Pi does NOT play audio directly. Spotify streams go from Spotify servers directly to your speakers via Spotify Connect. TTS and YouTube audio route through PipeWire to AirPlay.

## Quick Start

### Prerequisites

- Raspberry Pi 4 with Raspberry Pi OS Bookworm (64-bit)
- A USB microphone
- Spotify Connect-compatible speakers on your network
- API keys (see [Configuration](#configuration))

### 1. Clone and Install

```bash
git clone https://github.com/YOUR_USERNAME/ekip-assistant.git
cd ekip-assistant
chmod +x scripts/*.sh
./scripts/setup.sh
```

This will install all system dependencies, create a Python virtual environment, install Python packages, and build the frontend.

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

This starts the FastAPI backend on port 8000 and opens Chromium in kiosk mode.

### 4. (Optional) Auto-start on Boot

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
OPENAI_API_KEY=sk-...              # openai.com — used for STT, TTS, and LLM

# Spotify
SPOTIFY_CLIENT_ID=...              # developer.spotify.com
SPOTIFY_CLIENT_SECRET=...
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
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
FRONTEND_PORT=3000
```

### Getting API Keys

| Service | Where to get it | Cost |
|---------|----------------|------|
| **OpenAI** | [platform.openai.com](https://platform.openai.com) | Pay-as-you-go (minimal for voice assistant use) |
| **Spotify** | [developer.spotify.com](https://developer.spotify.com) | Free (requires Spotify Premium for playback) |
| **UniFi Protect** | Local UniFi Cloud Key | Free (requires UniFi hardware) |

> Open-Meteo is used for weather and requires no API key.

## Project Structure

```
ekip-assistant/
+-- backend/
|   +-- main.py                  # FastAPI app, WebSocket, voice pipeline
|   +-- config.py                # Environment variables and constants
|   +-- audio/
|   |   +-- capture.py           # USB microphone audio stream (PyAudio)
|   |   +-- wakeword.py          # Wake word detection (EfficientWord-Net + openWakeWord)
|   |   +-- output.py            # PipeWire audio output
|   |   +-- models/              # Wake word ONNX models
|   |   +-- hotword_refs/        # Custom wake word reference files
|   +-- services/
|   |   +-- stt.py               # Speech-to-Text (OpenAI GPT-4o-transcribe)
|   |   +-- tts.py               # Text-to-Speech (OpenAI TTS)
|   |   +-- llm.py               # LLM for complex intents (GPT-4o-mini)
|   |   +-- spotify.py           # Spotify Web API (Spotipy)
|   |   +-- weather.py           # Weather data (Open-Meteo)
|   |   +-- youtube.py           # YouTube search + VLC playback (yt-dlp)
|   |   +-- cameras.py           # UniFi Protect camera snapshots
|   +-- intent/
|   |   +-- router.py            # Intent classification (keyword + LLM fallback)
|   +-- admin/
|       +-- routes.py            # Admin panel API routes
|       +-- auth.py              # Admin authentication
|       +-- config_manager.py    # Runtime configuration
|       +-- static/              # Admin panel built frontend
+-- frontend/
|   +-- src/
|   |   +-- App.svelte           # Main app with swipe navigation
|   |   +-- pages/
|   |   |   +-- Music.svelte     # Spotify player UI
|   |   |   +-- Weather.svelte   # Weather display
|   |   |   +-- YouTube.svelte   # YouTube search and player
|   |   |   +-- Cameras.svelte   # Security camera grid
|   |   +-- components/
|   |   |   +-- WaveAnimation.svelte    # Voice listening animation
|   |   |   +-- VirtualKeyboard.svelte  # On-screen keyboard
|   |   +-- stores/
|   |       +-- assistant.js     # Svelte store (global state)
|   +-- admin/                   # Admin panel (separate Svelte app)
|       +-- src/pages/           # Dashboard, Voice, Audio, Music, etc.
+-- scripts/
|   +-- setup.sh                 # Full installation script
|   +-- start.sh                 # Launch backend + Chromium kiosk
|   +-- deploy-pi.sh             # Deploy from dev machine to Pi via scp
|   +-- record_wakeword.py       # Record wake word samples for training
|   +-- test_audio.sh            # Verify microphone and PipeWire setup
+-- systemd/
|   +-- piboard-backend.service  # Systemd service for the backend
|   +-- piboard-kiosk.service    # Systemd service for Chromium kiosk
+-- requirements.txt             # Python dependencies
+-- LICENSE                      # MIT License
```

## Voice Commands

Ekip Assistant understands French voice commands. Here are some examples:

| Command | What it does |
|---------|-------------|
| *"Hey Ekip, mets du jazz"* | Searches and plays jazz on Spotify |
| *"Hey Ekip, joue Stromae"* | Plays Stromae on your speakers |
| *"Hey Ekip, pause"* | Pauses the current track |
| *"Hey Ekip, suivant"* | Skips to the next track |
| *"Hey Ekip, plus fort"* | Increases volume |
| *"Hey Ekip, moins fort"* | Decreases volume |
| *"Hey Ekip, meteo"* | Reads the weather forecast aloud and switches to the weather page |
| *"Hey Ekip, YouTube Stromae"* | Searches YouTube and plays the top result via VLC |
| *"Hey Ekip, stop video"* | Stops YouTube playback |
| *"Hey Ekip, dodo"* | Turns off the screen (sleep mode) |
| *"Hey Ekip, debout"* | Turns the screen back on |
| *"Hey Ekip, c'est quoi la capitale du Japon?"* | General question answered by the LLM |

> **Tip:** The wake word is customizable. You can train your own using the admin panel or the `scripts/record_wakeword.py` script.

## Touch Controls

- **Swipe up/down** to navigate between pages (Music -> Weather -> YouTube -> Cameras)
- **Tap** play/pause, next/previous on the Music page
- **Volume slider** on the Music page
- **Search bar** on YouTube page with virtual keyboard
- **Tap** a camera to view its snapshot

## Admin Panel

Access the admin panel at `http://your-pi-ip:8000/admin` from any device on your network.

Features:
- **Dashboard** — System status, service health, uptime
- **Voice** — Wake word training (record samples, test detection)
- **Audio** — Microphone levels, PipeWire sink selection
- **Music** — Spotify connection status, device selection
- **Weather** — Location settings
- **YouTube** — Playback settings
- **Cameras** — UniFi Protect configuration
- **Screen** — Brightness, sleep schedule
- **System** — Logs, restart services
- **Interface** — UI customization

## Development

### Dev on Mac, Deploy to Pi

The recommended workflow is to develop on your Mac and deploy to the Pi:

```bash
# On your Mac — edit code, then deploy
./scripts/deploy-pi.sh

# On the Pi — restart the service
sudo systemctl restart piboard-backend
```

> **Note:** Node.js and npm are NOT installed on the Pi. Always build the frontend on your Mac before deploying.

### Running Locally (Mac)

The backend can run on macOS for development, but audio capture and wake word detection require mocking since there is no ReSpeaker or PipeWire:

```bash
# Create venv and install deps
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Build frontend
cd frontend && npm install && npm run build && cd ..

# Run backend (will start in mock mode for audio)
cd backend && uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI, asyncio, WebSocket |
| Frontend | Svelte 4, Vite 5 |
| Audio capture | PyAudio, numpy, scipy (resampling) |
| Wake word | EfficientWord-Net (custom) + openWakeWord (fallback) |
| Speech-to-Text | OpenAI GPT-4o-transcribe |
| Text-to-Speech | OpenAI TTS |
| LLM | OpenAI GPT-4o-mini (intent fallback + general questions) |
| Music | Spotipy (Spotify Web API + Spotify Connect) |
| Video | yt-dlp + VLC |
| Weather | Open-Meteo (free, no API key) |
| Cameras | UniFi Protect REST API |
| Audio routing | PipeWire + RAOP (AirPlay) |
| Display | Chromium in kiosk mode (Wayland) |

## Troubleshooting

### Common Issues

**Microphone not detected:**
```bash
arecord -l                         # List ALSA capture devices
pactl list sources | grep -i name  # List PipeWire sources
```

**No audio output to speakers:**
```bash
pactl list sinks | grep -i devialet  # Check if AirPlay sink is visible
wpctl status                          # Check PipeWire/WirePlumber status
```

**Spotify not connecting:**
- Make sure you have Spotify Premium
- Check that `SPOTIFY_DEVICE_NAME` in `.env` exactly matches your speaker name in the Spotify app
- Run the backend once manually to complete the OAuth flow

**Wake word not triggering:**
- Check microphone levels in the admin panel
- Try lowering the threshold in `backend/audio/wakeword.py`
- Re-record wake word samples using the admin panel

**Screen not turning on/off:**
```bash
# Check backlight control
cat /sys/class/backlight/10-0045/brightness
echo 255 | sudo tee /sys/class/backlight/10-0045/brightness  # Turn on
echo 0 | sudo tee /sys/class/backlight/10-0045/brightness    # Turn off
```

## Contributing

Contributions are welcome! This is a passion project, and there is always room for improvement.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -m 'Add my feature'`)
4. Push to the branch (`git push origin feature/my-feature`)
5. Open a Pull Request

### Ideas for Contributions

- Multi-language voice command support (English, Spanish, Creole)
- Home automation integration (Home Assistant, MQTT)
- Calendar and reminders page
- Alarm clock functionality
- Radio/podcast streaming
- Gesture recognition via camera
- Better wake word models

## Credits

- Built by **Anthony D.** in Guadeloupe
- Powered by [FastAPI](https://fastapi.tiangolo.com/), [Svelte](https://svelte.dev/), [Spotipy](https://spotipy.readthedocs.io/), [yt-dlp](https://github.com/yt-dlp/yt-dlp), [EfficientWord-Net](https://github.com/Ant-Brain/EfficientWord-Net), [openWakeWord](https://github.com/dscripka/openWakeWord)
- Weather data from [Open-Meteo](https://open-meteo.com/)
- Speech services by [OpenAI](https://openai.com/)

## License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  Made with care in Guadeloupe
  <br>
  <em>Un projet du soleil pour votre maison</em>
</p>
