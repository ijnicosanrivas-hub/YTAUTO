"""Fase 9: adaptadores de servicios externos probados contra servidores HTTP SIMULADOS (sin red ni costes).

Los servidores simulados imitan los flujos documentados por YouTube, Meta, TikTok, ElevenLabs y OpenAI. No
prueban cuentas reales: eso solo puede hacerse con credenciales propias (ver docs/integrations.md).
"""
from __future__ import annotations

import base64
import json
import subprocess
import urllib.parse
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from PIL import Image

from ytauto.core.errors import PhaseBlocked, ProviderError, SpendNotAuthorized
from ytauto.providers.contract import run_contract
from ytauto.providers.http import scrub
from ytauto.providers.image.openai_images import OpenAIImageProvider
from ytauto.providers.interfaces import ImageRequest, ProviderCategory as C, PublishRequest, TTSRequest
from ytauto.providers.publishing.instagram import InstagramPublishingProvider
from ytauto.providers.publishing.tiktok import MB, TikTokPublishingProvider, plan_chunks
from ytauto.providers.publishing.youtube import YouTubePublishingProvider
from ytauto.providers.voice.elevenlabs import ElevenLabsTTSProvider

SECRET = "SECRET-TOKEN-ABC123XYZ"


def transport(handler):
    return httpx.MockTransport(handler)


def attach(cls_or_inst, handler):
    cls_or_inst._transport = transport(handler)
    return cls_or_inst


def video(tmp_path: Path, size: int = 2_000) -> Path:
    p = tmp_path / "v.mp4"
    p.write_bytes(b"\x00" * size)
    return p


def req(tmp_path, platform="youtube_shorts", privacy="private", **kw) -> PublishRequest:
    path = kw.pop("video_path", None) or video(tmp_path)
    return PublishRequest(platform=platform, video_path=path, title="Un título",
                          description="Una descripción #uno", hashtags=["#uno", "#dos"], privacy=privacy,
                          authorization_id="apr_1", **kw)


# ======================================================================== YouTube
class YT:
    """Servidor simulado de YouTube Data API v3 + token endpoint de Google."""

    def __init__(self, privacy_returned="private", init_status=200, put_status=200):
        self.calls: list[httpx.Request] = []
        self.uploaded = 0
        self.privacy_returned, self.init_status, self.put_status = privacy_returned, init_status, put_status

    def __call__(self, r: httpx.Request) -> httpx.Response:
        self.calls.append(r)
        if r.url.host == "oauth2.googleapis.com":
            form = urllib.parse.parse_qs(r.content.decode())
            assert form["grant_type"] == ["refresh_token"] and form["refresh_token"] == [SECRET]
            return httpx.Response(200, json={"access_token": "AT-1", "expires_in": 3599})
        if r.method == "POST" and r.url.path == "/upload/youtube/v3/videos":
            if self.init_status != 200:
                return httpx.Response(self.init_status, text="boom")
            return httpx.Response(200, headers={"Location": "https://upload.youtube.test/session/abc"})
        if r.method == "PUT" and r.url.host == "upload.youtube.test":
            self.uploaded = len(r.read())
            if self.put_status != 200:
                return httpx.Response(self.put_status, text="fallo")
            return httpx.Response(200, json={"id": "VID123", "status": {"privacyStatus": self.privacy_returned}})
        return httpx.Response(404)


def yt(server, **params) -> YouTubePublishingProvider:
    p = YouTubePublishingProvider(params=params, credentials={"client_id": "cid", "client_secret": "cs",
                                                              "refresh_token": SECRET})
    p._transport = transport(server)
    return p


def test_youtube_resumable_upload_follows_documented_protocol(tmp_path):
    server = YT()
    r = yt(server).publish(req(tmp_path, video_path=video(tmp_path, 3_500_000)))
    token, init, put = server.calls
    assert token.url.host == "oauth2.googleapis.com"
    q = dict(init.url.params)
    assert q["uploadType"] == "resumable" and q["part"] == "snippet,status"
    assert init.headers["authorization"] == "Bearer AT-1"
    assert init.headers["x-upload-content-length"] == "3500000" and init.headers["x-upload-content-type"] == "video/mp4"
    body = json.loads(init.content)
    assert body["snippet"]["title"] == "Un título" and body["snippet"]["tags"] == ["uno", "dos"]
    assert body["status"]["privacyStatus"] == "private"  # nunca público por defecto
    assert server.uploaded == 3_500_000 and put.headers["content-length"] == "3500000"
    assert r.external_id == "VID123" and r.url == "https://www.youtube.com/shorts/VID123"
    assert r.status == "uploaded_private"


def test_youtube_reports_when_unverified_project_forces_private(tmp_path):
    r = yt(YT(privacy_returned="private")).publish(req(tmp_path, privacy="public"))
    assert r.status == "uploaded_private" and "sin verificar" in r.message
    assert yt(YT(privacy_returned="public")).publish(req(tmp_path, privacy="public")).status == "published"


def test_youtube_errors_are_classified_and_never_leak_secrets(tmp_path):
    def deny(r):
        return httpx.Response(401, text=f'{{"error":"invalid_grant","refresh_token":"{SECRET}"}}')

    with pytest.raises(ProviderError) as e:
        yt(deny).publish(req(tmp_path))
    assert SECRET not in str(e.value) and not e.value.transient and "autenticación" in str(e.value)
    with pytest.raises(ProviderError) as e:
        yt(YT(init_status=503)).publish(req(tmp_path))
    assert e.value.transient  # antes de subir nada: se puede reintentar
    with pytest.raises(ProviderError) as e:
        yt(YT(put_status=500)).publish(req(tmp_path))
    assert not e.value.transient and "YouTube Studio" in str(e.value)  # tras subir: nunca reintento ciego


def test_youtube_requirements_and_connection(tmp_path):
    p = yt(YT())
    bad = PublishRequest(platform="youtube_shorts", video_path=tmp_path / "no.mp4", title="x" * 101, description="d",
                         authorization_id="")
    issues = p.check_requirements(bad)
    assert any("autorización" in i for i in issues) and any("100" in i for i in issues) and any("No existe" in i for i in issues)
    assert p.verify_connection().ok
    assert not YouTubePublishingProvider().verify_connection().ok  # sin credenciales


# ======================================================================== Instagram
class IG:
    def __init__(self, statuses=("IN_PROGRESS", "IN_PROGRESS", "FINISHED"), publish_status=200):
        self.statuses, self.calls, self.publish_status = list(statuses), [], publish_status

    def __call__(self, r: httpx.Request) -> httpx.Response:
        self.calls.append(r)
        path = r.url.path
        if r.method == "POST" and path.endswith("/17841/media"):
            return httpx.Response(200, json={"id": "CONT1"})
        if r.method == "GET" and path.endswith("/CONT1"):
            code = self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
            return httpx.Response(200, json={"status_code": code, "status": "detalle"})
        if r.method == "POST" and path.endswith("/17841/media_publish"):
            return httpx.Response(self.publish_status, json={"id": "MEDIA9"})
        if r.method == "GET" and path.endswith("/MEDIA9"):
            return httpx.Response(200, json={"permalink": "https://www.instagram.com/reel/XYZ/"})
        if r.method == "GET" and path.endswith("/17841"):
            return httpx.Response(200, json={"id": "17841", "username": "mi_cuenta"})
        return httpx.Response(404)


def ig(server, **params) -> InstagramPublishingProvider:
    p = InstagramPublishingProvider(params={"poll_interval_s": 0, **params},
                                    credentials={"access_token": SECRET, "ig_user_id": "17841"})
    p._transport = transport(server)
    return p


def ig_req(tmp_path, **kw):
    return req(tmp_path, platform="instagram_reels", privacy="public", video_url="https://cdn.example.com/v.mp4", **kw)


def test_instagram_container_poll_and_publish_flow(tmp_path):
    server = IG()
    r = ig(server).publish(ig_req(tmp_path))
    create = server.calls[0]
    form = urllib.parse.parse_qs(create.content.decode())
    assert form["media_type"] == ["REELS"] and form["video_url"] == ["https://cdn.example.com/v.mp4"]
    assert form["caption"] == ["Una descripción #uno"]
    statuses = [c for c in server.calls if c.method == "GET" and c.url.path.endswith("/CONT1")]
    assert len(statuses) == 3  # esperó a FINISHED consultando el estado
    publish = next(c for c in server.calls if c.url.path.endswith("media_publish"))
    assert urllib.parse.parse_qs(publish.content.decode())["creation_id"] == ["CONT1"]
    assert "/v25.0/" in create.url.path  # versión configurable
    assert r.status == "published" and r.external_id == "MEDIA9" and r.url.endswith("/reel/XYZ/")


def test_instagram_container_error_and_timeout(tmp_path):
    with pytest.raises(ProviderError) as e:
        ig(IG(statuses=("ERROR",))).publish(ig_req(tmp_path))
    assert not e.value.transient and "ERROR" in str(e.value)
    with pytest.raises(ProviderError) as e:
        ig(IG(statuses=("IN_PROGRESS",)), max_wait_s=0.05, poll_interval_s=0.01).publish(ig_req(tmp_path))
    assert e.value.transient and "procesando" in str(e.value)


def test_instagram_failure_after_publish_call_is_not_retried_blindly(tmp_path):
    with pytest.raises(ProviderError) as e:
        ig(IG(publish_status=500)).publish(ig_req(tmp_path))
    assert not e.value.transient and "comprueba Instagram" in str(e.value)


def test_instagram_requires_public_url_and_explicit_public_authorization(tmp_path):
    p = ig(IG())
    private = req(tmp_path, platform="instagram_reels", privacy="private", video_url="https://x/v.mp4")
    assert any("privada" in i for i in p.check_requirements(private))
    no_url = req(tmp_path, platform="instagram_reels", privacy="public")
    assert any("URL pública" in i for i in p.check_requirements(no_url))
    http_url = req(tmp_path, platform="instagram_reels", privacy="public", video_url="http://x/v.mp4")
    assert any("https" in i for i in p.check_requirements(http_url))
    assert p.check_requirements(ig_req(tmp_path)) == []
    with pytest.raises(ProviderError):
        p.publish(no_url)  # y publish nunca salta los requisitos
    assert p.verify_connection().message == "Cuenta @mi_cuenta"


# ======================================================================== TikTok
class TT:
    def __init__(self, options=("SELF_ONLY",), statuses=("PROCESSING_UPLOAD", "PUBLISH_COMPLETE"), fail_reason=None):
        self.options, self.statuses, self.fail_reason = list(options), list(statuses), fail_reason
        self.calls, self.chunks, self.init_body = [], [], None

    def __call__(self, r: httpx.Request) -> httpx.Response:
        self.calls.append(r)
        path = r.url.path
        if path == "/v2/post/publish/creator_info/query/":
            return httpx.Response(200, json={"data": {"creator_username": "yo", "privacy_level_options": self.options,
                                                      "max_video_post_duration_sec": 300}, "error": {"code": "ok"}})
        if path == "/v2/post/publish/video/init/":
            self.init_body = json.loads(r.content)
            return httpx.Response(200, json={"data": {"publish_id": "PUB1", "upload_url": "https://upload.tiktok.test/u"}})
        if r.url.host == "upload.tiktok.test":
            self.chunks.append((r.headers["content-range"], len(r.read())))
            return httpx.Response(206)
        if path == "/v2/post/publish/status/fetch/":
            code = self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
            data = {"status": code}
            if code == "FAILED":
                data["fail_reason"] = self.fail_reason or "file_format_check_failed"
            return httpx.Response(200, json={"data": data})
        return httpx.Response(404)


def tt(server, **params) -> TikTokPublishingProvider:
    p = TikTokPublishingProvider(params={"poll_interval_s": 0, **params}, credentials={"access_token": SECRET})
    p._transport = transport(server)
    return p


@pytest.mark.parametrize("size,chunk,expected", [
    (3 * MB, 10 * MB, (3 * MB, 1, 3 * MB)),  # < 5 MB: un solo trozo
    (12 * MB, 10 * MB, (10 * MB, 1, 12 * MB)),  # total = 12 // 10 = 1; el último trozo absorbe el resto
    (25 * MB, 10 * MB, (10 * MB, 2, 15 * MB)),
    (70 * MB, 64 * MB, (64 * MB, 1, 70 * MB)),
    (50 * MB, 1 * MB, (5 * MB, 10, 5 * MB)),  # el trozo mínimo es 5 MB
])
def test_chunk_planning_follows_documented_rules(size, chunk, expected):
    assert plan_chunks(size, chunk) == expected
    c, total, last = plan_chunks(size, chunk)
    assert total == max(1, size // c) and (total - 1) * c + last == size and 1 <= total <= 1000


def test_chunk_planning_rejects_impossible_videos():
    with pytest.raises(ValueError):
        plan_chunks(0, 10 * MB)
    with pytest.raises(ValueError):
        plan_chunks(1000 * 64 * MB + 200 * MB, 64 * MB)


def test_tiktok_direct_post_flow_private(tmp_path):
    server = TT()
    big = video(tmp_path, 25 * MB)
    r = tt(server).publish(req(tmp_path, platform="tiktok", video_path=big))
    body = server.init_body
    assert body["post_info"]["privacy_level"] == "SELF_ONLY" and body["post_info"]["title"].startswith("Una descripción")
    assert body["source_info"] == {"source": "FILE_UPLOAD", "video_size": 25 * MB, "chunk_size": 10 * MB,
                                   "total_chunk_count": 2}
    # Trozos en orden, cubriendo el fichero entero
    assert server.chunks == [(f"bytes 0-{10 * MB - 1}/{25 * MB}", 10 * MB), (f"bytes {10 * MB}-{25 * MB - 1}/{25 * MB}", 15 * MB)]
    assert [c.url.path for c in server.calls][:2] == ["/v2/post/publish/creator_info/query/", "/v2/post/publish/video/init/"]
    assert r.status == "uploaded_private" and r.external_id == "PUB1"
    assert all(c.headers.get("authorization") == f"Bearer {SECRET}" for c in server.calls if c.url.host == "open.tiktokapis.com")


def test_tiktok_refuses_visibility_not_offered_to_the_creator(tmp_path):
    server = TT(options=("SELF_ONLY",))  # app sin auditar
    with pytest.raises(ProviderError) as e:
        tt(server).publish(req(tmp_path, platform="tiktok", privacy="public"))
    assert "auditada" in str(e.value) and not e.value.transient
    assert server.init_body is None  # ni siquiera se inició la publicación
    ok = TT(options=("PUBLIC_TO_EVERYONE", "SELF_ONLY"))
    assert tt(ok).publish(req(tmp_path, platform="tiktok", privacy="public")).status == "published"
    assert ok.init_body["post_info"]["privacy_level"] == "PUBLIC_TO_EVERYONE"


def test_tiktok_failed_processing_and_connection(tmp_path):
    with pytest.raises(ProviderError) as e:
        tt(TT(statuses=("PROCESSING_UPLOAD", "FAILED"), fail_reason="duration_check_failed")).publish(
            req(tmp_path, platform="tiktok"))
    assert "duration_check_failed" in str(e.value) and not e.value.transient
    assert "SELF_ONLY" in tt(TT()).verify_connection().message


# ======================================================================== ElevenLabs
@pytest.fixture(scope="module")
def mp3_bytes(tmp_path_factory):
    out = tmp_path_factory.mktemp("mp3") / "t.mp3"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=f=300:d=2", str(out)], check=True)
    return out.read_bytes()


def eleven(mp3: bytes, status=200, **params):
    seen = {"requests": []}

    def handler(r: httpx.Request) -> httpx.Response:
        seen["requests"].append(r)
        if r.url.path == "/v1/voices":
            return httpx.Response(200, json={"voices": [{"voice_id": "V1", "name": "Rachel", "labels": {"gender": "female"}}]})
        if r.url.path.startswith("/v1/text-to-speech/"):
            return httpx.Response(status, content=mp3, headers={"retry-after": "30"} if status == 429 else {})
        return httpx.Response(404)

    p = ElevenLabsTTSProvider(params=params, credentials={"api_key": SECRET})
    p._transport = transport(handler)
    return p, seen


def test_paid_providers_refuse_to_work_without_a_configured_price(mp3_bytes):
    p, _ = eleven(mp3_bytes)
    h = p.health_check()
    assert not h.ok and "price_per_1k_chars_eur" in h.message
    o = OpenAIImageProvider(credentials={"api_key": SECRET})
    assert not o.health_check().ok and "price_per_image_eur" in o.health_check().message
    assert eleven(mp3_bytes, price_per_1k_chars_eur=0.3)[0].health_check().ok  # con precio, sí está disponible


def test_elevenlabs_request_cost_and_wav_output(tmp_path, mp3_bytes):
    p, seen = eleven(mp3_bytes, price_per_1k_chars_eur=0.30)
    text = "Hola, esto es una prueba de voz con cincuenta caracteres."
    est = p.estimate_cost("synthesize", TTSRequest(text=text, out_path=tmp_path / "a.wav"))
    assert est.amount_eur == pytest.approx(len(text) / 1000 * 0.30) and est.units == len(text)
    a = p.synthesize(TTSRequest(text=text, voice_id="V1", out_path=tmp_path / "a.wav"))
    r = seen["requests"][-1]
    assert r.url.path == "/v1/text-to-speech/V1" and r.headers["xi-api-key"] == SECRET
    assert dict(r.url.params)["output_format"] == "mp3_44100_128"
    assert json.loads(r.content) == {"text": text, "model_id": "eleven_multilingual_v2"}
    assert a.cost_eur == pytest.approx(est.amount_eur) and 1.8 < a.duration_s < 2.3 and a.kind.value == "audio_voice"
    assert p.list_voices("es")[0].id == "V1" and p.verify_connection().message == "1 voces disponibles"


def test_elevenlabs_rate_limit_is_transient_with_retry_after(tmp_path, mp3_bytes):
    p, _ = eleven(mp3_bytes, status=429, price_per_1k_chars_eur=0.3)
    with pytest.raises(ProviderError) as e:
        p.synthesize(TTSRequest(text="hola", voice_id="V1", out_path=tmp_path / "a.wav"))
    assert e.value.transient and e.value.retry_after_s == 30
    with pytest.raises(ProviderError):  # sin voz seleccionada
        eleven(mp3_bytes, price_per_1k_chars_eur=0.3)[0].synthesize(TTSRequest(text="hola", out_path=tmp_path / "b.wav"))


def test_elevenlabs_satisfies_the_tts_contract_offline(tmp_path, mp3_bytes):
    p, _ = eleven(mp3_bytes, price_per_1k_chars_eur=0.3)
    report = run_contract(p, workdir=tmp_path, allow_paid=True)
    assert report.passed, [c for c in report.checks if not c.passed]


# ======================================================================== OpenAI Images
def png_b64(w=1024, h=1536) -> str:
    buf = BytesIO()
    Image.new("RGB", (w, h), (20, 90, 160)).save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


def openai(**params):
    seen = {"requests": []}

    def handler(r: httpx.Request) -> httpx.Response:
        seen["requests"].append(r)
        if r.url.path == "/v1/images/generations":
            return httpx.Response(200, json={"data": [{"b64_json": png_b64()}]})
        if r.url.path == "/v1/models":
            return httpx.Response(200, json={"data": []})
        return httpx.Response(404)

    p = OpenAIImageProvider(params=params, credentials={"api_key": SECRET})
    p._transport = transport(handler)
    return p, seen


def test_openai_images_request_and_asset(tmp_path):
    p, seen = openai(price_per_image_eur=0.05)
    a = p.generate(ImageRequest(prompt="un faro de noche", style_tags=["cinemático"], negative_prompt="texto",
                                out_dir=tmp_path))
    r = seen["requests"][-1]
    body = json.loads(r.content)
    assert r.headers["authorization"] == f"Bearer {SECRET}" and body["model"] == "gpt-image-1"
    assert body["size"] == "1024x1536" and body["n"] == 1 and "Estilo: cinemático" in body["prompt"] and "Evitar: texto" in body["prompt"]
    assert (a.width, a.height) == (1024, 1536) and a.cost_eur == 0.05 and Path(a.path).exists()
    assert a.license.name == "provider-terms" and a.license.commercial_use is None  # no se afirma lo que no consta
    assert p.verify_connection().ok


def test_openai_images_satisfies_the_image_contract_offline(tmp_path):
    p, _ = openai(price_per_image_eur=0.05)
    report = run_contract(p, workdir=tmp_path, allow_paid=True)
    assert report.passed, [c for c in report.checks if not c.passed]


def test_scrub_hides_secrets():
    assert SECRET not in scrub(f'access_token="{SECRET}" y {SECRET}', [SECRET])
    assert "xyz789" not in scrub("Authorization: Bearer xyz789abc")
    assert "tok12345" not in scrub("curl -H 'Bearer tok12345' https://x")
    assert "def456" not in scrub('{"client_secret": "def456ghi"}')


# ======================================================================== a través del registro, presupuesto y orquestador
@pytest.fixture
def system(tmp_path):
    from cryptography.fernet import Fernet
    from ytauto.db.schema import make_engine
    from ytauto.providers.registry import BudgetManager, CredentialVault, ProviderRegistry, RegistryGateway
    engine = make_engine(tmp_path / "i.db")
    reg = ProviderRegistry(engine, CredentialVault(engine, Fernet.generate_key()), include_mocks=True)
    state = {"authorized": False}
    budget = BudgetManager(engine, project_budget=lambda pid: 1.0)
    gw = RegistryGateway(reg, budget, is_spend_authorized=lambda pid, prov: state["authorized"])
    return reg, budget, gw, state


def test_paid_adapter_through_registry_needs_authorization_then_records_cost(system, tmp_path, mp3_bytes, monkeypatch):
    reg, budget, gw, state = system
    p, _ = eleven(mp3_bytes)
    monkeypatch.setattr(ElevenLabsTTSProvider, "_transport", p._transport)
    reg.add("elevenlabs", params={"price_per_1k_chars_eur": 0.5}, credentials={"api_key": SECRET})
    request_ = TTSRequest(text="x" * 1000, voice_id="V1", out_path=tmp_path / "a.wav")
    with pytest.raises(SpendNotAuthorized):
        gw.invoke(C.TTS, "synthesize", request_, project_id="p1")
    assert budget.ledger("p1") == []  # sin autorización: ni una llamada ni un céntimo
    state["authorized"] = True
    asset = gw.invoke(C.TTS, "synthesize", request_, project_id="p1")
    assert asset.cost_eur == pytest.approx(0.5)
    assert budget.spent_project("p1") == pytest.approx(0.5)


def test_paid_adapter_without_price_is_never_used_even_if_authorized(system, tmp_path, mp3_bytes, monkeypatch):
    reg, budget, gw, state = system
    monkeypatch.setattr(ElevenLabsTTSProvider, "_transport", eleven(mp3_bytes)[0]._transport)
    reg.add("elevenlabs", credentials={"api_key": SECRET})  # sin precio
    state["authorized"] = True
    with pytest.raises(ProviderError):
        gw.invoke(C.TTS, "synthesize", TTSRequest(text="hola", voice_id="V1", out_path=tmp_path / "a.wav"), project_id="p1")
    assert budget.ledger("p1") == []


def test_registry_test_connection_for_network_adapters_is_read_only(system, monkeypatch):
    reg, *_ = system
    server = YT()
    monkeypatch.setattr(YouTubePublishingProvider, "_transport", transport(server))
    reg.add("youtube_data_api", credentials={"client_id": "c", "client_secret": "s", "refresh_token": SECRET})
    report = reg.test("youtube_data_api")
    assert report.passed and [c.name for c in report.checks] == ["conexión"]
    assert [c.url.host for c in server.calls] == ["oauth2.googleapis.com"]  # solo pidió un token: nada subido


def test_network_adapters_are_never_registered_automatically(system):
    reg, *_ = system
    added = reg.seed_defaults()
    assert not {"elevenlabs", "openai_images", "youtube_data_api", "instagram_graph_api",
                "tiktok_content_posting_api"} & set(added)


# ======================================================================== fase de publicación (agente + orquestador)
from test_platforms import PIPE, _run  # noqa: E402

from ytauto.core.models import ProjectStatus  # noqa: E402
from ytauto.providers.gateway import DirectGateway  # noqa: E402
from ytauto.providers.interfaces import PublishingProvider, PublishResult  # noqa: E402
from ytauto.agents.publisher import PublisherAgent  # noqa: E402


class StubPublisher(PublishingProvider):
    """Publicador simulado que registra lo que recibe y puede fallar en plataformas concretas."""
    name = "stub_publisher"
    platforms = ["youtube_shorts", "instagram_reels", "tiktok"]

    def __init__(self, params=None, credentials=None):
        super().__init__(params, credentials)
        self.published: list[PublishRequest] = []
        self.fail: set[str] = set()

    def check_requirements(self, request):
        return [] if request.authorization_id else ["Falta autorización"]

    def publish(self, request):
        if request.platform in self.fail:
            raise ProviderError(self.name, f"fallo simulado en {request.platform}", transient=False)
        self.published.append(request)
        return PublishResult(platform=request.platform, status="uploaded_private", external_id=f"id-{len(self.published)}")


def publisher_ctx(make_ctx, mock_providers, stub, settings):
    providers = {**mock_providers, C.PUBLISHING: stub}
    ctx = make_ctx(providers=DirectGateway(providers), settings=settings)
    _run(ctx, *PIPE, "exports", "publish_prep")
    return ctx


def test_publish_uses_the_authorized_visibility_never_a_wider_one(make_ctx, mock_providers):
    stub = StubPublisher()
    ctx = publisher_ctx(make_ctx, mock_providers, stub, {
        "publish_authorizations": {"youtube_shorts": "a1", "tiktok": "a2"},
        "publish_privacy_by_platform": {"youtube_shorts": "public"}})
    PublisherAgent().run("publish", ctx)
    by = {r.platform: r.privacy for r in stub.published}
    assert by == {"youtube_shorts": "public", "tiktok": "private"}  # sin sufijo = privado


def test_visibility_not_supported_by_the_platform_falls_back_to_manual_package(make_ctx, mock_providers):
    stub = StubPublisher()
    ctx = publisher_ctx(make_ctx, mock_providers, stub, {"publish_authorizations": {"instagram_reels": "a1", "tiktok": "a2"},
                                                         "publish_privacy_by_platform": {"tiktok": "public"}})
    r = PublisherAgent().run("publish", ctx)
    assert stub.published == []  # IG solo admite público y TikTok sin auditar solo privado: no se publicó nada
    for platform in ("instagram_reels", "tiktok"):
        res = r.metrics["results"][platform]
        assert res["status"] == "manual_package" and "no admite" in res["message"] and Path(res["package_path"]).exists()


def test_failed_publication_blocks_with_reason_and_retry_does_not_duplicate(make_ctx, mock_providers):
    stub = StubPublisher()
    stub.fail = {"tiktok"}
    ctx = publisher_ctx(make_ctx, mock_providers, stub, {"publish_authorizations": {"youtube_shorts": "a1", "tiktok": "a2"}})
    with pytest.raises(PhaseBlocked) as e:
        PublisherAgent().run("publish", ctx)
    assert e.value.code == "publish_failed" and "tiktok" in e.value.reason
    saved = ctx.workspace.load("exports", "publish_results")
    assert saved["youtube_shorts"]["status"] == "uploaded_private" and saved["tiktok"]["status"] == "failed"
    stub.fail = set()  # el usuario arregla el problema y pulsa «Reintentar»
    r = PublisherAgent().run("publish", ctx)
    assert [p.platform for p in stub.published] == ["youtube_shorts", "tiktok"]  # YouTube no se repite
    assert r.metrics["results"]["youtube_shorts"]["external_id"] == "id-1"


def test_instagram_without_public_storage_url_gives_manual_package_and_sends_nothing(make_ctx, mock_providers, tmp_path):
    server = IG()
    adapter = ig(server)
    ctx = publisher_ctx(make_ctx, mock_providers, adapter, {"publish_authorizations": {"instagram_reels": "a1"},
                                                            "publish_privacy_by_platform": {"instagram_reels": "public"}})
    r = PublisherAgent().run("publish", ctx)
    res = r.metrics["results"]["instagram_reels"]
    assert res["status"] == "manual_package" and "URL pública" in res["message"]
    assert server.calls == []  # no se llamó a Meta


def test_instagram_publishes_when_storage_offers_a_public_url(make_ctx, mock_providers):
    from ytauto.providers.mock import MockStorageProvider

    class PublicStorage(MockStorageProvider):
        def public_url(self, key):
            return f"https://cdn.example.com/{key}"

    server = IG()
    providers = {**mock_providers, C.PUBLISHING: ig(server), C.STORAGE: PublicStorage()}
    ctx = make_ctx(providers=DirectGateway(providers), settings={
        "publish_authorizations": {"instagram_reels": "a1"}, "publish_privacy_by_platform": {"instagram_reels": "public"}})
    _run(ctx, *PIPE, "exports", "publish_prep")
    r = PublisherAgent().run("publish", ctx)
    assert r.metrics["results"]["instagram_reels"]["status"] == "published"
    form = urllib.parse.parse_qs(server.calls[0].content.decode())
    assert form["video_url"][0].startswith("https://cdn.example.com/") and form["video_url"][0].endswith("instagram_reels.mp4")


def test_public_url_is_never_created_for_private_authorizations(make_ctx, mock_providers, tmp_path):
    """La guarda se prueba de forma aislada: un perfil de Instagram que SÍ admitiera «privado» no debe, aun así,
    sacar el vídeo a una URL pública salvo con autorización pública explícita."""
    import shutil as _sh
    from ytauto.core.platforms import PLATFORMS_DIR
    from ytauto.providers.mock import MockStorageProvider
    pdir = tmp_path / "platforms"
    pdir.mkdir()
    for f in PLATFORMS_DIR.glob("*.yaml"):
        _sh.copy(f, pdir / f.name)
    ig_yaml = pdir / "instagram_reels.yaml"
    ig_yaml.write_text(ig_yaml.read_text().replace("privacy_options: [public]", "privacy_options: [private, public]"))
    puts = []

    class SpyStorage(MockStorageProvider):
        def put(self, local_path, key):
            puts.append(key)
            return super().put(local_path, key)

    def run(privacy):
        puts.clear()
        stub = StubPublisher()
        ctx = make_ctx(providers=DirectGateway({**mock_providers, C.PUBLISHING: stub, C.STORAGE: SpyStorage()}),
                       settings={"platforms_dir": pdir, "publish_authorizations": {"instagram_reels": "a1"},
                                 "publish_privacy_by_platform": {"instagram_reels": privacy}})
        _run(ctx, *PIPE, "exports", "publish_prep")
        (ctx.workspace.dir("exports") / "publish_results.json").unlink(missing_ok=True)  # otra publicación nueva
        PublisherAgent().run("publish", ctx)
        return list(puts), stub

    puts_private, stub = run("private")
    assert puts_private == [] and [p.platform for p in stub.published] == ["instagram_reels"]  # publicó, sin URL pública
    puts_public, _ = run("public")
    assert len(puts_public) == 1  # solo con autorización pública se sube a una URL pública


def to_publish_gate(orch, spec):
    pid = orch.create_project(spec.model_copy(update={"require_script_approval": False}))
    orch.run(pid)
    orch.approve(pid, "final_approval")
    orch.run(pid)
    return pid


def test_publish_gates_support_explicit_visibility_expiry_and_revocation(make_orchestrator, spec):
    orch = make_orchestrator()
    pid = to_publish_gate(orch, spec)
    for bad in ("publish:tiktok:secret", "publish::public", "publish:a:b:c"):
        with pytest.raises(ValueError):
            orch.approve(pid, bad)
    orch.approve(pid, "publish:tiktok")
    orch.approve(pid, "publish:youtube_shorts:public")
    assert orch._publish_grants(pid) == {"tiktok": {"id": orch._publish_grants(pid)["tiktok"]["id"], "privacy": "private"},
                                         "youtube_shorts": {"id": orch._publish_grants(pid)["youtube_shorts"]["id"],
                                                            "privacy": "public"}}
    orch.approve(pid, "publish:youtube_shorts", approved=False)  # revocar
    assert set(orch._valid_publish_auths(pid)) == {"tiktok"}
    orch.approve(pid, "publish:tiktok:public")  # la última decisión manda
    assert orch._publish_grants(pid)["tiktok"]["privacy"] == "public"


def test_real_youtube_adapter_end_to_end_through_the_orchestrator(make_orchestrator, spec, mock_providers):
    server = YT()
    youtube = yt(server)
    youtube.platforms = ["youtube_shorts"]
    orch = make_orchestrator(providers=DirectGateway({**mock_providers, C.PUBLISHING: youtube}))
    pid = to_publish_gate(orch, spec)
    orch.approve(pid, "publish:youtube_shorts")
    r = orch.run(pid)
    assert r.outcome == "completed" and orch.store.get_project(pid).status is ProjectStatus.COMPLETED
    from ytauto.core.workspace import Workspace
    results = Workspace(orch.settings.projects_dir, pid).load("exports", "publish_results")
    assert results["youtube_shorts"]["url"] == "https://www.youtube.com/shorts/VID123"
    assert json.loads(next(c for c in server.calls if c.url.path.endswith("/videos")).content)["status"]["privacyStatus"] == "private"
    assert results["tiktok"]["status"] == "skipped"  # lo no autorizado no se toca
