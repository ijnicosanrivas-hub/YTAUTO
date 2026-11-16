import { AGENT_COLOR } from "./format";
import type { AgentState, AgentStatus, Persona, Theme } from "./types";

export const CLASSIC_THEME: Theme = {
  id: "classic",
  name: "Clásico",
  brand: "YTAUTO",
  room_title: "Sala de producción",
  room_subtitle: "Fábrica multiagente de vídeos cortos",
  palette: { accent: "#22d3ee", background: "#0b1020", panel: "#121a30" },
  agents: {},
};

export function personaFor(theme: Theme, name: string): Persona | undefined {
  return theme.agents[name];
}

/** Nombre a mostrar: el personaje si el tema lo define; si no, el título funcional del agente. */
export function displayName(theme: Theme, agent: Pick<AgentState, "name" | "title">): string {
  return personaFor(theme, agent.name)?.character ?? agent.title;
}

/** Color del cuerpo del nodo: el del personaje, o el color de estado si no hay personaje. */
export function bodyColor(theme: Theme, agent: Pick<AgentState, "name" | "status">): string {
  return personaFor(theme, agent.name)?.color ?? AGENT_COLOR[agent.status] ?? "#5b6b8c";
}

/**
 * Frase del personaje según el estado REAL del agente (nunca inventa actividad):
 * running → started, waiting → waiting, error → error, idle → finished si ya trabajó, idle si no.
 */
export function quoteFor(theme: Theme, agent: Pick<AgentState, "name" | "status" | "runs" | "last_result">): string | undefined {
  const p = personaFor(theme, agent.name);
  if (!p) return undefined;
  const key: Record<AgentStatus, string> = { running: "started", waiting: "waiting", error: "error", idle: "idle" };
  const state = agent.status === "idle" && agent.runs > 0 && agent.last_result ? "finished" : key[agent.status];
  return p.quotes[state];
}
