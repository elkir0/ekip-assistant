
<p align="center">

```
 _____ _  _____ ____
| ____| |/ /_ _|  _ \
|  _| | ' / | || |_) |
| |___| . \ | ||  __/
|_____|_|\_\___|_|       ASSISTANT
```

**Una pantalla inteligente DIY controlada por voz, construida con Raspberry Pi**

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

Ekip Assistant es una **alternativa open-source y respetuosa con la privacidad al Amazon Echo Show**. Construido sobre un Raspberry Pi 4 con pantalla tactil de 7", responde a tu voz y a tus gestos. Sin dependencia de la nube para las funcionalidades basicas — solo llamadas API puntuales para reconocimiento de voz, musica y clima.

Nacido en **Guadalupe**, construido con pasion, y disenado para funcionar 24/7 en tu mesita de noche o encimera de cocina.

## Caracteristicas

- **Palabra de activacion personalizada** — Entrena una palabra de activacion con TU voz usando EfficientWord-Net (fallback: openWakeWord)
- **Comandos de voz en frances** — "Hey Ekip, mets du jazz" y reproduce jazz en tus altavoces
- **Interfaz de 4 paginas con swipe** — Musica, Clima, YouTube, Camaras de seguridad
- **Integracion Spotify Connect** — Transmite musica directamente a altavoces de alta gama (Devialet, Sonos, etc.)
- **Pronostico del clima** — Condiciones actuales y pronostico de 3 dias via Open-Meteo
- **Reproduccion de YouTube** — Busqueda por voz o tacto, reproduccion via VLC con audio dirigido a tus altavoces
- **Camaras de seguridad** — Capturas en vivo de camaras UniFi Protect en tu red local
- **Panel de administracion web** — Configura todo desde tu telefono o navegador
- **Tema oscuro** — Optimizado para pantallas siempre encendidas, comodo para los ojos de noche
- **Suspension/activacion automatica** — La pantalla se apaga a las 22h, se enciende a las 6h, modo nocturno desde las 20h
- **Speech-to-Text** — OpenAI GPT-4o-transcribe para transcripcion precisa en frances
- **Text-to-Speech** — OpenAI TTS para respuestas de voz naturales
- **Ducking de audio inteligente** — El volumen de la musica baja cuando el asistente habla, y luego se restaura

## Capturas de pantalla

| Musica | Clima | YouTube |
|:------:|:-----:|:-------:|
| ![Musica](docs/screenshots/music.png) | ![Clima](docs/screenshots/weather.png) | ![YouTube](docs/screenshots/youtube.png) |

## Arquitectura

```
Chromium Kiosk (pantalla completa, puerto 8000)
  +-- Svelte SPA <--> WebSocket <--> Backend FastAPI
       |
       +-- AudioCapture (micro USB, 44.1kHz -> 16kHz resampling)
       |    +-- WakeWordDetector (EfficientWord-Net / openWakeWord)
       |         +-- STT (OpenAI GPT-4o-transcribe)
       |              +-- IntentRouter (palabras clave + fallback LLM)
       |                   +-- MusicController (Spotify Connect)
       |                   +-- WeatherService (Open-Meteo)
       |                   +-- YouTubeController (yt-dlp + VLC)
       |                   +-- CameraService (UniFi Protect)
       |                   +-- LLMHandler -> TTS -> PipeWire -> AirPlay
       |
       +-- Panel Admin (/admin)
            +-- Entrenamiento de palabra de activacion, config, monitoreo del sistema
```

### Flujo del pipeline de voz

1. El microfono USB captura audio continuamente (44.1kHz, remuestreado a 16kHz)
2. El detector de palabra de activacion escucha tu hotword personalizado
3. Al detectarlo, la musica baja de volumen y se capturan 8 segundos de audio
4. El audio se envia a OpenAI GPT-4o-transcribe para la transcripcion en frances
5. El enrutador de intents hace coincidencia por palabras clave (costo cero) o usa el LLM como fallback
6. El handler correspondiente ejecuta la accion (reproducir musica, leer el clima, etc.)
7. La respuesta TTS se genera y se reproduce via PipeWire hacia tus altavoces
8. El sistema vuelve a modo inactivo, la deteccion de palabra de activacion se reanuda tras un cooldown

## Requisitos de hardware

| Componente | Modelo | Notas |
|------------|--------|-------|
| **SBC** | Raspberry Pi 4 (4 GB RAM) | ARM64, Raspberry Pi OS Bookworm 64-bit |
| **Pantalla** | Raspberry Pi Touch Display 2 (7") | 720x1280, capacitiva, conector DSI |
| **Microfono** | ReSpeaker Lite USB 2-Mic Array | O cualquier microfono USB |
| **Altavoces** | Devialet / Sonos / cualquier altavoz AirPlay | Spotify Connect + AirPlay via PipeWire |
| **Almacenamiento** | microSD 32 GB+ (clase A2 recomendada) | |
| **Red** | WiFi o Ethernet | Pi y altavoces en la misma LAN |

> **Nota:** El Pi NO reproduce audio directamente. Los flujos de Spotify van desde los servidores de Spotify directamente a tus altavoces via Spotify Connect. El TTS y el audio de YouTube se enrutan a traves de PipeWire hacia AirPlay.

## Inicio rapido

### Prerrequisitos

- Raspberry Pi 4 con Raspberry Pi OS Bookworm (64-bit)
- Un microfono USB
- Altavoces compatibles con Spotify Connect en tu red
- Claves API (ver [Configuracion](#configuracion))

### 1. Clonar e instalar

```bash
git clone https://github.com/YOUR_USERNAME/ekip-assistant.git
cd ekip-assistant
chmod +x scripts/*.sh
./scripts/setup.sh
```

Esto instala todas las dependencias del sistema, crea un entorno virtual Python, instala los paquetes Python y compila el frontend.

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

Esto inicia el backend FastAPI en el puerto 8000 y abre Chromium en modo kiosco.

### 4. (Opcional) Inicio automatico al arrancar

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
OPENAI_API_KEY=sk-...              # openai.com — usado para STT, TTS y LLM

# Spotify
SPOTIFY_CLIENT_ID=...              # developer.spotify.com
SPOTIFY_CLIENT_SECRET=...
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
SPOTIFY_DEVICE_NAME=Devialet       # Nombre exacto de tu altavoz Spotify Connect

# Clima (Open-Meteo es gratuito, no necesita clave)
WEATHER_CITY=Guadeloupe
WEATHER_LAT=16.25
WEATHER_LON=-61.58

# UniFi Protect (opcional — para camaras de seguridad)
UNIFI_HOST=192.168.1.18
UNIFI_USER=admin
UNIFI_PASS=...

# Audio
PIPEWIRE_AIRPLAY_SINK=Devialet     # Nombre de tu sink AirPlay PipeWire
RESPEAKER_DEVICE=hw:ReSpeaker,0    # Nombre del dispositivo ALSA de tu micro USB

# Servidor
BACKEND_PORT=8000
FRONTEND_PORT=3000
```

### Obtener claves API

| Servicio | Donde obtenerla | Costo |
|----------|----------------|-------|
| **OpenAI** | [platform.openai.com](https://platform.openai.com) | Pago por uso (minimo para un asistente de voz) |
| **Spotify** | [developer.spotify.com](https://developer.spotify.com) | Gratis (requiere Spotify Premium para la reproduccion) |
| **UniFi Protect** | Cloud Key UniFi local | Gratis (requiere hardware UniFi) |

> Open-Meteo se usa para el clima y no requiere clave API.

## Estructura del proyecto

```
ekip-assistant/
+-- backend/
|   +-- main.py                  # App FastAPI, WebSocket, pipeline de voz
|   +-- config.py                # Variables de entorno y constantes
|   +-- audio/
|   |   +-- capture.py           # Flujo audio micro USB (PyAudio)
|   |   +-- wakeword.py          # Deteccion de palabra de activacion (EfficientWord-Net + openWakeWord)
|   |   +-- output.py            # Salida de audio PipeWire
|   |   +-- models/              # Modelos ONNX de palabra de activacion
|   |   +-- hotword_refs/        # Archivos de referencia de palabra de activacion personalizada
|   +-- services/
|   |   +-- stt.py               # Speech-to-Text (OpenAI GPT-4o-transcribe)
|   |   +-- tts.py               # Text-to-Speech (OpenAI TTS)
|   |   +-- llm.py               # LLM para intents complejos (GPT-4o-mini)
|   |   +-- spotify.py           # API Web de Spotify (Spotipy)
|   |   +-- weather.py           # Datos meteorologicos (Open-Meteo)
|   |   +-- youtube.py           # Busqueda YouTube + reproduccion VLC (yt-dlp)
|   |   +-- cameras.py           # Capturas de camaras UniFi Protect
|   +-- intent/
|   |   +-- router.py            # Clasificacion de intents (palabras clave + fallback LLM)
|   +-- admin/
|       +-- routes.py            # Rutas API del panel admin
|       +-- auth.py              # Autenticacion admin
|       +-- config_manager.py    # Configuracion en tiempo real
|       +-- static/              # Frontend compilado del panel admin
+-- frontend/
|   +-- src/
|   |   +-- App.svelte           # App principal con navegacion swipe
|   |   +-- pages/
|   |   |   +-- Music.svelte     # Interfaz del reproductor Spotify
|   |   |   +-- Weather.svelte   # Visualizacion del clima
|   |   |   +-- YouTube.svelte   # Busqueda y reproductor YouTube
|   |   |   +-- Cameras.svelte   # Cuadricula de camaras de seguridad
|   |   +-- components/
|   |   |   +-- WaveAnimation.svelte    # Animacion de escucha por voz
|   |   |   +-- VirtualKeyboard.svelte  # Teclado virtual en pantalla
|   |   +-- stores/
|   |       +-- assistant.js     # Store Svelte (estado global)
|   +-- admin/                   # Panel admin (app Svelte separada)
|       +-- src/pages/           # Dashboard, Voice, Audio, Music, etc.
+-- scripts/
|   +-- setup.sh                 # Script de instalacion completa
|   +-- start.sh                 # Lanzar backend + Chromium kiosco
|   +-- deploy-pi.sh             # Desplegar desde la maquina de dev al Pi via scp
|   +-- record_wakeword.py       # Grabar muestras de palabra de activacion
|   +-- test_audio.sh            # Verificar microfono y PipeWire
+-- systemd/
|   +-- piboard-backend.service  # Servicio systemd para el backend
|   +-- piboard-kiosk.service    # Servicio systemd para Chromium kiosco
+-- requirements.txt             # Dependencias Python
+-- LICENSE                      # Licencia MIT
```

## Comandos de voz

Ekip Assistant entiende comandos de voz en frances. Aqui hay algunos ejemplos:

| Comando | Que hace |
|---------|----------|
| *"Hey Ekip, mets du jazz"* | Busca y reproduce jazz en Spotify |
| *"Hey Ekip, joue Stromae"* | Reproduce Stromae en tus altavoces |
| *"Hey Ekip, pause"* | Pausa la cancion actual |
| *"Hey Ekip, suivant"* | Salta a la siguiente cancion |
| *"Hey Ekip, plus fort"* | Sube el volumen |
| *"Hey Ekip, moins fort"* | Baja el volumen |
| *"Hey Ekip, meteo"* | Lee el pronostico del clima en voz alta y cambia a la pagina del clima |
| *"Hey Ekip, YouTube Stromae"* | Busca en YouTube y reproduce el primer resultado via VLC |
| *"Hey Ekip, stop video"* | Detiene la reproduccion de YouTube |
| *"Hey Ekip, dodo"* | Apaga la pantalla (modo suspension) |
| *"Hey Ekip, debout"* | Enciende la pantalla |
| *"Hey Ekip, c'est quoi la capitale du Japon ?"* | Pregunta general respondida por el LLM |

> **Consejo:** La palabra de activacion es personalizable. Puedes entrenar la tuya via el panel de administracion o el script `scripts/record_wakeword.py`.

## Controles tactiles

- **Desliza arriba/abajo** para navegar entre paginas (Musica -> Clima -> YouTube -> Camaras)
- **Toca** play/pausa, siguiente/anterior en la pagina de Musica
- **Control deslizante de volumen** en la pagina de Musica
- **Barra de busqueda** en la pagina de YouTube con teclado virtual
- **Toca** una camara para ver su captura

## Panel de administracion

Accede al panel de administracion en `http://ip-de-tu-pi:8000/admin` desde cualquier dispositivo en tu red.

Funcionalidades:
- **Dashboard** — Estado del sistema, salud de los servicios, tiempo de actividad
- **Voice** — Entrenamiento de palabra de activacion (grabar muestras, probar deteccion)
- **Audio** — Niveles del microfono, seleccion de sink PipeWire
- **Music** — Estado de conexion Spotify, seleccion de dispositivo
- **Weather** — Configuracion de ubicacion
- **YouTube** — Configuracion de reproduccion
- **Cameras** — Configuracion de UniFi Protect
- **Screen** — Brillo, programacion de suspension
- **System** — Logs, reinicio de servicios
- **Interface** — Personalizacion de la interfaz

## Desarrollo

### Desarrollar en Mac, desplegar en Pi

El flujo de trabajo recomendado es desarrollar en tu Mac y desplegar en el Pi:

```bash
# En tu Mac — editar el codigo, luego desplegar
./scripts/deploy-pi.sh

# En el Pi — reiniciar el servicio
sudo systemctl restart piboard-backend
```

> **Nota:** Node.js y npm NO estan instalados en el Pi. Siempre compila el frontend en tu Mac antes de desplegar.

### Ejecutar en local (Mac)

El backend puede ejecutarse en macOS para desarrollo, pero la captura de audio y la deteccion de palabra de activacion requieren mocking ya que no hay ReSpeaker ni PipeWire:

```bash
# Crear venv e instalar dependencias
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Compilar el frontend
cd frontend && npm install && npm run build && cd ..

# Ejecutar el backend (modo mock para audio)
cd backend && uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Stack tecnico

| Capa | Tecnologia |
|------|-----------|
| Backend | Python 3.11, FastAPI, asyncio, WebSocket |
| Frontend | Svelte 4, Vite 5 |
| Captura de audio | PyAudio, numpy, scipy (remuestreo) |
| Palabra de activacion | EfficientWord-Net (personalizado) + openWakeWord (fallback) |
| Speech-to-Text | OpenAI GPT-4o-transcribe |
| Text-to-Speech | OpenAI TTS |
| LLM | OpenAI GPT-4o-mini (fallback intents + preguntas generales) |
| Musica | Spotipy (API Web de Spotify + Spotify Connect) |
| Video | yt-dlp + VLC |
| Clima | Open-Meteo (gratuito, sin clave API) |
| Camaras | API REST UniFi Protect |
| Enrutamiento de audio | PipeWire + RAOP (AirPlay) |
| Pantalla | Chromium en modo kiosco (Wayland) |

## Solucion de problemas

### Problemas comunes

**Microfono no detectado:**
```bash
arecord -l                         # Listar dispositivos de captura ALSA
pactl list sources | grep -i name  # Listar fuentes PipeWire
```

**Sin salida de audio a los altavoces:**
```bash
pactl list sinks | grep -i devialet  # Verificar si el sink AirPlay es visible
wpctl status                          # Verificar estado PipeWire/WirePlumber
```

**Spotify no se conecta:**
- Asegurate de tener Spotify Premium
- Verifica que `SPOTIFY_DEVICE_NAME` en `.env` coincida exactamente con el nombre de tu altavoz en la app de Spotify
- Ejecuta el backend una vez manualmente para completar el flujo OAuth

**La palabra de activacion no se activa:**
- Verifica los niveles del microfono en el panel admin
- Intenta bajar el umbral en `backend/audio/wakeword.py`
- Vuelve a grabar muestras de la palabra de activacion via el panel admin

**La pantalla no se enciende/apaga:**
```bash
# Verificar control de retroiluminacion
cat /sys/class/backlight/10-0045/brightness
echo 255 | sudo tee /sys/class/backlight/10-0045/brightness  # Encender
echo 0 | sudo tee /sys/class/backlight/10-0045/brightness    # Apagar
```

## Contribuir

Las contribuciones son bienvenidas! Este es un proyecto de pasion, y siempre hay espacio para mejorar.

1. Haz un fork del repositorio
2. Crea una rama de funcionalidad (`git checkout -b feature/mi-funcionalidad`)
3. Haz commit de tus cambios (`git commit -m 'Agregar mi funcionalidad'`)
4. Sube la rama (`git push origin feature/mi-funcionalidad`)
5. Abre un Pull Request

### Ideas para contribuciones

- Soporte multilenguaje para comandos de voz (ingles, espanol, criollo)
- Integracion de domotica (Home Assistant, MQTT)
- Pagina de calendario y recordatorios
- Funcionalidad de despertador/alarma
- Streaming de radio/podcast
- Reconocimiento de gestos por camara
- Mejores modelos de palabra de activacion

## Creditos

- Construido por **Anthony D.** en Guadalupe
- Impulsado por [FastAPI](https://fastapi.tiangolo.com/), [Svelte](https://svelte.dev/), [Spotipy](https://spotipy.readthedocs.io/), [yt-dlp](https://github.com/yt-dlp/yt-dlp), [EfficientWord-Net](https://github.com/Ant-Brain/EfficientWord-Net), [openWakeWord](https://github.com/dscripka/openWakeWord)
- Datos meteorologicos de [Open-Meteo](https://open-meteo.com/)
- Servicios de voz por [OpenAI](https://openai.com/)

## Licencia

Este proyecto esta bajo la **Licencia MIT** — consulta el archivo [LICENSE](LICENSE) para mas detalles.

---

<p align="center">
  Hecho con cuidado en Guadalupe
  <br>
  <em>Un proyecto del sol para tu hogar</em>
</p>
