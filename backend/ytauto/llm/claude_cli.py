"""Adaptador que usa el binario oficial de Claude Code en modo no interactivo.

Usa la sesión iniciada con `claude /login` (suscripción Pro). No usa la API de Anthropic,
no lee ni reutiliza tokens y no lanza instancias en paralelo: la concurrencia la limita la
cola central.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

from .base import (
    AuthenticationError,
    LLMError,
    LLMProvider,
    LLMRequest,
    LLMResponse,
    LLMUsage,
    ModelUnavailableError,
    UsageLimitError,
    render_prompt,
)

_LIMIT_PATTERNS = re.compile(
    r"(usage limit|rate limit|limit reached|too many requests|\b429\b|quota|"
    r"límite de uso|out of (extra )?usage)",
    re.IGNORECASE,
)
_AUTH_PATTERNS = re.compile(
    r"(not logged in|please run /login|invalid api key|authentication|unauthorized|\b401\b|"
    r"oauth token|login required)",
    re.IGNORECASE,
)
_MODEL_PATTERNS = re.compile(
    r"(model .*(not found|not available|unavailable|does not exist)|invalid model|"
    r"not have access to .*model)",
    re.IGNORECASE,
)
_RESET_PATTERN = re.compile(r"reset[s]? (?:at )?([^\n.|]+)", re.IGNORECASE)

Runner = Callable[[list[str], str, float, Path], subprocess.CompletedProcess]


def _default_runner(cmd: list[str], stdin: str, timeout: float, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, input=stdin, capture_output=True, text=True, timeout=timeout, cwd=str(cwd)
    )


def classify_error(text: str) -> LLMError:
    if _LIMIT_PATTERNS.search(text):
        epoch = re.search(r"\|\s*(\d{10})\b", text)  # formato "usage limit reached|<epoch>"
        if epoch:
            return UsageLimitError(text.strip()[:500], resets_at=epoch.group(1))
        m = _RESET_PATTERN.search(text)
        return UsageLimitError(text.strip()[:500], resets_at=m.group(1).strip() if m else None)
    if _AUTH_PATTERNS.search(text):
        return AuthenticationError(text.strip()[:500])
    if _MODEL_PATTERNS.search(text):
        return ModelUnavailableError(text.strip()[:500])
    return LLMError(text.strip()[:500] or "Error desconocido de Claude Code")


def extract_json(text: str) -> dict[str, Any]:
    """Extrae el primer objeto JSON de un texto (admite bloques ```json)."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        obj = json.loads(text[start : end + 1])
        if isinstance(obj, dict):
            return obj
    raise LLMError("La respuesta de Claude no contiene un objeto JSON válido")


class ClaudeCodeCLIProvider(LLMProvider):
    name = "claude_cli"

    def __init__(
        self,
        claude_bin: str = "claude",
        workdir: Path | None = None,
        timeout_s: float = 600,
        use_agent_flag: bool = True,
        runner: Runner | None = None,
    ):
        self.claude_bin = claude_bin
        self.workdir = workdir or Path(__file__).resolve().parents[3]
        self.timeout_s = timeout_s
        self.use_agent_flag = use_agent_flag
        self._run = runner or _default_runner

    def build_command(self, request: LLMRequest) -> list[str]:
        cmd = [
            self.claude_bin,
            "-p",
            "--output-format", "json",
            "--model", request.model,
            "--json-schema", json.dumps(request.output_schema, ensure_ascii=False),
            "--tools", "",  # los agentes creativos no necesitan herramientas
            "--no-session-persistence",
        ]
        if self.use_agent_flag:
            cmd += ["--agent", request.agent]
        return cmd

    def complete(self, request: LLMRequest) -> LLMResponse:
        cmd = self.build_command(request)
        prompt = render_prompt(request)
        t0 = time.monotonic()
        try:
            proc = self._run(cmd, prompt, self.timeout_s, self.workdir)
        except FileNotFoundError as e:
            raise AuthenticationError(
                f"No se encuentra el binario '{self.claude_bin}'. Instala Claude Code."
            ) from e
        except subprocess.TimeoutExpired as e:
            raise LLMError(f"Claude Code superó el tiempo máximo ({self.timeout_s}s)") from e
        elapsed = time.monotonic() - t0

        stdout, stderr = proc.stdout or "", proc.stderr or ""
        envelope: dict[str, Any] | None = None
        try:
            envelope = json.loads(stdout) if stdout.strip() else None
        except json.JSONDecodeError:
            envelope = None

        if proc.returncode != 0 or (envelope and envelope.get("is_error")):
            detail = " ".join(
                str(x) for x in [
                    (envelope or {}).get("result", ""),
                    (envelope or {}).get("subtype", ""),
                    stderr,
                    stdout if envelope is None else "",
                ] if x
            )
            raise classify_error(detail)

        if envelope is None:
            raise LLMError("Salida de Claude Code no reconocida")

        if isinstance(envelope.get("structured_output"), dict):
            data = envelope["structured_output"]
        else:
            data = extract_json(str(envelope.get("result", "")))

        return LLMResponse(data=data, raw_text=str(envelope.get("result", "")), usage=self._usage(envelope, elapsed))

    @staticmethod
    def _usage(envelope: dict[str, Any], elapsed: float) -> LLMUsage:
        usage = envelope.get("usage") or {}
        model_usage = envelope.get("modelUsage") or {}
        served = next(iter(model_usage), None) if isinstance(model_usage, dict) else None
        return LLMUsage(
            duration_s=round(envelope.get("duration_ms", elapsed * 1000) / 1000, 2),
            model_served=served,
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            cost_usd_equivalent=envelope.get("total_cost_usd"),
            num_turns=envelope.get("num_turns"),
        )

    def health_check(self) -> tuple[bool, str]:
        if not shutil.which(self.claude_bin) and not Path(self.claude_bin).exists():
            return False, f"Binario '{self.claude_bin}' no encontrado"
        try:
            proc = self._run([self.claude_bin, "--version"], "", 30, self.workdir)
        except Exception as e:  # pragma: no cover - depende del sistema
            return False, str(e)
        return proc.returncode == 0, (proc.stdout or proc.stderr).strip()
