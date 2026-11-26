"""«Cuentas conectadas»: vincular ElevenLabs (voz) y Higgsfield (vídeo e imagen) desde la interfaz.

- ElevenLabs: clave de API (se guarda cifrada en el almacén, fuera de git) + saldo real de créditos del plan.
- Higgsfield: la CLI oficial con la sesión del usuario (créditos del plan; la API es otro producto y otro saldo).

Nada de esto autoriza gastos: cada vídeo necesita su autorización `spend:<proveedor>` (o la autorización permanente,
que el usuario activa a mano y queda registrada en los ajustes de presupuesto).
"""
from __future__ import annotations

import subprocess
import time
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from ..app import App
from ..core import audio_features as af
from ..core.channels import channels
from ..core.errors import ProviderError, ProviderNotConfigured
from ..core.workspace import Workspace
from ..providers import higgsfield as hf
from ..providers.registry import RegistryError

ELEVEN = "elevenlabs"
ELEVEN_SFX = "elevenlabs_sfx"
HF_VIDEO, HF_IMAGE = "higgsfield_video", "higgsfield_image"
PAID_ACCOUNTS = (ELEVEN, ELEVEN_SFX, HF_VIDEO, HF_IMAGE)
ELEVEN_MODELS = {"eleven_multilingual_v2": "Multilingual v2 · estable (1 crédito/carácter)",
                 "eleven_v4": "Eleven v4 · el más expresivo, con emociones (1 crédito/carácter)",
                 "eleven_flash_v2_5": "Flash v2.5 · rápido y barato (0,5 créditos/carácter)"}
# Planes que el usuario ha contratado (precios de su captura). Se pueden cambiar en la pantalla.
ELEVEN_PLANS = {"creator": {"label": "Creator", "credits": 121000, "price_eur": 20.0,
                            "note": "22 $/mes (11 $ el primer mes) ≈ 20 €"}}
_popen = subprocess.Popen


class ElevenIn(BaseModel):
    api_key: str | None = Field(default=None, min_length=10, max_length=200)
    voice_id: str | None = Field(default=None, max_length=80)
    model_id: str | None = None
    plan_price_eur: float | None = Field(default=None, ge=0, le=10000)
    plan_credits: int | None = Field(default=None, gt=0)
    reserve_credits: int | None = Field(default=None, ge=0)
    primary: bool = True


class HiggsIn(BaseModel):
    use_video: bool | None = None
    use_image: bool | None = None
    video_model: str | None = None
    image_model: str | None = None
    resolution: Literal["480p", "720p", "1080p"] | None = None
    plan_price_eur: float | None = Field(default=None, ge=0, le=10000)
    plan_credits: int | None = Field(default=None, gt=0)
    reserve_credits: int | None = Field(default=None, ge=0)
    max_clips_per_video: int | None = Field(default=None, ge=0, le=40)
    max_images_per_video: int | None = Field(default=None, ge=0, le=60)
    require_balance_check: bool | None = None


class AlwaysIn(BaseModel):
    authorized: bool


class FeaturesIn(BaseModel):
    features: list[str]


class CastIn(BaseModel):
    channel: str
    role: str
    voice_id: str | None = Field(default=None, max_length=80)


class DesignIn(BaseModel):
    description: str = Field(min_length=10, max_length=1000)
    text: str | None = Field(default=None, max_length=1000)


class DesignSaveIn(BaseModel):
    generated_voice_id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=2, max_length=60)
    description: str = Field(min_length=3, max_length=1000)
    channel: str | None = None
    role: str | None = None


class ReferenceIn(BaseModel):
    filename: str = Field(min_length=1, max_length=200)
    data_b64: str = Field(min_length=8)


def register(api: FastAPI, app: App, deps: list) -> None:
    A = deps
    cache: dict[str, tuple[float, Any]] = {}

    def reg():
        if not app.provider_system:
            raise HTTPException(503, "Registro de proveedores no disponible")
        return app.provider_system.registry

    def budget():
        return app.provider_system.budget if app.provider_system else None

    def cfg(pid: str):
        try:
            return reg().get(pid)
        except RegistryError:
            return None

    def always() -> list[str]:
        b = budget()
        return list(b.get_setting("spend_authorized_providers", []) or []) if b else []

    def ensure(adapter: str, params: dict[str, Any], primary: bool, **fields: Any):
        r = reg()
        cur = cfg(adapter)
        if cur is None:
            cur = r.add(adapter, id=adapter, params=params, **fields)
        else:
            cur = r.update(adapter, params={**cur.params, **params}, enabled=True, **fields)
        if primary:
            r.set_primary(cur.category, adapter)
        return r.get(adapter)

    def role(pid: str) -> str | None:
        c = cfg(pid)
        if c is None:
            return None
        chain = reg().chain(c.category)
        return "disabled" if not c.enabled else "primary" if chain and chain[0].id == pid else "fallback"

    # ------------------------------------------------------------ ElevenLabs
    def eleven_view(refresh: bool = False) -> dict[str, Any]:
        c = cfg(ELEVEN)
        out: dict[str, Any] = {"linked": False, "has_key": False, "models": ELEVEN_MODELS, "plans": ELEVEN_PLANS,
                               "always_authorized": ELEVEN in always()}
        tier = None
        if c is not None:
            hints = reg().vault.hints(ELEVEN)
            out.update(linked=True, has_key="api_key" in hints, key_hint=hints.get("api_key"), role=role(ELEVEN),
                       params={k: c.params.get(k) for k in ("model_id", "default_voice_id", "price_per_1k_chars_eur",
                                                              "reserve_credits")})
            if out["has_key"]:
                try:
                    inst = reg().instance(ELEVEN)
                    out["subscription"] = inst.subscription(max_age_s=0 if refresh else 60)
                    tier = out["subscription"].get("tier")
                except (ProviderError, ProviderNotConfigured) as e:
                    out["error"] = str(e)
        sfx = cfg(ELEVEN_SFX)
        out.update(features=af.feature_view(features(), tier), features_answered=features_answered(),
                   cast=cast_all(), roles=af.ROLES, channels=[{"id": ch.id, "name": ch.name} for ch in channels()],
                   sfx={"linked": bool(sfx and sfx.enabled),
                        "max_per_video": sfx.max_generations_per_project if sfx else None,
                        "always_authorized": ELEVEN_SFX in always()})
        return out

    def features() -> list[str]:
        b = budget()
        saved = b.get_setting("elevenlabs_features", None) if b else None
        return list(saved) if saved is not None else list(af.DEFAULT_FEATURES)

    def features_answered() -> bool:
        b = budget()
        return bool(b and b.get_setting("elevenlabs_features", None) is not None)

    def cast_all() -> dict[str, dict[str, str]]:
        b = budget()
        return dict(b.get_setting("voice_cast", {}) or {}) if b else {}

    def sync_sfx(enabled: bool) -> None:
        """Los efectos con IA son otro proveedor (categoría efectos) con la MISMA clave cifrada."""
        r = reg()
        current = cfg(ELEVEN_SFX)
        if not enabled:
            if current and current.enabled:
                r.update(ELEVEN_SFX, enabled=False)
            return
        main = cfg(ELEVEN)
        key = r.vault.get_all(ELEVEN).get("api_key") if main else None
        if not main or not key:
            raise HTTPException(400, "Vincula primero tu cuenta de ElevenLabs")
        params = {"price_per_1k_chars_eur": main.params.get("price_per_1k_chars_eur"),
                  "reserve_credits": main.params.get("reserve_credits", 2000)}
        ensure(ELEVEN_SFX, params, True, **({} if current else {"max_generations_per_project": 6}))
        r.set_credential(ELEVEN_SFX, "api_key", key)

    @api.put("/api/accounts/elevenlabs/features", dependencies=A)
    def set_features(body: FeaturesIn):
        unknown = set(body.features) - af.FEATURE_IDS
        if unknown:
            raise HTTPException(400, f"Capacidades desconocidas: {sorted(unknown)}")
        chosen = [f.id for f in af.FEATURES if f.id in body.features and f.in_app]
        if cfg(ELEVEN):
            sync_sfx("sfx" in chosen)
            if "expressive" in chosen:
                main = cfg(ELEVEN)
                reg().update(ELEVEN, params={**main.params, "dialogue_model_id": main.params.get("dialogue_model_id")
                                             or "eleven_v4"})
        budget().set_setting("elevenlabs_features", chosen)
        return eleven_view()

    @api.put("/api/accounts/elevenlabs/cast", dependencies=A)
    def set_cast(body: CastIn):
        if body.role not in af.ROLES:
            raise HTTPException(400, "Papel desconocido")
        if body.channel not in {c.id for c in channels()}:
            raise HTTPException(400, "Canal desconocido")
        cast = cast_all()
        mine = dict(cast.get(body.channel) or {})
        if body.voice_id:
            mine[body.role] = body.voice_id
        else:
            mine.pop(body.role, None)
        cast[body.channel] = mine
        budget().set_setting("voice_cast", cast)
        return {"cast": cast}

    @api.post("/api/accounts/elevenlabs/voice-design", dependencies=A)
    def design_voice(body: DesignIn):
        try:
            return reg().instance(ELEVEN).design_voice(body.description, body.text)
        except (ProviderError, ProviderNotConfigured, RegistryError) as e:
            raise HTTPException(400, str(e)) from e

    @api.post("/api/accounts/elevenlabs/voice-design/save", dependencies=A)
    def save_designed_voice(body: DesignSaveIn):
        try:
            voice = reg().instance(ELEVEN).create_voice(body.generated_voice_id, body.name, body.description)
        except (ProviderError, ProviderNotConfigured, RegistryError) as e:
            raise HTTPException(400, str(e)) from e
        if body.channel and body.role:
            set_cast(CastIn(channel=body.channel, role=body.role, voice_id=voice["voice_id"]))
        return {"voice": voice, "cast": cast_all()}

    # ------------------------------------------------------------ Voice Changer: tu interpretación por escena
    @api.post("/api/projects/{pid}/voice-reference/{scene}", dependencies=A, status_code=201)
    def upload_reference(pid: str, scene: int, body: ReferenceIn):
        import base64 as _b64
        import binascii
        from pathlib import Path as _P
        app.store.get_project(pid)
        ext = _P(body.filename).suffix.lower()
        if ext not in (".mp3", ".wav", ".m4a", ".ogg", ".webm", ".flac"):
            raise HTTPException(400, "Formato de audio no admitido")
        try:
            raw = _b64.b64decode(body.data_b64, validate=True)
        except (binascii.Error, ValueError) as e:
            raise HTTPException(400, "Archivo dañado") from e
        if not 1024 <= len(raw) <= 20 * 1024 * 1024:
            raise HTTPException(400, "La grabación debe pesar entre 1 KB y 20 MB")
        folder = Workspace(app.settings.projects_dir, pid).dir("voice")
        for old in folder.glob(f"reference_{scene}.*"):
            old.unlink()
        (folder / f"reference_{scene}{ext}").write_bytes(raw)
        return {"scene": scene, "file": f"reference_{scene}{ext}"}

    @api.delete("/api/projects/{pid}/voice-reference/{scene}", dependencies=A)
    def delete_reference(pid: str, scene: int):
        app.store.get_project(pid)
        folder = Workspace(app.settings.projects_dir, pid).dir("voice")
        for old in folder.glob(f"reference_{scene}.*"):
            old.unlink()
        return {"ok": True}

    @api.get("/api/projects/{pid}/voice-reference", dependencies=A)
    def list_references(pid: str):
        app.store.get_project(pid)
        folder = Workspace(app.settings.projects_dir, pid).dir("voice")
        return {"scenes": sorted(int(f.stem.split("_", 1)[1]) for f in folder.glob("reference_*")
                                 if f.stem.split("_", 1)[1].isdigit())}

    @api.get("/api/accounts", dependencies=A)
    def accounts(refresh: bool = Query(False)):
        return {"elevenlabs": eleven_view(refresh), "higgsfield": higgs_view(refresh), "always": always()}

    @api.post("/api/accounts/elevenlabs", dependencies=A)
    def link_eleven(body: ElevenIn):
        r = reg()
        cls = r.adapters().get(ELEVEN)
        if cls is None:
            raise HTTPException(500, "Adaptador de ElevenLabs no disponible")
        current = cfg(ELEVEN)
        params: dict[str, Any] = {}
        if body.model_id:
            if body.model_id not in ELEVEN_MODELS:
                raise HTTPException(400, "Modelo de voz no admitido")
            params["model_id"] = body.model_id
        if body.plan_price_eur is not None or body.plan_credits is not None:
            if body.plan_price_eur is None or not body.plan_credits:
                raise HTTPException(400, "Indica el precio mensual y los créditos del plan")
            params["price_per_1k_chars_eur"] = round(body.plan_price_eur / body.plan_credits * 1000, 5)
        elif not current or current.params.get("price_per_1k_chars_eur") in (None, ""):
            raise HTTPException(400, "Indica el precio mensual y los créditos de tu plan (para controlar el gasto)")
        if body.reserve_credits is not None:
            params["reserve_credits"] = body.reserve_credits
        if body.voice_id is not None:
            params["default_voice_id"] = body.voice_id
        if body.api_key:
            probe = cls(params={**(current.params if current else {}), **params}, credentials={"api_key": body.api_key})
            try:
                sub = probe.subscription()
            except ProviderError as e:
                raise HTTPException(400, f"ElevenLabs no aceptó la clave: {e}") from e
            if not params.get("default_voice_id") and not (current and current.params.get("default_voice_id")):
                try:
                    voices = probe.list_voices("es")
                    if voices:
                        params["default_voice_id"] = voices[0].id
                except ProviderError:
                    pass
            ensure(ELEVEN, params, body.primary)
            r.set_credential(ELEVEN, "api_key", body.api_key)
            if "sfx" in features() and features_answered():
                sync_sfx(True)  # lo que contestaste en el cuestionario se aplica al vincular la cuenta
            cache.pop(ELEVEN, None)
            return {**eleven_view(True), "verified": sub}
        if current is None or "api_key" not in r.vault.hints(ELEVEN):
            raise HTTPException(400, "Pega tu clave de API de ElevenLabs para vincular la cuenta")
        ensure(ELEVEN, params, body.primary)
        return eleven_view(True)

    @api.get("/api/accounts/elevenlabs/voices", dependencies=A)
    def eleven_voices():
        try:
            return [v.model_dump() for v in reg().instance(ELEVEN).list_voices("es")]
        except (ProviderError, ProviderNotConfigured, RegistryError) as e:
            raise HTTPException(400, str(e)) from e

    @api.delete("/api/accounts/elevenlabs", dependencies=A)
    def unlink_eleven():
        for pid in (ELEVEN, ELEVEN_SFX):
            if cfg(pid):
                reg().remove(pid)  # borra también la clave cifrada
            set_always(pid, False)
        return eleven_view()

    # ------------------------------------------------------------ Higgsfield
    def hf_params() -> dict[str, Any]:
        c = cfg(HF_VIDEO) or cfg(HF_IMAGE)
        return dict(c.params) if c else {}

    def higgs_status(refresh: bool) -> dict[str, Any]:
        hit = cache.get("hf")
        if hit and not refresh and time.time() - hit[0] < 30:
            return hit[1]
        cls = reg().adapters().get(HF_VIDEO)
        try:
            st = cls(params=hf_params()).cli().status() if cls else {"installed": False, "logged_in": False,
                                                                     "credits": None, "message": "Adaptador no disponible"}
        except ProviderError as e:
            st = {"installed": True, "logged_in": None, "credits": None, "message": str(e)}
        cache["hf"] = (time.time(), st)
        return st

    def higgs_view(refresh: bool = False) -> dict[str, Any]:
        binary = hf.find_cli(str(hf_params().get("cli_path") or ""))
        st = higgs_status(refresh) if binary else {"installed": False, "logged_in": False, "credits": None,
                                                   "message": "CLI no instalada"}
        v, i = cfg(HF_VIDEO), cfg(HF_IMAGE)
        params = hf_params()
        return {
            "cli_path": binary, "status": st, "video_models": {k: m["label"] for k, m in hf.VIDEO_MODELS.items()},
            "image_models": {k: m["label"] for k, m in hf.IMAGE_MODELS.items()}, "plans": hf.PLAN_PRESETS,
            "video": {"linked": bool(v and v.enabled), "role": role(HF_VIDEO), "model": v.params.get("model") if v else None,
                      "resolution": v.params.get("resolution") if v else None,
                      "max_per_video": v.max_generations_per_project if v else None},
            "image": {"linked": bool(i and i.enabled), "role": role(HF_IMAGE), "model": i.params.get("model") if i else None,
                      "max_per_video": i.max_generations_per_project if i else None},
            "price_per_credit_eur": params.get("price_per_credit_eur"),
            "reserve_credits": params.get("reserve_credits"),
            "require_balance_check": params.get("require_balance_check", True),
            "always_authorized": {HF_VIDEO: HF_VIDEO in always(), HF_IMAGE: HF_IMAGE in always()},
            "help": {"api": hf.HELP_API, "cli": hf.HELP_CLI},
        }

    @api.post("/api/accounts/higgsfield", dependencies=A)
    def link_higgs(body: HiggsIn):
        params: dict[str, Any] = {}
        if body.plan_price_eur is not None or body.plan_credits is not None:
            if body.plan_price_eur is None or not body.plan_credits:
                raise HTTPException(400, "Indica el precio mensual y los créditos del plan")
            params["price_per_credit_eur"] = round(body.plan_price_eur / body.plan_credits, 6)
        elif hf_params().get("price_per_credit_eur") in (None, ""):
            raise HTTPException(400, "Indica el precio mensual y los créditos de tu plan (para controlar el gasto)")
        if body.reserve_credits is not None:
            params["reserve_credits"] = body.reserve_credits
        if body.require_balance_check is not None:
            params["require_balance_check"] = body.require_balance_check
        binary = hf.find_cli(str(hf_params().get("cli_path") or ""))
        if binary:
            params["cli_path"] = binary
        for pid, use, model, models, cap in ((HF_VIDEO, body.use_video, body.video_model, hf.VIDEO_MODELS,
                                               body.max_clips_per_video),
                                              (HF_IMAGE, body.use_image, body.image_model, hf.IMAGE_MODELS,
                                               body.max_images_per_video)):
            p = dict(params)
            if model:
                if model not in models:
                    raise HTTPException(400, f"Modelo no admitido: {model}")
                p["model"] = model
            if pid == HF_VIDEO and body.resolution:
                p["resolution"] = body.resolution
            extra = {"max_generations_per_project": cap} if cap is not None else {}
            if use:
                ensure(pid, p, True, **extra)
            elif use is False and cfg(pid):
                reg().update(pid, enabled=False)
            elif cfg(pid):
                reg().update(pid, params={**cfg(pid).params, **p}, **extra)
        cache.pop("hf", None)
        return higgs_view(True)

    @api.post("/api/accounts/higgsfield/install", dependencies=A)
    def install_higgs():
        try:
            res = hf.install_cli()
        except ProviderError as e:
            raise HTTPException(502, str(e)) from e
        for pid in (HF_VIDEO, HF_IMAGE):
            if cfg(pid):
                reg().update(pid, params={**cfg(pid).params, "cli_path": res["path"]})
        cache.pop("hf", None)
        return {"installed": res, **higgs_view(True)}

    @api.post("/api/accounts/higgsfield/login", dependencies=A)
    def login_higgs():
        binary = hf.find_cli(str(hf_params().get("cli_path") or ""))
        if not binary:
            raise HTTPException(400, "Primero instala la CLI de Higgsfield")
        launch = hf.login_launch(binary)
        cache.pop("hf", None)
        if launch is None:
            return {"opened": False, "command": f"{binary} auth login"}
        argv, kw = launch
        try:
            _popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kw)
        except OSError:
            return {"opened": False, "command": f"{binary} auth login"}
        return {"opened": True, "command": f"{binary} auth login"}

    @api.post("/api/accounts/higgsfield/estimate", dependencies=A)
    def estimate_higgs(kind: Literal["video", "image"] = Query("video"), seconds: float = Query(5, gt=0, le=30)):
        pid = HF_VIDEO if kind == "video" else HF_IMAGE
        if not cfg(pid):
            raise HTTPException(400, "Activa primero Higgsfield para este uso")
        from ..providers.interfaces import ImageRequest, VideoRequest
        inst = reg().adapters()[pid](params=cfg(pid).params)
        req = VideoRequest(prompt="estimate", duration_s=seconds, out_dir=app.settings.data_dir) if kind == "video" \
            else ImageRequest(prompt="estimate", out_dir=app.settings.data_dir)
        est = inst.estimate_cost("generate", req)
        return {"credits": est.units, "eur": est.amount_eur, "detail": est.detail}

    @api.delete("/api/accounts/higgsfield", dependencies=A)
    def unlink_higgs():
        for pid in (HF_VIDEO, HF_IMAGE):
            if cfg(pid):
                reg().remove(pid)
            set_always(pid, False)
        cache.pop("hf", None)
        return higgs_view()

    # ------------------------------------------------------------ autorización permanente (explícita)
    def set_always(pid: str, value: bool) -> list[str]:
        b = budget()
        if not b:
            return []
        cur = [p for p in always() if p != pid]
        if value:
            cur.append(pid)
        b.set_setting("spend_authorized_providers", cur)
        return cur

    @api.put("/api/accounts/{pid}/always", dependencies=A)
    def always_authorize(pid: str, body: AlwaysIn):
        if pid not in PAID_ACCOUNTS:
            raise HTTPException(404, "Cuenta desconocida")
        if body.authorized and not cfg(pid):
            raise HTTPException(400, "Vincula primero la cuenta")
        return {"always": set_always(pid, body.authorized)}

