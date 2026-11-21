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

## Diseños oficiales en los que se basan las nueve figuras
**No existe un ranking público de unidades vendidas por figura.** Como aproximación se usó la popularidad entre
coleccionistas (BrickEconomy: figuras sueltas más poseídas del tema Batman 2005-08, donde Batman ocupa los puestos 1, 2 y 5,
el Joker el 4, el Pingüino el 6, Dos Caras el 7 y Catwoman el 8; Nightwing figura en el 5.º puesto de la subtemática
DC Batman) y las descripciones de cada diseño en Brickipedia/BrickLink/Brickset/BrickOwl. Estas páginas se consultaron a
través de resultados de búsqueda (las páginas completas no se pudieron abrir): el detalle de cada estampado es una
**reconstrucción propia** a partir de esas descripciones, no una copia de las figuras.

| Agente | Figura oficial elegida | Rasgos documentados que se reproducen | Confianza |
|---|---|---|---|
| Batman | Batman, traje gris azulado claro con máscara negra (2006) | Traje gris, capucha negra con orejas, capa negra, cinturón y emblema amarillos | Media: el nombre del diseño es el de la lista de popularidad; los estampados son de memoria de la figura |
| El Acertijo | The Riddler (2006) | Torso verde con «?» negro grande en el pecho, cinturón morado, bombín verde, antifaz morado | Alta (Brickipedia) |
| El Joker | The Joker (2006) | Traje morado, pajarita verde, flor en la solapa, pelo verde, cara blanca con sonrisa roja | Alta (Brickipedia) |
| Catwoman | Catwoman (2006) | Torso negro con líneas curvas moradas, cremallera gris, cinturón dorado, orejas de gata | Alta (Brickipedia) |
| Bane | Bane, bat021 (2007) | Máscara de luchador con **ojos rojos grandes y mangueras verdes** (nombre de la pieza en BrickLink) | Media: no se encontró descripción del torso; torso desnudo con arneses es inferido |
| Nightwing | Nightwing (2014/2016) | Torso negro con símbolo azul en V, brazos azules, piernas negras lisas, antifaz y pelo negro de pinchos | Media: las fuentes discrepan en los colores de la versión 2014 |
| El Pingüino | The Penguin (2012) | Chistera negra, cabeza clara con monóculo, cejas grandes y sonrisa amplia, chaqué negro con chaleco naranja y pajarita morada, manos blancas | Alta (Brickipedia/ToyPro) |
| Dos Caras | Two-Face (2006 + 2012) | Pelo partido (negro peinado / blanco de punta), mitad de la cara quemada, traje partido naranja y morado | Media: mezcla dos versiones documentadas |
| Harley Quinn | Harley Quinn, sh0838 (2022) | Traje bicolor rojo y negro, coletas altas alternas, torso y piernas estampados, antifaz arlequín negro | Media: el antifaz arlequín procede de otra variante |

Dos decisiones a tener en cuenta:
- **Batman** pasa a ser **gris** (como la figura más poseída) y no negro, que era la descripción que dabas al principio.
  Cambiarlo a traje negro es una edición de colores en `frontend/src/minifig/variants.ts`.
- Los modelos son procedurales: reproducen colores y estampados, no el molde exacto de cada pieza (por ejemplo, el
  pelo del Joker o el sombrero del Pingüino son aproximaciones de las piezas reales).

## Actualización: imagen de referencia del último videojuego
Más tarde se proporcionó una imagen del último videojuego de Batman en estilo LEGO que prevalece sobre los diseños
anteriores: figuras con objetos en la mano, Bane grande y la Batcueva con túneles y centro de mando. La interpretación de
esa imagen está en `docs/style_bible.md` (es una recreación propia, no los modelos del juego).

## Lo que NO se pudo confirmar
- Ventas reales (no son públicas) y el detalle exacto de varios estampados (ver columna «Confianza»).
- BrickEconomy, Brickset, BrickLink y Rebrickable no se pudieron leer como páginas completas desde el entorno de
  desarrollo (red restringida); se usaron resultados de búsqueda.
- Diámetro exacto de la cabeza: LDraw usa radio 13 en la primitiva exterior y 12 en el cuerpo; se usó **12 LDU**
  (≈ 9,6 mm). Un contraste con piezas físicas podría ajustarlo ±1 LDU.
- La altura total resulta 90 LDU (36 mm con taco; sin pelo ni sombrero) y las referencias de BrickArchitect hablan de
  ≈ 40 mm: la diferencia puede deberse a la altura de pierna y cadera acopladas, no medida con una pieza real.
- El número de tacos de la placa redonda 6×6 (24) sigue la misma regla que la 4×4 (12, confirmada); no se verificó
  contra una pieza real.

Uso personal, no distribuible. No se incluyen logotipos, ficheros de modelos ni imágenes de terceros.
