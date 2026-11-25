"""Clips de vídeo con Higgsfield usando los créditos del plan (CLI oficial). Ver `ytauto.providers.higgsfield`."""
from __future__ import annotations

from ...core.models import AssetKind, License, MediaAsset
from ...core.workspace import sha256_file
from ..higgsfield import VIDEO_MODELS, HiggsfieldCommon, download, pick_duration
from ..interfaces import VideoGenerationProvider, VideoRequest
from .local import ffprobe_video


class HiggsfieldVideoProvider(HiggsfieldCommon, VideoGenerationProvider):
    """Vídeo generativo 9:16 con la cuenta de higgsfield.ai (créditos del plan)."""
    name = "higgsfield_video"
    display_name = "Higgsfield · vídeo (créditos del plan)"
    is_paid = True
    is_local = False
    requires_network = True
    default_priority = 5
    kind = "video"
    fallback_credits = 40.0
    default_params = {"cli_path": "", "model": "kling3_0_turbo", "resolution": "720p", "price_per_credit_eur": None,
                      "credits_per_generation": None, "reserve_credits": 60, "require_balance_check": True,
                      "wait_minutes": 15}

    def capabilities(self):
        return {**super().capabilities(), "models": {k: v["label"] for k, v in VIDEO_MODELS.items()}}

    def flags_for(self, request: VideoRequest) -> dict:
        model = str(self.params["model"])
        flags = {"aspect_ratio": "9:16", "duration": pick_duration(model, request.duration_s),
                 "resolution": self.params.get("resolution") or None}
        if request.image_path:
            flags["start-image"] = str(request.image_path)
            if model.startswith("seedance"):
                flags["mode"] = "omni_reference"
        return flags

    def generate(self, request: VideoRequest) -> MediaAsset:
        prompt = f"{request.prompt.strip()}. Vertical 9:16, sin texto en pantalla."
        urls, credits = self.run_job(prompt, request)
        request.out_dir.mkdir(parents=True, exist_ok=True)
        tmp = download(urls[0], request.out_dir / "higgsfield_tmp.mp4", self._transport)
        digest = sha256_file(tmp)
        path = tmp.replace(request.out_dir / f"hf_{digest[:12]}.mp4")
        dur, w, h = ffprobe_video(path)
        price = float(self.params.get("price_per_credit_eur") or 0)
        return MediaAsset(kind=AssetKind.VIDEO, path=str(path), duration_s=dur, width=w, height=h, provider=self.name,
                          prompt=prompt, sha256=digest, perceptual_hash=digest[:16], cost_eur=round(credits * price, 4),
                          source_url=urls[0],
                          license=License(name="provider-terms", attribution="Vídeo generado con Higgsfield",
                                          url="https://higgsfield.ai/terms-of-use", commercial_use=None),
                          metadata={"model": self.params["model"], "credits": credits, "loop": dur < request.duration_s})
