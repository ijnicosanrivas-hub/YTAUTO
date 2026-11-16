# ADR 0004 — Ningún gasto ni publicación sin autorización

**Estado**: aceptado

## Decisión
Toda operación de un proveedor con `is_paid=True` requiere: presupuesto disponible
(proyecto, mes y proveedor) y autorización explícita del usuario. El fallback nunca salta a
un proveedor de pago sin ella; en su lugar la tarea queda `blocked`. Publicar requiere una
autorización por vídeo y plataforma, con caducidad.
