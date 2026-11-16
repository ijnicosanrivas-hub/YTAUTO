import { create } from "zustand";
import { wsUrl } from "./api";
import { CLASSIC_THEME } from "./theme";
import type { AgentState, Theme, YtEvent } from "./types";

export type Route = { page: string; id?: string };

export function parseHash(hash: string): Route {
  const [page, id] = hash.replace(/^#\/?/, "").split("?")[0].split("/"); // el «?» admite parámetros (p. ej. ?calidad=alta)
  return { page: page || "dashboard", id: id || undefined };
}

interface LiveState {
  route: Route;
  connected: boolean;
  agents: Record<string, AgentState>;
  theme: Theme;
  setTheme: (t: Theme) => void;
  events: YtEvent[];
  /** Última vez (ms) que cada agente emitió un evento real: anima las conexiones de la sala. */
  lastActivity: Record<string, number>;
  /** Contador que cambia con cada evento de un proyecto: las vistas lo usan para refrescar datos. */
  revision: number;
  navigate: (hash: string) => void;
  setRoute: (r: Route) => void;
  applyMessage: (msg: WsMessage) => void;
  setConnected: (c: boolean) => void;
}

export type WsMessage =
  | { type: "hello"; agents: AgentState[] }
  | { type: "event"; event: YtEvent; agent: AgentState | null };

const MAX_EVENTS = 400;

export const useLive = create<LiveState>((set) => ({
  route: parseHash(typeof location !== "undefined" ? location.hash : ""),
  connected: false,
  agents: {},
  theme: CLASSIC_THEME,
  setTheme: (theme) => set({ theme }),
  events: [],
  lastActivity: {},
  revision: 0,
  navigate: (hash) => {
    location.hash = hash;
  },
  setRoute: (route) => set({ route }),
  setConnected: (connected) => set({ connected }),
  applyMessage: (msg) =>
    set((s) => {
      if (msg.type === "hello") {
        return { agents: Object.fromEntries(msg.agents.map((a) => [a.name, a])) };
      }
      const agents = msg.agent ? { ...s.agents, [msg.agent.name]: msg.agent } : s.agents;
      const lastActivity = msg.agent ? { ...s.lastActivity, [msg.agent.name]: Date.now() } : s.lastActivity;
      const events = [msg.event, ...s.events].slice(0, MAX_EVENTS);
      const revision = msg.event.type === "agent.progress" ? s.revision : s.revision + 1;
      return { agents, lastActivity, events, revision };
    }),
}));

let socket: WebSocket | null = null;
let retry = 0;

export function connectLive(): void {
  if (socket && socket.readyState <= 1) return;
  socket = new WebSocket(wsUrl());
  socket.onopen = () => {
    retry = 0;
    useLive.getState().setConnected(true);
  };
  socket.onmessage = (ev) => {
    try {
      useLive.getState().applyMessage(JSON.parse(ev.data) as WsMessage);
    } catch {
      /* mensaje no válido */
    }
  };
  socket.onclose = () => {
    useLive.getState().setConnected(false);
    retry = Math.min(retry + 1, 6);
    setTimeout(connectLive, 500 * 2 ** retry);
  };
}
