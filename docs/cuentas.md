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
