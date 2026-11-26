import { describe, expect, it } from "vitest";
import { changedKinds, changedOnly } from "./components/Decisions";
import type { ScenePromptView } from "./types";

const list: ScenePromptView[] = [
  { scene_index: 0, kind: "image", prompt: "A", search_query: "a" },
  { scene_index: 1, kind: "video", prompt: "B", search_query: "b" },
];

describe("storyboard: solo se envía lo que el usuario cambió", () => {
  it("textos editados (sin vacíos ni iguales)", () => {
    expect(changedOnly(list, { 0: "A", 1: "B nuevo" })).toEqual({ 1: "B nuevo" });
    expect(changedOnly(list, { 0: "   " })).toEqual({});
  });
  it("tipo de recurso cambiado", () => {
    expect(changedKinds(list, { 0: "image", 1: "image" })).toEqual({ 1: "image" });
  });
});
