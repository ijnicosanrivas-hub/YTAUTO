"""Generación de subtítulos ASS (karaoke palabra a palabra) a partir de SubtitleCue."""
from __future__ import annotations

from pathlib import Path

from ..interfaces import SubtitleCue, SubtitleStyle


def _ass_color(hex_color: str, alpha: int = 0) -> str:
    h = hex_color.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def _ts(t: float) -> str:
    t = max(0.0, t)
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\n", " ")


def build_ass(cues: list[SubtitleCue], style: SubtitleStyle, width: int = 1080, height: int = 1920) -> str:
    # En karaoke ASS: SecondaryColour = antes de pronunciar, PrimaryColour = ya pronunciado.
    primary = _ass_color(style.highlight_color if style.karaoke else style.primary_color)
    secondary = _ass_color(style.primary_color)
    outline = _ass_color(style.outline_color)
    back = _ass_color("#000000", 0x80)
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{style.font},{style.font_size},{primary},{secondary},{outline},{back},-1,0,0,0,100,100,0,0,1,{style.outline},2,2,{style.margin_h},{style.margin_h},{style.margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    for cue in cues:
        if cue.end_s <= cue.start_s:
            continue
        if style.karaoke and cue.words:
            parts = []
            for w in cue.words:
                cs = max(1, round((w.end_s - w.start_s) * 100))
                word = w.word.upper() if style.uppercase else w.word
                parts.append(f"{{\\kf{cs}}}{_escape(word)} ")
            text = "".join(parts).rstrip()
        else:
            text = _escape(cue.text.upper() if style.uppercase else cue.text)
        # Pequeña animación de entrada (escala) para dinamismo.
        text = "{\\fad(60,40)\\fscx92\\fscy92\\t(0,90,\\fscx100\\fscy100)}" + text
        lines.append(f"Dialogue: 0,{_ts(cue.start_s)},{_ts(cue.end_s)},Default,,0,0,0,,{text}")
    return header + "\n".join(lines) + "\n"


def write_ass(cues: list[SubtitleCue], style: SubtitleStyle, path: Path, width: int, height: int) -> Path:
    path.write_text(build_ass(cues, style, width, height), encoding="utf-8")
    return path
