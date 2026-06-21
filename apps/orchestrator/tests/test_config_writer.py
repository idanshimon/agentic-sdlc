"""Tests for config_writer — the governed PR write-back core (#3), REST version.

Path validation and the no-token / dry-run degradation paths need no network.
The happy path is exercised against a mocked httpx transport so we verify the
REST sequence (ref → branch → contents → PR) without hitting GitHub.
"""
from __future__ import annotations

import asyncio

import httpx
import pytest

from apps.orchestrator import config_writer as cw
from apps.orchestrator.config_writer import ConfigWriteError


# ---- path validation (the security boundary) --------------------------------

def test_allows_agent_path():
    assert cw._validate_path(".github/agents/architect.agent.md") == ".github/agents/architect.agent.md"


def test_allows_bundle_and_prompt_paths():
    assert cw._validate_path("standards-bundles/security/v0.1.0/rules.yaml")
    assert cw._validate_path("prompts/global/architect/v1.yaml")


def test_refuses_path_outside_allowed_roots():
    with pytest.raises(ConfigWriteError):
        cw._validate_path("apps/orchestrator/main.py")
    with pytest.raises(ConfigWriteError):
        cw._validate_path("README.md")


def test_refuses_absolute_path():
    with pytest.raises(ConfigWriteError):
        cw._validate_path("/etc/passwd")


def test_refuses_dotdot_escape():
    with pytest.raises(ConfigWriteError):
        cw._validate_path(".github/agents/../../apps/orchestrator/main.py")
    with pytest.raises(ConfigWriteError):
        cw._validate_path("prompts/../../../../etc/hosts")


# ---- slug --------------------------------------------------------------------

def test_slug_sanitizes():
    assert cw._slug("Tighten PHI rule citations!") == "tighten-phi-rule-citations"
    assert cw._slug("") == "edit"


# ---- dry run -----------------------------------------------------------------

def test_dry_run_skips_network(monkeypatch):
    monkeypatch.setattr(cw, "_DRY_RUN", True)
    res = asyncio.run(cw.write_config_pr(
        rel_path=".github/agents/architect.agent.md",
        content="---\nname: architect\n---\n",
        commit_message="test edit",
        pr_title="test PR",
    ))
    assert res.ok is True
    assert res.dry_run is True
    assert res.pr_url is None
    assert res.path == ".github/agents/architect.agent.md"


def test_dry_run_still_validates_path(monkeypatch):
    monkeypatch.setattr(cw, "_DRY_RUN", True)
    with pytest.raises(ConfigWriteError):
        asyncio.run(cw.write_config_pr(
            rel_path="apps/orchestrator/main.py",
            content="malicious", commit_message="x", pr_title="x",
        ))


# ---- no token degrades to a clean ConfigWriteError (honest 422) --------------

def test_missing_token_degrades_to_config_error(monkeypatch):
    monkeypatch.setattr(cw, "_DRY_RUN", False)
    for var in ("CONFIG_GH_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(ConfigWriteError) as ei:
        asyncio.run(cw.write_config_pr(
            rel_path=".github/agents/architect.agent.md",
            content="x", commit_message="x", pr_title="x",
        ))
    assert "token" in str(ei.value).lower()


# ---- happy path against a mocked REST transport ------------------------------

def _mock_transport():
    """A mock GitHub API: ref lookup, branch create, contents 404 (new file),
    PUT, and PR create — the full sequence write_config_pr walks."""
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if request.method == "GET" and "/git/refs/heads/main" in url:
            return httpx.Response(200, json={"object": {"sha": "basesha123"}})
        if request.method == "POST" and url.endswith("/git/refs"):
            return httpx.Response(201, json={"ref": "refs/heads/x"})
        if request.method == "GET" and "/contents/" in url:
            return httpx.Response(404, json={"message": "Not Found"})
        if request.method == "PUT" and "/contents/" in url:
            return httpx.Response(201, json={"content": {"sha": "newfilesha"}})
        if request.method == "POST" and url.endswith("/pulls"):
            return httpx.Response(201, json={
                "html_url": "https://github.com/idanshimon/agentic-sdlc/pull/42",
                "number": 42,
            })
        if request.method == "POST" and "/labels" in url:
            return httpx.Response(200, json=[])
        return httpx.Response(500, json={"message": f"unexpected {request.method} {url}"})
    return httpx.MockTransport(handler)


def test_happy_path_opens_pr(monkeypatch):
    monkeypatch.setattr(cw, "_DRY_RUN", False)
    monkeypatch.setenv("GH_TOKEN", "ghp_faketoken")

    real_client = httpx.AsyncClient

    def patched_client(*a, **kw):
        kw["transport"] = _mock_transport()
        return real_client(*a, **kw)

    monkeypatch.setattr(cw.httpx, "AsyncClient", patched_client)

    res = asyncio.run(cw.write_config_pr(
        rel_path=".github/agents/architect.agent.md",
        content="---\nname: architect\n---\n# edited",
        commit_message="tighten architect role",
        pr_title="Edit architect agent",
        labels=["config-edit", "agent"],
    ))
    assert res.ok is True
    assert res.dry_run is False
    assert res.pr_url == "https://github.com/idanshimon/agentic-sdlc/pull/42"
    assert res.path == ".github/agents/architect.agent.md"


def test_base_branch_missing_is_clean_error(monkeypatch):
    monkeypatch.setattr(cw, "_DRY_RUN", False)
    monkeypatch.setenv("GH_TOKEN", "ghp_faketoken")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Not Found"})

    real_client = httpx.AsyncClient

    def patched_client(*a, **kw):
        kw["transport"] = httpx.MockTransport(handler)
        return real_client(*a, **kw)

    monkeypatch.setattr(cw.httpx, "AsyncClient", patched_client)
    with pytest.raises(ConfigWriteError) as ei:
        asyncio.run(cw.write_config_pr(
            rel_path="prompts/global/architect/v2.yaml",
            content="x", commit_message="x", pr_title="x",
        ))
    assert "base branch" in str(ei.value).lower()
