# Integraciones externas (fase 9)

Todos los adaptadores de servicios externos están **desactivados por defecto**: no se registran solos, no
se usan sin credenciales y los de pago necesitan además precio configurado, presupuesto y autorización
de gasto. Los datos de las APIs proceden de su documentación oficial (consultada el 2026-11-16 mediante
búsqueda web; las páginas no se pudieron abrir directamente), y se enlazan abajo.

> **Qué está probado y qué no.** Cada adaptador se prueba contra un servidor HTTP **simulado** que imita el
> flujo documentado (`backend/tests/test_integrations.py`). **Ninguno se ha probado contra una cuenta real**:
> eso solo puedes hacerlo tú con tus credenciales. Úsalos primero con contenido de prueba y visibilidad privada.

## Adaptadores

| Adaptador | Categoría | Coste | Credenciales (se guardan cifradas) |
|---|---|---|---|
| `youtube_data_api` | publicación (YouTube Shorts) | gratis (cuota de API) | `client_id`, `client_secret`, `refresh_token` |
| `instagram_graph_api` | publicación (Instagram Reels) | gratis | `access_token`, `ig_user_id` |
| `tiktok_content_posting_api` | publicación (TikTok) | gratis | `access_token` |
| `elevenlabs` | voz (TTS) | **de pago** | `api_key` + parámetro `price_per_1k_chars_eur` |
| `openai_images` | imágenes | **de pago** | `api_key` + parámetro `price_per_image_eur` |

No hay adaptadores de vídeo generativo (Runway, Kling…): no se verificó su API en esta fase. Se añadirían
igual que estos, implementando `VideoGenerationProvider`.

### Cómo activar uno
1. Panel «Proveedores» → «Añadir proveedor» (o `python -m ytauto providers add <adaptador>`).
2. Introduce las credenciales (nunca se muestran completas) y, si es de pago, el precio en `Parámetros`.
3. «Probar conexión»: hace **una llamada de solo lectura** (token, lista de voces/modelos, información de la
   cuenta). Nunca ejecuta la batería de contrato contra un servicio externo: costaría dinero o publicaría.
4. Hazlo principal en su categoría (publicación: se elige por plataforma automáticamente).

### Proveedores de pago: precio obligatorio
No se encontró una tarifa por defecto fiable y cambia según el plan, así que **sin precio configurado el
adaptador se declara no disponible y nunca se usa**, aunque tengas autorización: el control de presupuesto
no puede quedar ciego. El coste estimado = precio configurado × unidades; el registro de consumo guarda
estimado y real. Además: presupuesto del proyecto/mes/proveedor y autorización `spend:<proveedor>`.

`openai_images`: los nombres de modelo difieren entre las páginas de OpenAI; el parámetro `model` (por defecto
`gpt-image-1`) debe confirmarse en su lista de modelos. Las licencias de lo generado se registran como
`provider-terms` con `commercial_use` desconocido: revisa las condiciones del proveedor.

## Publicación: reglas de seguridad
- **Nada se publica sin autorización expresa** (por plataforma, caduca a las 24 h, se puede revocar).
- **Privado y público son decisiones distintas**: `publish:<plataforma>` autoriza **privado**;
  `publish:<plataforma>:public` autoriza público (la interfaz pide confirmación). Nunca se publica en abierto
  por defecto. La última decisión de cada plataforma manda.
- Si la plataforma no admite la visibilidad autorizada, o la API no permite la acción, se **explica la
  limitación y queda el paquete manual** en `exports/manual/<plataforma>/`.
- **Sin duplicados**: lo ya publicado no se repite al reintentar. Si falla tras haberse enviado el vídeo, el
  error es *no transitorio* (no hay reintento ciego) y el mensaje dice que compruebes la plataforma.
- Si una publicación autorizada falla, la fase queda **bloqueada con el motivo**; lo ya publicado se conserva y
  «Reintentar» solo repite lo pendiente.
- Los secretos nunca aparecen en mensajes de error ni en logs.

### YouTube (YouTube Data API v3)
Flujo: token de acceso (`oauth2.googleapis.com/token`, `grant_type=refresh_token`) → sesión de subida
reanudable (`POST /upload/youtube/v3/videos?uploadType=resumable&part=snippet,status`, cabecera `Location`) →
`PUT` del vídeo. **Limitación documentada**: los proyectos de API sin verificar (creados tras 28-jul-2020) solo
pueden subir vídeos **privados**; el adaptador lee la privacidad que aplica YouTube y lo informa. El
consentimiento OAuth (alcance `youtube.upload`) y la obtención del `refresh_token` los haces tú; no hay flujo
de consentimiento integrado. No sube miniaturas (no verificado).

### Instagram (Graph API, publicación de contenido)
Flujo: `POST /{ig-user-id}/media` (`media_type=REELS`, `video_url`, `caption`) → consulta de
`status_code` hasta `FINISHED` (`IN_PROGRESS`/`ERROR`/`EXPIRED`) → `POST /{ig-user-id}/media_publish`.
Requiere cuenta profesional y que el vídeo esté en una **URL pública https** (Meta lo descarga): el sistema solo
sube el vídeo a un almacenamiento con URL pública si autorizas la publicación **pública**; con el
almacenamiento local no hay URL pública y se usa el paquete manual. La API consultada no ofrece publicación
privada (marcado como no verificado). Límites: 100 publicaciones por API y 400 contenedores cada 24 h.
La versión de la API es el parámetro `api_version` (por defecto `v25.0`).

### TikTok (Content Posting API, Direct Post)
Flujo: consulta del creador (`creator_info/query`: opciones de privacidad) → `video/init` (`FILE_UPLOAD`) →
`PUT` de trozos en orden → `status/fetch` hasta `PUBLISH_COMPLETE`. **Limitación documentada**: los clientes
sin auditar solo publican con `SELF_ONLY` (privado), máx. 5 usuarios/24 h; el `privacy_level` debe estar entre
las opciones del creador. **No verificado**: el formato exacto de la cabecera de cada trozo (se usa
`Content-Range: bytes inicio-fin/total`) y que el flujo cumpla la **auditoría** de TikTok, que además exige
interfaz propia (vista previa, consentimiento, elección de privacidad). Los tokens de acceso caducan; aquí
solo se guarda el que proporciones.

## Qué falta para usar esto en real
- Un flujo de consentimiento OAuth integrado (hoy proporcionas tú los tokens).
- La auditoría de TikTok y la verificación del proyecto de YouTube para poder publicar en abierto.
- Una prueba con cuentas propias de cada plataforma.

## Fuentes
- YouTube: <https://developers.google.com/youtube/v3/docs/videos/insert>,
  <https://developers.google.com/youtube/data/guides/using_resumable_upload_protocol>,
  <https://developers.google.com/identity/protocols/oauth2/web-server>
- Instagram: <https://developers.facebook.com/docs/instagram-platform/content-publishing/>,
  <https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/media>
- TikTok: <https://developers.tiktok.com/docs/en/content-posting-api-reference-direct-post>,
  <https://developers.tiktok.com/docs/en/content-posting-api-media-transfer-guide>,
  <https://developers.tiktok.com/docs/en/content-posting-api-reference-query-creator-info>,
  <https://developers.tiktok.com/docs/en/content-posting-api-reference-get-video-status>
- ElevenLabs: <https://elevenlabs.io/docs/api-reference/text-to-speech/convert>
- OpenAI: <https://developers.openai.com/api/reference/resources/images/methods/generate/>
