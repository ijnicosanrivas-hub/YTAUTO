import { renderToString } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { HUB } from "../minifig/hub";
import type { AgentState, Persona } from "../types";
import { AgentPanel } from "./AgentPanel";

const persona: Persona = { character: "Nightwing", alias: "Dick Grayson", epithet: "El Acróbata de Gotham", alignment: "héroe", color: "#3B82F6", glyph: "🪽", persona: "x", quotes: {} };
const base: AgentState = {
  name: "editor", title: "Animador / Editor", uses_claude: false, phases: ["edit", "render"], status: "idle", project_id: null, phase: null, task: null,
  progress: null, started_at: null, finished_at: null, last_duration_s: 72.64, last_result: "Montaje: 14 escenas", last_error: null, runs: 3, errors: 1, llm_calls: 0,
};
const phases = [{ id: "edit", number: 10, title: "Montaje", agent: "editor" }, { id: "render", number: 11, title: "Renderizado", agent: "editor" }, { id: "voice", number: 9, title: "Locución", agent: "voice" }];
const noop = () => undefined;
const html = (a: Partial<AgentState> = {}, actions = [{ at: "2026-11-21T10:00:20Z", type: "agent.finished", text: "Montaje listo" }]) =>
  renderToString(<AgentPanel agent={{ ...base, ...a }} persona={persona} station={HUB.editor} phases={phases} actions={actions} quote="Calentando" onClose={noop} onOverview={noop} />).replace(/<!-- -->/g, "");

describe("expediente del agente", () => {
  it("muestra el personaje, la instalación, las estadísticas y las fases que gestiona", () => {
    const h = html();
    expect(h).toContain("Nightwing");
    expect(h).toContain("Mesa de trabajo");
    expect(h).toContain("3</b><span>ejecuciones");
    expect(h).toContain("1</b><span>errores");
    expect(h).toContain("72.64s");
    expect(h).toContain("Montaje"); expect(h).toContain("Renderizado");
    expect(h).not.toContain("Locución"); // solo sus fases
    expect(h).toContain("Montaje: 14 escenas");
  });

  it("en ejecución enseña la tarea, la fase actual y el enlace al proyecto; en espera no inventa actividad", () => {
    const run = html({ status: "running", task: "Escena 3", phase: "render", project_id: "prj_1", progress: 0.4, started_at: new Date().toISOString() });
    expect(run).toContain("Trabajando ahora mismo");
    expect(run).toContain("Escena 3");
    expect(run).toContain("fase 11: Renderizado");
    expect(run).toContain("#/projects/prj_1");
    const idle = html();
    expect(idle).toContain("En su puesto");
    expect(idle).not.toContain("Trabajando ahora mismo");
    expect(idle).not.toContain("#/projects/");
  });

  it("lista las últimas acciones reales y avisa si todavía no hay ninguna", () => {
    expect(html()).toContain("Montaje listo");
    expect(html({}, [])).toContain("Aún no ha hecho nada");
  });

  it("explica los errores y la espera de aprobación", () => {
    expect(html({ status: "error", last_error: "FFmpeg falló" })).toContain("FFmpeg falló");
    expect(html({ status: "waiting" })).toContain("Espera tu decisión");
  });
});
