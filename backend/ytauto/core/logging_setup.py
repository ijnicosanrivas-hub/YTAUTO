"""Logs con rotación y ocultación de secretos."""
from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

_SECRET_PATTERNS = [
    re.compile(r"(sk-[A-Za-z0-9_\-]{8,})"),
    re.compile(r"(?i)((?:api[_-]?key|token|secret|password|authorization)[\"'\s:=]+(?:bearer\s+)?)([^\s\"',}]{6,})"),
    re.compile(r"(gAAAAA[A-Za-z0-9_\-=]{20,})"),  # tokens Fernet
]


def redact(text: str) -> str:
    for pat in _SECRET_PATTERNS:
        if pat.groups >= 2:
            text = pat.sub(lambda m: m.group(1) + "***", text)
        else:
            text = pat.sub(lambda m: m.group(1)[:4] + "***", text)
    return text


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(str(record.getMessage()))
        record.args = ()
        return True


def setup_logging(logs_dir: Path, level: int = logging.INFO) -> None:
    logs_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger("ytauto")
    if any(getattr(h, "_ytauto", False) for h in root.handlers):
        return
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    fh = RotatingFileHandler(logs_dir / "ytauto.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8")
    fh.setFormatter(fmt)
    fh.addFilter(RedactingFilter())
    fh._ytauto = True  # type: ignore[attr-defined]
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    sh.addFilter(RedactingFilter())
    sh._ytauto = True  # type: ignore[attr-defined]
    root.addHandler(fh)
    root.addHandler(sh)
    root.setLevel(level)
