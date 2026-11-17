#!/usr/bin/env bash
# Arranca YTAUTO en segundo plano dentro del Codespace (se ejecuta cada vez que el Codespace se enciende).
# El Codespace reenvía el puerto de forma PRIVADA (solo tu cuenta de GitHub), así que no hace falta abrirlo a la red.
set -uo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"
PORT="${YTAUTO_PORT:-8000}"
mkdir -p data

if pgrep -f "ytauto.api.server" >/dev/null 2>&1; then
  echo "YTAUTO ya está en marcha (puerto $PORT)."
  exit 0
fi
nohup python -m ytauto.api.server --port "$PORT" >> data/server.log 2>&1 &
echo "YTAUTO arrancando en el puerto $PORT (registro: data/server.log)."
