#!/bin/bash
# Instalador de YTAUTO para Linux (Ubuntu/Debian, Fedora, Arch y derivadas).
# Instala Python 3.11+, FFmpeg, la voz eSpeak NG y Claude Code; despues prepara YTAUTO y crea un acceso en el menu.
LANZ="$(cd "$(dirname "$0")" && pwd)"
if [ -f "$LANZ/pyproject.toml" ]; then RAIZ="$LANZ"; else RAIZ="$(cd "$LANZ/../.." && pwd)"; fi
cd "$RAIZ" || exit 1
ok()    { printf '  \033[32m[OK]\033[0m %s\n' "$1"; }
aviso() { printf '  \033[33m[AVISO]\033[0m %s\n' "$1"; }
fallo() { printf '  \033[31m[FALLO]\033[0m %s\n' "$1"; exit 1; }

echo
echo "  =========================================================="
echo "     INSTALADOR DE YTAUTO  -  Fabrica de videos cortos (Linux)"
echo "  =========================================================="
[ -f "$RAIZ/pyproject.toml" ] || fallo "No encuentro los archivos de YTAUTO. Descomprime el paquete entero."

SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"
if command -v apt-get >/dev/null 2>&1; then
  PAQ="$SUDO apt-get install -y"; PRE="$SUDO apt-get update"; PKGS="python3 python3-venv python3-pip ffmpeg espeak-ng curl"
elif command -v dnf >/dev/null 2>&1; then
  PAQ="$SUDO dnf install -y"; PRE=":"; PKGS="python3 python3-pip ffmpeg espeak-ng curl"
elif command -v pacman >/dev/null 2>&1; then
  PAQ="$SUDO pacman -S --needed --noconfirm"; PRE=":"; PKGS="python python-pip ffmpeg espeak-ng curl"
else
  PAQ=""; aviso "No reconozco el gestor de paquetes: instala a mano Python 3.11+, ffmpeg y espeak-ng."
fi

echo; echo "[1/4] Python, FFmpeg y voz"
FALTA=""
for c in ffmpeg espeak-ng curl; do command -v "$c" >/dev/null 2>&1 || FALTA="$FALTA $c"; done
python3 -c 'import sys, venv; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null || FALTA="$FALTA python"
if [ -n "$FALTA" ] && [ -n "$PAQ" ]; then
  echo "  Falta:$FALTA. Se instala con el gestor del sistema (puede pedir tu contrasena)."
  $PRE && $PAQ $PKGS
fi
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null || fallo "Se necesita Python 3.11 o superior."
command -v ffmpeg >/dev/null 2>&1 || fallo "Falta FFmpeg."
command -v espeak-ng >/dev/null 2>&1 && ok "Python, FFmpeg y voz listos." || aviso "Falta la voz (espeak-ng)."

echo; echo "[2/4] Claude Code"
export PATH="$HOME/.local/bin:$PATH"
command -v claude >/dev/null 2>&1 || curl -fsSL https://claude.ai/install.sh | bash
command -v claude >/dev/null 2>&1 && { ok "Claude Code listo."; CL=1; } || { aviso "No se pudo instalar Claude Code (usa iniciar_sin_claude.sh)."; CL=0; }

echo; echo "[3/4] Preparando YTAUTO"
python3 "$RAIZ/scripts/instalar.py" || fallo "La preparacion de YTAUTO fallo. Lee el mensaje de arriba."

echo; echo "[4/4] Acceso en el menu de aplicaciones"
APPS="$HOME/.local/share/applications"; mkdir -p "$APPS"
cat > "$APPS/ytauto.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=YTAUTO
Comment=Fabrica de videos cortos
Exec=bash "$LANZ/iniciar.sh"
Icon=$RAIZ/frontend/public/icono-512.png
Terminal=true
Categories=AudioVideo;
DESK
ok "Acceso creado (YTAUTO en el menu)."

echo; echo "  INSTALACION TERMINADA. Para abrirla: YTAUTO en el menu o bash $LANZ/iniciar.sh"
if [ "$CL" = "1" ] && [ -t 0 ]; then
  read -r -p "  Iniciar sesion en Claude ahora (una vez)? [S/n] " r
  case "$r" in n|N|no|NO) ;; *) claude ;; esac
fi
