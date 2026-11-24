# YTAUTO en Mac

## Instalación
1. Descomprime el ZIP (doble clic) y abre `INSTALAR_MAC.command`.
2. Si macOS lo bloquea por ser «de un desarrollador no identificado»: **Ajustes del Sistema → Privacidad y seguridad →
   Abrir igualmente** (o clic derecho → Abrir). Alternativa: en Terminal, `bash ` + arrastrar el archivo + Intro.
3. El instalador hace, en este orden (si algo ya está, no lo repite):
   1. **Homebrew** (pide tu contraseña de Mac una vez y lo deja en el `PATH` de las próximas ventanas de Terminal).
   2. **Python 3.11+** (`brew install python@3.12` si no hay uno válido).
   3. **FFmpeg** (`brew install ffmpeg`, con libass para los subtítulos).
   4. **Voz**: `brew install espeak-ng`.
   5. **Claude Code** con el instalador oficial (`curl -fsSL https://claude.ai/install.sh | bash`).
   6. **YTAUTO**: `scripts/instalar.py` (entorno `.venv`, dependencias, `.env`, diagnóstico) y el acceso
      `YTAUTO.command` en el Escritorio.
4. Al final, inicia sesión en Claude una vez con tu cuenta (`claude`, y `/exit` al terminar).

También quita la «cuarentena» de macOS a la carpeta (`xattr -dr com.apple.quarantine`) para que los demás `.command`
abran sin avisos. No usa `sudo` por su cuenta.

## Uso
- `INICIAR_MAC.command` (o `YTAUTO.command` del Escritorio): diagnóstico y abre la fábrica en el navegador.
- `INICIAR_MAC_SIN_CLAUDE.command`: modo de prueba sin Claude.
- `DIAGNOSTICO_MAC.command`: qué está instalado y qué falta (prueba la voz generando una frase de verdad).

Los lanzadores cargan Homebrew (`/opt/homebrew` en Apple Silicon, `/usr/local` en Intel) y `~/.local/bin`, y
`core/tools.py` añade esas rutas al proceso, porque al abrir desde el Finder el `PATH` no siempre las incluye.

## Voz
La voz por defecto es **eSpeak NG** (su audio se puede usar comercialmente). Existe un adaptador opcional con las
voces del sistema de macOS (`macos_say`: Mónica, Jorge, Paulina…) que suenan mejor, pero **no se activa solo**: la
licencia de macOS solo permite esas voces para contenido personal y no comercial, y excluye publicarlas. Úsalo, si
acaso, para pruebas internas (Proveedores → añadir «Voz del sistema (macOS)»). Para una voz natural y publicable, usa
Piper con un modelo de licencia compatible.
