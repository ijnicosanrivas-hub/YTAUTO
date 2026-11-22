import { create } from "zustand";
import { wsUrl } from "./api";
import { CHANNEL_KEY, initialChannel } from "./channels";
import { CLASSIC_THEME } from "./theme";
import type { AgentState, Theme, YtEvent } from "./types";

export type Route = { page: string; id?: string };

export function parseHash(hash: string): Route {
  const [page, id] = hash.replace(/^#\/?/, "").split("?")[0].split("/"); // el «?» admite parámetros (p. ej. ?calidad=alta)
  return { page: page || "dashboard", id: id || undefined };
}

type Board = Record<string, AgentState>;

interface LiveState {
  route: Route;
  connected: boolean;
  /** Canal activo (los 4 producen en paralelo; aquí se elige cuál se ve). */
  channel: string;
  setChannel: (c: string) => void;
  /** Estado en vivo de los agentes de cada canal. */
  boards: Record<string, Board>;
  /** Agentes del canal activo (atajo de boards[channel]). */
  agents: Board;
  activity: Record<string, Record<string, number>>;
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
  | { type: "hello"; agents: AgentState[]; boards?: Record<string, AgentState[]> }
  | { type: "event"; event: YtEvent; agent: AgentState | null; channel?: string | null };

const toBoard = (list: AgentState[]): Board => Object.fromEntries(list.map((a) => [a.name, a]));

const MAX_EVENTS = 400;

export const useLive = create<LiveState>((set) => ({
  route: parseHash(typeof location !== "undefined" ? location.hash : ""),
  connected: false,
  channel: initialChannel(),
  setChannel: (channel) => {
    try {
      localStorage.setItem(CHANNEL_KEY, channel);
    } catch {
      /* sin almacenamiento */
    }
    set((s) => ({ channel, agents: s.boards[channel] ?? {}, lastActivity: s.activity[channel] ?? {}, revision: s.revision + 1 }));
  },
  boards: {},
  agents: {},
  activity: {},
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
        const boards = msg.boards
          ? Object.fromEntries(Object.entries(msg.boards).map(([c, list]) => [c, toBoard(list)]))
          : { [s.channel]: toBoard(msg.agents) };
        return { boards, agents: boards[s.channel] ?? {} };
      }
      const ch = msg.agent?.channel ?? msg.channel ?? s.channel; // sin canal (servidor antiguo, demo): el activo
      let { boards, activity } = s;
      if (msg.agent && ch) {
        boards = { ...boards, [ch]: { ...(boards[ch] ?? {}), [msg.agent.name]: msg.agent } };
        activity = { ...activity, [ch]: { ...(activity[ch] ?? {}), [msg.agent.name]: Date.now() } };
      }
      const events = [{ ...msg.event, channel: ch }, ...s.events].slice(0, MAX_EVENTS);
      const revision = msg.event.type === "agent.progress" ? s.revision : s.revision + 1;
      return { boards, activity, agents: boards[s.channel] ?? {}, lastActivity: activity[s.channel] ?? {}, events, revision };
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
