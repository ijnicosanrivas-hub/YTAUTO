import { describe, expect, it } from "vitest";
import { musicSpec, musicWarnings, YT_MUSIC_PROVIDER } from "./music";

describe("música del vídeo", () => {
  it("la de YouTube se pide como proveedor preferido; sin música es explícito", () => {
    expect(musicSpec("youtube", " épica ")).toEqual({ music: "épica", preferred_providers: { music: YT_MUSIC_PROVIDER } });
    expect(musicSpec("auto", "")).toEqual({ music: null, preferred_providers: {} });
    expect(musicSpec("none", "algo")).toEqual({ music: "none", preferred_providers: {} });
  });

  it("avisa si no hay pistas y si se publica fuera de YouTube", () => {
    expect(musicWarnings("auto", 0, ["tiktok"])).toEqual([]);
    expect(musicWarnings("youtube", 3, ["youtube_shorts"])).toEqual([]);
    const w = musicWarnings("youtube", 0, ["youtube_shorts", "tiktok"]);
    expect(w).toHaveLength(2);
    expect(w[0].link).toBe("#/music");
    expect(w[1].text).toMatch(/TikTok o Instagram/);
  });
});
