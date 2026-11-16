"""Publicación en YouTube Shorts con la YouTube Data API v3 (subida reanudable, OAuth 2.0).

Protocolo (documentación oficial de YouTube Data API):
  1. POST https://oauth2.googleapis.com/token  (grant_type=refresh_token) → access_token.
  2. POST https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status
     con el recurso de vídeo en el cuerpo → cabecera `Location` con la URI de la sesión.
  3. PUT a esa URI con los bytes del vídeo → recurso de vídeo con `id`.

Limitaciones documentadas: los vídeos subidos desde proyectos de API sin verificar (creados tras el
28-jul-2020) quedan restringidos a visualización PRIVADA. El adaptador lee la privacidad que devuelve
YouTube y lo informa. Los tokens los obtiene el usuario (consentimiento OAuth con el alcance
`https://www.googleapis.com/auth/youtube.upload`); aquí solo se guarda el `refresh_token` cifrado.
"""
from __future__ import annotations

from pathlib import Path

import httpx

from ...core.errors import ProviderError
from ..http import client, request
from ..interfaces import HealthStatus, PublishingProvider, PublishRequest, PublishResult

TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
API_VIDEOS = "https://www.googleapis.com/youtube/v3/videos"
PRIVACY = {"private": "private", "unlisted": "unlisted", "public": "public"}
CHUNK = 1024 * 1024


def stream_file(f, chunk: int = CHUNK):
    """Lee el fichero por bloques (sin cargarlo entero en memoria)."""
    while block := f.read(chunk):
        yield block


class YouTubePublishingProvider(PublishingProvider):
    """Publica Shorts en YouTube con la Data API v3 (credenciales OAuth del usuario)."""
    name = "youtube_data_api"
    display_name = "YouTube Data API v3"
    is_local = False
    requires_network = True
    platforms = ["youtube_shorts"]
    supports_direct_publish = True
    required_credentials = ["client_id", "client_secret", "refresh_token"]
    default_params = {"category_id": "22", "made_for_kids": False, "notify_subscribers": False}
    _transport: httpx.BaseTransport | None = None  # inyectable en pruebas

    def capabilities(self):
        return {"platforms": self.platforms, "privacy": ["private", "unlisted", "public"], "thumbnail": False,
                "note": "Los proyectos de API sin verificar solo pueden subir vídeos privados."}

    def _secrets(self) -> list[str]:
        return [v for v in self.credentials.values() if v]

    def _access_token(self, c: httpx.Client) -> str:
        r = request(self.name, c, "POST", TOKEN_URL, self._secrets(), data={
            "client_id": self.credentials["client_id"], "client_secret": self.credentials["client_secret"],
            "refresh_token": self.credentials["refresh_token"], "grant_type": "refresh_token"})
        token = r.json().get("access_token")
        if not token:
            raise ProviderError(self.name, "Google no devolvió un access_token", transient=False)
        return token

    def verify_connection(self) -> HealthStatus:
        local = self.health_check()
        if not local.ok:
            return local
        try:
            with client(self._transport) as c:
                self._access_token(c)  # solo lectura: confirma que las credenciales son válidas
        except ProviderError as e:
            return HealthStatus(ok=False, message=str(e))
        return HealthStatus(ok=True, message="Credenciales OAuth válidas (token de acceso obtenido)")

    def check_requirements(self, request: PublishRequest) -> list[str]:
        issues = []
        if not request.authorization_id:
            issues.append("Falta la autorización expresa del usuario")
        if not Path(request.video_path).exists():
            issues.append(f"No existe el vídeo {request.video_path}")
        if not request.title.strip() or len(request.title) > 100:
            issues.append("El título es obligatorio y debe tener 100 caracteres como máximo")
        if len(request.description.encode("utf-8")) > 5000:
            issues.append("La descripción supera los 5000 bytes")
        return issues

    def publish(self, req: PublishRequest) -> PublishResult:
        issues = self.check_requirements(req)
        if issues:
            raise ProviderError(self.name, "; ".join(issues), transient=False)
        video = Path(req.video_path)
        size = video.stat().st_size
        body = {
            "snippet": {"title": req.title, "description": req.description, "categoryId": self.params["category_id"],
                        "tags": [h.lstrip("#") for h in req.hashtags]},
            "status": {"privacyStatus": PRIVACY[req.privacy],
                       "selfDeclaredMadeForKids": bool(self.params["made_for_kids"])},
        }
        with client(self._transport) as c:
            token = self._access_token(c)
            secrets = [*self._secrets(), token]
            auth = {"Authorization": f"Bearer {token}"}
            init = request(self.name, c, "POST", UPLOAD_URL, secrets, params={
                "uploadType": "resumable", "part": "snippet,status",
                "notifySubscribers": str(bool(self.params["notify_subscribers"])).lower()},
                headers={**auth, "Content-Type": "application/json; charset=UTF-8",
                         "X-Upload-Content-Length": str(size), "X-Upload-Content-Type": "video/mp4"}, json=body)
            session = init.headers.get("location")
            if not session:
                raise ProviderError(self.name, "YouTube no devolvió la URI de subida (cabecera Location)",
                                    transient=False)
            with open(video, "rb") as f:
                # A partir de aquí el vídeo puede existir en YouTube aunque falle la respuesta: un fallo se
                # marca como NO transitorio para que ningún reintento automático duplique la publicación.
                try:
                    up = request(self.name, c, "PUT", session, secrets,
                                 headers={**auth, "Content-Type": "video/mp4", "Content-Length": str(size)},
                                 content=stream_file(f))
                except ProviderError as e:
                    raise ProviderError(self.name, f"{e} (la subida pudo completarse: comprueba YouTube Studio "
                                                   "antes de reintentar)", transient=False) from e
            data = up.json()
        vid = data.get("id")
        if not vid:
            raise ProviderError(self.name, "La subida terminó sin identificador de vídeo", transient=False)
        actual = (data.get("status") or {}).get("privacyStatus", req.privacy)
        note = ""
        if actual != req.privacy:
            note = (f" YouTube aplicó la visibilidad «{actual}» en lugar de «{req.privacy}» "
                    "(los proyectos de API sin verificar solo pueden subir vídeos privados).")
        return PublishResult(platform=req.platform, status="published" if actual == "public" else "uploaded_private",
                             url=f"https://www.youtube.com/shorts/{vid}", external_id=vid,
                             message=f"Subido a YouTube con visibilidad «{actual}».{note}")
