# Instalar YTAUTO en Windows (paso a paso, sin saber nada)

Tiempo total: **30–45 minutos** la primera vez, casi todo esperando. Solo se hace una vez.

## Antes de empezar
Necesitas:
- Un PC con **Windows 10 (versión 1809 o posterior) o Windows 11**, de 64 bits.
- **8 GB de memoria** (recomendado) y **10 GB libres** en el disco.
- **Internet**.
- Tu cuenta de **Claude Pro** (la de claude.ai).
- Tener abierta tu sesión de **GitHub**, porque descargarás el programa de ahí.

> **Qué es esto.** YTAUTO es un programa que se instala en tu PC y se usa desde el navegador (Chrome, Edge…).
> No se usa desde el móvil. Mientras trabaja, el PC debe estar encendido.

---

## Paso 1 · Descargar el programa
1. Abre en el navegador la página del proyecto en GitHub: **github.com/ijnicosanrivas-hub/ytauto**
2. Arriba a la izquierda hay un botón que pone **`main`** (o el nombre de una rama). Púlsalo, escribe
   **`claude/multiagent-audiovisual-system-hv0bwv`** y elige esa rama.
3. Pulsa el botón verde **`<> Code`** → **`Download ZIP`**.
4. Cuando termine, busca el archivo en tu carpeta **Descargas**. Haz clic derecho → **Extraer todo…**
5. En «Seleccionar un destino» escribe **`C:\YTAUTO`** y pulsa **Extraer**.

> **Importante:** usa una carpeta corta como `C:\YTAUTO`. Evita el Escritorio, OneDrive o rutas con tildes y espacios.

Al terminar, dentro de `C:\YTAUTO` (a veces dentro de otra carpeta con el nombre de la rama: entra en ella hasta ver
`INSTALAR_WINDOWS.bat`) deberías ver estos archivos: `INSTALAR_WINDOWS.bat`, `INICIAR_WINDOWS.bat`,
`DIAGNOSTICO_WINDOWS.bat`.

## Paso 2 · Instalar
1. Haz **doble clic** en **`INSTALAR_WINDOWS.bat`**.
2. Windows puede mostrar una pantalla azul que dice **«Windows protegió su PC»**. Es normal (el archivo no está
   firmado). Pulsa **«Más información»** y después **«Ejecutar de todos modos»**.
3. Se abre una ventana negra. Si Windows pregunta si permites cambios en el equipo, pulsa **«Sí»**.
4. **Espera.** Va instalando uno por uno: Python, FFmpeg, Node.js, eSpeak NG y Claude Code. Verás mucho texto;
   es normal. Tarda **15–30 minutos**. No la cierres.
5. Termina con **«INSTALACION TERMINADA»**. Pulsa una tecla para cerrar.

Si algo falla, mira «Problemas frecuentes» más abajo.

## Paso 3 · Iniciar sesión en Claude (una sola vez)
1. Pulsa la tecla **Windows**, escribe **`powershell`** y abre **Windows PowerShell**.
2. Escribe **`claude`** y pulsa **Intro**.
3. Se abrirá el navegador: inicia sesión con tu cuenta de **Claude Pro** y autoriza. (Si te pregunta por el tema de
   colores o la confianza en la carpeta, acepta lo que propone con **Intro**.)
4. Cuando vuelvas a la ventana y veas el cursor de Claude, escribe **`/exit`** y pulsa **Intro**. Cierra la ventana.

## Paso 4 · Comprobar que todo está bien (recomendado)
Haz doble clic en **`DIAGNOSTICO_WINDOWS.bat`**. Debe terminar con **«Todo listo para producir videos»** y todas las
líneas en **[OK]**. Si alguna dice **[FALLO]**, debajo te dice **cómo arreglarlo**.

## Paso 5 · Usarlo
1. Haz doble clic en **`INICIAR_WINDOWS.bat`**. Se abre el navegador con la **Sala de producción**
   (dirección `http://127.0.0.1:8000`). Si no se abre, escribe esa dirección tú en el navegador.
2. **No cierres la ventana negra** mientras lo uses. Para apagarlo, ciérrala.
3. Pulsa **Proyectos → + Nuevo vídeo**. Escribe solo la **Temática** (por ejemplo, «por qué los flamencos son rosas»),
   deja el modo **Automático** y pulsa **Crear y producir**.
4. Cuando el guion esté listo aparece un recuadro naranja **«Panel de aprobación»**: léelo en la pestaña **Guion** y
   pulsa **Aprobar guion**.
5. Espera unos **4–8 minutos**. Cuando vuelva a aparecer el panel naranja, mira el vídeo en la pestaña **Vídeo**
   y pulsa **Aprobar y exportar**.
6. En la pestaña **Exportaciones** pulsa **Descargar MP4** para cada red (YouTube Shorts, Instagram Reels, TikTok).
   También quedan guardados en `C:\YTAUTO\projects\…\exports\`.

> **No se publica nada en tus redes por sí solo.** La publicación automática exige configurar cuentas y tokens
> (ver `docs/integrations.md`); para empezar, descarga los vídeos y súbelos tú. En cada exportación hay también una
> carpeta `manual` con el vídeo y los textos listos para copiar.

### Usarlo desde el iPhone
Abre **`INICIAR_WINDOWS_MOVIL.bat`** en lugar de `INICIAR_WINDOWS.bat` y sigue `docs/MOVIL.md`.

### Probar sin gastar nada de Claude
Haz doble clic en **`INICIAR_WINDOWS_SIN_CLAUDE.bat`**. Funciona igual pero con guiones de ejemplo muy simples; sirve
para comprobar que el PC produce vídeos.

---

## Qué esperar (para no llevarte sorpresas)
- Las **imágenes serán fondos abstractos de colores**. Para tener imágenes reales debes poner **las tuyas, con
  licencia**, en `C:\YTAUTO\library\images` (cada una con un archivo `.json` que indique su licencia; ver
  `docs/local_engine.md`).
- La **voz es robótica** (eSpeak). Hay una voz mucho mejor y gratuita (Piper), pero requiere un paso avanzado
  (`docs/local_engine.md`).
- Un vídeo de 60 s tarda **unos 4–8 minutos** en un PC normal.
- Gasta **unas 6–9 llamadas de tu cuota de Claude** por vídeo (el panel «Modelos Claude» las cuenta).

## Problemas frecuentes
| Qué ves | Qué hacer |
|---|---|
| «Windows protegió su PC» | **Más información → Ejecutar de todos modos** (Paso 2) |
| El instalador dice que no encuentra `winget` | Actualiza Windows, o instala **«Instalador de aplicación»** desde la tienda de Microsoft, y repite |
| Termina con errores o se queda parado más de 40 min | Ciérrala, **reinicia el PC** y vuelve a abrir `INSTALAR_WINDOWS.bat` (retoma lo que falte) |
| `DIAGNOSTICO` marca **[FALLO] FFmpeg / Voz / Python** | Abre `INSTALAR_WINDOWS.bat` otra vez; si persiste, cierra todas las ventanas negras y repite |
| **[FALLO] Claude Code** | Abre PowerShell y escribe `irm https://claude.ai/install.ps1 \| iex`, luego repite el Paso 3 |
| El navegador no abre nada | Escribe `http://127.0.0.1:8000` (si el 8000 estaba ocupado, la ventana negra indica otro número) |
| Windows pregunta por el **Firewall** al iniciar | Pulsa **«Permitir acceso»** (solo en redes privadas) |
| El proyecto se queda en **«Bloqueada»** | Abre el proyecto: el motivo aparece arriba; tras arreglarlo pulsa **Reintentar** |
| Dice que has llegado al **límite de uso** de Claude | Es el límite de tu plan Pro: espera a la hora que indica y pulsa **Reanudar** en «Modelos Claude» |
| Dice que Claude **no está autenticado** | Repite el Paso 3 y pulsa **Reanudar** en «Modelos Claude» |
| Quieres empezar de cero | Cierra el programa y borra la carpeta `C:\YTAUTO\data` (se pierden proyectos y ajustes) |

## Actualizar o desinstalar
- **Actualizar:** descarga el ZIP nuevo, extráelo en otra carpeta y copia dentro tus carpetas `data`, `projects` y
  `library`. Ejecuta `INSTALAR_WINDOWS.bat` otra vez.
- **Desinstalar:** borra la carpeta `C:\YTAUTO`. Los programas que instaló (Python, FFmpeg, Node.js, eSpeak NG, Claude)
  se quitan desde **Configuración → Aplicaciones**.

## Qué está comprobado y qué no
Esta versión se desarrolló y probó en **Linux**. Para Windows se adaptó y comprobó lo que se puede reproducir allí
(rutas con espacios, tildes y `:`, codificación de textos, ausencia de la fuente Inter, instalación desde cero a partir
del ZIP), pero **no se ha ejecutado en un Windows real**. Los scripts de PowerShell y los `.bat` se han revisado
estáticamente, no ejecutado. Los identificadores de `winget` proceden de fuentes comunitarias. Si algo falla, ejecuta
`DIAGNOSTICO_WINDOWS.bat` y guarda el texto que muestra: dice exactamente qué falta.
