"""End-to-end test for the self-heal cowork loop via the orchestrator endpoints.

Proves the WORKING MVP: open heal → diagnose (brain) → validate → approve
(human) → execute (executor) → 3-entry ledger chain. Runs against the stub
brain + stub executor (no live runtime needed), which is exactly the
config-selected default for offline/demo.

Also proves the config-selectability: swapping HEAL_EXECUTOR changes which
executor runs, with zero endpoint changes.

Run: PYTHONPATH=. .venv/bin/python -m pytest apps/orchestrator/tests/test_heal_loop.py -v
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from apps.orchestrator import main as main_mod
from apps.orchestrator.heal_runtime import (
    StubBrain, StubExecutor, AzureExecutor, GitHubExecutor,
    get_brain, get_executor, reload_heal_settings,
)
from apps.orchestrator.models import RunMode, RunState, RunStatus, Stage


@pytest.fixture
def client():
    return TestClient(main_mod.app)


@pytest.fixture
def failed_run():
    """Seed a failed run directly into the in-memory store."""
    run = RunState(
        run_id="heal-test-run-1", team_id="cardiology",
        mode=RunMode.MANUAL, status=RunStatus.FAILED, current_stage=Stage.CODEGEN,
    )
    main_mod._runs[run.run_id] = run
    yield run
    main_mod._runs.pop(run.run_id, None)
    # clear any heal sessions created
    main_mod._heal_sessions.clear()


# --- config selectability (BOTH paths, configurable) -------------------------
def test_executor_is_config_selected():
    assert isinstance(get_executor("stub"), StubExecutor)
    assert isinstance(get_executor("github"), GitHubExecutor)
    assert isinstance(get_executor("azure"), AzureExecutor)


def test_brain_is_config_selected():
    # azure/github brains fall back to stub (reserved slots) but the selection
    # path works and never crashes.
    assert get_brain("stub").name == "stub"
    assert get_brain("azure").name == "stub"   # reserved, falls back
    assert get_brain("github").name == "stub"  # reserved, falls back


def test_env_var_selects_executor(monkeypatch):
    monkeypatch.setenv("HEAL_EXECUTOR", "azure")
    reload_heal_settings()
    assert get_executor().name == "azure"
    monkeypatch.setenv("HEAL_EXECUTOR", "stub")
    reload_heal_settings()
    assert get_executor().name == "stub"


# --- the working MVP loop, end to end ----------------------------------------
def test_full_heal_loop_stub_path(client, failed_run, monkeypatch):
    monkeypatch.setenv("HEAL_EXECUTOR", "stub")
    monkeypatch.setenv("HEAL_BRAIN", "stub")
    monkeypatch.setenv("HEAL_ACTIONS_ENABLED", "true")
    reload_heal_settings()

    # 1. open heal session (human-invoked, at run end)
    r = client.post(f"/api/runs/{failed_run.run_id}/heal")
    assert r.status_code == 200, r.text
    opened = r.json()
    heal_id = opened["heal_id"]
    assert opened["trigger"] == "at_run_end"
    assert opened["action"]["action_type"] == "assign_code_heal"
    assert opened["can_execute"] is True
    assert opened["requires_human_approval"] is True

    # 2. fetch session state
    r = client.get(f"/api/heal/{heal_id}")
    assert r.status_code == 200
    assert r.json()["decision"] is None

    # 3. human approves → executor lands the heal
    r = client.post(f"/api/heal/{heal_id}/approve",
                    json={"approver_id": "idan@microsoft.com", "approved": True})
    assert r.status_code == 200, r.text
    done = r.json()
    assert done["approved"] is True
    assert done["executed"] is True
    assert done["executor"] == "stub"
    # code heal → a PR-shaped url, never a bare commit
    assert "/pull/" in done["result_ref"]

    # 4. session now carries the full chain
    r = client.get(f"/api/heal/{heal_id}")
    state = r.json()
    assert state["decision"]["approved"] is True
    # Client-provided approver_id is untrusted; audit identity comes from auth.
    assert state["decision"]["approver_id"] == "development-principal"
    assert state["execution"]["success"] is True


def test_decline_does_not_execute(client, failed_run):
    reload_heal_settings()
    heal_id = client.post(f"/api/runs/{failed_run.run_id}/heal").json()["heal_id"]
    r = client.post(f"/api/heal/{heal_id}/approve",
                    json={"approver_id": "idan@microsoft.com", "approved": False})
    assert r.status_code == 200
    assert r.json()["executed"] is False
    # no execution recorded
    assert client.get(f"/api/heal/{heal_id}").json()["execution"] is None


def test_actions_disabled_blocks_open(client, failed_run, monkeypatch):
    monkeypatch.setenv("HEAL_ACTIONS_ENABLED", "false")
    reload_heal_settings()
    r = client.post(f"/api/runs/{failed_run.run_id}/heal")
    assert r.status_code == 403
    monkeypatch.setenv("HEAL_ACTIONS_ENABLED", "true")
    reload_heal_settings()


def test_running_run_cannot_open_heal(client, monkeypatch):
    monkeypatch.setenv("HEAL_ACTIONS_ENABLED", "true")
    reload_heal_settings()
    run = RunState(run_id="heal-running-1", team_id="t", mode=RunMode.MANUAL,
                   status=RunStatus.RUNNING, current_stage=Stage.CODEGEN)
    main_mod._runs[run.run_id] = run
    try:
        r = client.post(f"/api/runs/{run.run_id}/heal")
        # running is neither awaiting_gate nor terminal → 409
        assert r.status_code == 409
    finally:
        main_mod._runs.pop(run.run_id, None)


def test_azure_executor_rerun_path_is_real(client, monkeypatch):
    """The Azure executor's rerun path returns a real rerun ref (not a fake PR)."""
    import asyncio
    from apps.orchestrator.heal import HealProposal, HealAction, HealActionType, HealTrigger
    proposal = HealProposal(
        run_id="r1", team_id="t", trigger=HealTrigger.AT_RUN_END,
        action=HealAction(action_type=HealActionType.RERUN_STAGE, summary="rerun", stage="codegen"),
    )
    ex = AzureExecutor()
    result = asyncio.run(ex.execute(proposal))
    assert result.success is True
    assert result.result_ref.startswith("rerun://")


def test_azure_executor_code_heal_is_honest_not_faked(client):
    """The Azure code-PR path is not yet wired — it must say so, NOT fake a PR."""
    import asyncio
    from apps.orchestrator.heal import HealProposal, HealAction, HealActionType, HealTrigger
    proposal = HealProposal(
        run_id="r1", team_id="t", trigger=HealTrigger.AT_RUN_END,
        action=HealAction(action_type=HealActionType.ASSIGN_CODE_HEAL, summary="fix", stage="codegen"),
    )
    ex = AzureExecutor()
    result = asyncio.run(ex.execute(proposal))
    assert result.success is False
    assert result.result_ref == ""
    assert "managed-identity" in result.detail
