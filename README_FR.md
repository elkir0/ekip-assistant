
<p align="center">

```
 ____  _ ____                      _
|  _ \(_) __ )  ___   __ _ _ __ __| |
| |_) | |  _ \ / _ \ / _` | '__/ _` |
|  __/| | |_) | (_) | (_| | | | (_| |
|_|   |_|____/ \___/ \__,_|_|  \__,_|
```

**Votre maison merite une voix. Construisez-la vous-meme.**

</p>

<p align="center">
  <a href="#"><img alt="Licence : MIT" src="https://img.shields.io/badge/licence-MIT-blue.svg"></a>
  <a href="#"><img alt="Python 3.11" src="https://img.shields.io/badge/python-3.11-3776AB.svg"></a>
  <a href="#"><img alt="Svelte 4" src="https://img.shields.io/badge/svelte-4-FF3E00.svg"></a>
  <a href="#"><img alt="Raspberry Pi 4" src="https://img.shields.io/badge/raspberry%20pi-4-C51A4A.svg"></a>
  <a href="#"><img alt="FastAPI" src="https://img.shields.io/badge/fastapi-0.115-009688.svg"></a>
</p>

<p align="center">
  <a href="README.md">English</a> |
  <strong>Francais</strong> |
  <a href="README_ES.md">Espanol</a>
</p>

---

**Piboard** est un ecran intelligent open-source qui transforme un Raspberry Pi en assistant vocal de salon. Un Amazon Echo Show — mais que vous possedez, comprenez, et personnalisez comme vous voulez.

Dites *"Hey Piboard, mets du jazz"* et il lance du jazz sur votre Devialet. Demandez la meteo et il la lit a voix haute en basculant sur la page meteo. Dites-lui de mettre une video YouTube et il la diffuse en plein ecran avec le son envoye sans fil a vos enceintes via AirPlay.

Pas d'abonnement. Pas de dependance cloud. Juste un Pi, un ecran et votre voix.

Ne en **Guadeloupe**, concu pour tourner 24h/24 sur votre table de nuit ou plan de cuisine.

## Pourquoi Piboard ?

- **Audio hi-fi sans fil** — La musique et les videos envoient le son a n'importe quelle enceinte AirPlay ou Spotify Connect (Devialet, Sonos, HomePod...) via le sink RAOP de PipeWire. Le Pi ne touche jamais l'audio — vos enceintes s'en chargent.
- **Integration Spotify Connect** — Recherche vocale, controle de lecture, navigation dans les playlists. L'audio va directement des serveurs Spotify a votre enceinte — zero perte de qualite.
- **YouTube sur vos enceintes** — Recherche vocale ou tactile, lecture VLC plein ecran, audio route vers vos enceintes hi-fi en AirPlay. Gestion de file d'attente avec enchainement automatique.
- **Interaction vocale reelle** — Mot de reveil entraine avec VOTRE voix. Transcription OpenAI, reponses TTS naturelles, ducking audio qui baisse la musique quand l'assistant parle.
- **Interface tactile 4 pages** — Swipez entre Musique, Meteo, YouTube et Cameras. Theme sombre optimise pour ecran 7" toujours allume.
- **Cameras de securite** — Snapshots en direct de vos cameras UniFi Protect sur votre table de nuit.
- **Panneau d'admin complet** — Configurez tout depuis votre telephone : sensibilite du micro, routage audio, Spotify, cookies YouTube, planning ecran, et plus encore.
- **Veille intelligente** — Ecran eteint a 22h, rallume a 6h. Volume nuit des 20h. Luminosite adaptative.
- **100% open source** — Licence MIT, pas de firmware proprietaire, pas de dependance constructeur.

## Captures d'ecran

| Musique | Meteo | YouTube |
|:-------:|:-----:|:-------:|
| ![Musique](docs/screenshots/music.png) | ![Meteo](docs/screenshots/weather.png) | ![YouTube](docs/screenshots/youtube.png) |

## Comment ca marche

```
Raspberry Pi 4 + Ecran tactile 7"
  |
  +-- Chromium Kiosk (app Svelte plein ecran)
  |    +-- WebSocket <--> Backend FastAPI
  |
  +-- Micro USB (ReSpeaker 2-Mic Array)
  |    +-- Detection mot de reveil (EfficientWord-Net / openWakeWord)
  |    +-- Speech-to-Text (OpenAI GPT-4o-transcribe)
  |    +-- Routeur d'intents (mots-cles, zero cout pour les commandes courantes)
  |         |
  |         +-- "mets du jazz"       --> API Spotify --> Devialet (Spotify Connect)
  |         +-- "meteo demain"       --> Open-Meteo --> TTS --> AirPlay --> Enceinte
  |         +-- "YouTube Stromae"    --> yt-dlp --> VLC --> AirPlay --> Enceinte
  |         +-- "montre les cameras" --> UniFi Protect --> Snapshots en direct
  |         +-- toute autre question --> LLM (GPT-4o-mini) --> TTS --> Enceinte
  |
  +-- Moteur audio PipeWire
       +-- Sink RAOP (AirPlay) --> Devialet / Sonos / HomePod
       +-- Spotify Connect (flux direct, le Pi n'est pas dans le chemin audio)
```

### Architecture audio

C'est ce qui rend Piboard special :

| Source | Chemin | Qualite |
|--------|--------|---------|
| **Spotify** | Serveurs Spotify --> Spotify Connect --> votre enceinte | Sans perte (OGG 320kbps) |
| **Video YouTube** | yt-dlp --> VLC --> PipeWire --> AirPlay (RAOP) --> votre enceinte | Jusqu'a 720p video + audio AAC |
| **Reponses vocales** | OpenAI TTS --> PipeWire --> AirPlay --> votre enceinte | Voix naturelle |
| **Ducking** | Volume Spotify baisse via API pendant le TTS, puis remonte | Transparent |

Le Pi agit comme un **controleur et routeur**, jamais comme un DAC. Vos enceintes recoivent la meilleure qualite audio possible.

## Materiel requis

| Composant | Modele | Notes |
|-----------|--------|-------|
| **SBC** | Raspberry Pi 4 (4 Go RAM) | ARM64, Raspberry Pi OS Bookworm 64-bit |
| **Ecran** | Raspberry Pi Touch Display 2 (7") | 720x1280, capacitif, connecteur DSI |
| **Micro** | ReSpeaker Lite USB 2-Mic Array | AEC materiel, ou tout micro USB |
| **Enceintes** | Toute enceinte AirPlay ou Spotify Connect | Devialet, Sonos, HomePod, etc. |
| **Stockage** | microSD 32 Go+ (classe A2 recommandee) | |
| **Reseau** | WiFi ou Ethernet | Pi et enceintes sur le meme LAN |

**Cout total :** ~120 EUR (Pi + ecran + micro), plus les enceintes que vous avez deja.

## Demarrage rapide

### 1. Cloner et installer

```bash
git clone https://github.com/elkir0/ekip-assistant.git piboard
cd piboard
chmod +x scripts/*.sh
./scripts/setup.sh
```

### 2. Configurer

```bash
cp .env.example .env
nano .env
```

Remplissez vos cles API (voir [Configuration](#configuration) ci-dessous).

### 3. Lancer

```bash
./scripts/start.sh
```

Le backend demarre sur le port 8000, Chromium s'ouvre en mode kiosque. C'est pret.

### 4. Demarrage automatique au boot

```bash
sudo cp systemd/piboard-backend.service /etc/systemd/system/
sudo cp systemd/piboard-kiosk.service /etc/systemd/system/
sudo systemctl enable piboard-backend piboard-kiosk
sudo systemctl start piboard-backend piboard-kiosk
```

## Configuration

Creez un fichier `.env` depuis l'exemple :

```bash
# Speech-to-Text + Text-to-Speech + LLM
OPENAI_API_KEY=sk-...              # openai.com — STT, TTS et LLM

# Spotify
SPOTIFY_CLIENT_ID=...              # developer.spotify.com
SPOTIFY_CLIENT_SECRET=...
SPOTIFY_REDIRECT_URI=http://localhost:8000/api/spotify/callback
SPOTIFY_DEVICE_NAME=Devialet       # Nom exact de votre enceinte Spotify Connect

# Meteo (Open-Meteo est gratuit, pas de cle)
WEATHER_CITY=Guadeloupe
WEATHER_LAT=16.25
WEATHER_LON=-61.58

# UniFi Protect (optionnel — cameras de securite)
UNIFI_HOST=192.168.1.18
UNIFI_USER=admin
UNIFI_PASS=...

# Audio
PIPEWIRE_AIRPLAY_SINK=Devialet     # Nom de votre sink AirPlay PipeWire
RESPEAKER_DEVICE=hw:ReSpeaker,0    # Peripherique ALSA du micro USB

# Serveur
BACKEND_PORT=8000
```

### Cles API

| Service | Ou l'obtenir | Cout |
|---------|-------------|------|
| **OpenAI** | [platform.openai.com](https://platform.openai.com) | A la consommation (~0.01 EUR/jour pour un assistant vocal) |
| **Spotify** | [developer.spotify.com](https://developer.spotify.com) | Gratuit (Spotify Premium requis pour la lecture) |
| **Open-Meteo** | Pas de cle necessaire | Gratuit |
| **UniFi Protect** | Cloud Key UniFi local | Gratuit (materiel UniFi requis) |

## Commandes vocales

Piboard comprend les commandes vocales en francais :

| Commande | Action |
|----------|--------|
| *"Hey Piboard, mets du jazz"* | Cherche et lance du jazz sur Spotify via vos enceintes |
| *"Hey Piboard, joue Stromae"* | Lance Stromae en Spotify Connect |
| *"Hey Piboard, pause"* | Met en pause le morceau en cours |
| *"Hey Piboard, suivant"* | Passe au morceau suivant |
| *"Hey Piboard, plus fort"* | Monte le volume sur vos enceintes |
| *"Hey Piboard, moins fort"* | Baisse le volume |
| *"Hey Piboard, meteo"* | Lit la meteo a voix haute et affiche la page meteo |
| *"Hey Piboard, mets la video Stromae"* | Cherche sur YouTube, lance en plein ecran avec son sur vos enceintes |
| *"Hey Piboard, stop video"* | Arrete YouTube, reprend Spotify |
| *"Hey Piboard, dodo"* | Eteint l'ecran (mode veille) |
| *"Hey Piboard, debout"* | Rallume l'ecran |
| *"Hey Piboard, c'est quoi la capitale du Japon ?"* | Question generale traitee par le LLM |

> Le mot de reveil est personnalisable. Entrainez le votre via le panneau admin ou `scripts/record_wakeword.py`.

## Controles tactiles

- **Swipe haut/bas** pour naviguer entre les pages (Musique > Meteo > YouTube > Cameras)
- **Tap** play/pause, suivant/precedent sur la page Musique
- **Curseur de volume** sur la page Musique
- **Clavier virtuel** pour la recherche YouTube
- **Tap** sur une camera pour le snapshot en grand

## Panneau d'administration

Accessible a `http://ip-du-pi:8000/admin` depuis n'importe quel appareil sur votre reseau.

| Section | Ce que vous pouvez configurer |
|---------|-------------------------------|
| **Dashboard** | Etat systeme, sante des services, uptime, CPU/RAM |
| **Voice** | Modele de mot de reveil, seuil de detection, cooldown |
| **Audio** | Gain micro, selection du sink PipeWire |
| **Music** | Connexion Spotify, selection d'appareil, limites de recherche |
| **YouTube** | Format/qualite video, taille du tampon VLC (stabilite AirPlay), gestion des cookies d'authentification YouTube |
| **Weather** | Localisation, fuseau horaire, jours de prevision |
| **Cameras** | Hote UniFi Protect, resolution des snapshots, grille |
| **Screen** | Luminosite, planning veille/reveil, volume nuit |
| **System** | Logs en direct, redemarrage services, infos systeme |
| **Interface** | Couleur d'accent, vitesse de transition, sensibilite du swipe |

## Stack technique

| Couche | Technologie | Pourquoi |
|--------|------------|----------|
| Backend | Python 3.11, FastAPI, asyncio | Tout async, WebSocket temps reel |
| Frontend | Svelte 4, Vite 5 | Rapide, leger, parfait pour l'embarque |
| Capture audio | PyAudio + resampling scipy | Micro USB 44.1kHz -> 16kHz pour le STT |
| Mot de reveil | EfficientWord-Net + openWakeWord | Entrainement vocal + fallback fiable |
| STT | OpenAI GPT-4o-transcribe | Meilleure precision en francais |
| TTS | OpenAI TTS | Voix naturelle et expressive |
| LLM | OpenAI GPT-4o-mini | Rapide, economique, assez intelligent pour les intents |
| Musique | Spotipy + Spotify Connect | Streaming hi-fi direct vers les enceintes |
| Video | yt-dlp + VLC + deno (solver JS) | Extraction YouTube fiable + lecture |
| Meteo | Open-Meteo | Gratuit, sans cle, precis |
| Cameras | API REST UniFi Protect | Reseau local, pas de dependance cloud |
| Routage audio | PipeWire + RAOP (AirPlay) | Hi-fi sans fil vers toute enceinte AirPlay |
| Affichage | Chromium kiosque (Wayland) | Plein ecran, optimise tactile |

## Depannage

**Pas de son sur les enceintes :**
```bash
pactl list sinks short          # Verifier que le sink AirPlay est visible
wpctl status                    # Etat PipeWire/WirePlumber
```

**Spotify ne se connecte pas :**
- Spotify Premium requis
- `SPOTIFY_DEVICE_NAME` doit correspondre exactement au nom dans l'app Spotify
- Si deconnecte, la page Musique affiche un bouton "Reconnecter" pour la re-authentification OAuth
- Enregistrez `http://localhost:8000/api/spotify/callback` dans votre Spotify Developer Dashboard

**Les videos YouTube ne se lancent pas :**
- YouTube bloque les requetes non authentifiees — installez les cookies via Admin > YouTube
- Exportez les cookies depuis un navigateur connecte a YouTube (extension "Get cookies.txt LOCALLY")
- `deno` est requis pour le solver JS de yt-dlp : `curl -fsSL https://deno.land/install.sh | sh`
- Verifiez les logs : `journalctl -u piboard-backend -f`

**Le mot de reveil ne se declenche pas :**
- Verifiez les niveaux du micro dans le panneau admin
- Baissez le seuil ou re-enregistrez des echantillons

**Controle de l'ecran :**
```bash
cat /sys/class/backlight/10-0045/brightness      # Lire la valeur actuelle
echo 255 | sudo tee /sys/class/backlight/10-0045/brightness  # Max
echo 0 | sudo tee /sys/class/backlight/10-0045/brightness    # Eteint
```

## Contribuer

Les contributions sont les bienvenues ! Fork, branche, PR.

Idees :
- Support multilingue (anglais, espagnol, creole)
- Integration Home Assistant / MQTT
- Reveil et minuteurs
- Streaming radio/podcast
- Meilleurs modeles de mot de reveil

## Credits

- Construit par **Anthony D.** en Guadeloupe
- Propulse par [FastAPI](https://fastapi.tiangolo.com/), [Svelte](https://svelte.dev/), [Spotipy](https://spotipy.readthedocs.io/), [yt-dlp](https://github.com/yt-dlp/yt-dlp), [openWakeWord](https://github.com/dscripka/openWakeWord)
- Meteo par [Open-Meteo](https://open-meteo.com/) | Voix par [OpenAI](https://openai.com/)

## Licence

Licence MIT — voir [LICENSE](LICENSE).

---

<p align="center">
  Fait avec soin en Guadeloupe
  <br>
  <em>Un projet du soleil pour votre maison</em>
</p>
