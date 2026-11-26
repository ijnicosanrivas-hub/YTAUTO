# Cuentas conectadas: ElevenLabs (voz) y Higgsfield (vídeo e imagen)

Pantalla **Recursos → Cuentas conectadas**. Nada de lo que se vincula aquí autoriza gastos por sí solo: cada vídeo
pide su autorización (`spend:<cuenta>`) en el último paso de «Nuevo vídeo», con un tope en euros. También existe la
autorización permanente, que se activa a mano y queda registrada (regla 3 de `CLAUDE.md`).

## ElevenLabs (plan Creator)
1. En elevenlabs.io → Developers → API Keys, crea una clave.
2. Pégala en la tarjeta de ElevenLabs con el precio y los créditos del plan (Creator: 121.000 créditos, 22 $/mes ≈ 20 €).
   La clave se comprueba contra `GET /v1/user/subscription` antes de guardarse; una clave mala no se guarda.
   Se guarda cifrada en `data/` (fuera de git).
3. Elige la voz y el modelo (Multilingual v2: 1 crédito/carácter; Flash v2.5: 0,5).

Antes de cada locución se lee el saldo real; si no llega (más la reserva), se usa la voz gratuita y **nunca se entra
en uso extra facturable**. Si el saldo no se puede leer, no se sintetiza (falla cerrado). `commercial_use` se toma del
plan real (el gratuito no permite uso comercial).

## Higgsfield (plan Plus)
Dato oficial que lo condiciona todo: **los créditos del plan no sirven para la API de Higgsfield** (es otro producto
con saldo prepago en dólares). Solo la **CLI oficial** y el MCP usan los créditos del plan, sin clave de API, con tu
sesión, a tarifa estándar (lo «Unlimited» solo vale en la web). Fuentes:
- https://higgsfield.ai/creator-hub/help-center/integrations/what-is-the-higgsfield-api
- https://higgsfield.ai/creator-hub/help-center/integrations/how-do-i-access-higgsfield-via-cli

Por eso YTAUTO ejecuta la CLI (`higgsfield generate create … --wait --json`), igual que hace con `claude -p`. Nunca
lee ni copia la sesión de la CLI.

1. **Instalar**: descarga la CLI publicada por Higgsfield (GitHub Releases) a `tools/higgsfield/` y comprueba su
   SHA-256 con el manifiesto del paquete npm oficial `@higgsfield/cli`. Sin Node ni administrador.
   También vale una CLI ya instalada (`higgsfield` en el PATH).
2. **Iniciar sesión**: abre una ventana en el PC con `higgsfield auth login`; entras con tu cuenta y vuelves.
3. **Elegir uso**: clips de vídeo (Kling 3.0 Turbo económico o Seedance 2.5 máxima calidad, resolución, máximo de
   clips por vídeo) y/o imágenes (Nano Banana 2, GPT Image 2.6, Soul V2). Precio del plan (Plus: 59 €/1.200 créditos).

Freno: una generación a la vez; antes de cada una se lee el saldo (`account status`) y si no cubre coste + reserva no
se genera. El coste real de cada clip se anota como saldo antes − saldo después. Si un clip no está autorizado, supera
el tope o no hay saldo, la escena usa una imagen y el vídeo sigue.

Límites honestos: el formato exacto de la salida JSON de la CLI no está documentado públicamente; la lectura es
tolerante y está probada con una CLI simulada, pero la primera prueba real debe hacerse con un vídeo corto mirando el
saldo en higgsfield.ai. Los términos de uso comercial de lo generado se consultan en Higgsfield (no se afirma
`commercial_use`).

Código: `backend/ytauto/providers/higgsfield.py`, `providers/video/higgsfield.py`, `providers/image/higgsfield.py`,
`providers/voice/elevenlabs.py`, `api/accounts_api.py`, `frontend/src/pages/Accounts.tsx`. Pruebas:
`tests/test_higgsfield.py`, `tests/test_accounts.py`, `tests/test_integrations.py` (siempre con servicios simulados).

## Música: Biblioteca de audio de YouTube Studio (y ElevenLabs solo para la voz)
ElevenLabs se usa **únicamente para la voz** (no hay adaptador de música ni efectos de ElevenLabs; lo comprueba
`tests/test_youtube_music.py`). La música, cuando se elige en «Nuevo vídeo» → **Música: Biblioteca de audio de YouTube
Studio**, sale de pistas de esa biblioteca.

Dato oficial (Ayuda de YouTube, https://support.google.com/youtube/answer/3376882):
- La biblioteca está solo en YouTube Studio (youtube.com/audiolibrary); cada pista se descarga a mano (MP3). **No hay
  API**: YTAUTO no entra en tu cuenta ni descarga nada solo.
- Es música «copyright-safe»: Content ID no la reclama y se puede monetizar en YouTube.
- Las pistas Creative Commons exigen el crédito del artista en la descripción (texto copiado de «License type»).
- YouTube **no garantiza** el uso fuera de su plataforma («can't give legal guidance… off the platform»).

Cómo funciona:
1. **Recursos → Música de YouTube**: arrastras los MP3 descargados, indicas género y ánimo (filtros de la biblioteca)
   y, si es Creative Commons, pegas el crédito (obligatorio para importarla). Se guardan en
   `library/youtube_audio_library/` con su ficha `.json` (fuera de git).
2. En «Nuevo vídeo» eliges la música (Automática / Biblioteca de audio de YouTube Studio / Sin música) y, opcional, un
   estilo («épica y tensa»…). El agente de sonido elige la pista cuyo ánimo encaja (tensa → Dark/Dramatic, alegre →
   Happy/Bright…). Si no hay pistas importadas, usa la música automática y lo anota.
3. Si la pista exige crédito, el publicador lo añade solo a la descripción de cada plataforma.
4. Los paquetes de TikTok e Instagram llevan un aviso (en la app y en su `LEEME.txt`) para revisar la licencia de la
   pista antes de publicar fuera de YouTube.

La biblioteca se registra detrás de la música procedural: la música automática nunca la usa si no se pide.
Código: `providers/music/youtube_audio_library.py`, `api/music_api.py`, `frontend/src/pages/YouTubeMusic.tsx`.


## ElevenLabs avanzado: lo eliges tú (Cuentas conectadas → «¿Qué quieres usar de ElevenLabs?»)
Cuestionario con cada capacidad, su coste oficial en créditos y si tu plan la incluye. Lo que marques se ofrece en
cada «Nuevo vídeo» (ahí puedes quitarlo solo para ese vídeo). Datos oficiales (docs y precios de ElevenLabs, nov. 2026):

| Capacidad | Cómo se usa en YTAUTO | Coste |
|---|---|---|
| Interpretación emocional (Eleven v4) | El agente de voz marca cada frase con etiquetas (`[whispers]`, `[sighs]`, «…», MAYÚSCULAS) sin cambiar palabras y narra con Eleven v4 por Text to Dialogue | 1 crédito/carácter |
| Subtítulos palabra a palabra | Tiempos por carácter que devuelve ElevenLabs con el audio → cada palabra exacta | sin coste extra |
| Diálogos con varias voces | El guionista escribe «papel: frase»; se generan con las voces del canal en una sola petición (≤ 2.000 caracteres, ≤ 10 voces) | 1 crédito/carácter |
| Efectos de sonido IA | Solo los efectos narrativos descritos en el guion (en inglés); los de montaje siguen siendo locales | 200 por efecto (40/s con duración fija) |
| Voces por canal | Narrador, protagonista, antagonista, secundario y documental por canal; viajan con cada proyecto | sin coste |
| Diseño de voces | Descripción → 3 muestras (Voice Design) → guardar como papel del canal | lo indica ElevenLabs |
| Voice Changer | En «Guion», subes tu grabación de una escena y suena con la voz del canal (equivalente por API de Actor Mode) | 1.000 por minuto |
| Clonación profesional (PVC) | Se crea en la web de ElevenLabs (plan Creator) y luego se elige aquí como voz | incluida en Creator |
| Studio: multipista y Actor Mode | Sin API: el montaje multipista ya lo hace YTAUTO con FFmpeg | — |

Si Claude no puede preparar la interpretación, se narra sin etiquetas (nunca bloquea). Las voces que no entienden
etiquetas (eSpeak, Piper) reciben el texto plano. El freno de saldo sigue activo y los efectos IA piden su propia
autorización de gasto por vídeo (`spend:elevenlabs_sfx`, máximo 6 por vídeo por defecto).
Código: `core/audio_features.py`, `providers/voice/elevenlabs.py`, `providers/sound/elevenlabs_sfx.py`,
`agents/voice.py`, `api/accounts_api.py`, `frontend/src/components/AudioSetup.tsx`.
