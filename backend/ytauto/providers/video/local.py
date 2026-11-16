"""Clips de vídeo de la biblioteca local con licencia (library/videos)."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ...core.errors import ProviderError
from ...core.models import AssetKind, MediaAsset
from ...core.workspace import sha256_file
from ..interfaces import HealthStatus, VideoGenerationProvider, VideoRequest
from ..library import VIDEO_EXT, best_match, default_library_root, scan


def ffprobe_video(path: Path) -> tuple[float, int, int]:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height:format=duration", "-of", "json", str(path)],
                         capture_output=True, text=True)
    info = json.loads(out.stdout or "{}")
    st = (info.get("streams") or [{}])[0]
    return float(info.get("format", {}).get("duration", 0)), int(st.get("width", 0)), int(st.get("height", 0))


class LocalLibraryVideoProvider(VideoGenerationProvider):
    """Busca clips en la biblioteca local por etiquetas y nombre."""
    name = "library_videos"
    display_name = "Biblioteca local de vídeos"
    default_priority = 10
    default_params = {"root": ""}

    @property
    def folder(self) -> Path:
        return Path(self.params["root"] or default_library_root()) / "videos"

    def health_check(self) -> HealthStatus:
        n = len(scan(self.folder, VIDEO_EXT))
        return HealthStatus(ok=n > 0, message=f"{n} clips con licencia" if n else f"Sin clips con licencia en {self.folder}")

    def generate(self, request: VideoRequest) -> MediaAsset:
        items = scan(self.folder, VIDEO_EXT)
        item = best_match(items, f"{request.search_query} {request.prompt}",
                          exclude={str(i.path) for i in items if sha256_file(i.path)[:16] in request.exclude_hashes})
        if item is None:
            raise ProviderError(self.name, f"Sin clips para '{request.search_query}'", transient=False)
        dur, w, h = ffprobe_video(item.path)
        return MediaAsset(kind=AssetKind.VIDEO, path=str(item.path), duration_s=dur, width=w, height=h,
                          provider=self.name, prompt=request.prompt, sha256=sha256_file(item.path),
                          perceptual_hash=sha256_file(item.path)[:16], license=item.license,
                          source_url=item.meta.get("url"), metadata={"loop": dur < request.duration_s})
