"""Pruebas del adaptador Claude Code CLI con un ejecutor simulado (no llama a Claude)."""
from __future__ import annotations

import json
import subprocess

import pytest

from ytauto.llm.base import AuthenticationError, LLMError, LLMRequest, ModelUnavailableError, UsageLimitError
from ytauto.llm.claude_cli import ClaudeCodeCLIProvider, extract_json


def req():
    return LLMRequest(agent="director", model="sonnet", task="t", context={"a": 1},
                      output_schema={"type": "object", "properties": {"x": {"type": "integer"}}})


def runner_returning(stdout="", stderr="", code=0, capture=None):
    def run(cmd, stdin, timeout, cwd):
        if capture is not None:
            capture.update(cmd=cmd, stdin=stdin)
        return subprocess.CompletedProcess(cmd, code, stdout, stderr)
    return run


def test_command_uses_print_mode_agent_model_and_schema():
    cap = {}
    out = json.dumps({"type": "result", "is_error": False, "result": "", "structured_output": {"x": 1}})
    p = ClaudeCodeCLIProvider(runner=runner_returning(out, capture=cap))
    resp = p.complete(req())
    cmd = cap["cmd"]
    assert cmd[:2] == ["claude", "-p"]
    assert cmd[cmd.index("--model") + 1] == "sonnet"
    assert cmd[cmd.index("--agent") + 1] == "director"
    assert json.loads(cmd[cmd.index("--json-schema") + 1])["type"] == "object"
    assert cmd[cmd.index("--tools") + 1] == ""
    assert "--no-session-persistence" in cmd
    assert '"a": 1' in cap["stdin"]
    assert resp.data == {"x": 1}


def test_parses_result_text_and_usage():
    out = json.dumps({"is_error": False, "result": "```json\n{\"x\": 2}\n```", "duration_ms": 1500,
                      "num_turns": 1, "total_cost_usd": 0.01, "usage": {"input_tokens": 10, "output_tokens": 5},
                      "modelUsage": {"claude-sonnet-x": {}}})
    resp = ClaudeCodeCLIProvider(runner=runner_returning(out)).complete(req())
    assert resp.data == {"x": 2}
    assert resp.usage.duration_s == 1.5 and resp.usage.model_served == "claude-sonnet-x"
    assert resp.usage.input_tokens == 10


@pytest.mark.parametrize("text,exc", [
    ("Claude AI usage limit reached|1700000000", UsageLimitError),
    ("Error: 429 Too Many Requests", UsageLimitError),
    ("Invalid API key · Please run /login", AuthenticationError),
    ("model claude-opus not available for your plan", ModelUnavailableError),
    ("something odd", LLMError),
])
def test_error_classification(text, exc):
    out = json.dumps({"is_error": True, "result": text})
    with pytest.raises(exc):
        ClaudeCodeCLIProvider(runner=runner_returning(out, code=1)).complete(req())


def test_missing_binary_is_auth_error():
    def run(*a):
        raise FileNotFoundError()
    with pytest.raises(AuthenticationError):
        ClaudeCodeCLIProvider(runner=run).complete(req())


def test_timeout_is_transient_error():
    def run(cmd, *a):
        raise subprocess.TimeoutExpired(cmd, 1)
    with pytest.raises(LLMError) as e:
        ClaudeCodeCLIProvider(runner=run).complete(req())
    assert e.value.transient


def test_extract_json_variants():
    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json('Aquí está:\n{"a": {"b": 2}}\nfin') == {"a": {"b": 2}}
    with pytest.raises(LLMError):
        extract_json("sin json")


@pytest.mark.claude
def test_real_claude_smoke():
    """Solo se ejecuta con `pytest -m claude` en una máquina con `claude /login` hecho."""
    p = ClaudeCodeCLIProvider(use_agent_flag=False, timeout_s=180)
    r = p.complete(LLMRequest(agent="smoke", model="haiku", task="Devuelve x=7", context={},
                              output_schema={"type": "object", "properties": {"x": {"type": "integer"}},
                                             "required": ["x"]}))
    assert r.data.get("x") == 7
