"""Imágenes locales y gratuitas: biblioteca con licencia y generador procedural."""
from __future__ import annotations

import hashlib
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from ...core.errors import ProviderError
from ...core.models import AssetKind, License, MediaAsset
from ...core.workspace import sha256_file
from ..interfaces import HealthStatus, ImageGenerationProvider, ImageRequest
from ..library import IMAGE_EXT, average_hash, best_match, default_library_root, hamming, scan

PALETTES = {
    "dark": [(28, 30, 70), (90, 40, 120), (255, 196, 0), (240, 80, 110)],
    "ocean": [(4, 30, 66), (12, 90, 140), (80, 200, 220), (240, 250, 255)],
    "warm": [(40, 10, 10), (170, 50, 20), (250, 150, 40), (255, 230, 170)],
    "nature": [(10, 40, 20), (40, 110, 50), (160, 200, 90), (240, 240, 200)],
    "neon": [(30, 10, 70), (110, 20, 180), (0, 220, 255), (255, 40, 160)],
}
KEYWORDS = {
    "ocean": {"mar", "ocean", "sea", "water", "agua", "pulpo", "octopus", "ola", "wave", "glaciar", "ice", "hielo"},
    "warm": {"fuego", "fire", "volcan", "volcano", "sol", "sun", "desierto", "desert", "lava"},
    "nature": {"bosque", "forest", "planta", "plant", "naturaleza", "nature", "abeja", "bee", "selva"},
    "neon": {"tecnologia", "tech", "futuro", "future", "cyber", "ai", "robot", "espacio", "space"},
}


class LocalLibraryImageProvider(ImageGenerationProvider):
    """Busca imágenes en la biblioteca local (library/images) por etiquetas y nombre."""
    name = "library_images"
    display_name = "Biblioteca local de imágenes"
    default_priority = 10
    default_params = {"root": "", "min_short_side": 540}

    @property
    def folder(self) -> Path:
        return Path(self.params["root"] or default_library_root()) / "images"

    def health_check(self) -> HealthStatus:
        n = len(scan(self.folder, IMAGE_EXT))
        return HealthStatus(ok=n > 0, message=f"{n} imágenes con licencia en {self.folder}" if n else
                            f"Biblioteca vacía o sin licencias en {self.folder}")

    def generate(self, request: ImageRequest) -> MediaAsset:
        items = scan(self.folder, IMAGE_EXT)
        hashes = {i.path: average_hash(i.path) for i in items}
        excluded = {str(p) for p, h in hashes.items() if any(hamming(h, x) <= 4 for x in request.exclude_hashes)}
        query = f"{request.search_query} {request.prompt}"
        item = best_match(items, query, excluded)
        if item is None:
            raise ProviderError(self.name, f"Sin coincidencias en la biblioteca para '{request.search_query}'",
                                transient=False)
        with Image.open(item.path) as im:
            w, h = im.size
        if min(w, h) < self.params["min_short_side"]:
            raise ProviderError(self.name, f"{item.path.name}: resolución insuficiente", transient=False)
        return MediaAsset(kind=AssetKind.IMAGE, path=str(item.path), width=w, height=h, provider=self.name,
                          prompt=request.prompt, sha256=sha256_file(item.path), perceptual_hash=hashes[item.path],
                          license=item.license, source_url=item.meta.get("url"),
                          metadata={"library_tags": sorted(item.tags)})


class ProceduralImageProvider(ImageGenerationProvider):
    """Fondos abstractos generados localmente (degradados, formas y grano), coherentes por paleta.

    No representa objetos concretos: sirve como recurso de base o de respaldo garantizado.
    Para imágenes figurativas usa la biblioteca o un proveedor de generación.
    """
    name = "procedural_images"
    display_name = "Imágenes procedurales (local)"
    default_priority = 90
    default_params = {"grain": 10, "shapes": 7}

    def capabilities(self):
        return {"figurative": False, "aspect_ratios": ["9:16", "any"], "cost": 0}

    @staticmethod
    def _palette(text: str) -> list[tuple[int, int, int]]:
        words = text.lower().replace(",", " ").split()
        for name, keys in KEYWORDS.items():
            if any(w.startswith(k) for w in words for k in keys):  # "pulpos" coincide con "pulpo"
                return PALETTES[name]
        return PALETTES["dark"]

    def generate(self, request: ImageRequest) -> MediaAsset:
        w, h = request.width, request.height
        seed_src = f"{request.prompt}|{request.seed}|{len(request.exclude_hashes)}"
        seed = int(hashlib.sha256(seed_src.encode()).hexdigest()[:12], 16)
        rnd = random.Random(seed)
        pal = self._palette(f"{request.prompt} {request.search_query} {' '.join(request.style_tags)}")
        # Degradado vertical entre dos colores de la paleta
        top, bottom = pal[0], pal[1]
        grad = Image.new("RGB", (1, 256))
        for y in range(256):
            t = y / 255
            grad.putpixel((0, y), tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3)))
        img = grad.resize((w, h), Image.BICUBIC)
        # Formas luminosas difuminadas
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        for _ in range(self.params["shapes"]):
            r = rnd.randint(w // 8, w // 2)
            cx, cy = rnd.randint(0, w), rnd.randint(0, h)
            color = pal[rnd.choice([2, 3])]
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*color, rnd.randint(90, 170)))
        for _ in range(3):  # líneas diagonales sutiles
            x0 = rnd.randint(-w, w)
            d.line([(x0, 0), (x0 + w, h)], fill=(*pal[3], 30), width=rnd.randint(6, 30))
        layer = layer.filter(ImageFilter.GaussianBlur(radius=w // 18))
        img = Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")
        # Viñeta radial suave (centro iluminado, bordes algo más oscuros)
        import numpy as np
        yy, xx = np.mgrid[0:h, 0:w]
        dist = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2) / np.sqrt(2)
        mask = np.clip(1.25 - dist, 0.55, 1.0)
        arr = (np.asarray(img, dtype=np.float32) * mask[..., None]).clip(0, 255).astype("uint8")
        img = Image.fromarray(arr)
        if self.params["grain"]:
            noise = Image.effect_noise((w // 2, h // 2), self.params["grain"] * 4).resize((w, h)).convert("RGB")
            img = Image.blend(img, noise, 0.04)
        request.out_dir.mkdir(parents=True, exist_ok=True)
        path = request.out_dir / f"proc_{seed:012x}.jpg"
        img.save(path, "JPEG", quality=92)
        return MediaAsset(kind=AssetKind.IMAGE, path=str(path), width=w, height=h, provider=self.name,
                          prompt=request.prompt, sha256=sha256_file(path), perceptual_hash=average_hash(path),
                          license=License(name="generated", attribution="ytauto procedural (CC0)",
                                          commercial_use=True),
                          metadata={"seed": seed, "palette": [list(c) for c in pal]})
