import { describe, expect, it } from "vitest";
import { HUB, HUB_SCALE, OVERVIEW, facingYaw, focusShot, localToWorld, recentActions } from "./hub";
import type { YtEvent } from "../types";

const NINE = ["chief", "director", "scriptwriter", "resources", "voice", "editor", "sound", "reviewer", "publisher"];

describe("hub de la Batcueva", () => {
  it("hay una instalación distinta para cada uno de los nueve agentes", () => {
    expect(Object.keys(HUB).sort()).toEqual([...NINE].sort());
    expect(new Set(Object.values(HUB).map((s) => s.name)).size).toBe(9);
    for (const s of Object.values(HUB)) expect(s.blurb.length).toBeGreaterThan(20);
  });

  it("Batman está en el centro y nadie comparte sitio ni se solapa con otro", () => {
    expect(HUB.chief).toMatchObject({ x: 0, z: 0 });
    const list = Object.entries(HUB);
    for (const [a, sa] of list) for (const [b, sb] of list) if (a < b) expect(Math.hypot(sa.x - sb.x, sa.z - sb.z), `${a}/${b}`).toBeGreaterThan(5 * HUB_SCALE * 0.9);
  });

  it("todos miran a Batman y Batman mira a la cámara", () => {
    expect(facingYaw("chief")).toBe(0);
    for (const n of NINE.filter((x) => x !== "chief")) {
      const [fx, fz] = [Math.sin(facingYaw(n)), Math.cos(facingYaw(n))]; // vector «delante»
      const toCenter = [-HUB[n].x, -HUB[n].z];
      const len = Math.hypot(toCenter[0], toCenter[1]);
      expect(fx * (toCenter[0] / len) + fz * (toCenter[1] / len), n).toBeCloseTo(1, 6); // apunta al centro
    }
  });

  it("la instalación queda DETRÁS del personaje (lejos de Batman) y la cámara de zoom delante", () => {
    for (const n of NINE.filter((x) => x !== "chief")) {
      const [bx, bz] = localToWorld(n, 0, -2.4);
      expect(Math.hypot(bx, bz)).toBeGreaterThan(Math.hypot(HUB[n].x, HUB[n].z)); // más lejos del centro
      const shot = focusShot(n, -1.4);
      expect(Math.hypot(shot.position[0], shot.position[2])).toBeLessThan(Math.hypot(HUB[n].x, HUB[n].z)); // cámara hacia el centro
    }
  });

  it("el plano de zoom mira al pecho del personaje y es cercano; sin agente vuelve a la vista general", () => {
    for (const n of NINE) {
      const s = focusShot(n, -1.4);
      expect(s.target[0]).toBe(HUB[n].x);
      expect(s.target[2]).toBe(HUB[n].z);
      expect(s.target[1]).toBeGreaterThan(-1.4); // por encima de los pies
      const d = Math.hypot(s.position[0] - s.target[0], s.position[1] - s.target[1], s.position[2] - s.target[2]);
      expect(d).toBeGreaterThan(3);
      expect(d).toBeLessThan(9);
    }
    expect(focusShot("no-existe", 0)).toEqual(OVERVIEW);
  });
});

describe("últimas acciones de un agente", () => {
  const ev = (type: string, at: string, agent: string | null, phase: string | null, data: Record<string, unknown> = {}): YtEvent => ({ type, at, agent, phase, data, project_id: "p1" });
  const events = [
    ev("agent.started", "2026-11-21T10:00:00Z", "editor", "edit"),
    ev("agent.progress", "2026-11-21T10:00:05Z", "editor", "edit", { progress: 0.2, message: "Escena 1" }),
    ev("agent.progress", "2026-11-21T10:00:09Z", "editor", "edit", { progress: 0.6, message: "Escena 3" }),
    ev("agent.finished", "2026-11-21T10:00:20Z", "editor", "edit", { summary: "Montaje listo" }),
    ev("phase.status", "2026-11-21T10:00:21Z", null, "edit", { status: "completed" }),
    ev("agent.started", "2026-11-21T10:00:30Z", "voice", "voice"),
  ];
  const phaseAgent = { edit: "editor", voice: "voice" };

  it("solo trae eventos suyos (directos o de sus fases), los más recientes primero", () => {
    const a = recentActions(events, "editor", phaseAgent);
    expect(a.map((x) => x.type)).toEqual(["phase.status", "agent.finished", "agent.progress", "agent.started"]);
    expect(recentActions(events, "voice", phaseAgent)).toHaveLength(1);
    expect(recentActions(events, "sound", phaseAgent)).toEqual([]);
  });

  it("de los avances intermedios solo deja el último y respeta el límite", () => {
    const a = recentActions(events, "editor", phaseAgent);
    expect(a.filter((x) => x.type === "agent.progress")).toHaveLength(1);
    expect(a.find((x) => x.type === "agent.progress")!.text).toContain("Escena 3");
    expect(recentActions(events, "editor", phaseAgent, 2)).toHaveLength(2);
  });

  it("describe cada acción en español", () => {
    const a = recentActions(events, "editor", phaseAgent);
    expect(a.find((x) => x.type === "agent.finished")!.text).toBe("Montaje listo");
    expect(a.find((x) => x.type === "agent.started")!.text).toBe("comienza");
  });
});
