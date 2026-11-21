import { describe, expect, it } from "vitest";
import { billboardYaw, figureUrl, spriteMotion, spriteSize } from "./sprites";

describe("figuras 2D", () => {
  it("el tamaño es proporcional a los píxeles y centra la base", () => {
    const a = spriteSize({ anchor_x: 0.5, w: 115, h: 230 });
    expect(a.height).toBeCloseTo(2, 5);
    expect(a.offsetX).toBeCloseTo(0, 5);
    expect(spriteSize({ anchor_x: 0.25, w: 100, h: 100 }).offsetX).toBeGreaterThan(0);
  });
  it("cada estado se mueve distinto y trabajar brilla", () => {
    expect(spriteMotion("work", 1, 0).glow).toBeGreaterThan(0);
    expect(spriteMotion("wait", 1, 0).glow).toBe(0);
    const moves = new Set((["wait", "move", "work", "interact", "error"] as const).map((s) => JSON.stringify(spriteMotion(s, 0.7, 0))));
    expect(moves.size).toBe(5);
  });
  it("celebrar termina en reposo", () => {
    const end = spriteMotion("finish", 0, 0, 3.5);
    expect(end.y).toBeCloseTo(0, 5);
    expect(end.glow).toBeCloseTo(0, 5);
  });
  it("el cartel mira a la cámara", () => {
    expect(billboardYaw([0, 10], [0, 0])).toBeCloseTo(0);
    expect(billboardYaw([10, 0], [0, 0])).toBeCloseTo(Math.PI / 2);
  });
  it("la URL añade el token solo si existe", () => {
    expect(figureUrl("chief", null)).toBe("/api/figures/chief.png");
    expect(figureUrl("chief", "a b")).toBe("/api/figures/chief.png?token=a%20b");
  });
});
