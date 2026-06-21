"""Tests for config_writer — the governed PR write-back core (#3).

Focus on the security boundary (_validate_path) and dry-run, which need no git.
The full git/gh path is exercised in integration, not here.
"""
from __future__ import annotations

import asyncio
import pytest

from apps.orchestrator import config_writer as cw
from apps.orchestrator.config_writer import ConfigWriteError


# ---- path validation (the security boundary) --------------------------------

def test_allows_agent_path():
    p = cw._validate_path(".github/agents/architect.agent.md")
    assert p.name == "architect.agent.md"


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

def test_dry_run_skips_git(monkeypatch):
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
    assert "architect.agent.md" in res.path


def test_dry_run_still_validates_path(monkeypatch):
    monkeypatch.setattr(cw, "_DRY_RUN", True)
    with pytest.raises(ConfigWriteError):
        asyncio.run(cw.write_config_pr(
            rel_path="apps/orchestrator/main.py",
            content="malicious",
            commit_message="x",
            pr_title="x",
        ))
