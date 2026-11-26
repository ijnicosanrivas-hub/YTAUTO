"""Música de la Biblioteca de audio de YouTube Studio: importación, elección por ánimo, crédito y avisos."""
from __future__ import annotations

import base64
import json
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_agents import PIPE, run_until
from ytauto.api.music_api import guess_title_artist, safe_name
from ytauto.api.server import create_api
from ytauto.app import build_app
from ytauto.core.errors import ProviderError
from ytauto.core.settings import Settings
from ytauto.llm.mock import LocalDraftLLM
from ytauto.providers.interfaces import MusicRequest
from ytauto.providers.interfaces import ProviderCategory as C
from ytauto.providers.music.youtube_audio_library import (
    YouTubeAudioLibraryMusicProvider,
    expand_query,
)
from ytauto.providers.registry import catalog

CREDIT = 'Night Run by Artista Demo is licensed under a Creative Commons Attribution 4.0 licence.'


@pytest.fixture(scope="module")
def mp3(tmp_path_factory):
    out = tmp_path_factory.mktemp("yal") / "t.mp3"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=f=220:d=3", str(out)], check=True)
    return out.read_bytes()


def add(folder: Path, name: str, data: bytes, **meta):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_bytes(data)
    base = {"license": "YouTube Audio Library", "commercial_use": True, "duration_s": 3}
    (folder / f"{name}.json").write_text(json.dumps({**base, **meta}), encoding="utf-8")


def test_picks_by_mood_and_marks_attribution(tmp_path, mp3):
    root = tmp_path / "lib"
    folder = root / "youtube_audio_library"
    add(folder, "Sunny Day - A.mp3", mp3, genre="Pop", mood="Happy")
    add(folder, "Night Run - B.mp3", mp3, genre="Cinematic", mood="Dark", attribution_required=True,
        license="Creative Commons (YouTube Audio Library)", attribution=CREDIT)
    p = YouTubeAudioLibraryMusicProvider(params={"root": str(root)})
    assert p.health_check().ok and "2 pistas" in p.health_check().message
    assert {"dark", "dramatic"} <= expand_query("tensión épica de suspense")
    dark = p.get_track(MusicRequest(mood="tensa y misteriosa", duration_s=30, out_dir=tmp_path))
    assert dark.metadata["file"] == "Night Run - B.mp3" and dark.metadata["attribution_required"]
    assert dark.license.attribution == CREDIT and dark.license.commercial_use and dark.provider == "youtube_audio_library"
    happy = p.get_track(MusicRequest(mood="alegre y divertida", duration_s=30, out_dir=tmp_path))
    assert happy.metadata["file"] == "Sunny Day - A.mp3" and happy.license.attribution is None
    with pytest.raises(ProviderError):
        YouTubeAudioLibraryMusicProvider(params={"root": str(tmp_path / "vacia")}).get_track(
            MusicRequest(mood="x", duration_s=5, out_dir=tmp_path))


def test_only_used_when_the_video_asks_for_it(tmp_path, mp3, monkeypatch):
    """Se registra detrás de la música procedural: la música automática nunca la elige por su cuenta."""
    from cryptography.fernet import Fernet
    from ytauto.db.schema import make_engine
    from ytauto.providers.registry import (
        BudgetManager,
        CredentialVault,
        ProviderRegistry,
        RegistryGateway,
    )
    monkeypatch.setenv("YTAUTO_LIBRARY_DIR", str(tmp_path / "lib"))
    add(tmp_path / "lib" / "youtube_audio_library", "Calm - C.mp3", mp3, mood="Calm")
    engine = make_engine(tmp_path / "m.db")
    reg = ProviderRegistry(engine, CredentialVault(engine, Fernet.generate_key()))
    reg.seed_defaults()
    chain = [c.id for c in reg.chain(C.MUSIC)]
    assert "youtube_audio_library" in chain and chain.index("procedural_music") < chain.index("youtube_audio_library")
    prefs = {"p_yt": {"music": "youtube_audio_library"}}
    gw = RegistryGateway(reg, BudgetManager(engine), preferred=lambda pid: prefs.get(pid, {}))
    req = MusicRequest(mood="calma", duration_s=10, out_dir=tmp_path / "o")
    assert gw.invoke(C.MUSIC, "get_track", req, project_id="p_yt").provider == "youtube_audio_library"
    assert gw.invoke(C.MUSIC, "get_track", req, project_id="p_auto").provider != "youtube_audio_library"


def test_credit_goes_to_the_description_and_other_platforms_get_a_warning(make_ctx, mock_providers, tmp_path, mp3):
    root = tmp_path / "lib"
    add(root / "youtube_audio_library", "Night Run - B.mp3", mp3, mood="Dark", attribution_required=True,
        license="Creative Commons (YouTube Audio Library)", attribution=CREDIT)
    mock_providers[C.MUSIC] = YouTubeAudioLibraryMusicProvider(params={"root": str(root)})
    ctx = make_ctx()
    run_until(ctx, *PIPE, "exports", "publish_prep")
    sound = ctx.workspace.load("sound", "sound_manifest")
    assert sound["music_provider"] == "youtube_audio_library" and sound["music_credit"] == CREDIT
    pkg = ctx.workspace.load("exports", "publish_package")
    for platform, item in pkg.items():
        assert CREDIT in item["description"], platform
        off = any("Biblioteca de audio de YouTube" in n for n in item["publish_notes"])
        assert off == (platform != "youtube_shorts"), platform
    readme = (Path(pkg["tiktok"]["manual_dir"]) / "LEEME.txt").read_text(encoding="utf-8")
    assert "no garantiza su uso fuera" in readme


def test_import_api(tmp_path, monkeypatch, mp3):
    monkeypatch.setenv("YTAUTO_LIBRARY_DIR", str(tmp_path / "lib"))
    monkeypatch.delenv("YTAUTO_MASTER_KEY", raising=False)
    monkeypatch.delenv("YTAUTO_API_TOKEN", raising=False)  # otra prueba (modo móvil) puede dejarlo puesto
    s = Settings.from_env(load_env_file=False)
    s.data_dir, s.projects_dir = tmp_path / "data", tmp_path / "projects"
    s.db_path, s.logs_dir, s.backups_dir = tmp_path / "data/y.db", tmp_path / "logs", tmp_path / "b"
    c = TestClient(create_api(build_app(s, llm=LocalDraftLLM(), include_mock_providers=True)))
    b64 = base64.b64encode(mp3).decode()
    first = c.get("/api/music/youtube")
    assert first.status_code == 200, first.text
    assert first.json()["tracks"] == []
    bad = c.post("/api/music/youtube", json={"filename": "CC Song - X.mp3", "data_b64": b64, "attribution_required": True})
    assert bad.status_code == 400 and "atribución" in bad.json()["detail"]
    assert not list((tmp_path / "lib" / "youtube_audio_library").glob("*.mp3"))  # no queda a medias
    r = c.post("/api/music/youtube", json={"filename": "../../Epic Rise - Artista.mp3", "data_b64": b64,
                                           "genre": "Cinematic", "mood": "Dramatic"})
    assert r.status_code == 201, r.text
    t = r.json()
    assert t["file"] == "Epic Rise - Artista.mp3" and t["title"] == "Epic Rise" and t["artist"] == "Artista"
    assert t["usable"] and not t["attribution_required"] and t["duration_s"] > 2
    assert (tmp_path / "lib" / "youtube_audio_library" / "Epic Rise - Artista.mp3").exists()
    e = c.patch("/api/music/youtube/Epic Rise - Artista.mp3", json={"attribution_required": True, "attribution": CREDIT}).json()
    assert e["attribution_required"] and e["license"].startswith("Creative Commons")
    assert c.post("/api/music/youtube", json={"filename": "x.exe", "data_b64": b64}).status_code == 400
    assert c.delete("/api/music/youtube/Epic Rise - Artista.mp3").json()["ok"]
    assert c.get("/api/music/youtube").json()["tracks"] == []


def test_name_helpers_and_elevenlabs_never_does_music():
    assert safe_name("../../a/b/Canción Épica.MP3") == "Cancion Epica.mp3"
    assert guess_title_artist("Night Run - Artista Demo.mp3") == ("Night Run", "Artista Demo")
    assert guess_title_artist("solo_titulo.mp3") == ("solo titulo", None)
    eleven = {n: c for n, c in catalog.discover().items() if "eleven" in n.lower()}
    # Voz y, solo si lo eliges en el cuestionario, efectos con IA; la música nunca es de ElevenLabs.
    assert eleven and {c.category for c in eleven.values()} <= {C.TTS, C.SFX}
    assert all(c.requires_network and c.is_paid for c in eleven.values())  # nunca se registran ni gastan solos
