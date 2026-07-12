"""Tests for the multi-provider abstraction.

Covers:
  - registry resolution
  - APIM routing on aoai (default) + via_apim flag on others
  - Foundry endpoint construction (OAI shape vs Anthropic shape)
  - Databricks coding-agent header
  - Anthropic direct x-api-key auth
  - Config precedence: defaults → YAML → env → per-run override
  - Unknown provider raises
  - Stub fallback when provider raises
"""
from __future__ import annotations

import asyncio
import importlib
import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from apps.orchestrator.providers import (
    AnthropicDirectProvider,
    AOAIProvider,
    DatabricksAnthropicProvider,
    FoundryProvider,
    get_provider,
)
from apps.orchestrator.providers.base import ChatResponse


# --- helpers -----------------------------------------------------------------

def _run(coro):
    return asyncio.run(coro)


def _mock_httpx(handler):
    """Return an httpx.AsyncClient patched to use MockTransport(handler)."""
    transport = httpx.MockTransport(handler)
    orig = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = transport
        return orig(*args, **kwargs)
    return patch("httpx.AsyncClient", side_effect=factory)


# --- 1. registry -------------------------------------------------------------

def test_provider_registry_returns_correct_class():
    assert isinstance(get_provider("aoai"), AOAIProvider)
    assert isinstance(get_provider("foundry"), FoundryProvider)
    assert get_provider("foundry").shape == "foundry-oai"
    assert get_provider("foundry-anthropic").shape == "foundry-anthropic"
    assert isinstance(get_provider("databricks"), DatabricksAnthropicProvider)
    assert isinstance(get_provider("anthropic"), AnthropicDirectProvider)
    assert isinstance(get_provider("anthropic-direct"), AnthropicDirectProvider)


def test_unknown_provider_raises_clear_error():
    with pytest.raises(ValueError, match="unknown provider"):
        get_provider("bogus-llm")


# --- 2. AOAI routes through APIM by default ----------------------------------

def test_aoai_provider_routes_through_apim():
    p = AOAIProvider()
    assert p.via_apim is True
    # base URL strips /openai suffix
    assert "apim" in p.base_url.lower() or p.base_url  # ok if env set differently
    # Direct mode constructed when via_apim=False
    p2 = AOAIProvider(via_apim=False, base_url="https://my-aoai.openai.azure.com")
    assert p2.via_apim is False
    assert p2.base_url == "https://my-aoai.openai.azure.com"


# --- 3. Foundry endpoint construction ----------------------------------------

def test_foundry_oai_endpoint_construction():
    p = FoundryProvider(shape="foundry-oai", base_url="https://my-foundry.azure.com")
    url = p._endpoint("gpt-4-1")
    assert url.startswith("https://my-foundry.azure.com/openai/deployments/gpt-4-1/chat/completions")
    assert "api-version=" in url


def test_foundry_anthropic_endpoint_construction():
    p = FoundryProvider(shape="foundry-anthropic", base_url="https://my-foundry.azure.com")
    assert p._endpoint("claude-sonnet-4-6") == "https://my-foundry.azure.com/v1/messages"


def test_foundry_invalid_shape_raises():
    with pytest.raises(ValueError):
        FoundryProvider(shape="bogus")  # type: ignore[arg-type]


# --- 4. Databricks coding-agent header ---------------------------------------

def test_databricks_provider_includes_coding_agent_header():
    captured = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(req.headers)
        captured["url"] = str(req.url)
        return httpx.Response(200, json={
            "content": [{"type": "text", "text": "hello"}],
            "usage": {"input_tokens": 10, "output_tokens": 5},
        })

    p = DatabricksAnthropicProvider(
        via_apim=False, base_url="https://dbx.example.com", auth_token="tok",
    )
    with _mock_httpx(handler):
        resp = _run(p.chat(
            messages=[{"role": "system", "content": "s"}, {"role": "user", "content": "u"}],
            model="databricks-claude-sonnet-4-6",
        ))
    assert resp.text == "hello"
    assert resp.prompt_tokens == 10 and resp.completion_tokens == 5
    assert captured["headers"]["x-databricks-use-coding-agent-mode"] == "true"
    assert captured["headers"]["authorization"] == "Bearer tok"
    assert captured["url"].endswith("/v1/messages")


# --- 5. Anthropic direct uses x-api-key --------------------------------------

def test_anthropic_direct_uses_x_api_key():
    captured = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(req.headers)
        return httpx.Response(200, json={
            "content": [{"type": "text", "text": "hi"}],
            "usage": {"input_tokens": 1, "output_tokens": 2},
        })

    p = AnthropicDirectProvider(api_key="sk-test", base_url="https://api.anthropic.com")
    with _mock_httpx(handler):
        resp = _run(p.chat(
            messages=[{"role": "user", "content": "x"}],
            model="claude-3-opus",
        ))
    assert resp.text == "hi"
    assert captured["headers"]["x-api-key"] == "sk-test"
    assert "authorization" not in {k.lower() for k in captured["headers"]}


# --- 6. Config precedence: YAML override -------------------------------------

def test_stage_provider_config_yaml_override(tmp_path, monkeypatch):
    # Write a YAML override and reload config from a CWD that contains it.
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "stage_providers:\n"
        "  architect:\n"
        "    provider: foundry-anthropic\n"
        "    model: claude-sonnet-4-6-yaml\n"
        "    via_apim: false\n"
    )
    monkeypatch.chdir(tmp_path)
    # Clear any env overrides for architect so YAML wins
    for k in list(os.environ):
        if k.startswith("STAGE_ARCHITECT_"):
            monkeypatch.delenv(k, raising=False)

    from apps.orchestrator import config as cfg_mod
    importlib.reload(cfg_mod)
    try:
        assert cfg_mod.STAGE_PROVIDERS["architect"]["provider"] == "foundry-anthropic"
        assert cfg_mod.STAGE_PROVIDERS["architect"]["model"] == "claude-sonnet-4-6-yaml"
        assert cfg_mod.STAGE_PROVIDERS["architect"]["via_apim"] is False
    finally:
        # restore default config (no yaml in cwd)
        monkeypatch.chdir(Path(__file__).resolve().parents[3])
        importlib.reload(cfg_mod)


def test_stage_provider_config_env_var_override(monkeypatch):
    monkeypatch.setenv("STAGE_CODEGEN_PROVIDER", "anthropic")
    monkeypatch.setenv("STAGE_CODEGEN_MODEL", "claude-opus-4-7")
    monkeypatch.setenv("STAGE_CODEGEN_VIA_APIM", "true")
    from apps.orchestrator import config as cfg_mod
    importlib.reload(cfg_mod)
    try:
        assert cfg_mod.STAGE_PROVIDERS["codegen"]["provider"] == "anthropic"
        assert cfg_mod.STAGE_PROVIDERS["codegen"]["model"] == "claude-opus-4-7"
        assert cfg_mod.STAGE_PROVIDERS["codegen"]["via_apim"] is True
    finally:
        monkeypatch.delenv("STAGE_CODEGEN_PROVIDER", raising=False)
        monkeypatch.delenv("STAGE_CODEGEN_MODEL", raising=False)
        monkeypatch.delenv("STAGE_CODEGEN_VIA_APIM", raising=False)
        importlib.reload(cfg_mod)


def test_per_run_override_beats_config():
    from apps.orchestrator import config as cfg_mod
    from apps.orchestrator.models import RunState

    run = RunState(team_id="t", stage_provider_overrides={
        "architect": {"provider": "foundry-anthropic", "model": "claude-x", "via_apim": False},
    })
    p = cfg_mod.get_provider_for_stage(run, "architect")
    assert isinstance(p, FoundryProvider)
    assert p.shape == "foundry-anthropic"
    assert getattr(p, "resolved_model", None) == "claude-x"
    assert cfg_mod.get_model_for_stage(run, "architect") == "claude-x"

    # Without override, falls back to config default (databricks for architect)
    run2 = RunState(team_id="t")
    p2 = cfg_mod.get_provider_for_stage(run2, "architect")
    assert isinstance(p2, DatabricksAnthropicProvider)


# --- 7. via_apim flag routes through APIM URL --------------------------------

def test_via_apim_flag_routes_through_apim_url(monkeypatch):
    monkeypatch.setenv("APIM_BASE_URL", "https://apim.example.net/openai/v1")
    monkeypatch.setenv("APIM_SUBSCRIPTION_KEY", "sk-apim")
    from apps.orchestrator import config as cfg_mod
    from apps.orchestrator.providers import foundry as fmod
    from apps.orchestrator.providers import databricks as dmod
    importlib.reload(cfg_mod)
    importlib.reload(fmod)
    importlib.reload(dmod)
    try:
        p = fmod.FoundryProvider(shape="foundry-oai", via_apim=True)
        assert "apim.example.net" in p.base_url
        d = dmod.DatabricksAnthropicProvider(via_apim=True)
        assert "apim.example.net" in d.base_url
    finally:
        monkeypatch.delenv("APIM_BASE_URL", raising=False)
        monkeypatch.delenv("APIM_SUBSCRIPTION_KEY", raising=False)
        importlib.reload(cfg_mod)
        importlib.reload(fmod)
        importlib.reload(dmod)


# --- 8. Provider failure execution profiles ----------------------------------

def test_production_provider_error_fails_closed(monkeypatch):
    from apps.orchestrator import _pipeline_stages as ps
    from apps.orchestrator.models import RunState

    class BoomProvider:
        resolved_model = "gpt-4-1"
        async def chat(self, **kwargs):
            raise RuntimeError("backend down")

    monkeypatch.setenv("EXECUTION_PROFILE", "production")
    run = RunState(team_id="t")
    with patch("apps.orchestrator._pipeline_stages.get_provider_for_stage", return_value=BoomProvider()):
        with pytest.raises(ps.ProviderUnavailable, match="backend down"):
            _run(ps._call(
                run=run, stage_key="assessor", agent_name="assessor",
                system_prompt="s", user_prompt="hello world",
            ))
    assert run.contains_synthetic_output is False


def test_demo_provider_error_stamps_synthetic_output(monkeypatch):
    from apps.orchestrator import _pipeline_stages as ps
    from apps.orchestrator.models import RunState

    class BoomProvider:
        resolved_model = "gpt-4-1"
        async def chat(self, **kwargs):
            raise RuntimeError("backend down")

    monkeypatch.setenv("EXECUTION_PROFILE", "demo")
    run = RunState(team_id="t")
    with patch("apps.orchestrator._pipeline_stages.get_provider_for_stage", return_value=BoomProvider()):
        res = _run(ps._call(
            run=run, stage_key="assessor", agent_name="assessor",
            system_prompt="s", user_prompt="hello world",
        ))
    assert res.text.startswith("[stub:assessor]")
    assert res.synthetic is True
    assert res.error_category == "provider_unavailable"
    assert run.contains_synthetic_output is True
