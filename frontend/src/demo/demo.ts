/** Modo demostración (versión estática, p. ej. en Netlify): sin servidor, con datos de ejemplo y una producción simulada. */
import agents from "./agents.json";
import theme from "./theme.json";
import { useLive } from "../store";
import type { AgentState, YtEvent } from "../types";

export const DEMO = import.meta.env.VITE_DEMO === "1";

export class DemoError extends Error {}

/** Respuesta a las lecturas de la API en modo demostración. */
export async function demoGet(path: string): Promise<unknown> {
  const p = path.split("?")[0];
  if (p === "/api/agents") return agents;
  if (p === "/api/theme") return theme;
  if (p === "/api/channels") {
    const t = theme as { palette: { accent: string }; room_title: string; agents: Record<string, { character: string; glyph: string; color: string }> };
    const ref = (a: string) => ({ character: t.agents[a].character, glyph: t.agents[a].glyph, color: t.agents[a].color });
    return [{ id: "general", name: "General", theme: "gotham", tagline: "Demostración", accent: t.palette.accent, room_title: t.room_title,
      director: ref("director"), chief: ref("chief"), has_director_image: true }];
  }
  if (p === "/api/overview") return { channels: [], claude_slots: 1 };
  if (p === "/api/dashboard") return { projects: { total: 0, by_status: {} }, waiting_approval: [], claude: { calls: 0, seconds: 0, lanes: {} }, budget: null, agents: (agents as { agents: AgentState[] }).agents };
  if (p === "/api/projects") return [];
  if (p === "/api/health") return { ok: true, llm: { provider: "demostración", ok: true, message: "Sin servidor" }, worker: false };
  if (p === "/api/events") return [];
  if (p === "/api/figures" || p === "/api/profiles/gotham/figures") {
    const r = await fetch("/personajes/meta.json");
    const m = (await r.json()) as Record<string, { anchor_x: number; w: number; h: number }>;
    return Object.fromEntries(Object.entries(m).map(([k, v]) => [k, { anchor_x: v.anchor_x, w: v.w, h: v.h }]));
  }
  throw new DemoError("Modo demostración: esta sección necesita el servidor de YTAUTO (instálalo en tu PC para usarla).");
}

const ORDER = ["chief", "director", "scriptwriter", "resources", "voice", "editor", "sound", "reviewer", "publisher"];
const TASKS: Record<string, string> = {
  chief: "Planificando el vídeo", director: "Definiendo concepto y escenas", scriptwriter: "Escribiendo gancho y guion",
  resources: "Reuniendo recursos visuales", voice: "Preparando la locución", editor: "Montando el vídeo vertical",
  sound: "Mezclando música y efectos", reviewer: "Revisando calidad", publisher: "Preparando título y hashtags",
};

/** Simula una producción en bucle para que la sala se vea viva (solo demostración). */
export function startDemo(): () => void {
  const base = (agents as { agents: AgentState[] }).agents;
  const live = useLive.getState();
  live.setConnected(true);
  live.applyMessage({ type: "hello", agents: base });
  const state: Record<string, AgentState> = Object.fromEntries(base.map((a) => [a.name, { ...a }]));
  let i = 0, progress = 0;
  const push = (a: AgentState, type: string) => {
    const event: YtEvent = { type, project_id: "demo", agent: a.name, phase: a.phase, data: { task: a.task }, at: new Date().toISOString() };
    useLive.getState().applyMessage({ type: "event", event, agent: { ...a } });
  };
  const tick = setInterval(() => {
    const name = ORDER[i % ORDER.length];
    const a = state[name];
    if (progress === 0) { Object.assign(a, { status: "running", task: TASKS[name], progress: 0, started_at: new Date().toISOString(), project_id: "demo" }); push(a, "agent.started"); }
    progress += 0.25;
    if (progress < 1) { a.progress = progress; push(a, "agent.progress"); return; }
    Object.assign(a, { status: "idle", progress: 1, finished_at: new Date().toISOString(), runs: a.runs + 1, last_result: "Hecho" });
    push(a, "agent.finished");
    progress = 0; i++;
  }, 1500);
  return () => clearInterval(tick);
}
