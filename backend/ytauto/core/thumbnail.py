"""Composición local de miniaturas (fotograma + título). Sin proveedores externos."""
from __future__ import annotations

import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/inter/Inter-Black.otf",
    "/usr/share/fonts/opentype/inter/Inter-Bold.otf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    str(Path(__file__).resolve().parents[3] / "assets" / "fonts" / "DejaVuSans-Bold.ttf"),  # incluida en el repo
]


def load_font(size: int) -> ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def compose_thumbnail(frame: Path, title: str, out: Path, width: int = 1080, height: int = 1920,
                      safe_top: int = 220) -> Path:
    img = Image.open(frame).convert("RGB")
    img = img.resize((width, height)) if img.size != (width, height) else img
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    # Degradado superior para legibilidad
    for y in range(int(height * 0.45)):
        alpha = int(170 * (1 - y / (height * 0.45)))
        draw.line([(0, y), (width, y)], fill=(0, 0, 0, alpha))
    font = load_font(96)
    lines = textwrap.wrap(title.upper(), width=16)[:4]
    y = safe_top + 40
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font, stroke_width=6)
        x = (width - (bbox[2] - bbox[0])) // 2
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255), stroke_width=6, stroke_fill=(0, 0, 0, 255))
        y += bbox[3] - bbox[1] + 24
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB").save(out, "JPEG", quality=90)
    return out
