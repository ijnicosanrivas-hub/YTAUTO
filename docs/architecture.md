# Arquitectura — Fábrica multiagente de vídeos cortos

## Visión general

```
React/TS + React Three Fiber ──REST / WebSocket──► FastAPI
                                                     │
        Orquestador (Agente Jefe) ── grafo de 18 fases + puertas de aprobación + presupuesto
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

## Flujo de producción (18 fases)

| # | Fase | Agente | Tipo |
|---|---|---|---|
| 1 | intake | chief | auto |
| 2 | project_setup | chief | auto |
| 3 | creative_direction | director | claude |
| 4 | script | scriptwriter | claude |
| 5 | script_approval | — | aprobación (desactivable en modo automático) |
| 6 | scene_prep | resources | claude |
| 7 | resource_generation | resources | media |
| 8 | voice | voice | media (+claude ligero) |
| 9 | edit | editor | media |
| 10 | sound | sound | media |
| 11 | render | editor | media |
| 12 | review | reviewer | media + claude |
| 13 | corrections | chief | auto |
| 14 | final_approval | — | aprobación |
| 15 | exports | publisher | media |
| 16 | publish_prep | publisher | claude (haiku) |
| 17 | publish | publisher | aprobación + integración |
| 18 | report | chief | auto |

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
gasto y la cadena de alternativas (fallback).

## Persistencia

SQLite (WAL) + ficheros por proyecto en `projects/<id>/{planning,scripts,resources,voice,
scenes,sound,review,exports,reports}` y `memory.json` con resúmenes entre fases.

## Medios

FFmpeg es el motor principal: cada escena se renderiza a `scenes/sNN.mp4` con nombre
derivado del hash de sus entradas (render incremental), se ensamblan con `xfade`/concat,
se mezcla audio (ducking con `sidechaincompress`, `loudnorm` a −14 LUFS / −1 dBTP) y se
aplican subtítulos ASS por perfil de plataforma.
