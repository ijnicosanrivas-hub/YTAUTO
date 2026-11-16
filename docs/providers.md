# Proveedores intercambiables

Los agentes **nunca** llaman a un proveedor concreto: usan `ProviderGateway`
(`invoke` para operaciones que pueden costar dinero, `query` para consultas gratuitas).
La pasarela real (`RegistryGateway`) resuelve qué proveedor responde según el
**Provider Registry** guardado en la base de datos.

## Categorías e interfaces (`ytauto/providers/interfaces`)
| Categoría | Interfaz | Operaciones |
|---|---|---|
| image | `ImageGenerationProvider` | `generate(ImageRequest) -> MediaAsset` |
| video | `VideoGenerationProvider` | `generate(VideoRequest) -> MediaAsset` |
| tts | `TextToSpeechProvider` | `list_voices`, `synthesize(TTSRequest)` |
| music | `MusicGenerationProvider` | `get_track(MusicRequest)` |
| sfx | `SoundEffectsProvider` | `get_effect(SFXRequest)` |
| subtitle | `SubtitleProvider` | `align(SubtitleRequest) -> [SubtitleCue]` |
| rendering | `VideoRenderingProvider` | `render_scene`, `assemble`, `mix_audio`, `finalize`, `probe`, `extract_frame` |
| storage | `StorageProvider` | `put`, `get`, `exists`, `delete`, `public_url` |
| publishing | `PublishingProvider` | `check_requirements`, `publish` |

Todas devuelven el modelo interno común `MediaAsset` (ruta, tipo, duración, resolución,
licencia, coste, proyecto, escena…), sea cual sea el proveedor.

## Escribir un adaptador
```python
from ytauto.providers.interfaces import TextToSpeechProvider, TTSRequest, Voice
from ytauto.core.models import AssetKind, License, MediaAsset
from ytauto.core.errors import ProviderError

class MiVozProvider(TextToSpeechProvider):
    """Motor de voz X."""
    name = "mi_voz"                 # identificador único del adaptador
    display_name = "Mi Voz"
    is_paid = True                  # activa presupuesto y autorización de gasto
    is_local = False
    required_credentials = ["api_key"]
    default_params = {"model": "standard"}   # parámetros editables desde el panel

    def estimate_cost(self, operation, request):
        ...                         # CostEstimate(amount_eur=..., units=..., unit_name="chars")

    def list_voices(self, language=None): ...
    def synthesize(self, request: TTSRequest) -> MediaAsset:
        # usar self.credentials["api_key"] y self.params["model"]
        # errores: raise ProviderError(self.name, "msg", transient=True|False, retry_after_s=...)
        ...
```
Dónde colocarlo (se descubre automáticamente):
1. `backend/ytauto/providers/<categoría>/<archivo>.py`, o
2. un paquete externo con entry point `ytauto.providers` (`pip install`), sin tocar este repo.

## Sustituir un proveedor (p. ej. otro motor de voz)
1. Instalar/añadir el adaptador.
2. `python -m ytauto providers add mi_voz` y `python -m ytauto providers set-key mi_voz`
   (la clave se pide oculta y se guarda cifrada).
3. `python -m ytauto providers test mi_voz` → ejecuta la batería de contrato
   (los de pago se omiten para no generar costes salvo petición explícita).
4. `python -m ytauto providers primary tts mi_voz`.
5. Seguir produciendo. No se modifica ningún agente ni el orquestador
   (lo demuestra `tests/test_provider_swap.py`).

## Fallback, presupuesto y autorización
- Cadena por categoría: principal + alternativos activos en orden de prioridad; el proyecto
  puede indicar un proveedor preferido (`preferred_providers`).
- Si un proveedor falla (o tiene un rate limit activo) se prueba el siguiente.
- **Un proveedor de pago solo se usa si** el gasto está autorizado (`spend:<proveedor>` por
  proyecto, o autorización global) **y** cabe en los presupuestos: proyecto, mensual global,
  mensual del proveedor y nº de generaciones. Aviso al 80 %.
- El fallback nunca salta a un proveedor de pago sin autorización. Si no queda alternativa,
  la fase queda `blocked` con el motivo y el coste estimado, hasta que el usuario decida.
- Cada operación de pago queda en `cost_ledger` (estimado → real). Ningún gasto se hace en
  pruebas: los tests usan proveedores simulados.

## Credenciales
Cifradas con Fernet; clave maestra en `YTAUTO_MASTER_KEY` o `data/secrets/master.key` (600,
fuera de git). La interfaz y la CLI solo muestran `••••abcd`. Los logs ocultan claves.
