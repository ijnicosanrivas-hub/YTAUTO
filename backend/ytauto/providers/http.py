"""Utilidades HTTP compartidas por los adaptadores de servicios externos.

- Cliente `httpx` con tiempos máximos y transporte inyectable (pruebas con servidor simulado).
- Errores traducidos a `ProviderError`: 429/5xx/red → transitorios; 401/403/4xx → permanentes.
- Los secretos nunca aparecen en los mensajes de error.
"""
from __future__ import annotations

import re
from typing import Any

import httpx

from ..core.errors import ProviderError

TIMEOUT = httpx.Timeout(60.0, connect=15.0)
_SECRET = re.compile(r"(?i)(access_token|refresh_token|client_secret|api[_-]?key|authorization)([\"'=:\s]+)(?:bearer\s+)?([^\s\"'&,}]{4,})")
_BEARER = re.compile(r"(?i)(bearer\s+)([A-Za-z0-9._\-~+/=]{4,})")


def scrub(text: str, secrets: list[str] | None = None) -> str:
    for s in secrets or []:
        if s:
            text = text.replace(s, "***")
    text = _SECRET.sub(lambda m: m.group(1) + m.group(2) + "***", text)
    return _BEARER.sub(lambda m: m.group(1) + "***", text)[:400]


def client(transport: httpx.BaseTransport | None = None, **kw: Any) -> httpx.Client:
    return httpx.Client(transport=transport, timeout=kw.pop("timeout", TIMEOUT), follow_redirects=False, **kw)


def check(provider: str, resp: httpx.Response, secrets: list[str] | None = None, ok: tuple[int, ...] = ()) -> httpx.Response:
    """Lanza ProviderError con la clasificación adecuada si la respuesta no es correcta."""
    if resp.is_success or resp.status_code in ok:
        return resp
    detail = scrub(resp.text, secrets)
    retry_after = None
    if resp.status_code == 429:
        try:
            retry_after = float(resp.headers.get("retry-after", "60"))
        except ValueError:
            retry_after = 60.0
        raise ProviderError(provider, f"límite de uso del servicio (429): {detail}", transient=True,
                            retry_after_s=retry_after)
    transient = resp.status_code >= 500 or resp.status_code == 408
    kind = "autenticación rechazada" if resp.status_code in (401, 403) else "petición rechazada"
    raise ProviderError(provider, f"{kind} ({resp.status_code}): {detail}", transient=transient)


def request(provider: str, c: httpx.Client, method: str, url: str, secrets: list[str] | None = None,
            ok: tuple[int, ...] = (), **kw: Any) -> httpx.Response:
    try:
        resp = c.request(method, url, **kw)
    except httpx.TimeoutException as e:
        raise ProviderError(provider, "tiempo de espera agotado", transient=True) from e
    except httpx.HTTPError as e:
        raise ProviderError(provider, f"error de red: {scrub(str(e), secrets)}", transient=True) from e
    return check(provider, resp, secrets, ok)
