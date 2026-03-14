import os
from dotenv import load_dotenv

load_dotenv()

# Serveur
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8000"))
FRONTEND_PORT = int(os.getenv("FRONTEND_PORT", "3000"))

# Audio
RESPEAKER_DEVICE = os.getenv("RESPEAKER_DEVICE", "hw:ReSpeaker,0")
PIPEWIRE_AIRPLAY_SINK = os.getenv("PIPEWIRE_AIRPLAY_SINK", "Devialet")

# APIs
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")  # LLM (gpt-4o-mini) + TTS

# Spotify
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")
SPOTIFY_DEVICE_NAME = os.getenv("SPOTIFY_DEVICE_NAME", "Devialet")

# Meteo (Open-Meteo = gratuit, pas de cle)
WEATHER_CITY = os.getenv("WEATHER_CITY", "Guadeloupe")
WEATHER_LAT = float(os.getenv("WEATHER_LAT", "16.25"))
WEATHER_LON = float(os.getenv("WEATHER_LON", "-61.58"))

# UniFi Protect (cameras)
UNIFI_HOST = os.getenv("UNIFI_HOST", "192.168.1.18")
UNIFI_USER = os.getenv("UNIFI_USER", "")
UNIFI_PASS = os.getenv("UNIFI_PASS", "")

# Devialet IP Control
DEVIALET_IP = os.getenv("DEVIALET_IP", "192.168.1.106")

# Chemins
FRONTEND_BUILD_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
