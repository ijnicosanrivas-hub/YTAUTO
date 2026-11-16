"""Alineación local de subtítulos proporcional a la longitud de cada palabra.

No requiere modelos: reparte la duración real de la locución entre las palabras según
su número de caracteres (las palabras largas tardan más en pronunciarse) y agrupa en
líneas cortas legibles en móvil. Precisión típica ±150 ms con TTS de ritmo constante.
Para alineación acústica exacta usa el adaptador `faster_whisper` (opcional).
"""
from __future__ import annotations

import re

from ..interfaces import SubtitleCue, SubtitleProvider, SubtitleRequest, WordTiming

_PUNCT_PAUSE = {",": 0.6, ";": 0.8, ":": 0.8, ".": 1.2, "?": 1.2, "!": 1.2}


class ProportionalSubtitleProvider(SubtitleProvider):
    name = "proportional"
    display_name = "Alineación proporcional (local)"

    def capabilities(self):
        return {"word_timings": True, "acoustic": False, "languages": ["*"]}

    def align(self, request: SubtitleRequest) -> list[SubtitleCue]:
        words = request.text.split()
        if not words:
            return []
        weights = []
        for w in words:
            core = len(re.sub(r"\W", "", w)) or 1
            weights.append(core + 2 + _PUNCT_PAUSE.get(w[-1], 0) * 4)
        total_w = sum(weights)
        dur = max(0.1, request.audio_duration_s)
        t = request.offset_s
        timings = []
        for w, wt in zip(words, weights):
            d = dur * wt / total_w
            timings.append(WordTiming(word=w, start_s=round(t, 3), end_s=round(t + d, 3)))
            t += d
        cues, current = [], []
        for wt in timings:
            text = " ".join(x.word for x in current + [wt])
            if current and (len(text) > request.max_chars_per_cue or current[-1].word[-1] in ".?!"):
                cues.append(self._cue(current))
                current = [wt]
            else:
                current.append(wt)
        if current:
            cues.append(self._cue(current))
        return cues

    @staticmethod
    def _cue(words: list[WordTiming]) -> SubtitleCue:
        return SubtitleCue(start_s=words[0].start_s, end_s=words[-1].end_s,
                           text=" ".join(w.word for w in words), words=words)
