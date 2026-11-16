# Plataformas: Instagram Reels, YouTube Shorts y TikTok

Los requisitos de cada plataforma viven en `config/platforms/*.yaml` (perfiles actualizables).
Cada perfil indica **qué está verificado con documentación oficial** (`verified_at`, `sources`) y
**qué no** (`unverified`). Última verificación: **2026-11-16**.

> Cómo se verificó: se consultó la documentación oficial mediante búsqueda web; las páginas no se
> pudieron abrir directamente desde el entorno de desarrollo. Revisa las fuentes enlazadas en cada perfil
> antes de integrar una publicación real y actualiza `verified_at` cuando lo hagas.

## Resumen verificado
| | YouTube Shorts | Instagram Reels | TikTok |
|---|---|---|---|
| Duración (plataforma) | hasta 3 min | 3 s – 15 min | la mayoría de creadores 3 min (límite real por creador) |
| Contenedor | — | MP4/MOV, `moov` al principio, **sin listas de edición** | MP4 (recomendado), WebM, MOV |
| Códec vídeo | — | H.264 o HEVC, progresivo, GOP cerrado, 4:2:0 | H.264 (recomendado), H.265, VP8, VP9 |
| FPS | — | 23–60 | 23–60 |
| Audio | — | AAC, ≤48 kHz, mono/estéreo | — |
| Tamaño máx. | — | 300 MB | 4 GB |
| Resolución | 9:16 óptimo (cuadrado/vertical) | anchura ≤1920 px | cada lado 360–4096 px |
| Texto | título ≤100 car.; descripción ≤5000 **bytes**; etiquetas ≤500 car. | pie ≤2200 car.; ≤30 hashtags; ≤20 menciones | pie (campo `title`) ≤2200 unidades **UTF-16** |
| Publicación oficial | API Data v3 + OAuth (fase 9) | URL pública o subida reanudable; ≤100 posts/24 h | sin auditar: solo **privado**, ≤5 usuarios/24 h; el usuario elige la privacidad |

Nuestro producto limita siempre a 45–75 s, dentro del rango de las tres plataformas.

## Lo que NO está verificado (y se marca como tal)
- **Márgenes de seguridad** (`safe_area`, `subtitles.margin_v`): ninguna plataforma publica márgenes para
  contenido orgánico; las fuentes encontradas son de terceros y se contradicen. Se usa una zona central
  conservadora. **Compruébalos en la vista previa de cada app.**
- Tasa de bits recomendada (8 Mbps): decisión propia, no un requisito oficial.
- Límite de hashtags de YouTube (15) y TikTok (10); miniatura de YouTube/Instagram; y TikTok no define
  miniatura propia en lo consultado (por eso no se genera).

## Qué hace el sistema
- **Un máster limpio** (sin subtítulos grabados) y **una exportación por plataforma** a partir del mismo
  máster y la misma mezcla: no se regenera ningún recurso. Si las entradas no cambian, la exportación no se
  vuelve a codificar (caché por huella).
- **Validación de cada exportación** (`core/export_validation.py`) contra su perfil: duración, 9:16,
  resolución, contenedor, códecs, formato de píxel, progresivo, fps, audio, tamaño, tasa de bits, `moov` al
  principio y ausencia de listas de edición. Si falla, la fase se bloquea con el motivo.
- **Instagram sin listas de edición**: FFmpeg las añade por defecto; el perfil de Instagram codifica con
  `-use_editlist 0` y `negative_cts_offsets` (vídeo y audio siguen alineados) y GOP cerrado.
- **Textos medidos como cada plataforma**: bytes UTF-8 (YouTube), UTF-16 (TikTok), hashtags dentro del pie
  (Instagram/TikTok), comillas en etiquetas con espacios (YouTube). Si no caben, se recortan hashtags.
- **Paquete de publicación manual** en `exports/manual/<plataforma>/` (vídeo, miniatura si procede, textos y
  `LEEME.txt` con las limitaciones de la plataforma). Se prepara siempre: la publicación automática solo
  ocurre con autorización expresa y cuando exista una integración.
