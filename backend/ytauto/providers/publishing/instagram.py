"""Publicación en Instagram Reels con la Instagram Graph API (publicación de contenido).

Flujo (documentación oficial de Meta):
  1. POST /{ig-user-id}/media  media_type=REELS, video_url=<URL pública>, caption=...  → id del contenedor.
  2. GET  /{container-id}?fields=status_code,status  hasta FINISHED (IN_PROGRESS = procesando;
     ERROR/EXPIRED = fallo).
  3. POST /{ig-user-id}/media_publish  creation_id=<id del contenedor>  → id del medio publicado.

Requisitos: cuenta profesional de Instagram, token con permisos de publicación y el vídeo accesible en una URL
PÚBLICA (Meta lo descarga). Los contenedores caducan a las 24 h y hay un tope de 400 contenedores y 100
publicaciones por API cada 24 h. La API consultada no ofrece visibilidad privada: publicar es público, por eso
se exige una autorización de publicación pública explícita.
"""
from __future__ import annotations

import time

import httpx

from ...core.errors import ProviderError
from ..http import client, request
from ..interfaces import HealthStatus, PublishingProvider, PublishRequest, PublishResult

GRAPH = "https://graph.facebook.com"


class InstagramPublishingProvider(PublishingProvider):
    """Publica Reels en una cuenta profesional de Instagram con la Graph API."""
    name = "instagram_graph_api"
    display_name = "Instagram Graph API"
    is_local = False
    requires_network = True
    platforms = ["instagram_reels"]
    supports_direct_publish = True
    required_credentials = ["access_token", "ig_user_id"]
    default_params = {"api_version": "v25.0", "poll_interval_s": 5.0, "max_wait_s": 300.0, "share_to_feed": True}
    _transport: httpx.BaseTransport | None = None

    def capabilities(self):
        return {"platforms": self.platforms, "privacy": ["public"], "requires_public_video_url": True,
                "daily_limits": {"api_posts": 100, "containers": 400}}

    def _url(self, path: str) -> str:
        return f"{GRAPH}/{self.params['api_version']}/{path.lstrip('/')}"

    def _secrets(self) -> list[str]:
        return [v for v in self.credentials.values() if v]

    def verify_connection(self) -> HealthStatus:
        local = self.health_check()
        if not local.ok:
            return local
        try:
            with client(self._transport) as c:
                r = request(self.name, c, "GET", self._url(self.credentials["ig_user_id"]), self._secrets(),
                            params={"fields": "id,username", "access_token": self.credentials["access_token"]})
            return HealthStatus(ok=True, message=f"Cuenta @{r.json().get('username', '?')}")
        except ProviderError as e:
            return HealthStatus(ok=False, message=str(e))

    def check_requirements(self, request: PublishRequest) -> list[str]:
        issues = []
        if not request.authorization_id:
            issues.append("Falta la autorización expresa del usuario")
        if request.privacy != "public":
            issues.append("Instagram no ofrece publicación privada por API: autoriza una publicación pública "
                          "o usa el paquete manual")
        if not request.video_url or not request.video_url.startswith("https://"):
            issues.append("Instagram necesita una URL pública (https) del vídeo: configura un almacenamiento "
                          "con URL pública o usa el paquete manual")
        caption = request.description
        if len(caption) > 2200:
            issues.append("El pie supera los 2200 caracteres")
        return issues

    def publish(self, req: PublishRequest) -> PublishResult:
        issues = self.check_requirements(req)
        if issues:
            raise ProviderError(self.name, "; ".join(issues), transient=False)
        token = self.credentials["access_token"]
        uid = self.credentials["ig_user_id"]
        secrets = self._secrets()
        with client(self._transport) as c:
            created = request(self.name, c, "POST", self._url(f"{uid}/media"), secrets, data={
                "media_type": "REELS", "video_url": req.video_url, "caption": req.description,
                "share_to_feed": str(bool(self.params["share_to_feed"])).lower(), "access_token": token})
            container = created.json().get("id")
            if not container:
                raise ProviderError(self.name, "Instagram no devolvió el id del contenedor", transient=False)
            deadline = time.monotonic() + float(self.params["max_wait_s"])
            while True:  # el procesamiento del vídeo es asíncrono: hay que consultar el estado
                st = request(self.name, c, "GET", self._url(container), secrets,
                             params={"fields": "status_code,status", "access_token": token}).json()
                code = st.get("status_code")
                if code in ("FINISHED", "PUBLISHED"):
                    break
                if code in ("ERROR", "EXPIRED"):
                    raise ProviderError(self.name, f"El contenedor falló ({code}): {st.get('status', '')}",
                                        transient=False)
                if time.monotonic() >= deadline:
                    raise ProviderError(self.name, f"Instagram sigue procesando el vídeo tras "
                                                   f"{self.params['max_wait_s']:g}s (estado {code})", transient=True)
                time.sleep(float(self.params["poll_interval_s"]))
            # Desde aquí la publicación puede estar hecha aunque falle la respuesta: no transitorio.
            try:
                pub = request(self.name, c, "POST", self._url(f"{uid}/media_publish"), secrets,
                              data={"creation_id": container, "access_token": token})
            except ProviderError as e:
                raise ProviderError(self.name, f"{e} (la publicación pudo completarse: comprueba Instagram antes "
                                               "de reintentar)", transient=False) from e
            media_id = pub.json().get("id")
            permalink = None
            try:
                permalink = request(self.name, c, "GET", self._url(media_id), secrets,
                                    params={"fields": "permalink", "access_token": token}).json().get("permalink")
            except ProviderError:
                pass  # el enlace es opcional
        return PublishResult(platform=req.platform, status="published", url=permalink, external_id=media_id,
                             message="Reel publicado en Instagram (visibilidad pública).")
