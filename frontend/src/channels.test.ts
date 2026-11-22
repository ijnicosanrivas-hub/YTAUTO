import { describe, expect, it } from "vitest";
import { durationFromAnswer, groupByChannel, licenseWarning, nameFromIdea, tokens, withChannel } from "./channels";
import { AVATARS, avatarFor, avatarHeight } from "./minifig/avatars";
import { HUB, hasWorld, stationFor } from "./minifig/hub";
import { useLive } from "./store";
import type { AgentState, License } from "./types";

const lic = (over: Partial<License>): License => ({
  id: "lic_1", name: "A", channel_id: "gta6", kind: "claude_session", plan: "Pro", config_dir: null, secret_hint: null,
  monthly_token_limit: null, enabled: true, is_limited: false, limited_until: null, limited_reason: null, limited_now: false,
  status: "ok", usage_pct: null, last_used_at: null, notes: null,
  tokens: { today: 0, d7: 0, d30: 0, month: 0 }, calls: { today: 0, month: 0, total: 0 }, input_tokens: 0, output_tokens: 0,
  cache_read_tokens: 0, cost_usd_eq: 0, seconds: 0, by_agent: {}, by_channel: {}, daily: [], last_call_at: null, ...over,
});

const agent = (name: string, channel: string, status: AgentState["status"] = "idle"): AgentState => ({
  name, channel, title: name, uses_claude: true, phases: [], status, project_id: null, phase: null, task: null, progress: null,
  started_at: null, finished_at: null, last_duration_s: null, last_result: null, last_error: null, runs: 0, errors: 0, llm_calls: 0,
});

describe("canales", () => {
  it("añade el canal a cualquier ruta", () => {
    expect(withChannel("/api/projects", "gta6")).toBe("/api/projects?channel=gta6");
    expect(withChannel("/api/events?limit=5", "kids")).toBe("/api/events?limit=5&channel=kids");
  });
  it("formatea tokens", () => {
    expect(tokens(950)).toBe("950");
    expect(tokens(12400)).toBe("12 k");
    expect(tokens(3100000)).toBe("3,1 M");
    expect(tokens(null)).toBe("0");
  });
  it("agrupa licencias por canal en el orden de los canales", () => {
    const g = groupByChannel([lic({ id: "a", channel_id: "kids" }), lic({ id: "b", channel_id: "general" })], ["general", "gta6", "kids"]);
    expect(g.map(([c, l]) => [c, l.map((x) => x.id)])).toEqual([["general", ["b"]], ["gta6", []], ["kids", ["a"]]]);
  });
  it("avisa de licencias agotadas, casi llenas o prestadas", () => {
    expect(licenseWarning(lic({ limited_now: true }), "gta6")).toMatch(/Agotada/);
    expect(licenseWarning(lic({ usage_pct: 95 }), "gta6")).toMatch(/95/);
    expect(licenseWarning(lic({}), "kids")).toMatch(/otro canal/);
    expect(licenseWarning(lic({}), "gta6")).toBeNull();
    expect(licenseWarning(undefined, "gta6")).toBeNull();
  });
  it("lee la duración de la respuesta del director", () => {
    expect(durationFromAnswer("60 s")).toBe(60);
    expect(durationFromAnswer("unos 75 segundos")).toBe(75);
    expect(durationFromAnswer("2 minutos")).toBeNull();
  });
  it("nombra el proyecto a partir de la idea", () => {
    expect(nameFromIdea("Tiburones más antiguos que los árboles. Algo así")).toBe("Tiburones más antiguos que los árboles");
    expect(nameFromIdea("")).toBe("Nuevo vídeo");
    expect(nameFromIdea("a".repeat(80)).length).toBeLessThanOrEqual(60);
  });
});

describe("estado por canal", () => {
  it("cada canal tiene su tablero y cambiar de canal cambia los agentes visibles", () => {
    const s = useLive.getState();
    s.setChannel("general");
    s.applyMessage({ type: "hello", agents: [], boards: { general: [agent("director", "general")], gta6: [agent("director", "gta6")] } });
    s.applyMessage({ type: "event", event: { type: "agent.started", project_id: "p", agent: "director", phase: "x", data: {}, at: new Date().toISOString() },
      agent: agent("director", "gta6", "running") });
    expect(useLive.getState().agents.director.status).toBe("idle");
    expect(useLive.getState().boards.gta6.director.status).toBe("running");
    useLive.getState().setChannel("gta6");
    expect(useLive.getState().agents.director.status).toBe("running");
    expect(useLive.getState().events[0].channel).toBe("gta6");
    useLive.getState().setChannel("general");
  });
});

describe("perfiles", () => {
  it("cada perfil no LEGO tiene personaje para los 9 agentes", () => {
    for (const profile of ["gta6", "kids", "deportes"]) {
      expect(Object.keys(AVATARS[profile]).sort()).toEqual(Object.keys(HUB).sort());
    }
    expect(avatarFor("gotham", "chief")).toBeUndefined();
  });
  it("la etiqueta queda por encima de sombreros y orejas", () => {
    expect(avatarHeight(avatarFor("kids", "chief"))).toBeGreaterThan(avatarHeight(avatarFor("gta6", "director")));
    expect(avatarHeight(undefined)).toBe(2);
  });
  it("los puestos cambian de nombre según el perfil, no de sitio", () => {
    expect(stationFor("gotham", "chief")?.name).toBe("Batcomputer");
    const s = stationFor("deportes", "reviewer");
    expect(s?.name).toBe("Sala VAR");
    expect([s?.x, s?.z]).toEqual([HUB.reviewer.x, HUB.reviewer.z]);
    expect(hasWorld("kids") && hasWorld("gotham") && !hasWorld("classic")).toBe(true);
  });
});
