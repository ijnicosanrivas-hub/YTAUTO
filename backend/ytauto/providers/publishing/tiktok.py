"""Publicación en TikTok con la Content Posting API (Direct Post, subida de fichero por trozos).

Flujo (documentación oficial de TikTok):
  1. POST /v2/post/publish/creator_info/query/  → opciones de privacidad del creador y duración máxima.
  2. POST /v2/post/publish/video/init/  (source_info FILE_UPLOAD: video_size, chunk_size, total_chunk_count)
     → publish_id y upload_url.
  3. PUT de los trozos, en orden, a upload_url (5–64 MB cada uno; el último hasta 128 MB; menos de 5 MB = un
     solo trozo; total_chunk_count = video_size // chunk_size).
  4. POST /v2/post/publish/status/fetch/ {publish_id} hasta PUBLISH_COMPLETE o FAILED.

Limitaciones documentadas: los clientes SIN AUDITAR solo pueden publicar con visibilidad SELF_ONLY (privada),
con un tope de 5 usuarios por 24 h; el `privacy_level` debe ser una de las opciones devueltas por la consulta
del creador (si no, 403 privacy_level_option_mismatch). Requiere el permiso `video.publish`.

NO verificado en la documentación consultada: el formato exacto de las cabeceras de cada trozo
(`Content-Range`); se usa el estándar HTTP `bytes inicio-fin/total`. Revísalo con TikTok antes de producción.
"""
from __future__ import annotations

import time
from pathlib import Path

import httpx

from ...core.errors import ProviderError
from ..http import client, request
from ..interfaces import HealthStatus, PublishingProvider, PublishRequest, PublishResult

API = "https://open.tiktokapis.com"
MB = 1024 * 1024
MIN_CHUNK, MAX_CHUNK, MAX_LAST_CHUNK = 5 * MB, 64 * MB, 128 * MB
LEVELS = {"private": "SELF_ONLY", "public": "PUBLIC_TO_EVERYONE"}


def plan_chunks(size: int, chunk_size: int) -> tuple[int, int, int]:
    """Devuelve (chunk_size, total_chunk_count, tamaño del último trozo) según las reglas de TikTok."""
    if size <= 0:
        raise ValueError("Vídeo vacío")
    if size < MIN_CHUNK:
        return size, 1, size  # menos de 5 MB: un único trozo
    chunk = max(MIN_CHUNK, min(chunk_size, MAX_CHUNK))
    total = size // chunk  # redondeo hacia abajo: el último trozo absorbe el resto
    last = size - chunk * (total - 1)
    if last > MAX_LAST_CHUNK:  # el resto sería demasiado grande: se usan trozos mayores
        chunk = MAX_CHUNK
        total = size // chunk
        last = size - chunk * (total - 1)
    if total > 1000 or last > MAX_LAST_CHUNK:
        raise ValueError("El vídeo no cabe en los límites de trozos de TikTok")
    return chunk, total, last


class TikTokPublishingProvider(PublishingProvider):
    """Publica vídeos en TikTok con Direct Post (`video.publish`)."""
    name = "tiktok_content_posting_api"
    display_name = "TikTok Content Posting API"
    is_local = False
    requires_network = True
    platforms = ["tiktok"]
    supports_direct_publish = True
    required_credentials = ["access_token"]
    default_params = {"chunk_size_mb": 10, "poll_interval_s": 5.0, "max_wait_s": 300.0}
    _transport: httpx.BaseTransport | None = None

    def capabilities(self):
        return {"platforms": self.platforms, "privacy": ["private", "public"],
                "note": "Sin auditoría de TikTok solo se admite visibilidad privada (SELF_ONLY)."}

    def _secrets(self) -> list[str]:
        return [v for v in self.credentials.values() if v]

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.credentials['access_token']}",
                "Content-Type": "application/json; charset=UTF-8"}

    def _creator_info(self, c: httpx.Client) -> dict:
        r = request(self.name, c, "POST", f"{API}/v2/post/publish/creator_info/query/", self._secrets(),
                    headers=self._headers())
        return (r.json().get("data") or {})

    def verify_connection(self) -> HealthStatus:
        local = self.health_check()
        if not local.ok:
            return local
        try:
            with client(self._transport) as c:
                info = self._creator_info(c)
        except ProviderError as e:
            return HealthStatus(ok=False, message=str(e))
        opts = ", ".join(info.get("privacy_level_options", [])) or "?"
        return HealthStatus(ok=True, message=f"Creador @{info.get('creator_username', '?')}; privacidad: {opts}")

    def check_requirements(self, request: PublishRequest) -> list[str]:
        issues = []
        if not request.authorization_id:
            issues.append("Falta la autorización expresa del usuario")
        if request.privacy not in LEVELS:
            issues.append("TikTok solo admite visibilidad privada o pública en este adaptador")
        if not Path(request.video_path).exists():
            issues.append(f"No existe el vídeo {request.video_path}")
        if len(request.description) > 2200:
            issues.append("El pie supera los 2200 caracteres")
        return issues

    def publish(self, req: PublishRequest) -> PublishResult:
        issues = self.check_requirements(req)
        if issues:
            raise ProviderError(self.name, "; ".join(issues), transient=False)
        video = Path(req.video_path)
        size = video.stat().st_size
        level = LEVELS[req.privacy]
        with client(self._transport) as c:
            info = self._creator_info(c)
            options = info.get("privacy_level_options") or []
            if options and level not in options:
                raise ProviderError(
                    self.name, f"La visibilidad {level} no está entre las opciones del creador {options}. "
                    "Si la app no está auditada, TikTok solo permite SELF_ONLY (privado).", transient=False)
            chunk, total, _ = plan_chunks(size, int(float(self.params["chunk_size_mb"]) * MB))
            init = request(self.name, c, "POST", f"{API}/v2/post/publish/video/init/", self._secrets(),
                           headers=self._headers(), json={
                               "post_info": {"title": req.description, "privacy_level": level},
                               "source_info": {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": chunk,
                                               "total_chunk_count": total}}).json()
            data = init.get("data") or {}
            publish_id, upload_url = data.get("publish_id"), data.get("upload_url")
            if not publish_id or not upload_url:
                raise ProviderError(self.name, "TikTok no devolvió publish_id/upload_url", transient=False)
            # A partir de aquí puede haber contenido en TikTok: los fallos no deben provocar duplicados.
            try:
                with open(video, "rb") as f:
                    for i in range(total):
                        start = i * chunk
                        length = (size - start) if i == total - 1 else chunk
                        part = f.read(length)
                        request(self.name, c, "PUT", upload_url, self._secrets(), headers={
                            "Content-Type": "video/mp4", "Content-Length": str(len(part)),
                            "Content-Range": f"bytes {start}-{start + len(part) - 1}/{size}"}, content=part)
                result = self._wait(c, publish_id)
            except ProviderError as e:
                raise ProviderError(self.name, f"{e} (publish_id {publish_id}; comprueba TikTok antes de "
                                               "reintentar)", transient=False) from e
        private = level == "SELF_ONLY"
        return PublishResult(platform=req.platform, status="uploaded_private" if private else "published",
                             url=None, external_id=result or publish_id,
                             message=("Publicado en TikTok con visibilidad privada (SELF_ONLY)." if private
                                      else "Publicado en TikTok (visibilidad pública)."))

    def _wait(self, c: httpx.Client, publish_id: str) -> str | None:
        """Espera a PUBLISH_COMPLETE; devuelve el id público del post si TikTok ya lo asignó."""
        deadline = time.monotonic() + float(self.params["max_wait_s"])
        while True:
            st = request(self.name, c, "POST", f"{API}/v2/post/publish/status/fetch/", self._secrets(),
                         headers=self._headers(), json={"publish_id": publish_id}).json().get("data") or {}
            status = st.get("status")
            if status == "PUBLISH_COMPLETE":
                # El campo se documenta con la ortografía «publicaly_…»; se aceptan ambas.
                ids = st.get("publicaly_available_post_id") or st.get("publicly_available_post_id") or []
                return str(ids[0]) if ids else None
            if status == "FAILED":
                raise ProviderError(self.name, f"TikTok no pudo publicar: {st.get('fail_reason', 'sin motivo')}",
                                    transient=False)
            if time.monotonic() >= deadline:
                raise ProviderError(self.name, f"TikTok sigue procesando tras {self.params['max_wait_s']:g}s "
                                               f"(estado {status})", transient=False)
            time.sleep(float(self.params["poll_interval_s"]))
