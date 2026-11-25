#!/bin/bash
# Instalador de YTAUTO para macOS (Apple Silicon e Intel). Doble clic en el Finder.
# Instala con Homebrew: Python 3.12, FFmpeg (con subtitulos) y la voz eSpeak NG; despues Claude Code y YTAUTO.
# Compatible con el bash 3.2 que trae macOS.

LANZ="$(cd "$(dirname "$0")" && pwd)"  # carpeta de este archivo
# Funciona desde el paquete (todo junto) o desde el repositorio (instaladores/mac)
if [ -f "$LANZ/pyproject.toml" ]; then RAIZ="$LANZ"; else RAIZ="$(cd "$LANZ/../.." && pwd)"; fi
cd "$RAIZ" || exit 1
FALLOS=0

titulo() { printf '\n\033[1m%s\033[0m\n' "$1"; }
ok()     { printf '  \033[32m[OK]\033[0m %s\n' "$1"; }
aviso()  { printf '  \033[33m[AVISO]\033[0m %s\n' "$1"; }
fallo()  { printf '  \033[31m[FALLO]\033[0m %s\n' "$1"; FALLOS=1; }
salir()  { echo; read -r -p "  Pulsa Intro para cerrar esta ventana... " _; exit "${1:-0}"; }

echo
echo "  =========================================================="
echo "     INSTALADOR DE YTAUTO  -  Fabrica de videos cortos (Mac)"
echo "  =========================================================="
echo
echo "  En un Mac nuevo instala TODO: Homebrew, Python, FFmpeg, la voz, Claude Code y YTAUTO."
echo "  Si YTAUTO ya esta instalado, lo ACTUALIZA: solo cambia lo que trae de nuevo esta version"
echo "  y no toca tus datos, claves, licencias ni proyectos."
echo "  La primera vez tarda entre 10 y 30 minutos; una actualizacion, un par de minutos."
echo "  Te pedira la contrasena de tu Mac una vez (para Homebrew). Al escribirla no se ve: es normal."

if [ ! -f "$RAIZ/pyproject.toml" ]; then
  echo
  echo "  [ERROR] No encuentro los archivos de YTAUTO junto a este instalador."
  echo "          Descomprime el ZIP entero y abre INSTALAR_MAC.command desde la carpeta descomprimida."
  salir 1
fi
if [ "$(uname)" != "Darwin" ]; then
  echo "  [ERROR] Este instalador es para macOS."
  salir 1
fi

# Lo descargado de Internet viene en «cuarentena»: se quita en esta carpeta para que los demas .command abran sin avisos.
xattr -dr com.apple.quarantine "$RAIZ" 2>/dev/null
chmod +x "$LANZ"/*.command 2>/dev/null

# ------------------------------------------------------------ 1. Homebrew
titulo "[1/6] Homebrew (gestor de programas de Mac)"
buscar_brew() {
  for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do
    if [ -x "$b" ]; then eval "$("$b" shellenv)"; return 0; fi
  done
  command -v brew >/dev/null 2>&1
}
if ! buscar_brew; then
  echo "  Homebrew no esta instalado. Es el instalador de programas estandar en Mac (gratuito)."
  read -r -p "  Instalarlo ahora? [S/n] " r
  case "$r" in n|N|no|NO) echo "  Sin Homebrew no se pueden instalar FFmpeg ni la voz."; salir 1 ;; esac
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  if ! buscar_brew; then
    fallo "No se pudo instalar Homebrew. Instalalo desde https://brew.sh y vuelve a abrir este archivo."
    salir 1
  fi
  # Para que las proximas ventanas de Terminal tambien lo encuentren
  BREW_BIN="$(command -v brew)"
  if ! grep -q "brew shellenv" "$HOME/.zprofile" 2>/dev/null; then
    echo "eval \"\$($BREW_BIN shellenv)\"" >> "$HOME/.zprofile"
  fi
fi
ok "Homebrew listo ($(brew --version | head -n 1))."

instalar_brew() {  # instala el paquete si falta; no reinstala lo que ya hay
  if brew list --formula "$1" >/dev/null 2>&1; then return 0; fi
  echo "  Instalando $1 ..."
  brew install "$1"
}

# ------------------------------------------------------------ 2. Python
titulo "[2/6] Python"
PY=""
buscar_python() {
  PY=""
  for c in python3.13 python3.12 python3.11 \
           /opt/homebrew/bin/python3.13 /opt/homebrew/bin/python3.12 /opt/homebrew/bin/python3.11 \
           /usr/local/bin/python3.13 /usr/local/bin/python3.12 /usr/local/bin/python3.11 python3; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
      PY="$(command -v "$c")"; return 0
    fi
  done
  return 1
}
if ! buscar_python; then
  instalar_brew python@3.12
  buscar_python
fi
if [ -n "$PY" ]; then ok "Python listo ($("$PY" --version))."; else fallo "No se pudo instalar Python 3.11 o superior."; salir 1; fi

# ------------------------------------------------------------ 3. FFmpeg
titulo "[3/6] FFmpeg (motor de video)"
command -v ffmpeg >/dev/null 2>&1 || instalar_brew ffmpeg
if command -v ffmpeg >/dev/null 2>&1; then ok "FFmpeg listo."; else fallo "No se pudo instalar FFmpeg (brew install ffmpeg)."; salir 1; fi

# ------------------------------------------------------------ 4. Voz
titulo "[4/6] Voz (eSpeak NG)"
command -v espeak-ng >/dev/null 2>&1 || instalar_brew espeak-ng
if command -v espeak-ng >/dev/null 2>&1; then ok "Voz lista."; else aviso "No se pudo instalar la voz (brew install espeak-ng)."; fi

# ------------------------------------------------------------ 5. Claude Code
titulo "[5/6] Claude Code"
export PATH="$HOME/.local/bin:$PATH"
if ! command -v claude >/dev/null 2>&1; then
  echo "  Instalando Claude Code (instalador oficial) ..."
  curl -fsSL https://claude.ai/install.sh | bash
fi
if command -v claude >/dev/null 2>&1; then
  ok "Claude Code listo."
  CL=1
else
  aviso "No se pudo instalar Claude Code. Puedes probar el programa sin Claude con INICIAR_MAC_SIN_CLAUDE.command"
  CL=0
fi

# ------------------------------------------------------------ 6. YTAUTO
titulo "[6/6] Preparando YTAUTO (puede tardar unos minutos)"
# Equipo nuevo: instala todo. Ya instalado: actualiza esa instalacion (solo lo que cambie, sin tocar tus datos).
# scripts/instalar.py crea tambien el acceso YTAUTO.command del Escritorio apuntando a la instalacion.
"$PY" "$RAIZ/scripts/instalar.py"
RES=$?
if [ "$RES" = "75" ]; then
  fallo "YTAUTO esta abierto. Cierra su ventana de Terminal y vuelve a abrir este archivo para actualizarlo."
  salir 1
elif [ "$RES" != "0" ]; then
  fallo "La preparacion de YTAUTO fallo. Lee el mensaje de arriba."
  salir 1
fi
DEST="$("$PY" "$RAIZ/scripts/instalar.py" --resolver-destino 2>/dev/null)"
[ -n "$DEST" ] || DEST="$RAIZ"

echo
echo "  =========================================================="
echo "     INSTALACION TERMINADA"
echo "  =========================================================="
echo
echo "  Para abrir la fabrica usa YTAUTO.command del Escritorio o INICIAR_MAC.command de esta carpeta."
if [ "$CL" = "1" ] && [ "$DEST" = "$RAIZ" ]; then
  echo
  echo "  Falta UN paso: iniciar sesion en Claude, una sola vez, con TU cuenta de Claude."
  echo "  Se abrira Claude: sigue los pasos en el navegador y, al terminar, escribe /exit"
  read -r -p "  Quieres hacerlo ahora? [S/n] " r
  case "$r" in n|N|no|NO) ;; *) claude ;; esac
fi
echo
echo "  Todo listo. Ya puedes cerrar esta ventana."
salir "$FALLOS"
