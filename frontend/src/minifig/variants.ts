/**
 * Las nueve variantes de la minifigura. SOLO colores, estampados y accesorios: ninguna dimensión
 * (las proporciones salen de `styleBible.ts`, idénticas para todos). Identidades fijadas por el usuario.
 */
import { BAT_POLY, type Op } from "./ops";
import { PLASTIC as P } from "./styleBible";

export type Accessory =
  | { t: "ears"; kind: "bat" | "cat"; color: string }
  | { t: "cape"; outer: string; inner: string }
  | { t: "hair"; style: "joker" | "pigtails" | "nightwing"; a: string; b?: string }
  | { t: "hat"; style: "bowler" | "top"; color: string; band: string }
  | { t: "umbrella"; color: string }
  | { t: "monocle" }
  | { t: "baneMask" }
  | { t: "flower"; color: string };

export interface Variant {
  agent: string; // nombre interno del agente
  character: string;
  head: string; // color base de la cabeza (piel, capucha…)
  face: Op[]; // estampado de la cara (lienzo 100×100, transparente)
  torso: Op[]; // estampado frontal del torso (opaco)
  torsoColor: string; // color del torso por detrás y los lados
  hips: string;
  legs: { l: string; r: string };
  arms: { l: string; r: string };
  hands: string;
  accessories: Accessory[];
}

const BAT = BAT_POLY;

// Piezas de cara reutilizables (mismo lenguaje de dibujo para los nueve).
const eyes = (y: number, c: string = P.black, white = true): Op[] => [
  ...(white ? [{ k: "circle", x: 34, y, r: 7, c: P.white } as Op, { k: "circle", x: 66, y, r: 7, c: P.white } as Op] : []),
  { k: "circle", x: 34, y, r: 3.4, c }, { k: "circle", x: 66, y, r: 3.4, c },
];
const smile = (y: number, w = 14, c: string = P.black): Op[] => [{ k: "line", x1: 50 - w, y1: y, x2: 50 + w, y2: y, c, w: 3 }, { k: "line", x1: 50 - w, y1: y, x2: 50 - w - 3, y2: y - 4, c, w: 3 }, { k: "line", x1: 50 + w, y1: y, x2: 50 + w + 3, y2: y - 4, c, w: 3 }];
const slits = (y: number): Op[] => [{ k: "poly", pts: [[22, y + 4], [44, y - 2], [44, y + 6], [26, y + 9]], c: P.white }, { k: "poly", pts: [[78, y + 4], [56, y - 2], [56, y + 6], [74, y + 9]], c: P.white }];

export const VARIANTS: Record<string, Variant> = {
  chief: {
    agent: "chief", character: "Batman", head: P.black,
    face: [{ k: "rect", x: 16, y: 55, w: 68, h: 45, c: P.skin }, ...slits(40), ...smile(80, 9)],
    torsoColor: P.black,
    torso: [
      { k: "rect", x: 0, y: 0, w: 100, h: 100, c: P.black },
      { k: "rect", x: 0, y: 82, w: 100, h: 10, c: P.yellow }, { k: "rect", x: 44, y: 80, w: 12, h: 14, c: P.grey },
      { k: "rect", x: 14, y: 80, w: 8, h: 14, c: P.darkGrey }, { k: "rect", x: 78, y: 80, w: 8, h: 14, c: P.darkGrey },
      { k: "circle", x: 50, y: 45, r: 24, c: P.yellow }, { k: "poly", pts: BAT, c: P.black },
    ],
    hips: P.black, legs: { l: P.black, r: P.black }, arms: { l: P.black, r: P.black }, hands: P.black,
    accessories: [{ t: "ears", kind: "bat", color: P.black }, { t: "cape", outer: P.black, inner: P.darkGrey }],
  },
  director: {
    agent: "director", character: "El Acertijo", head: P.skin,
    face: [{ k: "rect", x: 14, y: 32, w: 72, h: 20, c: P.darkGreen }, ...eyes(42, P.black), ...smile(76, 16), { k: "text", x: 50, y: 66, s: "?", c: P.green, size: 14 }],
    torsoColor: P.green,
    torso: [
      { k: "rect", x: 0, y: 0, w: 100, h: 100, c: P.green },
      { k: "poly", pts: [[38, 0], [62, 0], [50, 24]], c: P.white }, { k: "poly", pts: [[44, 22], [56, 22], [50, 32]], c: P.darkPurple },
      ...[[22, 40], [70, 40], [22, 70], [70, 70], [46, 55]].map(([x, y]) => ({ k: "text", x, y, s: "?", c: P.darkGreen, size: 26 } as Op)),
      { k: "rect", x: 0, y: 88, w: 100, h: 12, c: P.darkGreen },
    ],
    hips: P.darkGreen, legs: { l: P.green, r: P.green }, arms: { l: P.green, r: P.green }, hands: P.white,
    accessories: [{ t: "hat", style: "bowler", color: P.green, band: P.purple }],
  },
  scriptwriter: {
    agent: "scriptwriter", character: "El Joker", head: P.white,
    face: [
      { k: "circle", x: 34, y: 42, r: 10, c: P.darkPurple }, { k: "circle", x: 66, y: 42, r: 10, c: P.darkPurple },
      ...eyes(42, P.black), { k: "poly", pts: [[18, 70], [50, 84], [82, 70], [74, 62], [50, 74], [26, 62]], c: P.red },
      { k: "rect", x: 40, y: 72, w: 20, h: 5, c: P.white },
    ],
    torsoColor: P.purple,
    torso: [
      { k: "rect", x: 0, y: 0, w: 100, h: 100, c: P.purple },
      { k: "poly", pts: [[30, 0], [70, 0], [50, 70]], c: P.green }, { k: "poly", pts: [[44, 0], [56, 0], [50, 22]], c: P.white },
      { k: "line", x1: 30, y1: 0, x2: 8, y2: 100, c: P.darkPurple, w: 4 }, { k: "line", x1: 70, y1: 0, x2: 92, y2: 100, c: P.darkPurple, w: 4 },
      { k: "circle", x: 72, y: 24, r: 6, c: P.yellow }, { k: "circle", x: 50, y: 62, r: 3, c: P.black }, { k: "circle", x: 50, y: 78, r: 3, c: P.black },
    ],
    hips: P.darkPurple, legs: { l: P.darkPurple, r: P.darkPurple }, arms: { l: P.purple, r: P.purple }, hands: P.white,
    accessories: [{ t: "hair", style: "joker", a: P.green }, { t: "flower", color: P.yellow }],
  },
  resources: {
    agent: "resources", character: "Catwoman", head: P.black,
    face: [{ k: "rect", x: 16, y: 56, w: 68, h: 44, c: P.skin }, { k: "poly", pts: [[20, 38], [44, 34], [44, 46], [26, 50]], c: P.white }, { k: "poly", pts: [[80, 38], [56, 34], [56, 46], [74, 50]], c: P.white },
      { k: "circle", x: 36, y: 41, r: 2.6, c: P.green }, { k: "circle", x: 64, y: 41, r: 2.6, c: P.green }, { k: "rect", x: 40, y: 72, w: 20, h: 6, c: P.red }],
    torsoColor: P.black,
    torso: [
      { k: "rect", x: 0, y: 0, w: 100, h: 100, c: P.black },
      { k: "line", x1: 50, y1: 0, x2: 50, y2: 86, c: P.grey, w: 3 },
      { k: "rect", x: 0, y: 80, w: 100, h: 9, c: P.yellow }, { k: "circle", x: 50, y: 85, r: 6, c: P.yellow },
      { k: "poly", pts: [[40, 30], [46, 20], [48, 32]], c: P.grey }, { k: "poly", pts: [[60, 30], [54, 20], [52, 32]], c: P.grey },
    ],
    hips: P.black, legs: { l: P.black, r: P.black }, arms: { l: P.black, r: P.black }, hands: P.black,
    accessories: [{ t: "ears", kind: "cat", color: P.black }],
  },
  voice: {
    agent: "voice", character: "Bane", head: P.nougat,
    face: [...slits(38), { k: "line", x1: 16, y1: 30, x2: 36, y2: 34, c: P.darkGrey, w: 3 }, { k: "line", x1: 84, y1: 30, x2: 64, y2: 34, c: P.darkGrey, w: 3 }],
    torsoColor: P.darkGrey,
    torso: [
      { k: "rect", x: 0, y: 0, w: 100, h: 100, c: P.tan },
      { k: "rect", x: 0, y: 0, w: 100, h: 30, c: P.darkGrey }, // hombreras/arneses
      { k: "line", x1: 18, y1: 0, x2: 44, y2: 100, c: P.black, w: 7 }, { k: "line", x1: 82, y1: 0, x2: 56, y2: 100, c: P.black, w: 7 },
      { k: "line", x1: 30, y1: 40, x2: 70, y2: 40, c: P.lightNougat, w: 2 }, { k: "line", x1: 50, y1: 38, x2: 50, y2: 78, c: P.lightNougat, w: 2 },
      { k: "rect", x: 0, y: 84, w: 100, h: 14, c: P.black }, { k: "rect", x: 42, y: 86, w: 16, h: 10, c: P.grey },
    ],
    hips: P.black, legs: { l: P.darkGrey, r: P.darkGrey }, arms: { l: P.tan, r: P.tan }, hands: P.black,
    accessories: [{ t: "baneMask" }],
  },
  editor: {
    agent: "editor", character: "Nightwing", head: P.skin,
    face: [{ k: "rect", x: 14, y: 33, w: 72, h: 18, c: P.black }, ...eyes(42, P.black), ...smile(74, 12)],
    torsoColor: P.black,
    torso: [
      { k: "rect", x: 0, y: 0, w: 100, h: 100, c: P.black },
      { k: "poly", pts: [[50, 8], [66, 10], [58, 40], [50, 78], [42, 40], [34, 10]], c: P.blue },
      { k: "poly", pts: [[50, 20], [58, 22], [50, 56], [42, 22]], c: P.black },
      { k: "line", x1: 12, y1: 0, x2: 12, y2: 100, c: P.blue, w: 5 }, { k: "line", x1: 88, y1: 0, x2: 88, y2: 100, c: P.blue, w: 5 },
    ],
    hips: P.black, legs: { l: P.black, r: P.black }, arms: { l: P.blue, r: P.blue }, hands: P.black,
    accessories: [{ t: "hair", style: "nightwing", a: P.black }],
  },
  sound: {
    agent: "sound", character: "El Pingüino", head: P.lightNougat,
    face: [...eyes(42, P.black), { k: "poly", pts: [[44, 50], [56, 50], [50, 66]], c: P.lightNougat }, ...smile(78, 14), { k: "line", x1: 16, y1: 34, x2: 40, y2: 38, c: P.black, w: 2.5 }],
    torsoColor: P.black,
    torso: [
      { k: "rect", x: 0, y: 0, w: 100, h: 100, c: P.black },
      { k: "poly", pts: [[30, 0], [70, 0], [60, 100], [40, 100]], c: P.white },
      { k: "poly", pts: [[38, 6], [50, 14], [62, 6], [62, 22], [50, 14], [38, 22]], c: P.red },
      { k: "circle", x: 50, y: 40, r: 2.6, c: P.black }, { k: "circle", x: 50, y: 58, r: 2.6, c: P.black }, { k: "circle", x: 50, y: 76, r: 2.6, c: P.black },
    ],
    hips: P.black, legs: { l: P.black, r: P.black }, arms: { l: P.black, r: P.black }, hands: P.white,
    accessories: [{ t: "hat", style: "top", color: P.black, band: P.grey }, { t: "monocle" }, { t: "umbrella", color: P.black }],
  },
  reviewer: {
    agent: "reviewer", character: "Dos Caras", head: P.skin,
    face: [
      { k: "rect", x: 50, y: 0, w: 50, h: 100, c: "#8A6FA0" }, // mitad dañada
      { k: "line", x1: 54, y1: 20, x2: 76, y2: 78, c: "#4A1B7A", w: 3 }, { k: "line", x1: 62, y1: 30, x2: 84, y2: 60, c: "#4A1B7A", w: 2 },
      ...eyes(42, P.black), { k: "circle", x: 66, y: 42, r: 8, c: P.white }, { k: "circle", x: 66, y: 42, r: 1.6, c: P.red },
      ...smile(76, 12),
    ],
    torsoColor: P.black,
    torso: [
      { k: "rect", x: 0, y: 0, w: 50, h: 100, c: P.black }, { k: "rect", x: 50, y: 0, w: 50, h: 100, c: "#C9CED6" },
      { k: "poly", pts: [[40, 0], [60, 0], [50, 26]], c: P.white }, { k: "poly", pts: [[44, 22], [56, 22], [50, 32]], c: P.black },
      { k: "line", x1: 50, y1: 0, x2: 50, y2: 100, c: P.red, w: 2 }, { k: "circle", x: 50, y: 66, r: 3, c: P.yellow },
    ],
    hips: P.black, legs: { l: P.black, r: "#C9CED6" }, arms: { l: P.black, r: "#C9CED6" }, hands: P.skin,
    accessories: [],
  },
  publisher: {
    agent: "publisher", character: "Harley Quinn", head: P.white,
    face: [{ k: "rect", x: 14, y: 33, w: 72, h: 18, c: P.black }, ...eyes(42, P.black), { k: "circle", x: 30, y: 58, r: 3.2, c: P.red }, { k: "circle", x: 70, y: 58, r: 3.2, c: P.black }, ...smile(76, 12, P.red)],
    torsoColor: P.red,
    torso: [
      { k: "rect", x: 0, y: 0, w: 50, h: 100, c: P.red }, { k: "rect", x: 50, y: 0, w: 50, h: 100, c: P.black },
      { k: "poly", pts: [[25, 30], [38, 45], [25, 60], [12, 45]], c: P.black }, { k: "poly", pts: [[75, 30], [88, 45], [75, 60], [62, 45]], c: P.red },
      { k: "poly", pts: [[25, 66], [34, 76], [25, 86], [16, 76]], c: P.black }, { k: "poly", pts: [[75, 66], [84, 76], [75, 86], [66, 76]], c: P.red },
      { k: "rect", x: 0, y: 0, w: 100, h: 8, c: P.white },
    ],
    hips: P.black, legs: { l: P.red, r: P.black }, arms: { l: P.red, r: P.black }, hands: P.white,
    accessories: [{ t: "hair", style: "pigtails", a: P.red, b: P.black }],
  },
};
