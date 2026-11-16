# Investigación LEGO: de dónde salen las medidas

Resumen de lo que se investigó para que las figuras y la Batcueva sean fieles a las piezas reales, **qué se confirmó
y qué no**.

## Fuente principal: biblioteca de piezas LDraw
Las dimensiones salen de los ficheros de piezas oficiales de LDraw (el estándar abierto de modelado LEGO), leídos
directamente: torso `973`, cabeza `3626b`, cadera `3815`, piernas `3816/3817`, brazos `3818/3819` y mano `3820`.
Unidad: **LDU** (1 LDU = 0,4 mm). Mediciones usadas:

| Pieza | Medida | Fuente |
|---|---|---|
| Taco | paso 20 LDU (8 mm), radio 6 LDU (Ø 4,8 mm), alto 4 LDU (1,6 mm) | primitivas LDraw (`stud`, `3626b`) |
| Ladrillo / placa | 24 LDU (9,6 mm) / 8 LDU (3,2 mm) | convención LDraw |
| Torso | 38 LDU ancho abajo (±19), ≈ 28,7 arriba (±14,3), 32 alto, 20 fondo (±10); borde biselado | `973` |
| Cadera | 36 LDU ancho (±18), 6 alto, 20 fondo | `3815` |
| Pierna | 18 LDU ancho, 28 alto, ≈ 20 fondo | `3816` |
| Brazo | radio 6,5 LDU, hombro a ±15,55 y 9 LDU por debajo de la parte superior del torso, **inclinado 9,782°** hacia fuera | `3818` (anotaciones `!HELP`) |
| Mano | pinza en C, Ø exterior 12 LDU | `3820` |
| Cabeza | cilindro con bordes redondeados y taco hueco (radio de taco 6) | `3626b` |

Los ficheros de LDraw se publican con licencia CC BY 2.0; **solo se usaron las medidas** (datos), no se copió su
geometría ni se incluyen sus ficheros.

## Colores
Paleta con los nombres oficiales de LEGO y los valores de las tablas de color de Rebrickable/BrickLink
(Negro `#05131D`, Azul `#0055BF`, Rojo `#C91A09`, Amarillo `#F2CD37`, Verde brillante `#4B9F4A`, Gris azulado claro
`#A0A5A9`, Gris azulado oscuro `#6C6E68`…). La búsqueda confirmó explícitamente negro y azul; las fuentes **discrepan
entre sí** en los valores RGB exactos de cada color (incluidas las listas oficiales), así que son aproximaciones.

## Tipografía
El logotipo y la tipografía de marca de LEGO son **propietarios**: no existe una fuente libre idéntica. Se usan
fuentes libres de licencia abierta (SIL OFL) de carácter redondeado y macizo:
**Lilita One** (títulos, botones, números) y **Nunito** (texto), empaquetadas con la aplicación (funcionan sin Internet).
No se usan fuentes de «réplica del logo» de procedencia dudosa.

## Videojuegos LEGO Batman
La investigación sobre TT Games solo aportó rasgos generales: la Batcueva como centro de mando con referencias a
distintas épocas, ladrillos que reaccionan a la luz y humor visual. **No hay documentación pública de su
técnica de sombreado de tacos y plástico**; el aspecto de la sala es una interpretación propia, no una réplica.

## Lo que NO se pudo confirmar
- Diámetro exacto de la cabeza: LDraw usa radio 13 en la primitiva exterior y 12 en el cuerpo; se usó **12 LDU**
  (≈ 9,6 mm). Un contraste con piezas físicas podría ajustarlo ±1 LDU.
- La altura total resulta 90 LDU (36 mm con taco; sin pelo ni sombrero) y las referencias de BrickArchitect hablan de
  ≈ 40 mm: la diferencia puede deberse a la altura de pierna y cadera acopladas, no medida con una pieza real.
- El número de tacos de la placa redonda 6×6 (24) sigue la misma regla que la 4×4 (12, confirmada); no se verificó
  contra una pieza real.

Uso personal, no distribuible. No se incluyen logotipos, ficheros de modelos ni imágenes de terceros.
