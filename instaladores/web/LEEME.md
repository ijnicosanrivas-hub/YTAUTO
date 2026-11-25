# Demostración web (Netlify y bot de Telegram)

Versión estática para enseñar YTAUTO: los 4 canales con sus estilos y una producción simulada. **No produce vídeos ni
guarda nada.** Se publica sola en cada versión como `YTAUTO-web-demo.zip` (ver la portada del repositorio).

## Netlify
- **Arrastrando:** descomprime `YTAUTO-web-demo.zip` y arrastra la carpeta a **app.netlify.com → Sites**.
- **Desde GitHub:** importa este repositorio en Netlify; `netlify.toml` ya trae la configuración
  (`npm run build:demo`, publica `frontend/dist-demo`).

## Bot de Telegram (Mini App)
1. En **@BotFather** abre tu bot (`/mybots`).
2. En **Mini Apps** (o **Bot Settings → Menu Button**) pega la dirección de Netlify con `https://` y el texto del botón.
3. Abre el bot y pulsa el botón junto a la caja de texto.

No compartas el token del bot: para el botón no hace falta.
