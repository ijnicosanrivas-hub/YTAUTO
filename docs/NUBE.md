# Usar YTAUTO sin instalar nada en tu PC (GitHub Codespaces)

**Idea:** en vez de instalar el programa en tu ordenador, usas un **ordenador en la nube de tu propia cuenta de
GitHub** (un *Codespace*). Se crea desde el navegador —sirve el del iPhone, de una tablet o de cualquier PC sin
instalar nada— y YTAUTO se instala y arranca solo. La interfaz se abre en una pestaña del navegador.

## Lo más corto: un solo toque
Abre este enlace con tu sesión de GitHub iniciada (sirve en el iPhone) y pulsa **«Create new codespace»**:

**https://codespaces.new/ijnicosanrivas-hub/ytauto/tree/claude/multiagent-audiovisual-system-hv0bwv?quickstart=1**

Eso crea el Codespace ya en la rama correcta. Después solo falta el inicio de sesión de Claude (paso 5 de abajo).

## Una sola vez: crear tu Codespace (a mano)
1. Abre en el navegador **github.com/ijnicosanrivas-hub/ytauto** e inicia sesión en GitHub.
2. Arriba a la izquierda, elige la rama **`claude/multiagent-audiovisual-system-hv0bwv`** (la configuración está ahí).
3. Pulsa el botón verde **`<> Code`** → pestaña **Codespaces** → **«Create codespace on claude/multiagent-…»**.
   (Para cambiar la potencia: `⋯` → *New with options*. Se recomienda **4 núcleos**: los vídeos tardan menos.)
4. **Espera 5–10 minutos.** Se instalan solos FFmpeg, la voz, el programa y Claude Code. Verás una pantalla tipo editor
   de código; no hace falta tocar nada de eso.
5. Cuando termine, abre la **terminal** (menú ☰ → *Terminal → New Terminal*) y escribe **`claude`** + Intro.
   Te da un enlace: ábrelo, inicia sesión con tu cuenta de **Claude Pro**, copia el código que te da y pégalo en la
   terminal. Después escribe `/exit`. (Hazlo con un ordenador o tablet si puedes: en el móvil es incómodo.)

## Cada vez que quieras usarlo
1. Entra en **github.com/codespaces** y pulsa tu Codespace (se reanuda solo; YTAUTO arranca solo).
2. Abre la pestaña **Puertos / Ports** (abajo en el editor). En la fila **YTAUTO (8000)** pulsa el icono del
   **globo** («Abrir en el navegador»). Se abre la Sala de producción.
3. Úsalo igual que en el PC: **Proyectos → + Nuevo vídeo**, aprueba el guion, mira el vídeo, **descarga los MP4**.
   Marca esa dirección como favorito: es privada y solo entra **tu cuenta de GitHub**.

## Dinero y tiempo
- GitHub da una **cuota mensual gratuita** de uso a las cuentas personales (compruébala en
  *github.com/settings/billing*). Un Codespace de 4 núcleos gasta el doble que uno de 2.
- Se **apaga solo** tras un rato sin uso. Al volver, se reanuda con tus proyectos. **No lo uses con la pestaña cerrada
  durante una producción larga**: puede apagarse antes de terminar.
- Cuando no lo necesites: en github.com/codespaces → `⋯` → **Stop codespace**. *Delete* lo borra con tus proyectos
  (descarga antes los vídeos).
- El consumo de **Claude** es el mismo que en el PC (unas 6–9 llamadas por vídeo de tu cuota Pro).

## Seguridad
- El puerto se reenvía como **privado**: solo se abre con tu sesión de GitHub. No lo cambies a «Público».
- Tu inicio de sesión de Claude queda **dentro de ese Codespace** (no en el repositorio). Si lo borras, se elimina.
- **Nada se publica ni se gasta sin tu autorización**, igual que en el PC.

## Si algo falla
| Qué ves | Qué hacer |
|---|---|
| «Claude Code no autenticado» | En la terminal: `claude`, inicia sesión; luego en la sala *Modelos Claude → Reanudar ahora* |
| El puerto 8000 no aparece o no abre | En la terminal: `bash scripts/codespace_start.sh`, espera unos segundos y recarga la pestaña *Ports* |
| Algo no se instaló | En la terminal: `python -m ytauto doctor` dice qué falta y cómo arreglarlo |
| Quieres ver el registro | `tail -n 50 data/server.log` |

## Qué está comprobado
La configuración (`.devcontainer/`, `scripts/codespace_setup.sh` y `scripts/codespace_start.sh`) se valida con pruebas:
JSON correcto, puerto **privado**, scripts válidos y el arranque idempotente (no lanza dos copias). **No se ha creado
un Codespace real**: los pasos de instalación (apt, npm, instalador de Claude Code) y el inicio de sesión de Claude
dentro del Codespace no se han ejecutado nunca allí.
