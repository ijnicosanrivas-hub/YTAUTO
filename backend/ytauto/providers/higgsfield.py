"""Higgsfield a través de su CLI oficial (`higgsfield`), con la cuenta y los créditos del plan del usuario.

Hechos oficiales (centro de ayuda de Higgsfield, agosto de 2026):
- La suscripción de higgsfield.ai y la API son productos distintos, con facturación distinta: los créditos del plan
  NO sirven para la API (que funciona con un saldo prepago en dólares).
  https://higgsfield.ai/creator-hub/help-center/integrations/what-is-the-higgsfield-api
- La CLI y el MCP usan la misma cuenta y los mismos créditos del plan, sin clave de API; se entra con
  `higgsfield auth login`. Todo lo que generan descuenta créditos a la tarifa estándar: los modelos «Unlimited» y
  las generaciones gratis solo valen en la web.
  https://higgsfield.ai/creator-hub/help-center/integrations/how-do-i-access-higgsfield-via-cli
- El uso programático se rige por las «Developer Terms»: el titular responde de lo que se genere con su cuenta.

Órdenes usadas (las de las «skills» oficiales `higgsfield-ai/skills`): `account status`, `generate cost <modelo>`,
`generate create <modelo> --prompt … --wait --json`, `auth login`.

YTAUTO nunca lee ni copia la sesión de la CLI: solo la ejecuta, como hace con `claude -p`. Una sola generación a la
vez (cerrojo), así el saldo leído antes y después de cada clip da su coste real en créditos.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import platform as _platform
import re
import shutil
import subprocess
import sys
import tarfile
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from ..core.errors import ProviderError
from ..core.settings import REPO_ROOT

NAME = "higgsfield"
CLI_NAMES = ("higgsfield", "higgs")  # «hf» a secas NO se busca en el PATH: es también la CLI de Hugging Face
NPM_LATEST = "https://registry.npmjs.org/@higgsfield/cli/latest"
RELEASE_URL = "https://github.com/higgsfield-ai/cli/releases/download/v{version}/{archive}"
HELP_API = "https://higgsfield.ai/creator-hub/help-center/integrations/what-is-the-higgsfield-api"
HELP_CLI = "https://higgsfield.ai/creator-hub/help-center/integrations/how-do-i-access-higgsfield-via-cli"
LOCK = threading.Lock()

# Modelos ofrecidos en la interfaz. Los identificadores y su papel salen del catálogo oficial de las skills.
VIDEO_MODELS: dict[str, dict[str, Any]] = {
    "kling3_0_turbo": {"label": "Kling 3.0 Turbo · económico y rápido", "durations": [5, 10]},
    "seedance_2_5": {"label": "Seedance 2.5 · máxima calidad", "range": [4, 12]},
}
IMAGE_MODELS: dict[str, dict[str, Any]] = {
    "nano_banana_flash": {"label": "Nano Banana 2 · personajes y estilo dibujo"},
    "gpt_image_2_6": {"label": "GPT Image 2.6 · alta fidelidad"},
    "text2image_soul_v2": {"label": "Soul V2 · estilo cinematográfico"},
}
# Plan Plus (lo que el usuario contrató): 1.200 créditos al mes por 59 € (40 € el primer mes).
PLAN_PRESETS = {"plus": {"label": "Plus", "credits": 1200, "price_eur": 59.0}}

_NOT_LOGGED = re.compile(r"(?i)not\s+authenticated|session\s+expired|not\s+logged\s+in|please\s+(?:run\s+)?"
                         r"[`'\"]?higgsfield auth login|unauthori[sz]ed|login\s+required")
_NO_CREDITS = re.compile(r"(?i)insufficient|not\s+enough\s+credits|out\s+of\s+credits|no\s+credits|balance\s+too\s+low")
_FAILED = {"failed", "error", "cancelled", "canceled", "nsfw", "rejected", "timeout", "timed_out"}
_VIDEO_EXT = (".mp4", ".mov", ".webm", ".m4v")
_IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp")


# ------------------------------------------------------------------ localizar la CLI
def bin_name(sys_platform: str | None = None) -> str:
    return "hf.exe" if (sys_platform or sys.platform).startswith("win") else "hf"


def local_install_dir(root: Path = REPO_ROOT) -> Path:
    return root / "tools" / "higgsfield"


def find_cli(explicit: str = "", root: Path = REPO_ROOT, which: Callable[[str], str | None] = shutil.which) -> str | None:
    """La CLI elegida a mano, la instalada por YTAUTO en tools/higgsfield o la del PATH (npm / install.sh)."""
    if explicit and Path(explicit).is_file():
        return explicit
    local = local_install_dir(root) / bin_name()
    if local.is_file():
        return str(local)
    for name in CLI_NAMES:
        found = which(name)
        if found:
            return found
    return None


# ------------------------------------------------------------------ lectura de la salida (funciones puras)
def parse_json(text: str) -> Any:
    """JSON de la salida aunque vaya precedido de avisos en texto."""
    text = (text or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except ValueError:
        pass
    for opener in ("{", "["):
        i = text.find(opener)
        if i >= 0:
            try:
                return json.loads(text[i:])
            except ValueError:
                continue
    return None


def _walk(obj: Any, path: str = ""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(v, f"{path}.{k}".lower() if path else str(k).lower())
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk(v, f"{path}[{i}]")
    else:
        yield path, obj


def _num(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        m = re.fullmatch(r"\s*([\d]+(?:[.,]\d+)?)\s*", v)
        if m:
            return float(m.group(1).replace(",", "."))
    return None


def find_credits(obj: Any) -> float | None:
    """Créditos disponibles en la respuesta de `account status` (el formato exacto no está documentado)."""
    best: tuple[int, float] | None = None
    for path, value in _walk(obj):
        n = _num(value)
        if n is None:
            continue
        leaf = path.rsplit(".", 1)[-1]
        if "credit" not in path and leaf not in ("balance", "remaining", "available"):
            continue
        if any(w in leaf for w in ("used", "spent", "limit", "total", "max", "price", "cost", "reset", "expire")):
            continue
        score = 3 if any(w in leaf for w in ("remain", "avail", "balance", "left")) else 2 if "credit" in leaf else 1
        if best is None or score > best[0]:
            best = (score, n)
    return best[1] if best else None


def credits_from_text(text: str) -> float | None:
    for pat in (r"(?i)(?:credits?|balance)\s*(?:left|remaining|available)?\s*[:=]\s*([\d][\d.,]*)",
                r"(?i)([\d][\d.,]*)\s*credits?\b"):
        m = re.search(pat, text or "")
        if m:
            raw = m.group(1).rstrip(".,")
            raw = raw.replace(",", "") if re.fullmatch(r"\d{1,3}(?:,\d{3})+", raw) else raw.replace(",", ".")
            try:
                return float(raw)
            except ValueError:
                continue
    return None


def find_cost(obj: Any) -> float | None:
    for path, value in _walk(obj):
        n = _num(value)
        if n is not None and any(w in path.rsplit(".", 1)[-1] for w in ("credit", "cost", "price", "amount")):
            return n
    return None


def media_urls(obj: Any, kind: str = "") -> list[str]:
    """URLs de resultados; primero las que tienen la extensión del tipo pedido."""
    urls: list[str] = []
    for _, value in _walk(obj):
        if isinstance(value, str) and value.startswith("https://") and value not in urls:
            urls.append(value)
    ext = _VIDEO_EXT if kind == "video" else _IMAGE_EXT if kind == "image" else ()

    def rank(u: str) -> int:
        clean = u.split("?", 1)[0].lower()
        return 0 if ext and clean.endswith(ext) else 1 if clean.endswith(_VIDEO_EXT + _IMAGE_EXT) else 2
    return sorted(urls, key=rank)


def failure_reason(obj: Any) -> str | None:
    for path, value in _walk(obj):
        if path.rsplit(".", 1)[-1] == "status" and isinstance(value, str) and value.lower() in _FAILED:
            return value.lower()
    return None


def pick_duration(model: str, seconds: float) -> int:
    """Duración admitida más corta que cubra la escena (el coste crece con la duración)."""
    spec = VIDEO_MODELS.get(model, {})
    want = max(1, math.ceil(seconds - 0.05))
    if spec.get("durations"):
        opts = sorted(spec["durations"])
        return next((d for d in opts if d >= want), opts[-1])
    lo, hi = spec.get("range", [4, 10])
    return int(min(hi, max(lo, want)))


def to_flags(params: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for k, v in params.items():
        if v is None or v == "":
            continue
        out += [f"--{k}", str(v).lower() if isinstance(v, bool) else str(v)]
    return out


# ------------------------------------------------------------------ ejecución
class HiggsfieldCLI:
    """Ejecuta la CLI oficial sin shell, sin entrada estándar y con tiempo máximo."""

    def __init__(self, binary: str | None = None, run: Callable[..., subprocess.CompletedProcess] = subprocess.run):
        self.binary = binary
        self._run_fn = run

    def run(self, args: list[str], timeout: float = 60) -> subprocess.CompletedProcess:
        if not self.binary:
            raise ProviderError(NAME, "La CLI de Higgsfield no está instalada (Cuentas conectadas → Instalar)",
                                transient=False)
        try:
            return self._run_fn([self.binary, *args], capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=timeout, stdin=subprocess.DEVNULL)
        except FileNotFoundError as e:
            raise ProviderError(NAME, f"No se encuentra la CLI de Higgsfield en {self.binary}", transient=False) from e
        except subprocess.TimeoutExpired as e:
            raise ProviderError(NAME, f"La CLI de Higgsfield no respondió en {int(timeout)} s", transient=True) from e

    @staticmethod
    def _text(proc: subprocess.CompletedProcess) -> str:
        return f"{proc.stdout or ''}\n{proc.stderr or ''}"

    def _raise_for(self, proc: subprocess.CompletedProcess, action: str) -> None:
        text = self._text(proc)
        if _NOT_LOGGED.search(text):
            raise ProviderError(NAME, "La sesión de Higgsfield no está iniciada o caducó: pulsa «Iniciar sesión» en "
                                      "Cuentas conectadas", transient=False)
        if _NO_CREDITS.search(text):
            raise ProviderError(NAME, "Higgsfield dice que no quedan créditos suficientes en el plan", transient=False)
        tail = " ".join(text.split())[-300:]
        raise ProviderError(NAME, f"{action} falló (código {proc.returncode}): {tail}", transient=False)

    def status(self) -> dict[str, Any]:
        """{installed, logged_in, credits, message}. Solo lectura, sin coste."""
        if not self.binary:
            return {"installed": False, "logged_in": False, "credits": None, "message": "CLI no instalada"}
        proc = self.run(["account", "status", "--json"], timeout=40)
        text = self._text(proc)
        if proc.returncode != 0 and re.search(r"(?i)unknown (?:flag|shorthand)", text):
            proc = self.run(["account", "status"], timeout=40)
            text = self._text(proc)
        if _NOT_LOGGED.search(text):
            return {"installed": True, "logged_in": False, "credits": None,
                    "message": "Sesión no iniciada: pulsa «Iniciar sesión»"}
        if proc.returncode != 0:
            return {"installed": True, "logged_in": None, "credits": None,
                    "message": " ".join(text.split())[-200:] or f"código {proc.returncode}"}
        data = parse_json(proc.stdout)
        credits = find_credits(data) if data is not None else None
        if credits is None:
            credits = credits_from_text(text)
        plan = None
        if isinstance(data, dict):
            for path, value in _walk(data):
                if path.rsplit(".", 1)[-1] in ("plan", "plan_name", "tier", "subscription") and isinstance(value, str):
                    plan = value
                    break
        return {"installed": True, "logged_in": True, "credits": credits, "plan": plan,
                "message": "Sesión iniciada" if credits is not None else "Sesión iniciada (no se pudo leer el saldo)"}

    def cost(self, model: str, prompt: str, flags: list[str]) -> float | None:
        proc = self.run(["generate", "cost", model, "--prompt", prompt, *flags, "--json"], timeout=40)
        if proc.returncode != 0:
            return None
        data = parse_json(proc.stdout)
        return find_cost(data) if data is not None else credits_from_text(self._text(proc))

    def generate(self, model: str, prompt: str, flags: list[str], kind: str, wait_minutes: int = 15) -> list[str]:
        proc = self.run(["generate", "create", model, "--prompt", prompt, *flags, "--wait",
                         "--wait-timeout", f"{wait_minutes}m", "--json"], timeout=wait_minutes * 60 + 60)
        if proc.returncode != 0:
            self._raise_for(proc, "La generación")
        data = parse_json(proc.stdout)
        if data is not None and failure_reason(data):
            raise ProviderError(NAME, f"Higgsfield no completó el trabajo (estado: {failure_reason(data)})",
                                transient=failure_reason(data) in ("timeout", "timed_out"))
        urls = media_urls(data if data is not None else re.findall(r"https://\S+", proc.stdout or ""), kind)
        if not urls:
            raise ProviderError(NAME, "La CLI terminó pero no devolvió la URL del resultado", transient=False)
        return urls


def download(url: str, dest: Path, transport: httpx.BaseTransport | None = None, max_mb: int = 400) -> Path:
    if not url.startswith("https://"):
        raise ProviderError(NAME, "URL de resultado no segura (se exige https)", transient=False)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with httpx.Client(transport=transport, timeout=httpx.Timeout(180.0, connect=20.0), follow_redirects=True) as c:
            with c.stream("GET", url) as r:
                if not r.is_success:
                    raise ProviderError(NAME, f"No se pudo descargar el resultado ({r.status_code})",
                                        transient=r.status_code >= 500)
                size = 0
                with open(dest, "wb") as f:
                    for chunk in r.iter_bytes():
                        size += len(chunk)
                        if size > max_mb * 1024 * 1024:
                            raise ProviderError(NAME, f"El resultado supera {max_mb} MB", transient=False)
                        f.write(chunk)
    except httpx.HTTPError as e:
        dest.unlink(missing_ok=True)
        raise ProviderError(NAME, f"Error de red al descargar el resultado: {type(e).__name__}", transient=True) from e
    except ProviderError:
        dest.unlink(missing_ok=True)
        raise
    return dest


# ------------------------------------------------------------------ instalación verificada
def platform_archive(version: str, sys_platform: str | None = None, machine: str | None = None) -> str:
    sp = sys_platform or sys.platform
    os_name = "windows" if sp.startswith("win") else "darwin" if sp == "darwin" else "linux"
    m = (machine or _platform.machine()).lower()
    arch = "arm64" if m in ("arm64", "aarch64") else "amd64"
    return f"hf_{version}_{os_name}_{arch}.tar.gz"


def install_cli(dest_dir: Path | None = None, transport: httpx.BaseTransport | None = None,
                sys_platform: str | None = None, machine: str | None = None) -> dict[str, str]:
    """Descarga la CLI oficial publicada por Higgsfield y comprueba su SHA-256 con el manifiesto del paquete npm
    oficial (`@higgsfield/cli`), igual que hace su propio instalador. Sin Node ni permisos de administrador."""
    dest_dir = dest_dir or local_install_dir()
    with httpx.Client(transport=transport, timeout=httpx.Timeout(120.0, connect=20.0), follow_redirects=True) as c:
        def get(url: str) -> httpx.Response:
            try:
                r = c.get(url)
            except httpx.HTTPError as e:
                raise ProviderError(NAME, f"Sin conexión con {httpx.URL(url).host}", transient=True) from e
            if not r.is_success:
                raise ProviderError(NAME, f"{httpx.URL(url).host} respondió {r.status_code}", transient=r.status_code >= 500)
            return r
        meta = get(NPM_LATEST).json()
        version = str(meta.get("version") or "")
        tarball = str((meta.get("dist") or {}).get("tarball") or "")
        if not re.fullmatch(r"\d+\.\d+\.\d+", version) or not tarball.startswith("https://registry.npmjs.org/"):
            raise ProviderError(NAME, "El paquete oficial de npm no tiene el formato esperado", transient=False)
        with tarfile.open(fileobj=io.BytesIO(get(tarball).content), mode="r:gz") as tgz:
            member = tgz.extractfile("package/checksums.json")
            manifest = json.loads(member.read().decode("utf-8")) if member else {}
        if manifest.get("version") != version:
            raise ProviderError(NAME, "El manifiesto de sumas no corresponde a la versión publicada", transient=False)
        archive = platform_archive(version, sys_platform, machine)
        expected = (manifest.get("archives") or {}).get(archive)
        if not expected:
            raise ProviderError(NAME, f"No hay CLI oficial para este sistema ({archive})", transient=False)
        blob = get(RELEASE_URL.format(version=version, archive=archive)).content
    if hashlib.sha256(blob).hexdigest() != expected:
        raise ProviderError(NAME, "La descarga no coincide con la suma oficial: no se instala", transient=False)
    name = bin_name(sys_platform)
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tar:
        members = [m for m in tar.getmembers() if m.isfile() and Path(m.name).name == name]
        if not members:
            raise ProviderError(NAME, f"El paquete no contiene {name}", transient=False)
        data = tar.extractfile(members[0]).read()
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / name
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.chmod(0o755)
    tmp.replace(target)
    (dest_dir / "VERSION").write_text(version, encoding="utf-8")
    return {"path": str(target), "version": version, "sha256": expected}


# ------------------------------------------------------------------ inicio de sesión (ventana visible)
def login_launch(binary: str, sys_platform: str | None = None,
                 which: Callable[[str], str | None] = shutil.which) -> tuple[list[str], dict[str, Any]] | None:
    """Orden para abrir `higgsfield auth login` en una ventana que el usuario ve (el inicio de sesión es suyo).
    None si no hay forma de abrir una terminal: entonces la interfaz muestra la orden para copiarla."""
    sp = sys_platform or sys.platform
    if sp.startswith("win"):
        return [binary, "auth", "login"], {"creationflags": 0x00000010}  # CREATE_NEW_CONSOLE
    if sp == "darwin":
        cmd = f"{_sh_quote(binary)} auth login".replace("\\", "\\\\").replace('"', '\\"')
        return ["osascript", "-e", f'tell application "Terminal" to do script "{cmd}"',
                "-e", 'tell application "Terminal" to activate'], {}
    for term, flag in (("x-terminal-emulator", "-e"), ("gnome-terminal", "--"), ("konsole", "-e"), ("xterm", "-e")):
        if which(term):
            return [term, flag, binary, "auth", "login"], {}
    return None


def _sh_quote(s: str) -> str:
    import shlex
    return shlex.quote(s)


# ------------------------------------------------------------------ lógica común de los adaptadores
class HiggsfieldCommon:
    """Mezcla para los adaptadores de vídeo e imagen (antes de la interfaz en la herencia)."""

    kind: str = "video"
    fallback_credits: float = 0.0  # estimación si la CLI no da el coste (se corrige con el saldo real)
    _runner: Callable[..., subprocess.CompletedProcess] | None = None  # pruebas: CLI simulada
    _transport: httpx.BaseTransport | None = None  # pruebas: descargas simuladas
    params: dict[str, Any]

    def cli(self) -> HiggsfieldCLI:
        binary = find_cli(str(self.params.get("cli_path") or ""))
        return HiggsfieldCLI(binary, run=self._runner) if self._runner else HiggsfieldCLI(binary)

    def capabilities(self) -> dict[str, Any]:
        return {"plan_credits": True, "aspect_ratios": ["9:16"], "needs_price_param": True,
                "note": "Usa los créditos del plan de higgsfield.ai a través de la CLI oficial (no la API)."}

    def health_check(self):
        from .interfaces import HealthStatus
        if self.params.get("price_per_credit_eur") in (None, ""):
            return HealthStatus(ok=False, message="Configura price_per_credit_eur (precio del plan ÷ créditos): sin él "
                                                  "no se puede estimar el coste ni aplicar el presupuesto")
        if not find_cli(str(self.params.get("cli_path") or "")):
            return HealthStatus(ok=False, message="La CLI de Higgsfield no está instalada")
        return HealthStatus(ok=True, message="Configurado")

    def verify_connection(self):
        from .interfaces import HealthStatus
        local = self.health_check()
        if not local.ok:
            return local
        try:
            st = self.cli().status()
        except ProviderError as e:
            return HealthStatus(ok=False, message=str(e))
        if not st["logged_in"]:
            return HealthStatus(ok=False, message=st["message"])
        credits = st.get("credits")
        return HealthStatus(ok=True, message=f"Sesión iniciada · {credits:g} créditos" if credits is not None
                            else st["message"])

    def flags_for(self, request: Any) -> dict[str, Any]:  # pragma: no cover - lo define cada adaptador
        raise NotImplementedError

    def estimate_credits(self, request: Any) -> tuple[float, str]:
        fixed = self.params.get("credits_per_generation")
        if fixed not in (None, ""):
            return float(fixed), "créditos por generación configurados por el usuario"
        key = json.dumps([self.params.get("model"), self.flags_for(request)], sort_keys=True, default=str)
        cache: dict[str, float] = self.__dict__.setdefault("_cost_cache", {})
        if key not in cache:
            try:
                real = self.cli().cost(str(self.params["model"]), "estimate",
                                       to_flags({k: v for k, v in self.flags_for(request).items() if k != "start-image"}))
            except ProviderError:
                real = None
            if real is None:
                return self.fallback_credits, "estimación aproximada (la CLI no dio el coste; se anota el real)"
            cache[key] = real
        return cache[key], "coste en créditos que indica Higgsfield"

    def estimate_cost(self, operation: str, request: Any):
        from .interfaces import CostEstimate
        credits, how = self.estimate_credits(request)
        price = float(self.params.get("price_per_credit_eur") or 0)
        return CostEstimate(amount_eur=round(credits * price, 4), units=credits, unit_name="créditos",
                            detail=f"{credits:g} créditos × {price:g} € ({how})")

    def run_job(self, prompt: str, request: Any) -> tuple[list[str], float]:
        """Generación con freno de saldo. Devuelve (URLs, créditos gastados de verdad)."""
        cli = self.cli()
        est, _ = self.estimate_credits(request)
        with LOCK:
            before = None
            if self.params.get("require_balance_check", True):
                st = cli.status()
                if st["logged_in"] is False:
                    raise ProviderError(NAME, st["message"], transient=False)
                if st["logged_in"] is None:
                    raise ProviderError(NAME, f"No se pudo comprobar la cuenta: {st['message']}", transient=True)
                if st["credits"] is None:
                    raise ProviderError(NAME, "No se pudo leer el saldo de créditos: no se genera a ciegas (puedes "
                                              "quitar la comprobación en Cuentas conectadas)", transient=False)
                before = float(st["credits"])
                reserve = float(self.params.get("reserve_credits") or 0)
                if before - est < reserve:
                    raise ProviderError(NAME, f"Créditos casi agotados: quedan {before:g}, esto gasta ≈{est:g} y la "
                                              f"reserva es {reserve:g}. Se usa la alternativa gratuita.", transient=False)
            urls = cli.generate(str(self.params["model"]), prompt, to_flags(self.flags_for(request)), self.kind,
                                int(self.params.get("wait_minutes") or 15))
            spent = est
            if before is not None:
                try:
                    after = cli.status().get("credits")
                except ProviderError:
                    after = None
                if after is not None and after <= before:
                    spent = before - float(after)
        return urls, spent
