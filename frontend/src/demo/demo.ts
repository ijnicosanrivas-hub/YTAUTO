/**
 * Modo demostración (versión estática, p. ej. en Netlify): sin servidor. Muestra los 4 canales con sus estilos,
 * datos de ejemplo y una producción simulada en paralelo en todos ellos. No produce vídeos reales.
 */
import agents from "./agents.json";
import channels from "./channels.json";
import themes from "./themes.json";
import { useLive } from "../store";
import type { AgentState, YtEvent } from "../types";

export const DEMO = import.meta.env.VITE_DEMO === "1";

export class DemoError extends Error {}

type Ch = { id: string; name: string; theme: string; tagline: string };
const CHANNELS = channels as Ch[];
const THEMES = themes as Record<string, unknown>;
const BASE = (agents as { agents: AgentState[] }).agents;
const ORDER = ["chief", "director", "scriptwriter", "resources", "voice", "editor", "sound", "reviewer", "publisher"];

const IDEAS: Record<string, string[]> = {
  general: ["El origen del Joker contado en 60 segundos", "Los 5 gadgets más locos de Batman"],
  gta6: ["Todo lo que sabemos de Lucia y Jason", "Los easter eggs del tráiler 2"],
  kids: ["Canción para aprender los colores con globos"],
  deportes: ["El gol más rápido de la historia", "Por qué el VAR cambió el fútbol"],
};
const TOKENS: Record<string, number> = { general: 5_400_000, gta6: 5_900_000, kids: 1_300_000, deportes: 3_000_000 };
const daysAgo = (d: number) => new Date(Date.now() - d * 86_400_000).toISOString();

function chOf(path: string): string {
  return new URLSearchParams(path.split("?")[1] ?? "").get("channel") ?? useLive.getState().channel ?? "general";
}

function projects(ch: string) {
  return (IDEAS[ch] ?? []).map((name, i) => ({
    id: `demo-${ch}-${i}`, name, topic: name, status: i === 0 ? "active" : "completed", duration_s: 60,
    progress: i === 0 ? 0.35 + (Date.now() / 60000) % 0.5 : 1, next_phase: i === 0 ? "script" : null,
    waiting_approval: [], created_at: daysAgo(i + 1), blocked_reason: null, channel: ch,
  }));
}

function demoLicenses() {
  const daily = (seed: number) => [...Array(14)].map((_, i) => ({ day: daysAgo(13 - i).slice(0, 10), tokens: Math.round(120_000 + Math.abs(Math.sin(i + seed)) * 380_000) }));
  const lic = (id: string, name: string, ch: string, plan: string, month: number, limit: number | null, limited = false) => ({
    id, name, channel_id: ch, kind: plan === "API" ? "api_key" : "claude_session", plan, config_dir: null, secret_hint: plan === "API" ? "••••1234" : null,
    monthly_token_limit: limit, enabled: true, is_limited: limited, limited_until: null, limited_reason: limited ? "Límite de 5 horas alcanzado (demostración)" : null,
    limited_now: limited, status: limited ? "limited" : "ok", usage_pct: limit ? Math.round((1000 * month) / limit) / 10 : null, last_used_at: daysAgo(0), notes: null,
    tokens: { today: Math.round(month / 25), d7: Math.round(month / 3.5), d30: month, month }, calls: { today: 6, month: 110, total: 180 },
    input_tokens: Math.round(month * 0.7), output_tokens: Math.round(month * 0.14), cache_read_tokens: Math.round(month * 0.6), cost_usd_eq: month / 180_000, seconds: 7000,
    by_agent: { director: month * 0.2, scriptwriter: month * 0.25, publisher: month * 0.15, reviewer: month * 0.2, chief: month * 0.1 }, by_channel: { [ch]: month },
    daily: daily(month % 7), last_call_at: daysAgo(0),
  });
  return {
    licenses: [
      lic("lic_demo01", "Pro Batman 1", "general", "Pro", 2_700_000, 4_000_000, true), lic("lic_demo02", "Max Batman", "general", "Max 5x", 2_700_000, 20_000_000),
      lic("lic_demo03", "Pro Vice 1", "gta6", "Pro", 3_400_000, 4_000_000), lic("lic_demo04", "Pro Vice 2", "gta6", "Pro", 2_500_000, 4_000_000),
      lic("lic_demo05", "Pro Kids", "kids", "Pro", 1_300_000, 4_000_000),
      lic("lic_demo06", "Pro Deportes", "deportes", "Pro", 2_200_000, 4_000_000), lic("lic_demo07", "API Deportes", "deportes", "API", 800_000, null),
    ],
    default: null, totals: { tokens_month: 15_600_000, calls_month: 770 }, days: [], claude_slots: 7,
    channels: CHANNELS.map((c) => ({ id: c.id, name: c.name, theme: c.theme })),
  };
}

function overview() {
  const s = useLive.getState();
  return {
    claude_slots: 7,
    channels: CHANNELS.map((c) => {
      const board = Object.values(s.boards[c.id] ?? {});
      const t = THEMES[c.theme] as { palette: { accent: string }; agents: Record<string, { character: string; glyph: string; color: string }> };
      const d = t.agents.director;
      const j = t.agents.chief;
      const ps = projects(c.id);
      return {
        channel: c, accent: t.palette.accent, director: { character: d.character, glyph: d.glyph, color: d.color },
        chief: { character: j.character, glyph: j.glyph, color: j.color },
        projects: { total: ps.length, by_status: { active: 1, ...(ps.length > 1 ? { completed: ps.length - 1 } : {}) } },
        current: { id: ps[0].id, name: ps[0].name },
        running_agents: board.filter((a) => a.status === "running").map((a) => ({ name: a.name, task: a.task, progress: a.progress })),
        waiting_agents: 0, error_agents: 0, tokens_total: TOKENS[c.id] ?? 0,
        licenses: { total: c.id === "kids" ? 1 : 2, limited: c.id === "general" ? 1 : 0, enabled: c.id === "kids" ? 1 : 2 },
      };
    }),
  };
}

/** Respuesta a las lecturas de la API en modo demostración. */
export async function demoGet(path: string): Promise<unknown> {
  const p = path.split("?")[0];
  const ch = chOf(path);
  if (p === "/api/channels") return channels;
  if (p === "/api/theme") return THEMES[CHANNELS.find((c) => c.id === ch)?.theme ?? "gotham"];
  if (p === "/api/agents") return { ...(agents as object), agents: Object.values(useLive.getState().boards[ch] ?? {}).length ? Object.values(useLive.getState().boards[ch]) : BASE };
  if (p === "/api/overview") return overview();
  if (p === "/api/projects") return projects(ch);
  if (p === "/api/dashboard") {
    const ps = projects(ch);
    return { projects: { total: ps.length, by_status: { active: 1, completed: ps.length - 1 } }, waiting_approval: [], budget: { spent_month_eur: 0, monthly_budget_eur: null },
      claude: { calls: 40 + ps.length * 37, seconds: 5200, lanes: {} }, agents: Object.values(useLive.getState().boards[ch] ?? {}) };
  }
  if (p === "/api/licenses") return demoLicenses();
  if (p === "/api/licenses/plan") return { plan: Object.fromEntries(ORDER.map((a) => [a, null])), license_map: {} };
  if (p === "/api/health") return { ok: true, llm: { provider: "demostración", ok: true, message: "Sin servidor" }, worker: false };
  if (p === "/api/events") return [];
  if (p === "/api/figures" || p === "/api/profiles/gotham/figures") {
    const r = await fetch("/personajes/meta.json");
    const m = (await r.json()) as Record<string, { anchor_x: number; w: number; h: number }>;
    return Object.fromEntries(Object.entries(m).map(([k, v]) => [k, { anchor_x: v.anchor_x, w: v.w, h: v.h }]));
  }
  if (/^\/api\/profiles\/[a-z0-9_-]+\/figures$/.test(p)) return {};
  throw new DemoError("Modo demostración: esta sección necesita el servidor de YTAUTO (instálalo en tu PC para usarla).");
}

const TASKS: Record<string, string> = {
  chief: "Planificando el vídeo", director: "Definiendo concepto y escenas", scriptwriter: "Escribiendo gancho y guion",
  resources: "Reuniendo recursos visuales", voice: "Preparando la locución", editor: "Montando el vídeo vertical",
  sound: "Mezclando música y efectos", reviewer: "Revisando calidad", publisher: "Preparando título y hashtags",
};

/** Simula una producción en bucle en los 4 canales a la vez para que todo se vea vivo (solo demostración). */
export function startDemo(): () => void {
  const live = useLive.getState();
  live.setConnected(true);
  const boards = Object.fromEntries(CHANNELS.map((c) => [c.id, BASE.map((a) => ({ ...a, channel: c.id }))]));
  live.applyMessage({ type: "hello", agents: boards[live.channel] ?? BASE, boards });
  const state = Object.fromEntries(CHANNELS.map((c, k) => [c.id, { i: k * 2, progress: 0, agents: Object.fromEntries(boards[c.id].map((a) => [a.name, a])) }]));
  const push = (ch: string, a: AgentState, type: string) => {
    const event: YtEvent = { type, project_id: `demo-${ch}-0`, agent: a.name, phase: a.phase, data: { task: a.task, summary: a.last_result }, at: new Date().toISOString(), channel: ch };
    useLive.getState().applyMessage({ type: "event", event, agent: { ...a }, channel: ch });
  };
  const tick = setInterval(() => {
    for (const c of CHANNELS) {
      const s = state[c.id];
      const name = ORDER[s.i % ORDER.length];
      const a = s.agents[name];
      if (s.progress === 0) { Object.assign(a, { status: "running", task: TASKS[name], progress: 0, started_at: new Date().toISOString(), project_id: `demo-${c.id}-0` }); push(c.id, a, "agent.started"); }
      s.progress += 0.2;
      if (s.progress < 1) { a.progress = s.progress; push(c.id, a, "agent.progress"); continue; }
      Object.assign(a, { status: "idle", progress: 1, finished_at: new Date().toISOString(), runs: a.runs + 1, last_result: "Hecho" });
      push(c.id, a, "agent.finished");
      s.progress = 0;
      s.i++;
    }
  }, 1600);
  return () => clearInterval(tick);
}
