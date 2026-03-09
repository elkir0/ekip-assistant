
<p align="center">

```
 ____  _ ____                      _
|  _ \(_) __ )  ___   __ _ _ __ __| |
| |_) | |  _ \ / _ \ / _` | '__/ _` |
|  __/| | |_) | (_) | (_| | | | (_| |
|_|   |_|____/ \___/ \__,_|_|  \__,_|
```

**Tu hogar merece una voz. Construyela tu mismo.**

</p>

<p align="center">
  <a href="#"><img alt="Licencia: MIT" src="https://img.shields.io/badge/licencia-MIT-blue.svg"></a>
  <a href="#"><img alt="Python 3.11" src="https://img.shields.io/badge/python-3.11-3776AB.svg"></a>
  <a href="#"><img alt="Svelte 4" src="https://img.shields.io/badge/svelte-4-FF3E00.svg"></a>
  <a href="#"><img alt="Raspberry Pi 4" src="https://img.shields.io/badge/raspberry%20pi-4-C51A4A.svg"></a>
  <a href="#"><img alt="FastAPI" src="https://img.shields.io/badge/fastapi-0.115-009688.svg"></a>
</p>

<p align="center">
  <a href="README.md">English</a> |
  <a href="README_FR.md">Francais</a> |
  <strong>Espanol</strong>
</p>

---

**Piboard** es una pantalla inteligente open-source que convierte un Raspberry Pi en un asistente de voz completo para el hogar. Piensa en Amazon Echo Show — pero uno que tu posees, comprendes y personalizas como quieras.

Di *"Hey Piboard, mets du jazz"* y reproduce jazz en tu Devialet. Pregunta por el clima y lo lee en voz alta mientras cambia a la pagina del clima. Pidele que ponga un video de YouTube y lo transmite en pantalla completa con el audio enviado de forma inalambrica a tus altavoces via AirPlay.

Sin suscripcion. Sin dependencia de la nube. Solo un Pi, una pantalla y tu voz.

Nacido en **Guadalupe**, disenado para funcionar 24/7 en tu mesita de noche o encimera de cocina.

## Por que Piboard?

- **Audio hi-fi inalambrico** — La musica y los videos envian el audio a cualquier altavoz AirPlay o Spotify Connect (Devialet, Sonos, HomePod, etc.) via el sink RAOP de PipeWire. El Pi nunca toca el audio — tus altavoces se encargan.
- **Integracion Spotify Connect** — Busqueda por voz, control de reproduccion, navegacion de playlists. El audio va directamente de los servidores de Spotify a tu altavoz — cero perdida de calidad.
- **YouTube en tus altavoces** — Busqueda por voz o tacto, reproduccion VLC en pantalla completa, audio dirigido a tus altavoces hi-fi via AirPlay. Cola de reproduccion con encadenamiento automatico.
- **Interaccion de voz real** — Palabra de activacion entrenada con TU voz. Transcripcion OpenAI, respuestas TTS naturales, ducking de audio que baja la musica cuando el asistente habla.
- **Interfaz tactil de 4 paginas** — Desliza entre Musica, Clima, YouTube y Camaras. Tema oscuro optimizado para pantallas de 7" siempre encendidas.
- **Camaras de seguridad** — Capturas en vivo de tus camaras UniFi Protect en tu mesita de noche.
- **Panel de admin completo** — Configura todo desde tu telefono: sensibilidad del micro, enrutamiento de audio, Spotify, cookies de YouTube, programacion de pantalla, y mas.
- **Suspension inteligente** — Pantalla apagada a las 22h, encendida a las 6h. Volumen nocturno desde las 20h. Brillo adaptativo.
- **100% open source** — Licencia MIT, sin firmware propietario, sin dependencia del fabricante.

## Capturas de pantalla

| Musica | Clima | YouTube |
|:------:|:-----:|:-------:|
| ![Musica](docs/screenshots/music.png) | ![Clima](docs/screenshots/weather.png) | ![YouTube](docs/screenshots/youtube.png) |

## Como funciona

```
Raspberry Pi 4 + Pantalla tactil 7"
  |
  +-- Chromium Kiosk (app Svelte en pantalla completa)
  |    +-- WebSocket <--> Backend FastAPI
  |
  +-- Microfono USB (ReSpeaker 2-Mic Array)
  |    +-- Deteccion de palabra de activacion (EfficientWord-Net / openWakeWord)
  |    +-- Speech-to-Text (OpenAI GPT-4o-transcribe)
  |    +-- Enrutador de intents (palabras clave, costo cero para comandos comunes)
  |         |
  |         +-- "mets du jazz"       --> API Spotify --> Devialet (Spotify Connect)
  |         +-- "meteo demain"       --> Open-Meteo --> TTS --> AirPlay --> Altavoz
  |         +-- "YouTube Stromae"    --> yt-dlp --> VLC --> AirPlay --> Altavoz
  |         +-- "montre les cameras" --> UniFi Protect --> Capturas en vivo
  |         +-- cualquier pregunta   --> LLM (GPT-4o-mini) --> TTS --> Altavoz
  |
  +-- Motor de audio PipeWire
       +-- Sink RAOP (AirPlay) --> Devialet / Sonos / HomePod
       +-- Spotify Connect (flujo directo, el Pi no esta en la ruta del audio)
```

### Arquitectura de audio

Esto es lo que hace especial a Piboard:

| Fuente | Ruta | Calidad |
|--------|------|---------|
| **Spotify** | Servidores Spotify --> Spotify Connect --> tu altavoz | Sin perdida (OGG 320kbps) |
| **Video YouTube** | yt-dlp --> VLC --> PipeWire --> AirPlay (RAOP) --> tu altavoz | Hasta 720p video + audio AAC |
| **Respuestas de voz** | OpenAI TTS --> PipeWire --> AirPlay --> tu altavoz | Voz natural |
| **Ducking** | Volumen de Spotify bajado via API mientras TTS habla, luego restaurado | Transparente |

El Pi actua como un **controlador y enrutador**, nunca como un DAC. Tus altavoces reciben la mejor calidad de audio posible.

## Requisitos de hardware

| Componente | Modelo | Notas |
|------------|--------|-------|
| **SBC** | Raspberry Pi 4 (4 GB RAM) | ARM64, Raspberry Pi OS Bookworm 64-bit |
| **Pantalla** | Raspberry Pi Touch Display 2 (7") | 720x1280, capacitiva, conector DSI |
| **Microfono** | ReSpeaker Lite USB 2-Mic Array | AEC por hardware, o cualquier micro USB |
| **Altavoces** | Cualquier altavoz AirPlay o Spotify Connect | Devialet, Sonos, HomePod, etc. |
| **Almacenamiento** | microSD 32 GB+ (clase A2 recomendada) | |
| **Red** | WiFi o Ethernet | Pi y altavoces en la misma LAN |

**Costo total:** ~120 USD (Pi + pantalla + micro), mas los altavoces que ya tengas.

## Inicio rapido

### 1. Clonar e instalar

```bash
git clone https://github.com/elkir0/ekip-assistant.git piboard
cd piboard
chmod +x scripts/*.sh
./scripts/setup.sh
```

### 2. Configurar

```bash
cp .env.example .env
nano .env
```

Rellena tus claves API (ver [Configuracion](#configuracion) mas abajo).

### 3. Ejecutar

```bash
./scripts/start.sh
```

El backend inicia en el puerto 8000, Chromium se abre en modo kiosco. Listo.

### 4. Inicio automatico al arrancar

```bash
sudo cp systemd/piboard-backend.service /etc/systemd/system/
sudo cp systemd/piboard-kiosk.service /etc/systemd/system/
sudo systemctl enable piboard-backend piboard-kiosk
sudo systemctl start piboard-backend piboard-kiosk
```

## Configuracion

Crea un archivo `.env` desde el ejemplo:

```bash
# Speech-to-Text + Text-to-Speech + LLM
OPENAI_API_KEY=sk-...              # openai.com — STT, TTS y LLM

# Spotify
SPOTIFY_CLIENT_ID=...              # developer.spotify.com
SPOTIFY_CLIENT_SECRET=...
SPOTIFY_REDIRECT_URI=http://localhost:8000/api/spotify/callback
SPOTIFY_DEVICE_NAME=Devialet       # Nombre exacto de tu altavoz Spotify Connect

# Clima (Open-Meteo es gratuito, sin clave)
WEATHER_CITY=Guadeloupe
WEATHER_LAT=16.25
WEATHER_LON=-61.58

# UniFi Protect (opcional — camaras de seguridad)
UNIFI_HOST=192.168.1.18
UNIFI_USER=admin
UNIFI_PASS=...

# Audio
PIPEWIRE_AIRPLAY_SINK=Devialet     # Nombre de tu sink AirPlay PipeWire
RESPEAKER_DEVICE=hw:ReSpeaker,0    # Dispositivo ALSA del micro USB

# Servidor
BACKEND_PORT=8000
```

### Claves API

| Servicio | Donde obtenerla | Costo |
|----------|----------------|-------|
| **OpenAI** | [platform.openai.com](https://platform.openai.com) | Pago por uso (~$0.01/dia para asistente de voz) |
| **Spotify** | [developer.spotify.com](https://developer.spotify.com) | Gratis (Spotify Premium requerido para reproduccion) |
| **Open-Meteo** | Sin clave necesaria | Gratis |
| **UniFi Protect** | Cloud Key UniFi local | Gratis (hardware UniFi requerido) |

## Comandos de voz

Piboard entiende comandos de voz en frances:

| Comando | Que hace |
|---------|----------|
| *"Hey Piboard, mets du jazz"* | Busca y reproduce jazz en Spotify via tus altavoces |
| *"Hey Piboard, joue Stromae"* | Reproduce Stromae en Spotify Connect |
| *"Hey Piboard, pause"* | Pausa la cancion actual |
| *"Hey Piboard, suivant"* | Salta a la siguiente cancion |
| *"Hey Piboard, plus fort"* | Sube el volumen en tus altavoces |
| *"Hey Piboard, moins fort"* | Baja el volumen |
| *"Hey Piboard, meteo"* | Lee el clima en voz alta y muestra la pagina del clima |
| *"Hey Piboard, mets la video Stromae"* | Busca en YouTube, reproduce en pantalla completa con audio en tus altavoces |
| *"Hey Piboard, stop video"* | Detiene YouTube, reanuda Spotify |
| *"Hey Piboard, dodo"* | Apaga la pantalla (modo suspension) |
| *"Hey Piboard, debout"* | Enciende la pantalla |
| *"Hey Piboard, c'est quoi la capitale du Japon?"* | Pregunta general respondida por LLM |

> La palabra de activacion es personalizable. Entrena la tuya via el panel admin o `scripts/record_wakeword.py`.

## Stack tecnico

| Capa | Tecnologia | Por que |
|------|-----------|---------|
| Backend | Python 3.11, FastAPI, asyncio | Todo async, WebSocket en tiempo real |
| Frontend | Svelte 4, Vite 5 | Rapido, ligero, perfecto para embebido |
| Captura de audio | PyAudio + remuestreo scipy | Micro USB 44.1kHz -> 16kHz para STT |
| Palabra de activacion | EfficientWord-Net + openWakeWord | Entrenamiento vocal + fallback confiable |
| STT | OpenAI GPT-4o-transcribe | Mejor precision en frances |
| TTS | OpenAI TTS | Voz natural y expresiva |
| LLM | OpenAI GPT-4o-mini | Rapido, economico, inteligente para intents |
| Musica | Spotipy + Spotify Connect | Streaming hi-fi directo a altavoces |
| Video | yt-dlp + VLC + deno (solver JS) | Extraccion YouTube confiable + reproduccion |
| Clima | Open-Meteo | Gratuito, sin clave, preciso |
| Camaras | API REST UniFi Protect | Red local, sin dependencia cloud |
| Enrutamiento de audio | PipeWire + RAOP (AirPlay) | Hi-fi inalambrico a cualquier altavoz AirPlay |
| Pantalla | Chromium kiosco (Wayland) | Pantalla completa, optimizado para tacto |

## Solucion de problemas

**Sin audio en los altavoces:**
```bash
pactl list sinks short          # Verificar que el sink AirPlay es visible
wpctl status                    # Estado PipeWire/WirePlumber
```

**Spotify no se conecta:**
- Spotify Premium requerido
- `SPOTIFY_DEVICE_NAME` debe coincidir exactamente con el nombre en la app de Spotify
- Si se desconecta, la pagina de Musica muestra un boton "Reconectar" para re-autenticacion OAuth
- Registra `http://localhost:8000/api/spotify/callback` en tu Spotify Developer Dashboard

**Los videos de YouTube no se reproducen:**
- YouTube bloquea solicitudes no autenticadas — instala cookies via Admin > YouTube
- Exporta cookies desde un navegador conectado a YouTube (extension "Get cookies.txt LOCALLY")
- `deno` es requerido para el solver JS de yt-dlp: `curl -fsSL https://deno.land/install.sh | sh`
- Revisa logs: `journalctl -u piboard-backend -f`

**La palabra de activacion no se activa:**
- Verifica los niveles del micro en el panel admin
- Baja el umbral o vuelve a grabar muestras

**Control de pantalla:**
```bash
cat /sys/class/backlight/10-0045/brightness      # Leer valor actual
echo 255 | sudo tee /sys/class/backlight/10-0045/brightness  # Max
echo 0 | sudo tee /sys/class/backlight/10-0045/brightness    # Apagado
```

## Contribuir

Las contribuciones son bienvenidas! Fork, branch, PR.

Ideas:
- Soporte multilenguaje (ingles, espanol, criollo)
- Integracion Home Assistant / MQTT
- Despertador y temporizadores
- Streaming de radio/podcast
- Mejores modelos de palabra de activacion

## Creditos

- Construido por **Anthony D.** en Guadalupe
- Impulsado por [FastAPI](https://fastapi.tiangolo.com/), [Svelte](https://svelte.dev/), [Spotipy](https://spotipy.readthedocs.io/), [yt-dlp](https://github.com/yt-dlp/yt-dlp), [openWakeWord](https://github.com/dscripka/openWakeWord)
- Clima por [Open-Meteo](https://open-meteo.com/) | Voz por [OpenAI](https://openai.com/)

## Licencia

Licencia MIT — consulta [LICENSE](LICENSE).

---

<p align="center">
  Hecho con cuidado en Guadalupe
  <br>
  <em>Un proyecto del sol para tu hogar</em>
</p>
