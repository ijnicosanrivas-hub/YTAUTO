"""Higgsfield por su CLI oficial, probado con una CLI SIMULADA y descargas simuladas (sin red, sin créditos reales)."""
from __future__ import annotations

import hashlib
import io
import json
import subprocess
import tarfile
from pathlib import Path

import httpx
import pytest
from PIL import Image
from ytauto.core.errors import ProviderError, SpendNotAuthorized
from ytauto.providers import higgsfield as hf
from ytauto.providers.image.higgsfield import HiggsfieldImageProvider
from ytauto.providers.interfaces import ImageRequest, VideoRequest
from ytauto.providers.interfaces import ProviderCategory as C
from ytauto.providers.video.higgsfield import HiggsfieldVideoProvider


class FakeCLI:
    """Imita `higgsfield`: saldo, coste, generación con --wait --json y sesión caducada."""

    def __init__(self, credits=1200.0, cost=25.0, logged=True, status_json=True, kind="video", fail=None):
        self.credits, self.cost, self.logged, self.status_json, self.kind, self.fail = credits, cost, logged, status_json, kind, fail
        self.calls: list[list[str]] = []

    def __call__(self, argv, **kw):
        assert kw.get("stdin") is subprocess.DEVNULL and "timeout" in kw and not kw.get("shell")
        args = argv[1:]
        self.calls.append(args)

        def out(stdout="", code=0, stderr=""):
            return subprocess.CompletedProcess(argv, code, stdout, stderr)
        if not self.logged:
            return out(code=1, stderr="Error: Session expired. Run `higgsfield auth login`.")
        if args[:2] == ["account", "status"]:
            if self.status_json:
                return out(json.dumps({"user": {"plan": "plus"}, "credits": {"available": self.credits, "used": 99}}))
            return out("Plan: Plus\nCredits: 1,150\n")
        if args[:2] == ["generate", "cost"]:
            return out(json.dumps({"credits": self.cost}))
        if args[:2] == ["generate", "create"]:
            if self.fail:
                return out(code=1, stderr=self.fail)
            self.credits -= self.cost
            ext = "mp4" if self.kind == "video" else "png"
            return out(json.dumps([{"id": "job1", "status": "completed",
                                    "result": {"thumbnail": "https://cdn.example/t.webp",
                                               "url": f"https://cdn.example/out.{ext}"}}]))
        return out(code=2, stderr="unknown command")


@pytest.fixture(scope="module")
def mp4_bytes(tmp_path_factory):
    out = tmp_path_factory.mktemp("hf") / "c.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=blue:s=360x640:d=5",
                    "-pix_fmt", "yuv420p", str(out)], check=True)
    return out.read_bytes()


def png_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (576, 1024), (200, 40, 40)).save(buf, "PNG")
    return buf.getvalue()


def make(cls, cli: FakeCLI, content: bytes, tmp_path: Path, **params):
    fake_bin = tmp_path / "hf"
    fake_bin.write_text("#")
    p = cls(params={"cli_path": str(fake_bin), "price_per_credit_eur": 59 / 1200, **params})
    p._runner = cli
    p._transport = httpx.MockTransport(lambda r: httpx.Response(200, content=content))
    return p


# ------------------------------------------------------------------ lectura de la salida
def test_output_parsing_is_tolerant_with_undocumented_formats():
    assert hf.find_credits({"credits": {"available": 812, "used": 388, "limit": 1200}}) == 812
    assert hf.find_credits({"balance": "40.5"}) == 40.5 and hf.find_credits({"credits": 7}) == 7
    assert hf.find_credits({"plan": "plus"}) is None
    assert hf.credits_from_text("Plan: Plus\nCredits: 1,150\n") == 1150
    assert hf.credits_from_text("You have 37.5 credits left") == 37.5
    assert hf.parse_json('aviso: nueva versión\n{"a": 1}') == {"a": 1}
    urls = hf.media_urls([{"thumb": "https://x/t.webp", "video": "https://x/v.mp4?sig=1", "http": "http://inseguro"}], "video")
    assert urls[0] == "https://x/v.mp4?sig=1" and "http://inseguro" not in urls
    assert hf.failure_reason([{"status": "nsfw"}]) == "nsfw" and hf.failure_reason({"status": "completed"}) is None
    assert hf.pick_duration("kling3_0_turbo", 4.2) == 5 and hf.pick_duration("kling3_0_turbo", 7) == 10
    assert hf.pick_duration("kling3_0_turbo", 30) == 10 and hf.pick_duration("seedance_2_5", 2) == 4
    assert hf.to_flags({"aspect_ratio": "9:16", "x": None, "audio": False}) == ["--aspect_ratio", "9:16", "--audio", "false"]


def test_cli_lookup_never_picks_the_hugging_face_hf(tmp_path):
    assert hf.find_cli(root=tmp_path, which=lambda n: "/usr/bin/hf" if n == "hf" else None) is None
    assert hf.find_cli(root=tmp_path, which=lambda n: "/usr/local/bin/higgsfield" if n == "higgsfield" else None) \
        == "/usr/local/bin/higgsfield"
    (tmp_path / "tools" / "higgsfield").mkdir(parents=True)
    (tmp_path / "tools" / "higgsfield" / hf.bin_name()).write_text("#")
    assert hf.find_cli(root=tmp_path, which=lambda n: None).endswith(hf.bin_name())


# ------------------------------------------------------------------ adaptador de vídeo
def test_video_clip_uses_plan_credits_and_records_real_cost(tmp_path, mp4_bytes):
    cli = FakeCLI(credits=1200, cost=25)
    p = make(HiggsfieldVideoProvider, cli, mp4_bytes, tmp_path)
    assert p.health_check().ok and p.verify_connection().message == "Sesión iniciada · 1200 créditos"
    est = p.estimate_cost("generate", VideoRequest(prompt="x", duration_s=4.5, out_dir=tmp_path))
    assert est.units == 25 and est.amount_eur == pytest.approx(25 * 59 / 1200, abs=1e-4)
    a = p.generate(VideoRequest(prompt="Batman sobre un tejado", duration_s=4.5, out_dir=tmp_path / "out",
                                image_path=tmp_path / "ref.png"))
    create = next(c for c in cli.calls if c[:2] == ["generate", "create"])
    assert create[2] == "kling3_0_turbo" and "--wait" in create and "--json" in create
    flags = dict(zip(create[5::2], create[6::2]))
    assert flags["--aspect_ratio"] == "9:16" and flags["--duration"] == "5" and flags["--resolution"] == "720p"
    assert flags["--start-image"].endswith("ref.png")
    assert a.kind.value == "video" and Path(a.path).exists() and (a.width, a.height) == (360, 640)
    assert a.metadata["credits"] == 25 and a.cost_eur == pytest.approx(25 * 59 / 1200, abs=1e-4)
    assert a.license.commercial_use is None  # no se afirma lo que no consta
    statuses = [c for c in cli.calls if c[:2] == ["account", "status"]]
    assert len(statuses) >= 2  # saldo antes y después: coste real


def test_balance_guard_refuses_before_spending(tmp_path, mp4_bytes):
    cli = FakeCLI(credits=70, cost=25)
    p = make(HiggsfieldVideoProvider, cli, mp4_bytes, tmp_path, reserve_credits=60)
    with pytest.raises(ProviderError) as e:
        p.generate(VideoRequest(prompt="x", duration_s=5, out_dir=tmp_path))
    assert "casi agotados" in str(e.value) and not e.value.transient
    assert not any(c[:2] == ["generate", "create"] for c in cli.calls)


def test_expired_session_and_unknown_balance_fail_closed(tmp_path, mp4_bytes):
    p = make(HiggsfieldVideoProvider, FakeCLI(logged=False), mp4_bytes, tmp_path)
    with pytest.raises(ProviderError) as e:
        p.generate(VideoRequest(prompt="x", duration_s=5, out_dir=tmp_path))
    assert "Iniciar sesión" in str(e.value)
    assert not p.verify_connection().ok

    class NoBalance(FakeCLI):
        def __call__(self, argv, **kw):
            if argv[1:3] == ["account", "status"]:
                self.calls.append(argv[1:])
                return subprocess.CompletedProcess(argv, 0, '{"user": {"name": "x"}}', "")
            return super().__call__(argv, **kw)
    blind = NoBalance()
    p2 = make(HiggsfieldVideoProvider, blind, mp4_bytes, tmp_path)
    with pytest.raises(ProviderError) as e2:
        p2.generate(VideoRequest(prompt="x", duration_s=5, out_dir=tmp_path))
    assert "a ciegas" in str(e2.value) and not any(c[:2] == ["generate", "create"] for c in blind.calls)


def test_generation_errors_are_classified(tmp_path, mp4_bytes):
    p = make(HiggsfieldVideoProvider, FakeCLI(fail="Error: insufficient credits for this job"), mp4_bytes, tmp_path)
    with pytest.raises(ProviderError) as e:
        p.generate(VideoRequest(prompt="x", duration_s=5, out_dir=tmp_path))
    assert "no quedan créditos" in str(e.value)
    no_price = HiggsfieldVideoProvider(params={"cli_path": str(tmp_path / "hf")})
    assert "price_per_credit_eur" in no_price.health_check().message


def test_text_status_output_is_understood(tmp_path, mp4_bytes):
    p = make(HiggsfieldVideoProvider, FakeCLI(status_json=False), mp4_bytes, tmp_path)
    st = p.cli().status()
    assert st["logged_in"] and st["credits"] == 1150


# ------------------------------------------------------------------ adaptador de imagen
def test_image_generation_through_cli(tmp_path):
    cli = FakeCLI(cost=2, kind="image")
    p = make(HiggsfieldImageProvider, cli, png_bytes(), tmp_path)
    a = p.generate(ImageRequest(prompt="Bluey en el jardín", style_tags=["dibujo"], out_dir=tmp_path / "img"))
    create = next(c for c in cli.calls if c[:2] == ["generate", "create"])
    assert create[2] == "nano_banana_flash" and "--aspect_ratio" in create and "Estilo: dibujo" in create[4]
    assert a.kind.value == "image" and (a.width, a.height) == (576, 1024) and a.metadata["credits"] == 2
    assert Path(a.path).suffix == ".png" and a.perceptual_hash


# ------------------------------------------------------------------ registro y autorización
def test_never_registered_automatically_and_needs_spend_authorization(tmp_path, mp4_bytes, monkeypatch):
    from cryptography.fernet import Fernet
    from ytauto.db.schema import make_engine
    from ytauto.providers.registry import (
        BudgetManager,
        CredentialVault,
        ProviderRegistry,
        RegistryGateway,
    )
    engine = make_engine(tmp_path / "h.db")
    reg = ProviderRegistry(engine, CredentialVault(engine, Fernet.generate_key()))
    reg.seed_defaults()
    assert not {"higgsfield_video", "higgsfield_image"} & {p.adapter for p in reg.list()}
    cli = FakeCLI(cost=25)
    probe = make(HiggsfieldVideoProvider, cli, mp4_bytes, tmp_path)
    monkeypatch.setattr(HiggsfieldVideoProvider, "_runner", staticmethod(cli))
    monkeypatch.setattr(HiggsfieldVideoProvider, "_transport", probe._transport)
    reg.add("higgsfield_video", params={"cli_path": probe.params["cli_path"], "price_per_credit_eur": 0.05})
    state = {"ok": False}
    gw = RegistryGateway(reg, BudgetManager(engine, project_budget=lambda pid: 20.0),
                         is_spend_authorized=lambda pid, prov: state["ok"])
    req = VideoRequest(prompt="x", duration_s=5, out_dir=tmp_path / "o")
    with pytest.raises((SpendNotAuthorized, ProviderError)) as e:
        gw.invoke(C.VIDEO, "generate", req, project_id="p1")
    assert "sin autorización" in str(e.value)
    assert not any(c[:2] == ["generate", "create"] for c in cli.calls)  # sin autorización no se gasta ni un crédito
    state["ok"] = True
    asset = gw.invoke(C.VIDEO, "generate", req, project_id="p1")
    assert asset.cost_eur == pytest.approx(25 * 0.05)


# ------------------------------------------------------------------ instalación verificada e inicio de sesión
def _tgz(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            t.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def _registry_server(release: bytes, checksum: str | None = None):
    archive = hf.platform_archive("1.2.2", "linux", "x86_64")
    manifest = {"version": "1.2.2", "archives": {archive: checksum or hashlib.sha256(release).hexdigest()}}
    npm_tgz = _tgz({"package/checksums.json": json.dumps(manifest).encode()})
    seen = []

    def handler(r: httpx.Request):
        seen.append(str(r.url))
        if str(r.url) == hf.NPM_LATEST:
            return httpx.Response(200, json={"version": "1.2.2", "dist": {
                "tarball": "https://registry.npmjs.org/@higgsfield/cli/-/cli-1.2.2.tgz"}})
        if r.url.host == "registry.npmjs.org":
            return httpx.Response(200, content=npm_tgz)
        if r.url.path.endswith(archive):
            return httpx.Response(200, content=release)
        return httpx.Response(404)
    return httpx.MockTransport(handler), seen


def test_install_verifies_the_official_checksum(tmp_path):
    release = _tgz({"hf": b"#!binario", "README.md": b"x"})
    t, seen = _registry_server(release)
    res = hf.install_cli(tmp_path / "tools", transport=t, sys_platform="linux", machine="x86_64")
    target = Path(res["path"])
    assert target.read_bytes() == b"#!binario" and res["version"] == "1.2.2" and target.stat().st_mode & 0o111
    assert any("github.com/higgsfield-ai/cli/releases/download/v1.2.2/hf_1.2.2_linux_amd64.tar.gz" in u for u in seen)
    bad, _ = _registry_server(release, checksum="0" * 64)
    with pytest.raises(ProviderError) as e:
        hf.install_cli(tmp_path / "otra", transport=bad, sys_platform="linux", machine="x86_64")
    assert "suma oficial" in str(e.value) and not (tmp_path / "otra" / "hf").exists()
    assert hf.platform_archive("1.2.2", "win32", "AMD64") == "hf_1.2.2_windows_amd64.tar.gz"
    assert hf.platform_archive("1.2.2", "darwin", "arm64") == "hf_1.2.2_darwin_arm64.tar.gz"


def test_login_opens_a_visible_window_per_system():
    argv, kw = hf.login_launch(r"C:\YTAUTO\tools\higgsfield\hf.exe", "win32")
    assert argv[1:] == ["auth", "login"] and kw["creationflags"] == 0x10
    mac, _ = hf.login_launch("/Users/a b/YTAUTO/tools/higgsfield/hf", "darwin")
    assert mac[0] == "osascript" and "auth login" in mac[2] and "'/Users/a b/" in mac[2]
    lin, _ = hf.login_launch("/opt/hf", "linux", which=lambda n: "/usr/bin/xterm" if n == "xterm" else None)
    assert lin == ["xterm", "-e", "/opt/hf", "auth", "login"]
    assert hf.login_launch("/opt/hf", "linux", which=lambda n: None) is None
