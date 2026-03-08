#!/bin/bash
set -e

echo "=== PI-Board — Installation ==="

# Mise a jour systeme
sudo apt update && sudo apt upgrade -y

# Paquets systeme
sudo apt install -y \
  python3 python3-pip python3-venv \
  chromium-browser \
  vlc \
  portaudio19-dev \
  pipewire pipewire-pulse wireplumber \
  curl git

# Node.js via NodeSource (LTS)
if ! command -v node &> /dev/null; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
  sudo apt install -y nodejs
fi

echo "[OK] Node $(node -v) / npm $(npm -v)"

# Python venv + deps
cd "$(dirname "$0")/.."
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo "[OK] Python deps installees"

# Frontend deps + build
cd frontend
npm install
npm run build
echo "[OK] Frontend build"

echo ""
echo "=== Installation terminee ==="
echo "Lancer avec: ./scripts/start.sh"
