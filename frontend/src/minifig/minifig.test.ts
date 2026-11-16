import { describe, expect, it } from "vitest";
import { CANVAS, drawOps, type Ctx, type Op } from "./ops";
import { FINISH_MS, animationState, poseFor } from "./pose";
import { ANIMATION_STATES, BODY, FIGURE_HEIGHT, FIGURE_SCALE, MATERIAL, PLASTIC } from "./styleBible";
import { VARIANTS } from "./variants";

const NINE: Record<string, string> = {
  chief: "Batman", director: "El Acertijo", scriptwriter: "El Joker", resources: "Catwoman", voice: "Bane",
  editor: "Nightwing", sound: "El Pingüino", reviewer: "Dos Caras", publisher: "Harley Quinn",
};
const ALLOWED_KEYS = ["accessories", "agent", "arms", "character", "face", "hands", "head", "hips", "legs", "torso", "torsoColor"];
const ACCESSORIES = ["ears", "cape", "hair", "hat", "umbrella", "monocle", "baneMask", "flower"];

describe("Style Bible: una única minifigura para los nueve", () => {
  it("hay exactamente las nueve identidades fijadas por el usuario", () => {
    expect(Object.fromEntries(Object.values(VARIANTS).map((v) => [v.agent, v.character]))).toEqual(NINE);
    expect(Object.keys(VARIANTS).sort()).toEqual(Object.keys(NINE).sort());
  });

  it("las variantes solo aportan colores, estampados y accesorios: ninguna dimensión", () => {
    for (const v of Object.values(VARIANTS)) {
      expect(Object.keys(v).sort()).toEqual(ALLOWED_KEYS);
      for (const a of v.accessories) expect(ACCESSORIES).toContain(a.t);
      for (const c of [v.head, v.torsoColor, v.hips, v.legs.l, v.legs.r, v.arms.l, v.arms.r, v.hands]) expect(c).toMatch(/^#[0-9a-fA-F]{6}$/);
    }
  });

  it("las proporciones son una constante común y coherentes con una minifigura", () => {
    expect(FIGURE_HEIGHT).toBeCloseTo(BODY.legs.h + BODY.hips.h + BODY.torso.h + BODY.neck.h + BODY.head.h, 6);
    expect(BODY.head.r * 2).toBeGreaterThan(BODY.torso.wTop * 0.8); // cabeza grande de juguete
    expect(BODY.arm.shoulderX).toBeGreaterThan(BODY.torso.wTop / 2); // brazos fuera del torso
    expect(BODY.hand.arc).toBeLessThan(Math.PI * 2); // pinza abierta (C), no anillo
    expect(FIGURE_SCALE).toBeGreaterThan(0);
    expect(MATERIAL.clearcoat).toBeGreaterThan(0); // plástico moldeado brillante
  });

  it("cada variante tiene cara y torso estampados con operaciones válidas dentro del lienzo", () => {
    for (const v of Object.values(VARIANTS)) {
      expect(v.face.length, v.agent).toBeGreaterThan(2);
      expect(v.torso.length, v.agent).toBeGreaterThan(2);
      const inside = (n: number) => n >= -1 && n <= CANVAS + 1;
      for (const op of [...v.face, ...v.torso]) {
        if (op.k === "rect") [op.x, op.y, op.x + op.w, op.y + op.h].forEach((n) => expect(inside(n)).toBe(true));
        if (op.k === "circle") [op.x, op.y].forEach((n) => expect(inside(n)).toBe(true));
        if (op.k === "poly") op.pts.flat().forEach((n) => expect(inside(n)).toBe(true));
        expect(op.c).toMatch(/^#[0-9a-fA-F]{6}$/);
      }
    }
  });

  it("el estampado del torso cubre el frente completo (sin huecos transparentes)", () => {
    for (const v of Object.values(VARIANTS)) {
      const covered = v.torso.filter((o): o is Extract<Op, { k: "rect" }> => o.k === "rect").slice(0, 2).reduce((a, o) => a + o.w * o.h, 0);
      expect(covered, v.agent).toBeGreaterThanOrEqual(9800);
    }
  });

  it("los rasgos reconocibles de cada personaje se conservan", () => {
    const has = (agent: string, t: string) => VARIANTS[agent].accessories.some((a) => a.t === t);
    expect(has("chief", "cape") && has("chief", "ears")).toBe(true); // capa y orejas de murciélago
    expect(VARIANTS.chief.torsoColor).toBe(PLASTIC.black);
    expect(VARIANTS.director.torso.filter((o) => o.k === "text" && o.s === "?").length).toBeGreaterThan(2); // signos de interrogación
    expect(VARIANTS.scriptwriter.accessories).toContainEqual({ t: "hair", style: "joker", a: PLASTIC.green }); // pelo verde
    expect(VARIANTS.scriptwriter.torsoColor).toBe(PLASTIC.purple);
    expect(VARIANTS.resources.accessories).toContainEqual({ t: "ears", kind: "cat", color: PLASTIC.black });
    expect(has("voice", "baneMask")).toBe(true); // máscara respiratoria
    expect(VARIANTS.editor.arms.l).toBe(PLASTIC.blue); // detalles azules sobre traje oscuro
    expect(VARIANTS.editor.torsoColor).toBe(PLASTIC.black);
    expect(has("sound", "hat") && has("sound", "umbrella") && has("sound", "monocle")).toBe(true); // sombrero, paraguas
    expect(VARIANTS.reviewer.legs.l).not.toBe(VARIANTS.reviewer.legs.r); // vestimenta dividida
    expect(VARIANTS.reviewer.arms.l).not.toBe(VARIANTS.reviewer.arms.r);
    expect(VARIANTS.publisher.accessories).toContainEqual({ t: "hair", style: "pigtails", a: PLASTIC.red, b: PLASTIC.black }); // coletas rojas y negras
    expect(new Set([VARIANTS.publisher.legs.l, VARIANTS.publisher.legs.r])).toEqual(new Set([PLASTIC.red, PLASTIC.black]));
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
    expect(new Set(calls.map((c) => c.split(":")[0]))).toEqual(new Set(["fillRect", "beginPath", "arc", "fill", "moveTo", "lineTo", "closePath", "stroke", "fillText"]));
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
    for (const p of poses) for (const n of [p.bodyY, p.bodyYaw, p.headYaw, p.headPitch, p.armL.x, p.armL.z, p.armR.x, p.armR.z, p.legL, p.legR, p.cape]) expect(Number.isFinite(n)).toBe(true);
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
