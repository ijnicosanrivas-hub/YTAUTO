# Arquitectura — Fábrica multiagente de vídeos cortos

## Visión general

```
React/TS + React Three Fiber ──REST / WebSocket──► FastAPI
                                                     │
        Orquestador (Agente Jefe) ── grafo de 20 fases + puertas de aprobación + presupuesto
                 │                          │
          Cola SQLite                 Bus de eventos ──► WebSocket (actividad real)
          ├─ worker "claude"  (concurrencia 1 por defecto)
          └─ worker "media"   (FFmpeg / TTS local; no consume Claude)
                 │
          9 agentes ──► LLMProvider  (ClaudeCodeCLI | Mock | futuro API)
                 └────► ProviderGateway ──► ProviderRegistry ──► interfaces ──► adaptadores
```

## Capas y reglas de dependencia

| Capa | Paquete | Puede depender de |
|---|---|---|
| Dominio | `ytauto.core` | nada del resto del sistema |
| Inteligencia | `ytauto.llm` | `core` |
| Interfaces de proveedores | `ytauto.providers.interfaces` | `core` |
| Agentes | `ytauto.agents` | `core`, `llm` (interfaz), `providers.interfaces` |
| Orquestador | `ytauto.orchestrator` | `core`, `agents` (por registro), puertos de estado |
| Adaptadores | `ytauto.providers.<categoría>` | `core`, `providers.interfaces`, librerías externas |
| Registro | `ytauto.providers.registry` | `providers.interfaces`, persistencia |
| API | `ytauto.api` | todo lo anterior (composición) |

**Regla innegociable**: `ytauto.agents` y `ytauto.orchestrator` nunca importan un adaptador
concreto (`ytauto.providers.voice.elevenlabs`, etc.). Hay una prueba automática
(`tests/test_architecture.py`) que analiza los imports y falla si se rompe esta regla.

## Motor de inteligencia (Claude con una sola licencia Pro)

- `LLMProvider` es una interfaz. La implementación principal, `ClaudeCodeCLIProvider`,
  invoca el binario oficial `claude` en modo no interactivo:
  `claude -p --agent <agente> --model <alias> --output-format json --json-schema <schema>`.
  Usa la sesión iniciada con `claude /login` (suscripción Pro). No usa la API de Anthropic,
  no extrae tokens y no crea instancias paralelas.
- Los modelos se indican por alias (`sonnet`, `opus`, `haiku`) para no fijar versiones
  obsoletas. `config/models/models.yaml` asigna un modelo a cada agente.
- Errores de límite de uso o de autenticación se traducen a `UsageLimitError` /
  `AuthenticationError`; la cola se pausa y no lanza nuevas tareas Claude.
- Cada llamada se registra (duración, modelo servido, tokens/coste equivalente si el CLI
  los informa) como **indicador** de consumo, no como factura.

## Agentes

Contrato común (`ytauto.agents.base.Agent`):

```python
class Agent(ABC):
    name: str                 # "director", "scriptwriter", ...
    phases: set[str]          # fases que sabe ejecutar
    def run(self, phase: str, ctx: AgentContext) -> AgentResult
```

- `AgentContext` da acceso a la especificación del proyecto, artefactos previos, memoria
  del proyecto, `LLMProvider`, `ProviderGateway` y el directorio de trabajo.
- `AgentResult` contiene estado, artefactos (JSON y ficheros), resumen para la memoria y
  solicitudes de corrección dirigidas.
- Cada agente con salida de Claude define un **JSON Schema** y **criterios de aceptación
  verificados por código**. Si la salida no los cumple, se reintenta una vez con el
  detalle de los fallos; si persiste, la fase queda en `Error`.
- Las instrucciones creativas viven en `.claude/agents/<agente>.md` y se reutilizan en el
  modo interactivo de Claude Code.

## Flujo de producción (20 fases)

| # | Fase | Agente | Tipo |
|---|---|---|---|
| 1 | intake | chief | auto |
| 2 | project_setup | chief | auto |
| 3 | creative_direction | director | claude (estrategia viral: 3 ganchos, ángulo, retención, CTA, títulos, portada) |
| 4 | concept_approval | — | aprobación: el usuario elige gancho y enfoque (desactivable) |
| 5 | script | scriptwriter | claude |
| 6 | script_approval | — | aprobación (desactivable en modo automático) |
| 7 | scene_prep | resources | claude |
| 8 | storyboard_approval | — | aprobación del storyboard antes de gastar créditos (desactivable) |
| 9 | resource_generation | resources | media |
| 10 | voice | voice | media (+claude ligero) |
| 11 | edit | editor | media |
| 12 | sound | sound | media |
| 13 | render | editor | media |
| 14 | review | reviewer | media + claude |
| 15 | corrections | chief | auto |
| 16 | final_approval | — | aprobación |
| 17 | exports | publisher | media |
| 18 | publish_prep | publisher | claude (haiku) |
| 19 | publish | publisher | aprobación + integración |
| 20 | report | chief | auto |

Puertas previas (`OPTIONAL_GATES`): concepto, guion y storyboard. La interfaz las activa por defecto; al rechazar una,
solo se rehace su fase (director, guionista o recursos) con el comentario del usuario. Lo aprobado no se vuelve a
pedir por correcciones internas, y con el storyboard aprobado no se regeneran imágenes en silencio. Los proyectos
creados con versiones anteriores reciben las fases nuevas como ya aprobadas (siguen su flujo original).

Estados: `pending`, `assigned`, `running`, `blocked`, `completed`, `error`, `in_review`,
`approved`. Los proyectos pueden pausarse, reanudarse y cancelarse.

Correcciones: el revisor devuelve `CorrectionRequest(target_agent, phase, scene_index,
reason)`. El jefe invalida solo las fases/escenas afectadas y sus dependientes y vuelve a
ejecutarlas (máximo de rondas configurable).

## Proveedores intercambiables

Nueve interfaces en `ytauto.providers.interfaces`: `ImageGenerationProvider`,
`VideoGenerationProvider`, `TextToSpeechProvider`, `MusicGenerationProvider`,
`SoundEffectsProvider`, `SubtitleProvider`, `VideoRenderingProvider`, `StorageProvider`,
`PublishingProvider`. Todas heredan de `BaseProvider` (`capabilities`, `estimate_cost`,
`health_check`, `is_paid`) y devuelven el modelo común `MediaAsset`.

Los agentes no acceden a proveedores directamente sino a través de `ProviderGateway`,
que resuelve el proveedor principal de la categoría, aplica presupuesto, autorización de
gasto y la cadena de alternativas (fallback). Detalle completo en `docs/providers.md`.

`ytauto.providers.registry`: catálogo (descubrimiento automático + entry points),
`ProviderRegistry` (alta, activación, principal/alternativos, estado, "probar conexión"),
`CredentialVault` (Fernet), `BudgetManager` (límites y libro de costes) y `RegistryGateway`.

## Persistencia

SQLite (WAL) en `data/ytauto.db` (`ytauto.db`): proyectos, fases, aprobaciones, consumo de
Claude, tareas, control de carriles y registro de actividad. Además, ficheros por proyecto en
`projects/<id>/{planning,scripts,resources,voice,scenes,sound,review,exports,reports}` y
`memory.json` con decisiones y resúmenes entre fases (contexto compacto para Claude).

## Cola y worker (`ytauto.queue`)

- Carriles: `claude` (concurrencia 1 por defecto, máx. `max_concurrency` de
  `config/models/models.yaml`), `media` (FFmpeg/TTS local) y `none` (pasos instantáneos).
- Unidad de trabajo: "ejecutar la siguiente fase del proyecto". Índice único parcial:
  como mucho una tarea activa por (proyecto, fase); y una sola en ejecución por proyecto.
- Leases con caducidad y latido: si el proceso muere, la tarea vuelve a la cola y la fase
  interrumpida pasa de `running` a `pending`. Las fases completadas nunca se repiten.
- Límite de uso de Claude → se pausa solo el carril `claude` (lo local sigue). Si Claude
  Code indica la hora de reinicio, se reanuda automáticamente; si no, reanudación manual
  (`python -m ytauto resume-claude`). Sin reintentos a ciegas.
- Errores transitorios de proveedores → reintento con espera creciente (30 s, 2 min, 10 min);
  errores permanentes → fase en `error` y proyecto detenido.

## Operación

- `python -m ytauto new|list|status|run [--forever]|approve|pause|resume|cancel|redo|resume-claude|queue|backup`
- Copias de seguridad: SQLite con la API de backup (consistente en caliente) + `config/` +
  JSON de proyectos, con rotación (10 por defecto). Medios opcionales (`--include-media`).
- Logs con rotación en `data/logs/` y ocultación automática de claves y tokens.

## Medios

FFmpeg es el motor principal: cada escena se renderiza a `scenes/sNN.mp4` con nombre
derivado del hash de sus entradas (render incremental), se ensamblan con `xfade`/concat,
se mezcla audio (ducking con `sidechaincompress`, `loudnorm` a −14 LUFS / −1 dBTP) y se
aplican subtítulos ASS por perfil de plataforma.

## Calidad de vídeo corto
`ytauto.core.retention` calcula con el montaje real (manifiestos de voz y edición) las
comprobaciones de retención que el revisor suma a su nota. Detalle en `docs/local_engine.md`.

## Correcciones tras la revisión
- **Nota no apta** (< umbral, por defecto 75) o fallo crítico: el revisor dirige correcciones a agentes y escenas
  concretas; hasta `max_correction_rounds` (2) rondas; después decide el usuario.
- **Nota apta con incidencias graves de contenido** (guion o recursos, marcadas por Claude): **una** ronda de
  mejora automática, solo si no se gastó ninguna ronda. No se aplica a audio/montaje (repetir un cálculo
  determinista da lo mismo) ni al director (replantear todo es caro). Si el usuario aprobó el guion, el guion
  **no se reescribe en silencio**: esas incidencias quedan visibles en «Revisión». Se desactiva con
  `YTAUTO_FIX_MAJOR_ISSUES=0`. Cuesta unas llamadas más de Claude (guion o prompts, y una nueva revisión).
- El guionista recibe **siempre** las correcciones y el guion anterior (también el comentario del usuario al
  rechazar un guion); antes solo llegaban las correcciones por escena.
