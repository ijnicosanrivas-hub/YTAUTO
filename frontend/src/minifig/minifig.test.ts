import { describe, expect, it } from "vitest";
import { CANVAS, drawOps, type Ctx, type Op } from "./ops";
import { FINISH_MS, animationState, poseFor } from "./pose";
import { ANIMATION_STATES, BODY, BRICK, FIGURE_HEIGHT, LDU, MATERIAL, PLASTIC, STUD } from "./styleBible";
import { VARIANTS } from "./variants";

const NINE: Record<string, string> = {
  chief: "Batman", director: "El Acertijo", scriptwriter: "El Joker", resources: "Catwoman", voice: "Bane",
  editor: "Nightwing", sound: "El Pingüino", reviewer: "Dos Caras", publisher: "Harley Quinn",
};
const ALLOWED_KEYS = ["accessories", "agent", "arms", "character", "design", "face", "hands", "head", "hips", "legs", "legsPrint", "scale", "torso", "torsoBack", "torsoColor"];
const OPTIONAL_KEYS = ["legsPrint", "torsoBack", "scale"];
const ACCESSORIES = ["ears", "cape", "hair", "hat", "umbrella", "monocle", "baneMask", "flower", "held", "jester", "furCollar", "ball", "armband"];
const COLOR = /^(#[0-9a-fA-F]{6}|rgba\(\d+,\d+,\d+,[\d.]+\))$/;

describe("Style Bible: una única minifigura para los nueve", () => {
  it("hay exactamente las nueve identidades fijadas por el usuario", () => {
    expect(Object.fromEntries(Object.values(VARIANTS).map((v) => [v.agent, v.character]))).toEqual(NINE);
    expect(Object.keys(VARIANTS).sort()).toEqual(Object.keys(NINE).sort());
  });

  it("las variantes solo aportan colores, estampados y accesorios: ninguna dimensión", () => {
    for (const v of Object.values(VARIANTS)) {
      expect(Object.keys(v).filter((k) => !OPTIONAL_KEYS.includes(k)).sort()).toEqual(ALLOWED_KEYS.filter((k) => !OPTIONAL_KEYS.includes(k)));
      expect(v.design.length).toBeGreaterThan(10); // cada figura cita el diseño oficial en que se basa
      for (const a of v.accessories) expect(ACCESSORIES).toContain(a.t);
      for (const c of [v.head, v.torsoColor, v.hips, v.legs.l, v.legs.r, v.arms.l, v.arms.r, v.hands]) expect(c).toMatch(COLOR);
    }
  });

  it("las proporciones son las de las piezas oficiales LEGO (medidas LDraw en LDU)", () => {
    expect(STUD).toMatchObject({ pitch: 20, r: 6, h: 4 }); // taco: Ø 4,8 mm, 1,6 mm de alto, paso 8 mm
    expect(BRICK).toMatchObject({ h: 24, plate: 8 });
    expect(BODY.torso).toMatchObject({ wBottom: 38, h: 32, d: 20 }); // pieza 973
    expect(BODY.torso.wTop).toBeLessThan(BODY.torso.wBottom); // trapecio: más ancho abajo
    expect(BODY.legs.w * 2).toBeCloseTo(BODY.hips.w, 0); // dos piernas = ancho de la cadera
    expect(BODY.arm.tilt).toBeCloseTo((9.782 * Math.PI) / 180, 3); // brazos 9,782° hacia fuera
    expect(BODY.arm.shoulderX).toBeCloseTo(15.55, 1);
    expect(BODY.hand.arc).toBeLessThan(Math.PI * 2); // pinza abierta (C), no anillo
    expect(BODY.head.r * 2).toBeLessThan(BODY.torso.wBottom); // cabeza más estrecha que el torso
    expect(FIGURE_HEIGHT).toBe(BODY.legs.h + BODY.hips.h + BODY.torso.h + BODY.head.h + BODY.headStud.h);
    expect(FIGURE_HEIGHT * LDU).toBeGreaterThan(1.5); // tamaño visible en la sala
    expect(MATERIAL.clearcoat).toBeGreaterThan(0); // plástico ABS brillante
  });

  it("cada variante tiene cara y torso estampados con operaciones válidas dentro del lienzo", () => {
    for (const v of Object.values(VARIANTS)) {
      expect(v.face.length, v.agent).toBeGreaterThan(2);
      expect(v.torso.length, v.agent).toBeGreaterThan(2);
      const inside = (n: number) => n >= -1 && n <= CANVAS + 1;
      for (const op of [...v.face, ...v.torso]) {
        if (op.k === "rect") [op.x, op.y, op.x + op.w, op.y + op.h].forEach((n) => expect(inside(n)).toBe(true));
        if (op.k === "circle" || op.k === "ellipse") [op.x, op.y].forEach((n) => expect(inside(n)).toBe(true));
        if (op.k === "poly") op.pts.flat().forEach((n) => expect(inside(n)).toBe(true));
        expect(op.c).toMatch(COLOR);
      }
    }
  });

  it("el estampado del torso cubre el frente completo (sin huecos transparentes)", () => {
    for (const v of Object.values(VARIANTS)) {
      const covered = v.torso.filter((o): o is Extract<Op, { k: "rect" }> => o.k === "rect").slice(0, 2).reduce((a, o) => a + o.w * o.h, 0);
      expect(covered, v.agent).toBeGreaterThanOrEqual(9800);
    }
  });

  it("cada figura reproduce el diseño de la referencia (último videojuego LEGO Batman)", () => {
    const has = (agent: string, t: string) => VARIANTS[agent].accessories.some((a) => a.t === t);
    const held = (agent: string, item: string, hand?: string) => VARIANTS[agent].accessories.some((a) => a.t === "held" && a.item === item && (!hand || a.hand === hand));
    const polyColors = (ops: { k: string; c: string }[]) => ops.filter((o) => o.k === "poly").map((o) => o.c);
    // Batman: traje gris, capucha negra con orejas, capa, cinturón y óvalo amarillos, batarang en la mano
    expect(VARIANTS.chief.torsoColor).toBe(PLASTIC.grey);
    expect(VARIANTS.chief.head).toBe(PLASTIC.black);
    expect(has("chief", "cape") && has("chief", "ears") && held("chief", "batarang")).toBe(true);
    expect(VARIANTS.chief.torso.some((o) => o.k === "ellipse" && o.c === PLASTIC.yellow)).toBe(true);
    // El Acertijo: traje verde con «?», corbata morada, bombín y bastón dorado
    expect(VARIANTS.director.torso.filter((o) => o.k === "text" && o.s === "?").length).toBeGreaterThanOrEqual(5);
    expect(polyColors(VARIANTS.director.torso)).toContain(PLASTIC.purple);
    expect(VARIANTS.director.accessories).toContainEqual({ t: "hat", style: "bowler", color: PLASTIC.darkGreen, band: PLASTIC.darkPurple });
    expect(held("director", "cane")).toBe(true);
    // El Joker: traje morado, chaleco naranja, pajarita verde, pelo verde, cara blanca, dentadura de cuerda
    expect(VARIANTS.scriptwriter.torsoColor).toBe(PLASTIC.purple);
    expect(VARIANTS.scriptwriter.head).toBe(PLASTIC.white);
    expect(polyColors(VARIANTS.scriptwriter.torso)).toEqual(expect.arrayContaining([PLASTIC.orange, PLASTIC.green]));
    expect(VARIANTS.scriptwriter.accessories).toContainEqual({ t: "hair", style: "joker", a: PLASTIC.green });
    expect(held("scriptwriter", "teeth")).toBe(true);
    // Catwoman: orejas, gafas grandes, líneas moradas, látigo
    expect(VARIANTS.resources.accessories).toContainEqual({ t: "ears", kind: "cat", color: PLASTIC.black });
    expect(VARIANTS.resources.face.filter((o) => o.k === "ellipse" && o.c === "#d7ecf2")).toHaveLength(2); // lentes
    expect(VARIANTS.resources.torso.some((o) => o.k === "line" && o.c === PLASTIC.purple)).toBe(true);
    expect(held("resources", "whip")).toBe(true);
    // Bane: figura grande, máscara con ojos rojos y mangueras verdes, arneses
    expect(VARIANTS.voice.scale).toBeGreaterThan(1.2);
    expect(VARIANTS.voice.accessories).toContainEqual({ t: "baneMask", mask: PLASTIC.reddishBrown, hose: PLASTIC.green });
    expect(VARIANTS.voice.face.some((o) => o.k === "ellipse" && o.c === PLASTIC.red)).toBe(true);
    expect(VARIANTS.voice.torsoColor).toBe(PLASTIC.nougat);
    // Nightwing: negro y azul, guantes azules y dos bastones de escrima (uno en cada mano)
    expect(VARIANTS.editor.torsoColor).toBe(PLASTIC.black);
    expect(VARIANTS.editor.arms.l).toBe(PLASTIC.blue);
    expect(VARIANTS.editor.hands).toBe(PLASTIC.blue);
    expect(held("editor", "escrima", "l") && held("editor", "escrima", "r")).toBe(true);
    // El Pingüino: chistera, monóculo, collar de piel, chaleco gris y paraguas
    expect(has("sound", "hat") && has("sound", "monocle") && has("sound", "furCollar") && held("sound", "umbrella")).toBe(true);
    expect(polyColors(VARIANTS.sound.torso)).toContain(PLASTIC.grey);
    // Dos Caras: traje blanco a un lado y negro al otro, cara con mitad quemada, moneda
    expect(VARIANTS.reviewer.torso.filter((o) => o.k === "rect").map((o) => o.c).slice(0, 2)).toEqual([PLASTIC.white, PLASTIC.black]);
    expect(new Set([VARIANTS.reviewer.legs.l, VARIANTS.reviewer.legs.r])).toEqual(new Set([PLASTIC.white, PLASTIC.black]));
    expect(VARIANTS.reviewer.face.some((o) => o.k === "rect" && o.c === PLASTIC.pink)).toBe(true);
    expect(held("reviewer", "coin")).toBe(true);
    // Harley Quinn: capucha de bufón roja y negra, traje bicolor con golilla blanca, mazo
    expect(VARIANTS.publisher.accessories).toContainEqual({ t: "jester", a: PLASTIC.red, b: PLASTIC.black });
    expect(polyColors(VARIANTS.publisher.torso)).toContain(PLASTIC.white);
    expect(new Set([VARIANTS.publisher.legs.l, VARIANTS.publisher.legs.r])).toEqual(new Set([PLASTIC.red, PLASTIC.black]));
    expect(held("publisher", "mallet")).toBe(true);
  });

  it("solo Bane es una figura grande; el resto comparte exactamente la misma escala", () => {
    for (const v of Object.values(VARIANTS)) expect(v.scale ?? 1, v.agent).toBe(v.agent === "voice" ? 1.32 : 1);
  });

  it("las figuras llevan más detalle que un dibujo plano: estampados de piernas y espalda, caras con pupilas y cejas", () => {
    const all = Object.values(VARIANTS);
    expect(all.filter((v) => v.torsoBack).length).toBeGreaterThanOrEqual(8);
    expect(all.filter((v) => v.legsPrint).length).toBeGreaterThanOrEqual(8);
    for (const v of all) expect(v.torso.length + v.face.length, v.agent).toBeGreaterThan(18);
    expect(all.reduce((n, v) => n + v.torso.length + v.face.length + (v.torsoBack?.length ?? 0), 0)).toBeGreaterThan(300);
  });

  it("los nueve son visualmente distintos entre sí", () => {
    const sig = Object.values(VARIANTS).map((v) => JSON.stringify([v.head, v.torsoColor, v.legs, v.arms, v.accessories.map((a) => a.t)]));
    expect(new Set(sig).size).toBe(9);
  });
});

describe("estampados (drawOps)", () => {
  it("ejecuta todos los tipos de operación sobre un lienzo", () => {
    const calls: string[] = [];
    const ctx = new Proxy({} as Record<string, unknown>, {
      get: (t, k: string) => (k in t ? t[k] : (...a: unknown[]) => void calls.push(`${k}:${a.length}`)),
      set: (t, k: string, v) => ((t[k] = v), true),
    }) as unknown as Ctx;
    for (const v of Object.values(VARIANTS)) drawOps(ctx, [...v.face, ...v.torso], 256);
    expect(new Set(calls.map((c) => c.split(":")[0]))).toEqual(new Set(["fillRect", "beginPath", "arc", "ellipse", "fill", "moveTo", "lineTo", "closePath", "stroke", "fillText"]));
  });
});

describe("animación común", () => {
  const base = { finishedAt: null as string | null, now: 1_000_000, receiving: false };
  it("el estado sale del estado real del agente", () => {
    expect(animationState({ ...base, status: "idle" }).state).toBe("wait");
    expect(animationState({ ...base, status: "running" }).state).toBe("work");
    expect(animationState({ ...base, status: "waiting" }).state).toBe("interact");
    expect(animationState({ ...base, status: "error" }).state).toBe("error");
    expect(animationState({ ...base, status: "idle", receiving: true }).state).toBe("move");
  });
  it("finish solo dura FINISH_MS tras terminar y nunca antes de terminar", () => {
    const at = (ms: number) => new Date(base.now - ms).toISOString();
    expect(animationState({ ...base, status: "idle", finishedAt: at(1000) }).state).toBe("finish");
    expect(animationState({ ...base, status: "idle", finishedAt: at(FINISH_MS + 500) }).state).toBe("wait");
    expect(animationState({ ...base, status: "idle", finishedAt: at(-5000) }).state).toBe("wait"); // fecha futura: no es "terminó"
    expect(animationState({ ...base, status: "running", finishedAt: at(100) }).state).toBe("work"); // trabajar manda sobre terminar
  });
  it("no inventa actividad: sin eventos, todos esperan", () => {
    for (const status of ["idle"] as const) expect(animationState({ ...base, status }).state).toBe("wait");
  });
  it("los seis estados existen, son finitos y distintos entre sí", () => {
    const poses = ANIMATION_STATES.map((s) => poseFor(s, 1.3, 0.7, 0.4));
    for (const p of poses) for (const n of [p.bodyY, p.bodyYaw, p.headYaw, p.headPitch, p.armL.x, p.armL.spread, p.armR.x, p.armR.spread, p.legL, p.legR, p.cape]) expect(Number.isFinite(n)).toBe(true);
    expect(new Set(poses.map((p) => JSON.stringify(p))).size).toBe(ANIMATION_STATES.length);
  });
  it("cada estado tiene el movimiento que dice su nombre", () => {
    expect(poseFor("work", 0.5).armL.x).toBeLessThan(-0.8); // brazos adelante, tecleando
    expect(poseFor("interact", 0.5).armR.x).toBeLessThan(-2); // brazo levantado
    expect(Math.abs(poseFor("move", 0.2).legL)).toBeGreaterThan(0.1);
    expect(poseFor("wait", 0.3).legL).toBe(0);
    expect(poseFor("error", 0.3).headPitch).toBeGreaterThan(0.4); // cabeza gacha
    expect(poseFor("finish", 0.1, 0, 0.1).armL.x).toBeLessThan(-1); // brazos arriba
  });
  it("la celebración se apaga: al terminar su ventana vuelve al reposo", () => {
    const end = poseFor("finish", 0, 0, FINISH_MS / 1000);
    expect(end.bodyY).toBeCloseTo(0, 6);
    expect(end.armL.x).toBeCloseTo(0, 6);
  });
  it("los personajes no se mueven al unísono (fase distinta por semilla)", () => {
    expect(poseFor("wait", 1, 0).headYaw).not.toBeCloseTo(poseFor("wait", 1, 2.4).headYaw, 3);
  });
});
