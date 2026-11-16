import { describe, expect, it } from "vitest";
import { describeEvent, elapsed, statusLabel } from "./format";
import { linkActive, nodePositions } from "./pages/ProductionRoom";
import { parseHash, useLive } from "./store";
import type { AgentState } from "./types";

const agent = (name: string, status: AgentState["status"] = "idle"): AgentState => ({
  name, title: name, uses_claude: false, phases: [], status, project_id: null, phase: null, task: null,
  progress: null, started_at: null, finished_at: null, last_duration_s: null, last_result: null, last_error: null,
  runs: 0, errors: 0, llm_calls: 0,
});

describe("rutas", () => {
  it("interpreta el hash", () => {
    expect(parseHash("")).toEqual({ page: "dashboard", id: undefined });
    expect(parseHash("#/projects/prj_1")).toEqual({ page: "projects", id: "prj_1" });
  });
});

describe("estado en vivo", () => {
  it("aplica el saludo y los eventos reales", () => {
    const s = useLive.getState();
    s.applyMessage({ type: "hello", agents: [agent("director"), agent("editor")] });
    expect(Object.keys(useLive.getState().agents)).toEqual(["director", "editor"]);
    const rev = useLive.getState().revision;
    s.applyMessage({
      type: "event",
      event: { type: "agent.started", project_id: "p", agent: "director", phase: "creative_direction", data: {}, at: new Date().toISOString() },
      agent: agent("director", "running"),
    });
    const st = useLive.getState();
    expect(st.agents.director.status).toBe("running");
    expect(st.lastActivity.director).toBeGreaterThan(0);
    expect(st.revision).toBe(rev + 1);
    expect(st.events[0].type).toBe("agent.started");
  });

  it("el progreso no fuerza recargas de datos", () => {
    const rev = useLive.getState().revision;
    useLive.getState().applyMessage({
      type: "event",
      event: { type: "agent.progress", project_id: "p", agent: "director", phase: "x", data: { progress: 0.5 }, at: new Date().toISOString() },
      agent: agent("director", "running"),
    });
    expect(useLive.getState().revision).toBe(rev);
  });
});

describe("sala de producción", () => {
  it("coloca al jefe en el centro y 8 agentes en anillo", () => {
    const pos = nodePositions();
    expect(pos.chief).toEqual([0, 0, 0]);
    expect(Object.keys(pos)).toHaveLength(9);
  });

  it("las conexiones solo se activan con actividad real", () => {
    const agents = { chief: agent("chief"), director: agent("director"), scriptwriter: agent("scriptwriter") };
    const now = 100_000;
    expect(linkActive({ source: "chief", target: "director", kind: "control" }, agents, {}, now)).toBe(false);
    expect(linkActive({ source: "chief", target: "director", kind: "control" }, { ...agents, director: agent("director", "running") }, {}, now)).toBe(true);
    expect(linkActive({ source: "director", target: "scriptwriter", kind: "flow" }, agents, { director: now - 500, scriptwriter: now - 400 }, now)).toBe(true);
    expect(linkActive({ source: "director", target: "scriptwriter", kind: "flow" }, agents, { director: now - 10_000 }, now)).toBe(false);
  });
});

describe("formato", () => {
  it("traduce estados y eventos", () => {
    expect(statusLabel("in_review")).toBe("En revisión");
    expect(describeEvent("llm.call", { model: "sonnet", attempt: 1 })).toContain("Claude");
    expect(elapsed("2026-01-01T00:00:00Z", "2026-01-01T00:01:05Z")).toBe("1m 05s");
  });
});

import { CLASSIC_THEME, bodyColor, displayName, quoteFor } from "./theme";
import type { Theme } from "./types";

describe("tema de personajes", () => {
  const theme: Theme = {
    ...CLASSIC_THEME,
    id: "gotham",
    agents: {
      chief: {
        character: "Batman", alias: "Bruce Wayne", epithet: "El Caballero Oscuro", alignment: "héroe",
        color: "#FFD400", glyph: "🦇", persona: "x",
        quotes: { idle: "i", started: "s", finished: "f", waiting: "w", error: "e" },
      },
    },
  };
  const base = { name: "chief", title: "Jefe", status: "idle" as const, runs: 0, last_result: null };

  it("muestra el personaje o, sin tema, el título funcional", () => {
    expect(displayName(theme, base)).toBe("Batman");
    expect(displayName(CLASSIC_THEME, base)).toBe("Jefe");
  });
  it("el color del cuerpo es el del personaje; sin personaje, el del estado", () => {
    expect(bodyColor(theme, base)).toBe("#FFD400");
    expect(bodyColor(CLASSIC_THEME, { name: "chief", status: "error" })).toBe("#f43f5e");
  });
  it("la frase depende del estado real, no de nada inventado", () => {
    expect(quoteFor(theme, base)).toBe("i");
    expect(quoteFor(theme, { ...base, status: "running" })).toBe("s");
    expect(quoteFor(theme, { ...base, status: "waiting" })).toBe("w");
    expect(quoteFor(theme, { ...base, status: "error" })).toBe("e");
    expect(quoteFor(theme, { ...base, runs: 2, last_result: "ok" })).toBe("f");
    expect(quoteFor(theme, { ...base, runs: 2, last_result: null })).toBe("i");
    expect(quoteFor(CLASSIC_THEME, base)).toBeUndefined();
  });
});
