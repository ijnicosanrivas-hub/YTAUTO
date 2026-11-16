"""Almacén cifrado de credenciales de proveedores (Fernet / AES-128-CBC + HMAC).

- La clave maestra viene de `YTAUTO_MASTER_KEY` o, si no existe, de un fichero
  `data/secrets/master.key` creado con permisos 600 (fuera del repositorio).
- Las credenciales se guardan cifradas en SQLite; la interfaz solo recibe una pista
  enmascarada (`••••abcd`). Nunca se devuelven completas por la API.
"""
from __future__ import annotations

import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine

from ...core.errors import YtautoError
from ...core.models import utcnow
from ...db import schema as s


class VaultError(YtautoError):
    pass


def load_or_create_master_key(env_key: str | None, key_file: Path) -> bytes:
    if env_key:
        return env_key.encode()
    if key_file.exists():
        return key_file.read_bytes().strip()
    key_file.parent.mkdir(parents=True, exist_ok=True)
    key = Fernet.generate_key()
    fd = os.open(str(key_file), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(key)
    return key


def mask(value: str) -> str:
    return "••••" + value[-4:] if len(value) > 8 else "••••"


class CredentialVault:
    def __init__(self, engine: Engine, master_key: bytes):
        try:
            self._fernet = Fernet(master_key)
        except (ValueError, TypeError) as e:
            raise VaultError("YTAUTO_MASTER_KEY no es una clave Fernet válida") from e
        self.engine = engine
        s.init_db(engine)

    def set(self, provider_id: str, key: str, value: str) -> str:
        if not value:
            raise VaultError("La credencial no puede estar vacía")
        token = self._fernet.encrypt(value.encode()).decode()
        hint = mask(value)
        stmt = sqlite_insert(s.credentials).values(provider_id=provider_id, key=key, ciphertext=token, hint=hint,
                                                   updated_at=utcnow().isoformat())
        stmt = stmt.on_conflict_do_update(index_elements=["provider_id", "key"],
                                          set_={"ciphertext": token, "hint": hint, "updated_at": utcnow().isoformat()})
        with self.engine.begin() as c:
            c.execute(stmt)
        return hint

    def get_all(self, provider_id: str) -> dict[str, str]:
        """Solo para uso interno del registro al instanciar adaptadores."""
        with self.engine.connect() as c:
            rows = c.execute(select(s.credentials).where(s.credentials.c.provider_id == provider_id)).mappings().all()
        out = {}
        for r in rows:
            try:
                out[r["key"]] = self._fernet.decrypt(r["ciphertext"].encode()).decode()
            except InvalidToken as e:
                raise VaultError(f"No se puede descifrar la credencial '{r['key']}' de {provider_id}: "
                                 "¿ha cambiado la clave maestra?") from e
        return out

    def hints(self, provider_id: str) -> dict[str, str]:
        with self.engine.connect() as c:
            rows = c.execute(select(s.credentials.c.key, s.credentials.c.hint)
                             .where(s.credentials.c.provider_id == provider_id)).all()
        return {k: h for k, h in rows}

    def delete(self, provider_id: str, key: str | None = None) -> None:
        q = delete(s.credentials).where(s.credentials.c.provider_id == provider_id)
        if key:
            q = q.where(s.credentials.c.key == key)
        with self.engine.begin() as c:
            c.execute(q)
