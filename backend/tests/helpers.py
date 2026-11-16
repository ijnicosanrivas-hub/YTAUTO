"""Utilidades de prueba: biblioteca local con licencias generada al vuelo."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from PIL import Image

from ytauto.providers.audio_synth import sfx, synth_music, write_wav


def build_library(root: Path) -> Path:
    lic = {"license": "CC0", "attribution": "test", "commercial_use": True}
    imgs = root / "images"
    imgs.mkdir(parents=True, exist_ok=True)
    for i, (name, color) in enumerate([("lighthouse_night", (20, 30, 90)), ("ocean_waves", (10, 120, 160)),
                                        ("volcano_lava", (200, 60, 10))]):
        p = imgs / f"{name}.jpg"
        im = Image.new("RGB", (1080, 1920), color)
        # Composición distinta por imagen (bloque claro en otra zona) → hash perceptual distinto
        box = [(0, 0, 540, 960), (540, 960, 1080, 1920), (0, 960, 1080, 1440)][i]
        im.paste((255, 255, 255), box)
        im.save(p, quality=90)
        (imgs / f"{name}.jpg.json").write_text(json.dumps({**lic, "tags": name.split("_")}))
    (imgs / "sin_licencia.jpg").write_bytes((imgs / "ocean_waves.jpg").read_bytes())  # debe ignorarse
    vids = root / "videos"
    vids.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=1080x1920:r=30:d=3",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(vids / "ocean_waves.mp4")], check=True)
    (vids / "licenses.json").write_text(json.dumps({"*": {**lic, "tags": ["ocean", "waves"]}}))
    music = root / "music"
    write_wav(music / "calm_piano.wav", synth_music("calm", 10))
    (music / "calm_piano.wav.json").write_text(json.dumps({**lic, "mood": "calm"}))
    s = root / "sfx"
    for e in ("whoosh", "impact"):
        write_wav(s / f"{e}.wav", sfx(e))
        (s / f"{e}.wav.json").write_text(json.dumps({**lic, "tags": [e]}))
    return root
