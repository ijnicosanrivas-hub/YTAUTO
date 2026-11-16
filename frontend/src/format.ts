import type { AgentStatus } from "./types";

export const STATUS_LABEL: Record<string, string> = {
  pending: "Pendiente",
  assigned: "Asignada",
  running: "En ejecución",
  blocked: "Bloqueada",
  completed: "Completada",
  error: "Error",
  in_review: "En revisión",
  approved: "Aprobada",
  active: "Activo",
  paused: "Pausado",
  cancelled: "Cancelado",
  idle: "En espera",
  waiting: "Esperando",
};

export const AGENT_COLOR: Record<AgentStatus, string> = {
  idle: "#5b6b8c",
  running: "#22d3ee",
  waiting: "#f5b941",
  error: "#f43f5e",
};

export const CATEGORY_LABEL: Record<string, string> = {
  image: "Imágenes",
  video: "Vídeo",
  tts: "Voz",
  music: "Música",
  sfx: "Efectos",
  subtitle: "Subtítulos",
  rendering: "Renderizado",
  storage: "Almacenamiento",
  publishing: "Publicación",
};

export const PLATFORM_LABEL: Record<string, string> = {
  youtube_shorts: "YouTube Shorts",
  instagram_reels: "Instagram Reels",
  tiktok: "TikTok",
};

export function statusLabel(s: string): string {
  return STATUS_LABEL[s] ?? s;
}

export function elapsed(from: string | null, to: string | null = null, now: number = Date.now()): string {
  if (!from) return "—";
  const start = Date.parse(from);
  const end = to ? Date.parse(to) : now;
  const s = Math.max(0, Math.round((end - start) / 1000));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  return `${m}m ${String(s % 60).padStart(2, "0")}s`;
}

export function eur(v: number | null | undefined): string {
  return v == null ? "—" : `${v.toFixed(2)} €`;
}

export function shortDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("es-ES", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export function describeEvent(type: string, data: Record<string, unknown>): string {
  switch (type) {
    case "agent.started":
      return "comienza";
    case "agent.finished":
      return String(data.summary ?? "termina");
    case "agent.progress":
      return `${Math.round(Number(data.progress ?? 0) * 100)}% ${data.message ?? ""}`;
    case "llm.call":
      return `consulta a Claude (${data.model}, intento ${data.attempt})`;
    case "phase.status":
      return `fase → ${statusLabel(String(data.status))}${data.error ? `: ${data.error}` : ""}`;
    case "provider.fallback":
      return `proveedor alternativo: ${data.used} (fallaron ${(data.skipped as string[] | undefined)?.join(", ")})`;
    case "budget.warning":
      return `aviso de presupuesto: ${data.message}`;
    case "cost":
      return `coste ${Number(data.eur).toFixed(3)} € en ${data.provider_id}`;
    case "approval":
      return `${data.approved ? "aprobado" : "rechazado"} ${data.gate}`;
    default:
      return type;
  }
}
