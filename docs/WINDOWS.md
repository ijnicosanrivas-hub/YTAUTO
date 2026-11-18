# Instalar YTAUTO en Windows (un solo archivo, sin saber nada)

Tiempo total: **10–30 minutos** la primera vez, casi todo esperando. Solo se hace una vez.
Sirve para **cualquier persona**: puedes pasar el ZIP (o el enlace) a quien quieras (ver `docs/COMPARTIR.md`).

## Qué necesitas
- **Windows 10 (versión 1803 o posterior) o Windows 11**, de 64 bits.
- **Internet** y **10 GB libres**.
- Tu propia cuenta de **Claude Pro** (la de claude.ai). Cada persona usa la suya.
- **No hace falta ser administrador** ni instalar nada antes: el instalador lo hace todo.

> YTAUTO se usa desde el navegador (Chrome, Edge…) pero corre en tu PC: debe estar encendido mientras trabaja.

## Paso 1 · Descargar y extraer
1. Descarga el ZIP del programa (si te lo han enviado, ya lo tienes).
2. Clic derecho sobre el ZIP → **Extraer todo…** y elige una carpeta corta, por ejemplo **`C:\YTAUTO`**
   (evita el Escritorio y OneDrive).

> **No abras el instalador desde dentro del ZIP**: Windows lo ejecuta desde una carpeta temporal y no funciona.
> Si lo haces, el propio instalador te avisa.

## Paso 2 · Instalar (un doble clic)
1. En la carpeta extraída, haz **doble clic en `INSTALAR_WINDOWS.bat`**.
2. Si sale **«Windows protegió su PC»**: **Más información → Ejecutar de todos modos** (el archivo no está firmado).
3. Se abre una ventana negra y va instalando solo, en este orden, mostrando `[OK]` en cada paso:
   **Python → Git → FFmpeg → voz → Claude Code → YTAUTO**. No la cierres.
4. Al terminar dice **INSTALACION TERMINADA** y crea el icono **YTAUTO** en tu Escritorio.
5. Te ofrece **iniciar sesión en Claude** (una sola vez). Pulsa **S**, sigue los pasos en el navegador con tu cuenta
   de Claude Pro y, al acabar, escribe **`/exit`**.

Si algo falla, vuelve a abrir `INSTALAR_WINDOWS.bat`: **retoma lo que falte**.

## Paso 3 · Usarlo
1. Doble clic en el icono **YTAUTO** del Escritorio (o en `INICIAR_WINDOWS.bat`). Se abre el navegador con la **Sala de producción**
   (`http://127.0.0.1:8000`). **No cierres la ventana negra** mientras lo uses.
2. **Proyectos → + Nuevo vídeo**: escribe la **Temática** (p. ej. «por qué los flamencos son rosas»), deja el modo
   **Automático** y pulsa **Crear y producir**.
3. Cuando el guion esté listo aparece el **Panel de aprobación**: léelo en la pestaña **Guion** y pulsa **Aprobar guion**.
4. Espera unos **4–8 minutos**. Cuando vuelva el panel, mira el vídeo y pulsa **Aprobar y exportar**.
5. En **Exportaciones** pulsa **Descargar MP4** de cada red (YouTube Shorts, Instagram Reels, TikTok).

> **No se publica nada por sí solo.** La publicación automática exige configurar cuentas (ver `docs/integrations.md`);
> para empezar, descarga los vídeos y súbelos tú.

Otras formas de abrirlo: `INICIAR_WINDOWS_SIN_CLAUDE.bat` (prueba sin gastar Claude, guiones de ejemplo) y
`INICIAR_WINDOWS_MOVIL.bat` (desde el iPhone, ver `docs/MOVIL.md`).

## Qué instala y dónde
| Qué | Dónde | Para qué |
|---|---|---|
| Python 3.12 | Tu usuario (`%LOCALAPPDATA%\Programs\Python`) | Ejecuta el programa |
| Git para Windows | Tu usuario (`%LOCALAPPDATA%\Programs\Git`) | Lo necesita Claude Code en Windows |
| FFmpeg | `tools\ffmpeg` dentro de la carpeta | Motor de vídeo |
| Voz (eSpeak NG) | `tools\espeak-ng` dentro de la carpeta | Locución local |
| Claude Code | `%USERPROFILE%\.local\bin` | La inteligencia (tu sesión de Claude Pro) |
| YTAUTO | `.venv` dentro de la carpeta | El programa |

## Qué esperar
- Las **imágenes serán fondos abstractos** salvo que pongas las tuyas, con licencia, en `library\images` (ver `docs/local_engine.md`).
- La **voz es robótica** (eSpeak). Hay una voz gratuita mejor (Piper), con un paso avanzado.
- Un vídeo de 60 s tarda **unos 4–8 minutos** y usa **unas 6–9 llamadas** de tu cuota de Claude.

## Problemas frecuentes
| Qué ves | Qué hacer |
|---|---|
| «Windows protegió su PC» | **Más información → Ejecutar de todos modos** |
| «Este archivo se está ejecutando desde dentro del ZIP» | Extrae el ZIP primero (Paso 1) |
| «Tu Windows es demasiado antiguo» | Actualiza a Windows 10 versión 1803 o posterior |
| Se queda parado más de 40 min o termina con `[FALLO]` | Ciérralo, **reinicia el PC** y vuelve a abrir `INSTALAR_WINDOWS.bat` |
| `[FALLO]` en Python o FFmpeg | Comprueba tu conexión a Internet y repite; si tu empresa bloquea descargas, pide permiso a tu administrador |
| `DIAGNOSTICO_WINDOWS.bat` marca algo en rojo | Debajo te dice cómo arreglarlo; casi siempre es repetir `INSTALAR_WINDOWS.bat` |
| El navegador no abre nada | Escribe `http://127.0.0.1:8000` (si el 8000 estaba ocupado, la ventana negra indica otro número) |
| Windows pregunta por el **Firewall** | **Permitir acceso** (solo redes privadas) |
| Un proyecto se queda en **«Bloqueada»** | Abre el proyecto: el motivo aparece arriba; tras arreglarlo pulsa **Reintentar** |
| «Límite de uso» de Claude | Es el límite de tu plan Pro: espera a la hora indicada y pulsa **Reanudar** en «Modelos Claude» |
| «Claude no está autenticado» | Abre `INSTALAR_WINDOWS.bat` otra vez y acepta iniciar sesión, y pulsa **Reanudar** en «Modelos Claude» |
| Quieres empezar de cero | Cierra el programa y borra la carpeta `data` (se pierden proyectos y ajustes) |

## Actualizar o desinstalar
- **Actualizar:** descarga el ZIP nuevo, extráelo en otra carpeta y copia dentro tus carpetas `data`, `projects` y `library`;
  ejecuta `INSTALAR_WINDOWS.bat` otra vez.
- **Desinstalar:** borra la carpeta de YTAUTO y el icono del Escritorio. Python, Git y Claude Code se quitan desde
  **Configuración → Aplicaciones** si quieres.

## Qué está comprobado y qué no
La lógica de instalación en Python y sus pruebas, los comandos de descarga y la revisión estática del `.bat` (sin
PowerShell, sin saltos rotos, esperas correctas) están comprobados en Linux. **El `.bat` no se ha ejecutado nunca en un
Windows real**: las descargas (Python, Git, FFmpeg, voz) y el instalador de Claude Code se hacen desde sus páginas
oficiales y pueden cambiar de dirección con el tiempo. Si algo falla, abre `DIAGNOSTICO_WINDOWS.bat`
y manda lo que muestra a quien te pasó el programa.
