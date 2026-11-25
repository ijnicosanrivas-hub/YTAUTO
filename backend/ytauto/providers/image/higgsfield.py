"""Imágenes con Higgsfield usando los créditos del plan (CLI oficial). Ver `ytauto.providers.higgsfield`."""
from __future__ import annotations

from PIL import Image

from ...core.models import AssetKind, License, MediaAsset
from ...core.workspace import sha256_file
from ..higgsfield import IMAGE_MODELS, HiggsfieldCommon, download
from ..interfaces import ImageGenerationProvider, ImageRequest
from ..library import average_hash


class HiggsfieldImageProvider(HiggsfieldCommon, ImageGenerationProvider):
    """Imagen generativa 9:16 con la cuenta de higgsfield.ai (créditos del plan)."""
    name = "higgsfield_image"
    display_name = "Higgsfield · imagen (créditos del plan)"
    is_paid = True
    is_local = False
    requires_network = True
    default_priority = 5
    kind = "image"
    fallback_credits = 3.0
    default_params = {"cli_path": "", "model": "nano_banana_flash", "price_per_credit_eur": None,
                      "credits_per_generation": None, "reserve_credits": 60, "require_balance_check": True,
                      "wait_minutes": 10}

    def capabilities(self):
        return {**super().capabilities(), "figurative": True, "models": {k: v["label"] for k, v in IMAGE_MODELS.items()}}

    def flags_for(self, request: ImageRequest) -> dict:
        return {"aspect_ratio": "9:16"}

    def generate(self, request: ImageRequest) -> MediaAsset:
        prompt = request.prompt.strip()
        if request.style_tags:
            prompt += f". Estilo: {', '.join(request.style_tags)}"
        if request.negative_prompt:
            prompt += f". Evitar: {request.negative_prompt}"
        urls, credits = self.run_job(prompt, request)
        request.out_dir.mkdir(parents=True, exist_ok=True)
        tmp = download(urls[0], request.out_dir / "higgsfield_tmp.img", self._transport, max_mb=60)
        with Image.open(tmp) as im:
            img = im.convert("RGB")
        digest = sha256_file(tmp)
        path = request.out_dir / f"hf_{digest[:12]}.png"
        img.save(path, "PNG")
        tmp.unlink(missing_ok=True)
        price = float(self.params.get("price_per_credit_eur") or 0)
        return MediaAsset(kind=AssetKind.IMAGE, path=str(path), width=img.width, height=img.height, provider=self.name,
                          prompt=prompt, sha256=digest, perceptual_hash=average_hash(path),
                          cost_eur=round(credits * price, 4), source_url=urls[0],
                          license=License(name="provider-terms", attribution="Imagen generada con Higgsfield",
                                          url="https://higgsfield.ai/terms-of-use", commercial_use=None),
                          metadata={"model": self.params["model"], "credits": credits})
