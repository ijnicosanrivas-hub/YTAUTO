"""Imágenes de pago con la API de imágenes de OpenAI (ejemplo de adaptador comercial).

API (documentación oficial): POST https://api.openai.com/v1/images/generations con `Authorization: Bearer …` y
cuerpo {model, prompt, size, n}; los modelos de imagen GPT devuelven la imagen en base64 en data[0].b64_json.

MODELO: los nombres de modelo difieren entre las propias páginas de OpenAI, así que `model` es un parámetro que
debes confirmar en su lista de modelos. COSTE: no hay tarifa por defecto: indica `price_per_image_eur`. Sin él,
el adaptador se declara no disponible y nunca se usa.
"""
from __future__ import annotations

import base64
import hashlib
from io import BytesIO

import httpx
from PIL import Image

from ...core.errors import ProviderError
from ...core.models import AssetKind, License, MediaAsset
from ..http import client, request
from ..interfaces import CostEstimate, HealthStatus, ImageGenerationProvider, ImageRequest
from ..library import average_hash

BASE = "https://api.openai.com"


class OpenAIImageProvider(ImageGenerationProvider):
    """Generación de imágenes con la API de OpenAI (de pago)."""
    name = "openai_images"
    display_name = "OpenAI Images (de pago)"
    is_paid = True
    is_local = False
    requires_network = True
    required_credentials = ["api_key"]
    default_params = {"model": "gpt-image-1", "size": "1024x1536", "price_per_image_eur": None}
    _transport: httpx.BaseTransport | None = None

    def capabilities(self):
        return {"figurative": True, "aspect_ratios": ["9:16"], "needs_price_param": True,
                "note": "Confirma el nombre del modelo en la lista de modelos de OpenAI."}

    def health_check(self) -> HealthStatus:
        base = super().health_check()
        if not base.ok:
            return base
        if self.params.get("price_per_image_eur") in (None, ""):
            return HealthStatus(ok=False, message="Configura price_per_image_eur (tu coste real por imagen): sin él "
                                                  "no se puede estimar el coste ni aplicar el presupuesto")
        return HealthStatus(ok=True, message="Configurado")

    def verify_connection(self) -> HealthStatus:
        local = self.health_check()
        if not local.ok:
            return local
        try:
            with client(self._transport) as c:
                request(self.name, c, "GET", f"{BASE}/v1/models", [self.credentials["api_key"]],
                        headers={"Authorization": f"Bearer {self.credentials['api_key']}"})
            return HealthStatus(ok=True, message="Clave válida (lista de modelos accesible)")
        except ProviderError as e:
            return HealthStatus(ok=False, message=str(e))

    def estimate_cost(self, operation, request_):
        price = float(self.params.get("price_per_image_eur") or 0)
        return CostEstimate(amount_eur=price, units=1, unit_name="imagen",
                            detail=f"{price} € por imagen (precio configurado por el usuario)")

    def generate(self, req: ImageRequest) -> MediaAsset:
        prompt = req.prompt
        if req.style_tags:
            prompt += f". Estilo: {', '.join(req.style_tags)}"
        if req.negative_prompt:
            prompt += f". Evitar: {req.negative_prompt}"
        with client(self._transport) as c:
            r = request(self.name, c, "POST", f"{BASE}/v1/images/generations", [self.credentials["api_key"]],
                        headers={"Authorization": f"Bearer {self.credentials['api_key']}"},
                        json={"model": self.params["model"], "prompt": prompt, "size": self.params["size"], "n": 1})
        data = (r.json().get("data") or [{}])[0]
        if not data.get("b64_json"):
            raise ProviderError(self.name, "La respuesta no incluye la imagen (b64_json)", transient=False)
        raw = base64.b64decode(data["b64_json"])
        img = Image.open(BytesIO(raw))
        digest = hashlib.sha256(raw).hexdigest()
        req.out_dir.mkdir(parents=True, exist_ok=True)
        path = req.out_dir / f"oai_{digest[:12]}.png"
        img.save(path, "PNG")
        return MediaAsset(kind=AssetKind.IMAGE, path=str(path), width=img.width, height=img.height,
                          provider=self.name, prompt=prompt, sha256=digest, perceptual_hash=average_hash(path),
                          cost_eur=self.estimate_cost("generate", req).amount_eur,
                          license=License(name="provider-terms", attribution="Imagen generada con OpenAI",
                                          url="https://openai.com/policies/terms-of-use", commercial_use=None),
                          metadata={"model": self.params["model"], "size": self.params["size"]})
