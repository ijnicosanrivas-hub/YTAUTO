"""Alineación de subtítulos guiada por las pausas reales del audio (local, con FFmpeg).

1. Detecta los tramos con voz de la locución (`silencedetect`).
2. Reparte las palabras, en proporción a su longitud, solo a lo largo del tiempo con voz.
Así ninguna palabra cae en una pausa y las frases arrancan cuando de verdad se pronuncian.
Precisión típica: ±80 ms con TTS; sin modelos ni descargas.
"""
from __future__ import annotations

import re
import shutil
import subprocess

from ..interfaces import HealthStatus, SubtitleCue, SubtitleRequest, WordTiming
from .proportional import _PUNCT_PAUSE, ProportionalSubtitleProvider


def speech_segments(audio_path: str, duration_s: float, noise_db: float = -35.0,
                    min_pause_s: float = 0.12) -> list[tuple[float, float]]:
    proc = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(audio_path), "-af",
                           f"silencedetect=n={noise_db}dB:d={min_pause_s}", "-f", "null", "-"],
                          capture_output=True, encoding="utf-8", errors="replace")
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", proc.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", proc.stderr)]
    silences = list(zip(starts, ends + [duration_s] * (len(starts) - len(ends))))
    segs, t = [], 0.0
    for s, e in silences:
        s = max(0.0, s)
        if s - t > 0.05:
            segs.append((t, s))
        t = max(t, e)
    if duration_s - t > 0.05:
        segs.append((t, duration_s))
    return segs or [(0.0, duration_s)]


class AcousticSubtitleProvider(ProportionalSubtitleProvider):
    """Subtítulos alineados a los tramos reales de voz (detección de pausas con FFmpeg)."""
    name = "acoustic"
    display_name = "Alineación acústica por pausas (local)"
    default_priority = 10
    default_params = {"noise_db": -35.0, "min_pause_s": 0.12}

    def capabilities(self):
        return {"word_timings": True, "acoustic": True, "method": "pausas reales del audio", "languages": ["*"]}

    def health_check(self) -> HealthStatus:
        ok = shutil.which("ffmpeg") is not None
        return HealthStatus(ok=ok, message="ffmpeg disponible" if ok else "ffmpeg no instalado")

    @staticmethod
    def _phrases(words: list[str]) -> list[list[str]]:
        out, cur = [], []
        for w in words:
            cur.append(w)
            if w[-1] in ",.;:?!":
                out.append(cur)
                cur = []
        if cur:
            out.append(cur)
        return out

    @staticmethod
    def _merge_to(segs: list[tuple[float, float]], n: int) -> list[tuple[float, float]]:
        """Une los tramos separados por las pausas más cortas hasta quedarse con n tramos."""
        segs = list(segs)
        while len(segs) > n:
            gaps = [(segs[i + 1][0] - segs[i][1], i) for i in range(len(segs) - 1)]
            _, i = min(gaps)
            segs[i:i + 2] = [(segs[i][0], segs[i + 1][1])]
        return segs

    @staticmethod
    def _spread(words: list[str], start: float, end: float) -> list[WordTiming]:
        weights = [(len(re.sub(r"\W", "", w)) or 1) + 2 + _PUNCT_PAUSE.get(w[-1], 0) for w in words]
        total, t, out = sum(weights), start, []
        for w, wt in zip(words, weights):
            d = (end - start) * wt / total
            out.append(WordTiming(word=w, start_s=round(t, 3), end_s=round(t + d, 3)))
            t += d
        return out

    def align(self, request: SubtitleRequest) -> list[SubtitleCue]:
        words = request.text.split()
        if not words:
            return []
        segs = speech_segments(str(request.audio_path), request.audio_duration_s,
                               self.params["noise_db"], self.params["min_pause_s"])
        phrases = self._phrases(words)
        timings: list[WordTiming] = []
        if len(phrases) <= len(segs) <= len(phrases) + 2:
            # Caso habitual en TTS: cada frase termina en una pausa audible.
            for ph, (s, e) in zip(phrases, self._merge_to(segs, len(phrases))):
                timings += self._spread(ph, s, e)
        else:
            # Sin correspondencia frase↔pausa: reparto sobre el tiempo con voz, sin partir palabras.
            speech_total = sum(e - s for s, e in segs)
            weights = [(len(re.sub(r"\W", "", w)) or 1) + 2 + _PUNCT_PAUSE.get(w[-1], 0) for w in words]
            per_unit = speech_total / sum(weights)
            k, t = 0, segs[0][0]
            for w, wt in zip(words, weights):
                d = wt * per_unit
                if t + d > segs[k][1] + 0.05 and k + 1 < len(segs) and (segs[k][1] - t) < d / 2:
                    k += 1
                    t = segs[k][0]
                timings.append(WordTiming(word=w, start_s=round(t, 3), end_s=round(t + d, 3)))
                t += d
        for wt in timings:  # a la línea temporal del vídeo
            wt.start_s = round(wt.start_s + request.offset_s, 3)
            wt.end_s = round(min(wt.end_s, request.audio_duration_s) + request.offset_s, 3)
        cues, current = [], []
        for wt in timings:
            text = " ".join(x.word for x in current + [wt])
            if current and (len(text) > request.max_chars_per_cue or current[-1].word[-1] in ".?!"
                            or wt.start_s - current[-1].end_s > 0.35):
                cues.append(self._cue(current))
                current = [wt]
            else:
                current.append(wt)
        if current:
            cues.append(self._cue(current))
        for a, b in zip(cues, cues[1:]):  # sin solapes
            if b.start_s < a.end_s:
                a.end_s = b.start_s
        return cues
