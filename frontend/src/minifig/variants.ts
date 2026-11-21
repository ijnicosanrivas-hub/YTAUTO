/**
 * Las nueve variantes de la minifigura, basadas en los diseños oficiales de LEGO más poseídos/populares de
 * cada personaje (ver `docs/lego_research.md`). SOLO colores, estampados y accesorios: ninguna dimensión
 * (las proporciones salen de `styleBible.ts`, idénticas para todos). Los estampados son reconstrucciones
 * propias a partir de las descripciones de cada figura, no copias de los originales.
 */
import { BAT_POLY, type Op } from "./ops";
import { PLASTIC as P } from "./styleBible";

export type Accessory =
  | { t: "ears"; kind: "bat" | "cat"; color: string }
  | { t: "cape"; outer: string; inner: string }
  | { t: "hair"; style: "joker" | "pigtails" | "nightwing" | "split"; a: string; b?: string }
  | { t: "hat"; style: "bowler" | "top"; color: string; band: string }
  | { t: "umbrella"; color: string }
  | { t: "held"; item: "mallet" | "cane" | "whip" | "coin" | "teeth" | "batarang" | "escrima" | "umbrella"; hand: "l" | "r" } // objeto en la mano (l = la del lado izquierdo de la pantalla)
  | { t: "jester"; a: string; b: string } // capucha de bufón con dos cuernos
  | { t: "furCollar"; color: string }
  | { t: "monocle" }
  | { t: "baneMask"; mask: string; hose: string } // mangueras que suben sobre la cabeza
  | { t: "flower"; color: string };

export interface Variant {
  agent: string; // nombre interno del agente
  character: string;
  design: string; // figura oficial en la que se basa
  head: string; // color base de la cabeza (piel, capucha…)
  face: Op[]; // estampado de la cara (lienzo 100×100, transparente)
  torso: Op[]; // estampado frontal del torso (opaco)
  torsoBack?: Op[]; // estampado de la espalda (opaco)
  torsoColor: string; // color del torso por los lados
  hips: string;
  legs: { l: string; r: string };
  legsPrint?: { l?: Op[]; r?: Op[] }; // estampado frontal de cada pierna (transparente)
  arms: { l: string; r: string };
  hands: string;
  accessories: Accessory[];
  scale?: number; // factor de tamaño uniforme (Bane es una figura grande en el juego)
}

// --- piezas de dibujo reutilizables (el mismo lenguaje para los nueve) ----------------------------
const SH = "rgba(0,0,0,0.18)"; // sombra suave
const HI = "rgba(255,255,255,0.22)"; // brillo suave

const bat = (cx: number, cy: number, k: number): [number, number][] => BAT_POLY.map(([x, y]) => [cx + (x - 50) * k, cy + (y - 45) * k] as [number, number]);
const arc = (cx: number, cy: number, rx: number, ry: number, a0: number, a1: number, c: string, w: number, n = 8): Op[] =>
  Array.from({ length: n }, (_, i) => {
    const t0 = a0 + ((a1 - a0) * i) / n, t1 = a0 + ((a1 - a0) * (i + 1)) / n;
    return { k: "line", x1: cx + rx * Math.cos(t0), y1: cy + ry * Math.sin(t0), x2: cx + rx * Math.cos(t1), y2: cy + ry * Math.sin(t1), c, w } as Op;
  });
const eye = (x: number, y: number, rx = 7.5, ry = 9.5, iris: string = P.black): Op[] => [
  { k: "ellipse", x, y, rx, ry, c: P.white },
  { k: "ellipse", x, y: y + 1, rx: rx * 0.58, ry: ry * 0.62, c: iris },
  { k: "circle", x, y: y + 1.4, r: rx * 0.3, c: P.black },
  { k: "circle", x: x - rx * 0.25, y: y - ry * 0.22, r: 1.5, c: P.white },
];
const brow = (x1: number, y1: number, x2: number, y2: number, c: string = P.black, w = 3.6): Op => ({ k: "line", x1, y1, x2, y2, c, w });
const smile = (y: number, w: number, depth: number, c: string = P.black): Op[] => arc(50, y - depth, w, depth + 2, 0.25, Math.PI - 0.25, c, 3, 8);
const slitEyes = (y: number): Op[] => [
  { k: "poly", pts: [[19, y + 6], [45, y - 3], [45, y + 6], [26, y + 11]], c: P.white, s: P.black, sw: 1.2 },
  { k: "poly", pts: [[81, y + 6], [55, y - 3], [55, y + 6], [74, y + 11]], c: P.white, s: P.black, sw: 1.2 },
];
const muscles = (c: string): Op[] => [
  ...arc(34, 32, 19, 13, 0.2, 2.8, c, 1.6, 8), ...arc(66, 32, 19, 13, 0.34, 2.94, c, 1.6, 8),
  { k: "line", x1: 50, y1: 22, x2: 50, y2: 78, c, w: 1.4 },
  { k: "line", x1: 38, y1: 52, x2: 62, y2: 52, c, w: 1.2 }, { k: "line", x1: 38, y1: 62, x2: 62, y2: 62, c, w: 1.2 }, { k: "line", x1: 40, y1: 72, x2: 60, y2: 72, c, w: 1.2 },
];
const fill = (c: string): Op => ({ k: "rect", x: 0, y: 0, w: 100, h: 100, c });

export const VARIANTS: Record<string, Variant> = {
  // Batman — traje gris con óvalo amarillo, capucha negra con orejas, capa larga; lleva un batarang en la mano
  chief: {
    agent: "chief", character: "Batman", design: "Batman (último videojuego LEGO Batman): traje gris, cinturón dorado, capa y batarang", head: P.black,
    face: [
      { k: "poly", pts: [[13, 53], [30, 49], [50, 52], [70, 49], [87, 53], [88, 100], [12, 100]], c: P.skin },
      { k: "ellipse", x: 50, y: 92, rx: 30, ry: 10, c: SH },
      ...slitEyes(38),
      { k: "line", x1: 34, y1: 66, x2: 40, y2: 66, c: SH, w: 2 }, { k: "line", x1: 60, y1: 66, x2: 66, y2: 66, c: SH, w: 2 },
      ...arc(50, 70, 13, 6, 0.3, Math.PI - 0.7, P.black, 3, 6),
      { k: "line", x1: 62, y1: 79, x2: 66, y2: 76, c: P.black, w: 2.6 },
    ],
    torsoColor: P.grey,
    torso: [
      fill(P.grey), ...muscles(P.darkGrey),
      { k: "ellipse", x: 50, y: 36, rx: 23, ry: 15.5, c: P.yellow }, { k: "poly", pts: bat(50, 37, 0.42), c: P.black },
      { k: "rect", x: 0, y: 79, w: 100, h: 13, c: "#D4A017" }, { k: "rect", x: 0, y: 79, w: 100, h: 1.6, c: SH }, { k: "rect", x: 0, y: 90.5, w: 100, h: 1.6, c: SH },
      ...[17, 30, 62, 75].map((x) => ({ k: "rect", x, y: 81, w: 9, h: 9, c: "#9a7410" } as Op)),
      { k: "rect", x: 44, y: 80, w: 12, h: 11, c: "#D4A017" }, { k: "rect", x: 46.5, y: 82.5, w: 7, h: 6, c: P.black },
      { k: "rect", x: 0, y: 93, w: 100, h: 7, c: P.black },
    ],
    torsoBack: [fill(P.grey), { k: "rect", x: 0, y: 79, w: 100, h: 13, c: "#D4A017" }, { k: "rect", x: 0, y: 93, w: 100, h: 7, c: P.black }],
    hips: P.black, legs: { l: P.darkGrey, r: P.darkGrey },
    legsPrint: { l: [{ k: "rect", x: 0, y: 86, w: 100, h: 14, c: P.black }], r: [{ k: "rect", x: 0, y: 86, w: 100, h: 14, c: P.black }] },
    arms: { l: P.grey, r: P.grey }, hands: P.black,
    accessories: [{ t: "ears", kind: "bat", color: P.black }, { t: "cape", outer: P.black, inner: P.black }, { t: "held", item: "batarang", hand: "l" }],
  },
  // El Acertijo — traje verde con «?», corbata morada, antifaz morado, bombín verde; bastón dorado en forma de «?»
  director: {
    agent: "director", character: "El Acertijo", design: "The Riddler (último videojuego LEGO Batman): traje verde con «?», bombín y bastón dorado", head: P.skin,
    face: [
      { k: "poly", pts: [[10, 31], [30, 26], [50, 33], [70, 26], [90, 31], [90, 56], [66, 52], [50, 49], [34, 52], [10, 56]], c: P.darkPurple, s: P.black, sw: 1 },
      ...eye(33, 43, 7, 8, P.black), ...eye(67, 43, 7, 8, P.black),
      brow(22, 29, 41, 34, P.black, 3.4), brow(78, 29, 59, 34, P.black, 3.4),
      { k: "poly", pts: [[33, 72], [67, 72], [64, 79], [36, 79]], c: P.white },
      ...arc(50, 70, 21, 9, 0.2, Math.PI - 0.2, P.black, 3, 8),
    ],
    torsoColor: P.green,
    torso: [
      fill(P.green), { k: "ellipse", x: 50, y: 20, rx: 36, ry: 20, c: HI },
      ...[[20, 30], [80, 30], [18, 62], [82, 62], [34, 82], [66, 82], [50, 56]].map(([x, y]) => ({ k: "text", x, y, s: "?", c: P.darkGreen, size: 26 } as Op)),
      { k: "poly", pts: [[30, 0], [70, 0], [50, 24]], c: P.darkPurple }, { k: "poly", pts: [[41, 14], [59, 14], [50, 27]], c: P.purple },
      { k: "poly", pts: [[44, 26], [56, 26], [54, 74], [50, 80], [46, 74]], c: P.purple, s: P.darkPurple, sw: 1 },
      { k: "rect", x: 0, y: 88, w: 100, h: 12, c: P.darkGreen },
    ],
    torsoBack: [fill(P.green), { k: "text", x: 50, y: 44, s: "?", c: P.darkGreen, size: 70 }],
    hips: P.darkGreen, legs: { l: P.green, r: P.green },
    legsPrint: { l: [{ k: "text", x: 50, y: 38, s: "?", c: P.darkGreen, size: 40 }], r: [{ k: "text", x: 50, y: 38, s: "?", c: P.darkGreen, size: 40 }] },
    arms: { l: P.green, r: P.green }, hands: P.darkPurple,
    accessories: [{ t: "hat", style: "bowler", color: P.darkGreen, band: P.darkPurple }, { t: "held", item: "cane", hand: "l" }],
  },
  // El Joker — traje morado, chaleco naranja, pajarita verde, flor amarilla, pelo verde; sostiene una dentadura de juguete
  scriptwriter: {
    agent: "scriptwriter", character: "El Joker", design: "The Joker (último videojuego LEGO Batman): traje morado, chaleco naranja y dentadura de cuerda", head: P.white,
    face: [
      { k: "ellipse", x: 33, y: 41, rx: 11, ry: 12, c: P.darkPurple }, { k: "ellipse", x: 67, y: 41, rx: 11, ry: 12, c: P.darkPurple },
      ...eye(33, 42, 6.5, 8, P.green), ...eye(67, 42, 6.5, 8, P.green),
      brow(21, 27, 42, 32, P.green, 3.4), brow(79, 27, 58, 32, P.green, 3.4),
      { k: "poly", pts: [[10, 62], [28, 66], [50, 70], [72, 66], [90, 62], [88, 74], [74, 88], [50, 92], [26, 88], [12, 74]], c: P.red, s: P.black, sw: 1.6 },
      { k: "poly", pts: [[20, 70], [80, 70], [74, 80], [50, 83], [26, 80]], c: P.white },
      ...[32, 44, 56, 68].map((x) => ({ k: "line", x1: x, y1: 70, x2: x, y2: 82, c: SH, w: 1 } as Op)),
      { k: "line", x1: 10, y1: 62, x2: 5, y2: 56, c: P.red, w: 3.2 }, { k: "line", x1: 90, y1: 62, x2: 95, y2: 56, c: P.red, w: 3.2 },
    ],
    torsoColor: P.purple,
    torso: [
      fill(P.purple), { k: "poly", pts: [[22, 0], [78, 0], [62, 70], [50, 76], [38, 70]], c: P.orange },
      { k: "poly", pts: [[38, 0], [62, 0], [50, 36]], c: P.white },
      { k: "poly", pts: [[34, 12], [48, 18], [34, 26]], c: P.green, s: P.darkGreen, sw: 1 }, { k: "poly", pts: [[66, 12], [52, 18], [66, 26]], c: P.green, s: P.darkGreen, sw: 1 }, { k: "circle", x: 50, y: 18, r: 3.4, c: P.darkGreen },
      { k: "line", x1: 22, y1: 0, x2: 6, y2: 100, c: P.darkPurple, w: 5 }, { k: "line", x1: 78, y1: 0, x2: 94, y2: 100, c: P.darkPurple, w: 5 },
      { k: "circle", x: 22, y: 30, r: 7, c: P.yellow }, { k: "circle", x: 22, y: 30, r: 3.4, c: P.orange }, { k: "line", x1: 22, y1: 37, x2: 27, y2: 46, c: P.darkGreen, w: 2 },
      ...[48, 62, 76].map((y) => ({ k: "circle", x: 50, y, r: 2.6, c: P.black } as Op)),
    ],
    torsoBack: [fill(P.purple), { k: "line", x1: 50, y1: 0, x2: 50, y2: 100, c: P.darkPurple, w: 2.5 }],
    hips: P.darkPurple, legs: { l: P.purple, r: P.purple },
    legsPrint: { l: [{ k: "line", x1: 50, y1: 6, x2: 50, y2: 90, c: P.darkPurple, w: 3 }], r: [{ k: "line", x1: 50, y1: 6, x2: 50, y2: 90, c: P.darkPurple, w: 3 }] },
    arms: { l: P.purple, r: P.purple }, hands: P.white,
    accessories: [{ t: "hair", style: "joker", a: P.green }, { t: "held", item: "teeth", hand: "l" }],
  },
  // Catwoman — capucha con orejas y gafas grandes, traje negro con líneas moradas, cinturón morado; látigo
  resources: {
    agent: "resources", character: "Catwoman", design: "Catwoman (último videojuego LEGO Batman): capucha con orejas, gafas, traje con líneas moradas y látigo", head: P.black,
    face: [
      { k: "poly", pts: [[14, 54], [32, 50], [50, 53], [68, 50], [86, 54], [87, 100], [13, 100]], c: P.skin },
      { k: "ellipse", x: 50, y: 93, rx: 30, ry: 9, c: SH },
      { k: "ellipse", x: 32, y: 42, rx: 15, ry: 11, c: P.black }, { k: "ellipse", x: 68, y: 42, rx: 15, ry: 11, c: P.black },
      { k: "ellipse", x: 32, y: 42, rx: 12, ry: 8.5, c: "#d7ecf2" }, { k: "ellipse", x: 68, y: 42, rx: 12, ry: 8.5, c: "#d7ecf2" },
      { k: "ellipse", x: 34, y: 41, rx: 4.5, ry: 6, c: P.darkPurple }, { k: "ellipse", x: 66, y: 41, rx: 4.5, ry: 6, c: P.darkPurple },
      { k: "ellipse", x: 28, y: 38, rx: 3, ry: 2, c: "rgba(255,255,255,0.8)" }, { k: "ellipse", x: 64, y: 38, rx: 3, ry: 2, c: "rgba(255,255,255,0.8)" },
      { k: "line", x1: 34, y1: 64, x2: 40, y2: 64, c: SH, w: 2 }, { k: "line", x1: 60, y1: 64, x2: 66, y2: 64, c: SH, w: 2 },
      { k: "poly", pts: [[36, 76], [50, 73], [64, 76], [50, 82]], c: P.red, s: P.darkRed, sw: 1 },
    ],
    torsoColor: P.black,
    torso: [
      fill(P.black), ...muscles("rgba(255,255,255,0.10)"),
      ...arc(15, 40, 26, 42, -1.2, 1.2, P.purple, 3.2, 10), ...arc(85, 40, 26, 42, Math.PI - 1.2, Math.PI + 1.2, P.purple, 3.2, 10),
      { k: "line", x1: 50, y1: 0, x2: 50, y2: 78, c: P.grey, w: 2.4 }, { k: "rect", x: 47, y: 0, w: 6, h: 9, c: P.grey },
      { k: "rect", x: 0, y: 79, w: 100, h: 12, c: P.darkPurple }, { k: "rect", x: 0, y: 79, w: 100, h: 1.6, c: SH }, { k: "rect", x: 40, y: 80, w: 20, h: 10, c: P.yellow },
      { k: "rect", x: 44, y: 82, w: 12, h: 6, c: P.darkPurple }, { k: "rect", x: 0, y: 92, w: 100, h: 8, c: P.black },
    ],
    torsoBack: [fill(P.black), ...arc(15, 40, 26, 42, -1.2, 1.2, P.purple, 3.2, 10), ...arc(85, 40, 26, 42, Math.PI - 1.2, Math.PI + 1.2, P.purple, 3.2, 10), { k: "rect", x: 0, y: 79, w: 100, h: 12, c: P.darkPurple }],
    hips: P.black, legs: { l: P.black, r: P.black },
    legsPrint: { l: [...arc(0, 50, 20, 60, -0.9, 0.9, P.purple, 3, 8)], r: [...arc(100, 50, 20, 60, Math.PI - 0.9, Math.PI + 0.9, P.purple, 3, 8)] },
    arms: { l: P.black, r: P.black }, hands: P.black,
    accessories: [{ t: "ears", kind: "cat", color: P.black }, { t: "held", item: "whip", hand: "l" }],
  },
  // Bane — figura GRANDE: máscara con ojos rojos, mangueras verdes que suben sobre la cabeza, torso desnudo con arneses
  voice: {
    agent: "voice", character: "Bane", design: "Bane (último videojuego LEGO Batman): figura grande con máscara, mangueras verdes y arneses", head: P.reddishBrown, scale: 1.32,
    face: [
      { k: "ellipse", x: 33, y: 42, rx: 12, ry: 12, c: P.black }, { k: "ellipse", x: 67, y: 42, rx: 12, ry: 12, c: P.black },
      { k: "ellipse", x: 33, y: 42, rx: 9, ry: 9, c: P.red }, { k: "ellipse", x: 67, y: 42, rx: 9, ry: 9, c: P.red },
      { k: "circle", x: 33, y: 42, r: 3.2, c: P.black }, { k: "circle", x: 67, y: 42, r: 3.2, c: P.black }, { k: "circle", x: 30, y: 38, r: 1.8, c: "#ff9a8a" }, { k: "circle", x: 64, y: 38, r: 1.8, c: "#ff9a8a" },
      brow(18, 27, 44, 33, P.black, 4.2), brow(82, 27, 56, 33, P.black, 4.2),
      { k: "line", x1: 50, y1: 0, x2: 50, y2: 24, c: P.darkBrown, w: 2.4 }, ...[4, 10, 16].map((y) => ({ k: "line", x1: 46, y1: y, x2: 54, y2: y, c: P.darkBrown, w: 1.6 } as Op)),
      { k: "rect", x: 26, y: 64, w: 48, h: 26, c: P.darkGrey },
      ...[34, 42, 50, 58, 66].map((x) => ({ k: "line", x1: x, y1: 67, x2: x, y2: 87, c: P.black, w: 2 } as Op)),
    ],
    torsoColor: P.nougat,
    torso: [
      fill(P.nougat), ...muscles("rgba(60,25,5,0.4)"), { k: "ellipse", x: 34, y: 28, rx: 20, ry: 9, c: HI }, { k: "ellipse", x: 66, y: 28, rx: 20, ry: 9, c: HI },
      { k: "poly", pts: [[10, 0], [28, 0], [58, 100], [40, 100]], c: P.black }, { k: "poly", pts: [[90, 0], [72, 0], [42, 100], [60, 100]], c: P.black },
      { k: "rect", x: 0, y: 80, w: 100, h: 15, c: P.darkBrown }, { k: "rect", x: 36, y: 81, w: 28, h: 13, c: P.grey }, { k: "circle", x: 50, y: 87.5, r: 4, c: P.red },
      { k: "rect", x: 0, y: 95, w: 100, h: 5, c: P.black },
    ],
    torsoBack: [fill(P.nougat), { k: "poly", pts: [[10, 0], [28, 0], [58, 100], [40, 100]], c: P.black }, { k: "poly", pts: [[90, 0], [72, 0], [42, 100], [60, 100]], c: P.black }, { k: "rect", x: 0, y: 80, w: 100, h: 15, c: P.darkBrown }],
    hips: P.darkBrown, legs: { l: P.black, r: P.black },
    legsPrint: { l: [{ k: "rect", x: 0, y: 84, w: 100, h: 16, c: P.darkGrey }, { k: "rect", x: 10, y: 28, w: 80, h: 14, c: P.darkGrey }], r: [{ k: "rect", x: 0, y: 84, w: 100, h: 16, c: P.darkGrey }, { k: "rect", x: 10, y: 28, w: 80, h: 14, c: P.darkGrey }] },
    arms: { l: P.nougat, r: P.nougat }, hands: P.nougat,
    accessories: [{ t: "baneMask", mask: P.reddishBrown, hose: P.green }],
  },
  // Nightwing — torso negro con V azul, mangas y guantes azules, antifaz y pelo negro de pinchos; dos bastones de escrima
  editor: {
    agent: "editor", character: "Nightwing", design: "Nightwing (último videojuego LEGO Batman): traje negro y azul con dos bastones de escrima", head: P.skin,
    face: [
      { k: "poly", pts: [[10, 30], [32, 25], [50, 34], [68, 25], [90, 30], [90, 55], [66, 52], [50, 49], [34, 52], [10, 55]], c: P.black },
      ...[[33, 43], [67, 43]].flatMap(([x, y]) => eye(x, y, 6.5, 7, P.blue)), brow(22, 27, 42, 34, P.black, 3.6), brow(78, 27, 58, 34, P.black, 3.6),
      { k: "line", x1: 47, y1: 58, x2: 53, y2: 58, c: SH, w: 2 }, ...smile(76, 15, 6),
      { k: "line", x1: 64, y1: 72, x2: 68, y2: 68, c: P.black, w: 2 },
    ],
    torsoColor: P.black,
    torso: [
      fill(P.black), ...muscles("rgba(255,255,255,0.12)"),
      { k: "poly", pts: [[8, 0], [30, 0], [50, 58], [70, 0], [92, 0], [58, 86], [42, 86]], c: P.blue, s: "#003a82", sw: 1 },
      { k: "poly", pts: [[22, 0], [34, 0], [50, 40], [66, 0], [78, 0], [54, 68], [46, 68]], c: P.black },
      { k: "rect", x: 0, y: 88, w: 100, h: 12, c: P.black },
    ],
    torsoBack: [fill(P.black), { k: "poly", pts: [[8, 0], [30, 0], [50, 58], [70, 0], [92, 0], [58, 86], [42, 86]], c: P.blue }],
    hips: P.black, legs: { l: P.black, r: P.black },
    legsPrint: { l: [{ k: "rect", x: 0, y: 86, w: 100, h: 14, c: P.blue }], r: [{ k: "rect", x: 0, y: 86, w: 100, h: 14, c: P.blue }] },
    arms: { l: P.blue, r: P.blue }, hands: P.blue,
    accessories: [{ t: "hair", style: "nightwing", a: P.black }, { t: "held", item: "escrima", hand: "l" }, { t: "held", item: "escrima", hand: "r" }],
  },
  // El Pingüino — chistera, monóculo, collar de piel, frac con chaleco gris; paraguas negro
  sound: {
    agent: "sound", character: "El Pingüino", design: "The Penguin (último videojuego LEGO Batman): chistera, monóculo, collar de piel y paraguas", head: P.lightNougat,
    face: [
      brow(20, 29, 44, 24, P.black, 5), brow(80, 29, 56, 24, P.black, 5),
      ...eye(33, 40, 6, 7.5, P.black), ...eye(67, 40, 6, 7.5, P.black),
      { k: "poly", pts: [[44, 50], [56, 50], [50, 66]], c: P.lightNougat, s: SH, sw: 1 },
      { k: "poly", pts: [[14, 66], [50, 74], [86, 66], [82, 80], [50, 90], [18, 80]], c: P.white, s: P.black, sw: 1.6 },
      ...[26, 38, 50, 62, 74].map((x) => ({ k: "line", x1: x, y1: 70, x2: x, y2: 84, c: SH, w: 1 } as Op)),
    ],
    torsoColor: P.black,
    torso: [
      fill(P.black), { k: "poly", pts: [[26, 0], [74, 0], [66, 100], [34, 100]], c: P.grey }, { k: "poly", pts: [[38, 0], [62, 0], [50, 44]], c: P.white },
      { k: "poly", pts: [[36, 12], [48, 18], [36, 26]], c: P.black }, { k: "poly", pts: [[64, 12], [52, 18], [64, 26]], c: P.black }, { k: "circle", x: 50, y: 18, r: 3.4, c: P.black },
      ...[46, 62, 78].map((y) => ({ k: "circle", x: 50, y, r: 2.6, c: P.darkGrey } as Op)),
      { k: "line", x1: 26, y1: 0, x2: 34, y2: 100, c: P.black, w: 4 }, { k: "line", x1: 74, y1: 0, x2: 66, y2: 100, c: P.black, w: 4 },
    ],
    torsoBack: [fill(P.black), { k: "line", x1: 50, y1: 0, x2: 50, y2: 100, c: "rgba(255,255,255,0.15)", w: 2 }],
    hips: P.black, legs: { l: P.black, r: P.black },
    legsPrint: { l: [{ k: "line", x1: 50, y1: 4, x2: 50, y2: 94, c: P.darkGrey, w: 2.4 }], r: [{ k: "line", x1: 50, y1: 4, x2: 50, y2: 94, c: P.darkGrey, w: 2.4 }] },
    arms: { l: P.black, r: P.black }, hands: P.white,
    accessories: [{ t: "hat", style: "top", color: P.black, band: P.grey }, { t: "monocle" }, { t: "furCollar", color: "#cfd2d6" }, { t: "held", item: "umbrella", hand: "l" }],
  },
  // Dos Caras — traje partido blanco / negro, cara con mitad quemada, pelo oscuro; sostiene la moneda
  reviewer: {
    agent: "reviewer", character: "Dos Caras", design: "Two-Face (último videojuego LEGO Batman): traje blanco y negro, cara partida y moneda", head: P.lightNougat,
    face: [
      { k: "rect", x: 50, y: 0, w: 50, h: 100, c: P.pink },
      { k: "poly", pts: [[50, 8], [58, 30], [52, 54], [60, 78], [50, 96]], c: "#8a1f2c", s: "#5a0f18", sw: 1.4 },
      ...[[56, 22], [62, 46], [58, 68]].map(([x, y]) => ({ k: "line", x1: x - 5, y1: y, x2: x + 7, y2: y + 1, c: "#5a0f18", w: 1.4 } as Op)),
      ...eye(30, 42, 7, 9, P.black), { k: "ellipse", x: 70, y: 42, rx: 9, ry: 11, c: P.white }, { k: "circle", x: 70, y: 44, r: 3, c: P.red },
      brow(19, 28, 40, 32, P.black, 3.6), { k: "line", x1: 82, y1: 27, x2: 60, y2: 33, c: "#5a0f18", w: 3 },
      { k: "line", x1: 22, y1: 74, x2: 50, y2: 78, c: P.black, w: 3 }, { k: "poly", pts: [[50, 72], [82, 72], [80, 84], [50, 86]], c: P.white, s: "#5a0f18", sw: 1.2 },
      ...[58, 66, 74].map((x) => ({ k: "line", x1: x, y1: 72, x2: x, y2: 85, c: SH, w: 1 } as Op)),
    ],
    torsoColor: P.white,
    torso: [
      { k: "rect", x: 0, y: 0, w: 50, h: 100, c: P.white }, { k: "rect", x: 50, y: 0, w: 50, h: 100, c: P.black },
      { k: "poly", pts: [[38, 0], [62, 0], [50, 30]], c: P.white }, { k: "poly", pts: [[44, 22], [56, 22], [54, 70], [50, 76], [46, 70]], c: P.black },
      { k: "line", x1: 36, y1: 0, x2: 14, y2: 66, c: "rgba(0,0,0,0.25)", w: 3 }, { k: "line", x1: 64, y1: 0, x2: 86, y2: 66, c: "rgba(255,255,255,0.18)", w: 3 },
      { k: "line", x1: 50, y1: 0, x2: 50, y2: 100, c: P.red, w: 1.6 },
      ...[48, 62, 76].map((y) => ({ k: "circle", x: 50, y, r: 2.4, c: P.darkGrey } as Op)),
    ],
    torsoBack: [{ k: "rect", x: 0, y: 0, w: 50, h: 100, c: P.black }, { k: "rect", x: 50, y: 0, w: 50, h: 100, c: P.white }, { k: "line", x1: 50, y1: 0, x2: 50, y2: 100, c: P.red, w: 1.6 }],
    hips: P.black, legs: { l: P.white, r: P.black },
    legsPrint: { l: [{ k: "line", x1: 90, y1: 0, x2: 90, y2: 100, c: "rgba(0,0,0,0.18)", w: 4 }], r: [{ k: "line", x1: 10, y1: 0, x2: 10, y2: 100, c: "rgba(255,255,255,0.15)", w: 4 }] },
    arms: { l: P.white, r: P.black }, hands: P.lightNougat,
    accessories: [{ t: "hair", style: "split", a: P.black, b: P.darkGrey }, { t: "held", item: "coin", hand: "r" }],
  },
  // Harley Quinn — capucha de bufón roja y negra con cuernos, antifaz, torso rojo y negro con golilla blanca; gran mazo
  publisher: {
    agent: "publisher", character: "Harley Quinn", design: "Harley Quinn (último videojuego LEGO Batman): capucha de bufón, traje rojo y negro y mazo", head: P.white,
    face: [
      { k: "poly", pts: [[8, 36], [30, 24], [50, 34], [70, 24], [92, 36], [88, 60], [64, 56], [50, 50], [36, 56], [12, 60]], c: P.black },
      ...eye(33, 45, 6.5, 7.5, P.blue), ...eye(67, 45, 6.5, 7.5, P.blue),
      { k: "line", x1: 26, y1: 32, x2: 41, y2: 37, c: P.white, w: 1.4 }, { k: "line", x1: 74, y1: 32, x2: 59, y2: 37, c: P.white, w: 1.4 },
      { k: "ellipse", x: 22, y: 64, rx: 6, ry: 3.6, c: "rgba(255,90,90,0.35)" }, { k: "ellipse", x: 78, y: 64, rx: 6, ry: 3.6, c: "rgba(255,90,90,0.35)" },
      { k: "poly", pts: [[32, 72], [50, 70], [68, 72], [64, 80], [50, 86], [36, 80]], c: P.red, s: P.darkRed, sw: 1.2 }, ...arc(50, 73, 18, 6, 0.3, Math.PI - 0.3, P.darkRed, 1.4, 6),
    ],
    torsoColor: P.red,
    torso: [
      { k: "rect", x: 0, y: 0, w: 50, h: 100, c: P.red }, { k: "rect", x: 50, y: 0, w: 50, h: 100, c: P.black },
      ...[[22, 38, P.black], [78, 38, P.red], [22, 66, P.black], [78, 66, P.red]].map(([x, y, c]) => ({ k: "poly", pts: [[x as number, (y as number) - 12], [(x as number) + 12, y as number], [x as number, (y as number) + 12], [(x as number) - 12, y as number]], c: c as string } as Op)),
      { k: "poly", pts: [[0, 0], [10, 10], [20, 0], [30, 10], [40, 0], [50, 10], [60, 0], [70, 10], [80, 0], [90, 10], [100, 0], [100, 14], [0, 14]], c: P.white, s: "#bfc3c8", sw: 1 },
      { k: "line", x1: 50, y1: 14, x2: 50, y2: 100, c: P.black, w: 1.4 },
    ],
    torsoBack: [{ k: "rect", x: 0, y: 0, w: 50, h: 100, c: P.black }, { k: "rect", x: 50, y: 0, w: 50, h: 100, c: P.red }, { k: "rect", x: 0, y: 0, w: 100, h: 12, c: P.white }],
    hips: P.black, legs: { l: P.red, r: P.black },
    legsPrint: { l: [...[24, 56].map((y) => ({ k: "poly", pts: [[50, y - 14], [72, y], [50, y + 14], [28, y]], c: P.black } as Op))], r: [...[24, 56].map((y) => ({ k: "poly", pts: [[50, y - 14], [72, y], [50, y + 14], [28, y]], c: P.red } as Op))] },
    arms: { l: P.red, r: P.black }, hands: P.white,
    accessories: [{ t: "jester", a: P.red, b: P.black }, { t: "held", item: "mallet", hand: "l" }],
  },
};
