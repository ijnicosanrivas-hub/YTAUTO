#!/usr/bin/env bash
# Instala YTAUTO dentro de un GitHub Codespace (se ejecuta una vez al crearlo).
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Programas del sistema (FFmpeg y voz local)"
sudo apt-get update -y
sudo apt-get install -y --no-install-recommends ffmpeg espeak-ng

echo "==> Dependencias de Python"
python -m pip install --upgrade pip
python -m pip install -e .

echo "==> Interfaz web"
(cd frontend && npm ci && npm run build)

echo "==> Claude Code (para la inteligencia del programa)"
if ! command -v claude >/dev/null 2>&1; then
  curl -fsSL https://claude.ai/install.sh | bash || echo "AVISO: no se pudo instalar Claude Code; reintenta: curl -fsSL https://claude.ai/install.sh | bash"
fi

[ -f .env ] || cp .env.example .env
mkdir -p data
echo
echo "Instalación terminada. Falta iniciar sesión en Claude UNA vez: abre una terminal y escribe  claude"
