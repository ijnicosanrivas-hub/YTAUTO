# Canales, licencias y entrevista del director

## Cuatro canales en paralelo
`config/channels.yaml` define los canales: **General** (perfil `gotham`, la Baticueva), **GTA VI** (`gta6`, Vice City),
**YouTube Kids** (`kids`, la casa de juegos) y **Deportes** (`deportes`, el estadio). Cada proyecto pertenece a un canal
(`ProjectSpec.channel`). Cada canal tiene su propio tablero de agentes en vivo (`api/board.py: ChannelBoards`), así que los
nueve agentes de cada canal trabajan a la vez sin pisarse.

En la interfaz, arriba a la izquierda está la cara del director del canal activo. Al pulsarla se despliegan los demás
canales; elegir uno cambia de canal y abre el panel. El panel general muestra los 4 canales a la vez. Las pantallas de
gestión tienen una estética neutra común; solo la sala de agentes es inmersiva según el perfil.

## Licencias de Claude por canal
Página **Licencias**. Cada licencia pertenece a un canal y puede ser:
- **Sesión de Claude Code** (suscripción): tiene su propia carpeta de sesión (`data/licencias/<id>`). Se inicia sesión una
  vez con esa cuenta: `set CLAUDE_CONFIG_DIR=<carpeta>&& claude /login` (la página muestra el comando exacto).
- **Clave de API de Anthropic**: se guarda cifrada en `data/` (clave maestra fuera de git) y nunca se devuelve entera.

Reglas (`llm/licenses.py`):
- Cada llamada usa la licencia asignada a ese agente en ese proyecto; si no hay asignación, una licencia disponible de su
  canal; si el canal no tiene licencias, la sesión principal.
- Nunca dos llamadas simultáneas con la misma licencia (un candado por licencia). La concurrencia del carril de Claude es
  el número de licencias activas (máximo 8).
- Si una licencia se agota, se bloquea **solo** el proyecto que la usaba; los demás canales siguen. Se reanuda sola al
  pasar la hora de reinicio, al pulsar «Ya tiene uso disponible» o al asignar otra licencia al agente.
- No hay salto automático a la licencia de otro canal: el préstamo lo decide el usuario en la pantalla de asignación.

Estadísticas: tokens de hoy, 7 y 30 días y del mes, llamadas, entrada/salida/caché, equivalente API (orientativo), uso por
agente, préstamos a otros canales y barras de los últimos 14 días. Las suscripciones no publican un límite en tokens: la
«referencia mensual» la pone el usuario para ver el porcentaje.

## Nuevo vídeo: idea → preguntas del director → licencias → lanzar
1. Escribes la idea en bruto.
2. El director (con la licencia de su canal) hace 5–8 preguntas a medida, siempre con duración y calidad
   (`agents/briefing.py`). Sin Claude, usa un cuestionario base. Las respuestas se guardan en `ProjectSpec.brief` y el
   director las respeta al crear el plan.
3. Eliges la licencia de cada agente entre todo el pool (con avisos de agotada, cerca del límite o prestada).
4. Revisas y lanzas.

## Perfiles inmersivos
- `gotham`: Baticueva con las figuras recortadas del render de Batman.
- `gta6`, `kids`, `deportes`: escenarios procedurales (`frontend/src/minifig/Worlds.tsx`) y personajes 3D propios
  (`avatars.ts`, `Avatar.tsx`), animados con el estado real de cada agente.
- Imagen oficial de un personaje: súbela con `PUT /api/profiles/<perfil>/figures/<agente>` (PNG con fondo transparente
  recomendado) o déjala en `assets/perfiles/<perfil>/<agente>.png`. Sustituye a la figura 3D y a la cara del selector.

## Monitor de tokens (en vivo)
Página **Monitor de tokens**. Por licencia: tokens en la ventana de 5 h (como las suscripciones de Claude), últimos 7 días y
gasto del mes (claves de API), ritmo de los últimos 15 min, cuándo se acaba a ese ritmo, cuándo se libera la ventana,
llamadas en curso y las últimas llamadas. Se actualiza con cada llamada (eventos `license.usage` por WebSocket).

- **Saldo:** Anthropic no publica cuánto le queda a una suscripción; leer el token interno de la sesión para preguntarlo
  está prohibido (regla 2). El saldo se mide contra los límites de cada licencia (**Ajustar límites**: 5 h, semana, $/mes)
  o contra el **límite observado**: lo gastado en la ventana cuando Claude cortó la cuenta.
- **Freno de gasto:** si una licencia alcanza un límite, el enrutador NO llama a Claude: la marca como frenada hasta que
  la ventana deja sitio y solo se para el proyecto que la usaba. Subir el límite la libera al momento.
