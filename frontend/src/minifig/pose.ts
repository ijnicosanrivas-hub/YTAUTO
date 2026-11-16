/**
 * Animación común a los nueve personajes. El estado sale SOLO del estado real del agente:
 *  work     → status "running"
 *  interact → status "waiting" (espera tu decisión: saluda)
 *  error    → status "error"
 *  finish   → terminó hace menos de FINISH_MS
 *  move     → recibe una entrega real de otro agente (conexión activa hacia él)
 *  wait     → todo lo demás
 */
import type { AgentStatus } from "../types";
import type { AnimationState } from "./styleBible";

export const FINISH_MS = 3500;

export interface Pose {
  bodyY: number; // salto/rebote vertical
  bodyYaw: number;
  headYaw: number;
  headPitch: number;
  armL: { x: number; spread: number }; // spread > 0 separa el brazo del cuerpo (se suma a la inclinación de 9,8° de la pieza)
  armR: { x: number; spread: number };
  lean: number; // inclinación del torso hacia delante
  legL: number;
  legR: number;
  cape: number; // balanceo de la capa
}

export interface AnimInput {
  status: AgentStatus;
  finishedAt: string | null;
  now: number;
  receiving: boolean;
}

export function animationState(i: AnimInput): { state: AnimationState; sinceFinish: number } {
  const since = i.finishedAt ? (i.now - Date.parse(i.finishedAt)) / 1000 : Infinity;
  if (i.status === "running") return { state: "work", sinceFinish: Infinity };
  if (i.status === "error") return { state: "error", sinceFinish: Infinity };
  if (i.status === "waiting") return { state: "interact", sinceFinish: Infinity };
  if (since >= 0 && since * 1000 < FINISH_MS) return { state: "finish", sinceFinish: since };
  if (i.receiving) return { state: "move", sinceFinish: Infinity };
  return { state: "wait", sinceFinish: Infinity };
}

const REST: Pose = { bodyY: 0, bodyYaw: 0, headYaw: 0, headPitch: 0, armL: { x: 0, spread: 0 }, armR: { x: 0, spread: 0 }, lean: 0, legL: 0, legR: 0, cape: 0.05 };

/** Pose en el instante t (s). `seed` desfasa a cada personaje para que no se muevan al unísono. */
export function poseFor(state: AnimationState, t: number, seed = 0, sinceFinish = 0): Pose {
  const p: Pose = { ...REST, armL: { ...REST.armL }, armR: { ...REST.armR } };
  const s = (f: number, ph = 0) => Math.sin(t * f + seed + ph);
  switch (state) {
    case "wait": // espera: respira, mira alrededor
      p.bodyY = s(1.6) * 0.012;
      p.headYaw = s(0.5) * 0.35;
      p.armL.spread += s(1.6) * 0.04;
      p.armR.spread += s(1.6) * 0.04;
      p.cape = 0.05 + s(1.1) * 0.04;
      break;
    case "move": // movimiento: marcha en el sitio
      p.bodyY = Math.abs(s(7)) * 0.05;
      p.legL = s(7) * 0.7;
      p.legR = -s(7) * 0.7;
      p.armL.x = -s(7) * 0.6;
      p.armR.x = s(7) * 0.6;
      p.cape = 0.25 + s(7) * 0.08;
      break;
    case "work": // trabajo: ante su consola, tecleando
      p.armL.x = -1.15 + s(9) * 0.14;
      p.armR.x = -1.15 - s(9) * 0.14;
      p.armL.spread = 0.12;
      p.armR.spread = 0.12;
      p.lean = 0.1 + s(2) * 0.015;
      p.headPitch = 0.22 + s(2.2) * 0.05;
      p.bodyYaw = s(1.3) * 0.05;
      p.bodyY = s(9) * 0.006;
      p.cape = 0.12 + s(2) * 0.03;
      break;
    case "interact": // interacción: te llama (necesita tu decisión)
      p.armR.x = -2.7;
      p.armR.spread = 0.25 + s(7) * 0.4;
      p.armL.spread = 0.35;
      p.headYaw = s(1) * 0.15;
      p.bodyY = Math.abs(s(3.5)) * 0.03;
      break;
    case "finish": { // finalización: salto de victoria que se apaga
      const k = Math.max(0, 1 - sinceFinish / (FINISH_MS / 1000));
      p.bodyY = Math.abs(Math.sin(sinceFinish * Math.PI * 2.5)) * 0.25 * k;
      p.armL.x = -2.9 * Math.min(1, k * 2.5);
      p.armR.x = -2.9 * Math.min(1, k * 2.5);
      p.armL.spread = 0.4 + s(8) * 0.15;
      p.armR.spread = 0.4 + s(8) * 0.15;
      p.cape = 0.3 * k;
      break;
    }
    case "error": // error: cabizbajo y temblando
      p.headPitch = 0.55;
      p.bodyYaw = s(14) * 0.05;
      p.bodyY = -0.02;
      p.armL.x = 0.1;
      p.armR.x = 0.1;
      break;
  }
  return p;
}
