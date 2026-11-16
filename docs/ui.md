# Interfaz: sala de producción

## Arranque
```bash
# Una vez: dependencias e interfaz compilada
pip install -e ".[dev]" && pip install websockets
cd frontend && npm install && npm run build && cd ..

# Servidor (API + WebSocket + interfaz + worker de producción) en http://127.0.0.1:8000
python -m ytauto.api.server                # con Claude Code (sesión Pro)
python -m ytauto.api.server --offline      # sin Claude (borradores locales, para probar)
```
Desarrollo del frontend con recarga en caliente: `cd frontend && npm run dev` (http://localhost:5173,
con proxy de `/api` y `/ws` al servidor en :8000).

Seguridad: escucha solo en `127.0.0.1`. Para exponerlo en red es obligatorio definir
`YTAUTO_API_TOKEN` (cabecera `Authorization: Bearer …` o `?token=` en WebSocket/medios).

## Secciones
| Sección | Qué muestra / permite |
|---|---|
| Dashboard | KPIs, decisiones pendientes, estado de los 9 agentes, actividad en directo |
| Proyectos | Lista con avance real; formulario de creación (automático / personalizado) |
| Proyecto | Fases y reintentos, **panel de aprobación** (guion, final, publicación por plataforma, gasto), guion, plan, visor de vídeo, rehacer escenas, revisión con puntuación, exportaciones, actividad y memoria |
| Sala de producción | Escena 3D (React Three Fiber): jefe en el centro, 8 agentes en anillo, conexiones de control y de entrega. Con el tema Gotham: Batcueva de ladrillos y minifiguras animadas según el estado real (`docs/style_bible.md`); con `YTAUTO_THEME=classic`, nodos geométricos |
| Agentes | Fases de cada agente, ejecuciones, errores, llamadas a Claude, último resultado |
| Biblioteca | Recursos de todas las producciones con proveedor y licencia |
| Proveedores | Añadir, credenciales (nunca se muestran completas), parámetros, probar conexión, principal/alternativo, activar/desactivar |
| Presupuesto | Gasto mensual, límites, aviso, registro de consumo por proveedor |
| Modelos Claude | Modelo por agente (alias), concurrencia, pausa por límite de uso y reanudación |
| Exportaciones | Ficheros por plataforma y estado de publicación |
| Historial | Registro persistente de eventos con filtro |

## Actividad real, no decorativa
La sala se alimenta exclusivamente de eventos del orquestador (`agent.started`, `agent.progress`,
`llm.call`, `agent.finished`, `phase.status`…) recibidos por WebSocket:
- un nodo pulsa solo si su agente está realmente en ejecución;
- una conexión se ilumina y transporta un pulso solo si hubo un evento real en sus extremos en los
  últimos 2,5 s;
- tras un reinicio, el estado se reconstruye desde el registro persistido y nada aparece "en
  ejecución" si no lo está.

## Robustez del servidor
- WebSocket: detecta desconexiones (no bloquea el apagado). Apagado ordenado con límite de 10 s.
- Worker: leases de 2 min renovados por latido mientras la tarea trabaja e identificador único por
  proceso; si el proceso muere a mitad, la tarea vuelve a la cola en minutos y la fase se reanuda.
