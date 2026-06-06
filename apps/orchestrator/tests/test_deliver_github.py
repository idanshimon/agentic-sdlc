"""Tests for deliver_github stage with httpx MockTransport."""
from __future__ import annotations
import sys
import json
import pytest
import httpx
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Make this test run without orchestrator FastAPI deps:
# add the orchestrator dir to sys.path so we can import as a package
ORCH_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ORCH_ROOT.parent))

from orchestrator.models import RunState, RunStatus, Stage


def _make_config(target_repo="idanshimon/agentic-sdlc-target"):
    cfg = MagicMock()
    cfg.github_app_id = "1234567"
    cfg.github_app_private_key = "-----BEGIN RSA PRIVATE KEY-----\nfake\n-----END RSA PRIVATE KEY-----"
    cfg.github_app_installation_id = 99999
    cfg.github_default_target_repo = target_repo
    cfg.delivery_overrides = {}
    cfg.deliver_provider = "github"
    return cfg


def _make_run():
    return RunState(
        run_id="run-test-1",
        team_id="team-demo",
        status=RunStatus.COMPLETED,
        current_stage=Stage.DELIVER,
        cards=[],
        decisions=[],
        events=[],
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
    )


@pytest.mark.asyncio
async def test_resolve_target_repo_default():
    """Without per-team override, falls back to github_default_target_repo."""
    from orchestrator.stages.deliver_github import _resolve_target_repo
    cfg = _make_config()
    assert _resolve_target_repo("team-demo", cfg) == "idanshimon/agentic-sdlc-target"


@pytest.mark.asyncio
async def test_resolve_target_repo_override():
    from orchestrator.stages.deliver_github import _resolve_target_repo
    cfg = _make_config()
    cfg.delivery_overrides = {"team-demo": {"target_repo": "custom/repo"}}
    assert _resolve_target_repo("team-demo", cfg) == "custom/repo"


@pytest.mark.asyncio
async def test_resolve_installation_id_override():
    from orchestrator.stages.deliver_github import _resolve_installation_id
    cfg = _make_config()
    cfg.delivery_overrides = {"team-demo": {"installation_id": 12345}}
    assert _resolve_installation_id("team-demo", cfg) == 12345


@pytest.mark.asyncio
async def test_render_pr_body_includes_run_id():
    from orchestrator.stages.deliver_github import _render_pr_body
    run = _make_run()
    body = _render_pr_body(run)
    assert run.run_id in body
    assert run.team_id in body
    assert "Decision Ledger" in body


@pytest.mark.asyncio
async def test_b64_round_trips():
    from orchestrator.stages.deliver_github import _b64
    import base64
    s = "hello world\nwith newline"
    encoded = _b64(s)
    decoded = base64.b64decode(encoded).decode("utf-8")
    assert decoded == s


@pytest.mark.asyncio
async def test_dispatcher_returns_correct_fn():
    """The stages.__init__ dispatcher returns the right function per provider."""
    from orchestrator.stages import get_deliver_fn, deliver_to_github, deliver_to_ado
    assert get_deliver_fn("github") is deliver_to_github
    assert get_deliver_fn("ado") is deliver_to_ado


@pytest.mark.asyncio
async def test_dispatcher_rejects_unknown_provider():
    from orchestrator.stages import get_deliver_fn
    with pytest.raises(ValueError, match="Unknown deliver_provider"):
        get_deliver_fn("gitlab")


@pytest.mark.asyncio
async def test_deliver_ado_stub_returns_error():
    """ADO path is a v0.7 placeholder; should return error indicator."""
    from orchestrator.stages.deliver_ado import deliver_to_ado
    cfg = _make_config()
    run = _make_run()
    result = await deliver_to_ado(run, cfg, ledger_client=None)
    assert result["pr_url"] is None
    assert "error" in result
    assert "not implemented" in result["error"]
