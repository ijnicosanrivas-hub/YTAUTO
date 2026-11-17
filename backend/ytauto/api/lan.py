"""Acceso desde otros dispositivos de la red local (p. ej. el iPhone) con un código de acceso.

El servidor solo escucha fuera de este ordenador si hay token. Aquí se genera y guarda uno (fuera de git,
en `data/`) y se calculan las direcciones que debe abrir el móvil.
"""
from __future__ import annotations

import ipaddress
import secrets
import socket
from pathlib import Path

TOKEN_FILE = "lan_token.txt"
LINK_FILE = "acceso_movil.txt"


def ensure_lan_token(data_dir: Path) -> str:
    """Devuelve el código de acceso guardado o crea uno nuevo (12 caracteres, no adivinable)."""
    path = data_dir / TOKEN_FILE
    try:
        existing = path.read_text(encoding="utf-8").strip()
        if len(existing) >= 8:
            return existing
    except OSError:
        pass
    token = secrets.token_urlsafe(9)
    data_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(token + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:  # Windows: sin permisos POSIX
        pass
    return token


def is_lan_address(ip: str) -> bool:
    """Dirección privada de una red doméstica (192.168.x.x, 10.x.x.x, 172.16-31.x.x); no loopback ni link-local."""
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return a.version == 4 and a.is_private and not a.is_loopback and not a.is_link_local


def local_addresses() -> list[str]:
    """Direcciones de este equipo en la red local, la principal primero."""
    found: list[str] = []
    try:  # la interfaz que usaría para salir a Internet (no envía ningún paquete)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            found.append(s.getsockname()[0])
    except OSError:
        pass
    try:
        found += socket.gethostbyname_ex(socket.gethostname())[2]
    except OSError:
        pass
    out: list[str] = []
    for ip in found:
        if is_lan_address(ip) and ip not in out:
            out.append(ip)
    return out


def lan_urls(addresses: list[str], port: int, token: str) -> list[str]:
    """Enlaces completos (con el código de acceso) para abrir en el móvil."""
    return [f"http://{ip}:{port}/?token={token}" for ip in addresses]
