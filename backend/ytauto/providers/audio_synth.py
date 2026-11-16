"""Síntesis de audio local con numpy (música de fondo y efectos), sin dependencias externas.

Todo lo generado aquí es propio (CC0): no hay riesgos de licencia.
"""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 48000
NOTE = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}


def write_wav(path: Path, data: np.ndarray, sr: int = SR) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if data.ndim == 1:
        data = np.stack([data, data], axis=1)
    peak = float(np.max(np.abs(data))) or 1.0
    pcm = (data / peak * 0.89 * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(data.shape[1])
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return path


def freq(note: str, octave: int) -> float:
    return 440.0 * 2 ** ((NOTE[note] - 9) / 12 + (octave - 4))


def lowpass(x: np.ndarray, alpha: float) -> np.ndarray:
    """Filtro paso bajo de un polo (vectorizado por bloques mediante lfilter manual)."""
    y = np.empty_like(x)
    acc = 0.0
    for i in range(0, len(x), 4096):
        block = x[i:i + 4096]
        out = np.empty_like(block)
        for j, v in enumerate(block):
            acc += alpha * (v - acc)
            out[j] = acc
        y[i:i + 4096] = out
    return y


def envelope(n: int, attack: float, release: float, sr: int = SR) -> np.ndarray:
    env = np.ones(n)
    a, r = min(n, int(attack * sr)), min(n, int(release * sr))
    if a:
        env[:a] = np.linspace(0, 1, a)
    if r:
        env[-r:] *= np.linspace(1, 0, r)
    return env


# ------------------------------------------------------------------ música
PROGRESSIONS = {
    "tense": [("A", "minor"), ("F", "major"), ("C", "major"), ("G", "major")],
    "dark": [("D", "minor"), ("A#", "major"), ("F", "major"), ("C", "major")],
    "epic": [("C", "minor"), ("G#", "major"), ("D#", "major"), ("A#", "major")],
    "happy": [("C", "major"), ("G", "major"), ("A", "minor"), ("F", "major")],
    "calm": [("F", "major"), ("C", "major"), ("D", "minor"), ("A#", "major")],
}
MOOD_WORDS = {
    "tense": {"tens", "intriga", "misterio", "mystery", "suspense", "intrigante", "suspens"},
    "dark": {"oscur", "dark", "terror", "miedo", "sombr"},
    "epic": {"épic", "epic", "cinem", "orquest", "grandios", "electr"},
    "happy": {"alegr", "happy", "divert", "fun", "optim", "positiv"},
    "calm": {"calm", "relaj", "suave", "ambient", "chill", "tranquil"},
}


def pick_mood(text: str) -> str:
    t = text.lower()
    for mood, keys in MOOD_WORDS.items():
        if any(k in t for k in keys):
            return mood
    return "tense"


def chord(root: str, quality: str) -> list[float]:
    third = 3 if quality == "minor" else 4
    base = NOTE[root]
    names = list(NOTE)
    notes = [names[(base + i) % 12] for i in (0, third, 7)]
    return [freq(n, 3) for n in notes] + [freq(root, 2)]


def synth_music(mood: str, duration_s: float, bpm: int = 100, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    prog = PROGRESSIONS.get(mood, PROGRESSIONS["tense"])
    bar_s = 4 * 60 / bpm
    n_total = int(duration_s * SR)
    out = np.zeros((n_total, 2))
    t_bar = np.arange(int(bar_s * SR)) / SR
    bars = int(np.ceil(duration_s / bar_s))
    detune = 1.003
    for b in range(bars):
        root, q = prog[b % len(prog)]
        freqs = chord(root, q)
        pad = np.zeros_like(t_bar)
        for f in freqs[:3]:
            # Pad: dos osciladores ligeramente desafinados (sensación de amplitud)
            pad += np.sin(2 * np.pi * f * t_bar) + 0.6 * np.sin(2 * np.pi * f * detune * t_bar + 1.3)
        bass = 0.9 * np.sin(2 * np.pi * freqs[3] * t_bar)
        env = envelope(len(t_bar), 0.25, 0.35)
        left = (pad * 0.22 + bass * 0.35) * env
        right = (pad * 0.22 * 0.95 + bass * 0.35) * env
        # Arpegio sencillo en corcheas
        step = int(60 / bpm / 2 * SR)
        arp_notes = [f * 2 for f in freqs[:3]]
        for k in range(len(t_bar) // step):
            f = arp_notes[(k + b) % 3]
            seg = np.arange(step) / SR
            tone = np.sin(2 * np.pi * f * seg) * np.exp(-seg * 9) * 0.12
            pan = 0.5 + 0.4 * np.sin(k)
            left[k * step:(k + 1) * step] += tone * (1 - pan)
            right[k * step:(k + 1) * step] += tone * pan
        # Pulso de bombo suave en cada negra (más presencia en "epic"/"tense")
        if mood in ("epic", "tense", "happy"):
            beat = int(60 / bpm * SR)
            kick_t = np.arange(int(0.25 * SR)) / SR
            kick = np.sin(2 * np.pi * (50 + 60 * np.exp(-kick_t * 30)) * kick_t) * np.exp(-kick_t * 14) * 0.5
            for k in range(4):
                s = k * beat
                e = min(len(t_bar), s + len(kick))
                left[s:e] += kick[:e - s]
                right[s:e] += kick[:e - s]
        start = int(b * bar_s * SR)
        end = min(n_total, start + len(t_bar))
        out[start:end, 0] += left[:end - start]
        out[start:end, 1] += right[:end - start]
    out += rng.normal(0, 0.003, out.shape)  # aire
    out *= envelope(n_total, 1.0, 2.0)[:, None]
    return out


# ------------------------------------------------------------------ efectos
def noise(n: int, rng) -> np.ndarray:
    return rng.normal(0, 1, n)


def sfx(effect: str, duration_s: float | None = None, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    kind = effect.split(":")[0]
    if kind == "whoosh":
        d = duration_s or 0.6
        n = int(d * SR)
        t = np.linspace(0, 1, n)
        x = noise(n, rng)
        # Barrido: paso bajo cuyo corte sube y baja
        alpha = 0.02 + 0.25 * np.sin(np.pi * t) ** 2
        y = np.empty(n)
        acc = 0.0
        for i in range(n):
            acc += alpha[i] * (x[i] - acc)
            y[i] = acc
        y *= np.sin(np.pi * t) ** 1.5
        pan = t
        return np.stack([y * (1 - pan * 0.6), y * (0.4 + pan * 0.6)], axis=1)
    if kind == "impact":
        d = duration_s or 1.2
        n = int(d * SR)
        t = np.arange(n) / SR
        boom = np.sin(2 * np.pi * (40 + 80 * np.exp(-t * 18)) * t) * np.exp(-t * 3.5)
        hit = lowpass(noise(n, rng), 0.3) * np.exp(-t * 25) * 0.6
        return boom + hit
    if kind == "riser":
        d = duration_s or 1.6
        n = int(d * SR)
        t = np.arange(n) / SR
        f = 200 + 1400 * (t / d) ** 2
        tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.3
        hiss = lowpass(noise(n, rng), 0.15) * (t / d) * 0.5
        return (tone + hiss) * (t / d) ** 1.5
    if kind == "pop":
        d = duration_s or 0.18
        n = int(d * SR)
        t = np.arange(n) / SR
        return np.sin(2 * np.pi * (900 - 500 * t / d) * t) * np.exp(-t * 35)
    if kind == "ambience":
        d = duration_s or 8.0
        n = int(d * SR)
        brown = np.cumsum(noise(n, rng))
        brown -= np.convolve(brown, np.ones(4800) / 4800, mode="same")
        return brown * envelope(n, 0.8, 0.8)
    if kind in ("click", "tick"):
        n = int(0.05 * SR)
        t = np.arange(n) / SR
        return np.sin(2 * np.pi * 2000 * t) * np.exp(-t * 120)
    raise ValueError(f"Efecto no soportado: {effect}")


SUPPORTED_SFX = ["whoosh", "impact", "riser", "pop", "ambience", "click"]
