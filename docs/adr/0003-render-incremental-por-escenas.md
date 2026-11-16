# ADR 0003 — Render incremental por escenas con FFmpeg

**Estado**: aceptado

## Decisión
Cada escena se renderiza a un segmento cuyo nombre deriva del hash de sus entradas. El
vídeo maestro se ensambla a partir de segmentos. Rehacer una escena solo regenera su
recurso/voz y su segmento, y repite ensamblado y mezcla.

Se genera un máster limpio (sin subtítulos grabados) y las versiones por plataforma
aplican subtítulos con sus márgenes de seguridad y se recodifican, sin regenerar recursos.
