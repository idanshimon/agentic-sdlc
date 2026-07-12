"""Phase 4 refusal-ledger tests — a model-policy refusal is AUDITED, not silent.

openspec scenario "denied model blocks the stage" / "PHI-adjacent stage requires
a cleared model": when a stage is refused by config/models.yaml, the run fails
AND a ledger entry is written citing the governing model-policy rule (the audit
answer the compliance query reads). A refused run must never be indistinguishable
from a crash — the WHY has to be queryable.
"""
from __future__ import annotations

import asyncio

import pytest

from apps.orchestrator import _pipeline_stages as ps
from apps.orchestrator import main as m
from apps.orchestrator.models import RunState, RunStatus


def test_model_refusal_writes_ledger_entry_citing_rule(monkeypatch):
    captured = []

    class FakeLedger:
        async def write_decision(self, entry):
            captured.append(entry)
            return entry
        async def save_run_cas(self, run):
            return None
        async def save_run(self, run):
            return None

    monkeypatch.setattr(m, "_ledger", FakeLedger())

    refusal = ps.ModelPolicyRefusal(
        stage="codegen", model="gpt-4-1-mini",
        reason="model 'gpt-4-1-mini' is not phi_eligible but stage 'codegen' is PHI-adjacent",
        rule_ref="models/phi_eligible/codegen/gpt-4-1-mini",
    )
    run = RunState(team_id="cardiology", prd_blob_url="x")

    asyncio.run(m._write_model_refusal_entry(run, refusal))

    assert len(captured) == 1, "a model-policy refusal must write exactly one ledger entry"
    entry = captured[0]
    # cites the governing rule in the queryable autonomy_ref field
    assert entry.autonomy_ref == "models/phi_eligible/codegen/gpt-4-1-mini"
    assert entry.team_id == "cardiology"
    assert entry.run_id == run.run_id
    # decision text names the refusal so the compliance row is self-explaining
    assert "gpt-4-1-mini" in (entry.resolution_text or entry.decision or "")


def test_write_refusal_is_safe_when_ledger_disabled(monkeypatch):
    # _ledger None (bootstrap/test) must not raise — refusal still fails the run
    monkeypatch.setattr(m, "_ledger", None)
    refusal = ps.ModelPolicyRefusal(
        stage="assessor", model="bad", reason="denylist", rule_ref="models/denylist/bad",
    )
    run = RunState(team_id="t", prd_blob_url="x")
    # no raise
    asyncio.run(m._write_model_refusal_entry(run, refusal))


def test_drive_marks_run_failed_on_model_refusal(monkeypatch):
    """End-to-end-ish: a refusal raised from a stage generator flips the run to
    FAILED and emits a failed StageEvent (not a silent hang)."""
    captured = []

    class FakeLedger:
        async def write_decision(self, entry):
            captured.append(entry)
        async def save_run_cas(self, run):
            return None
        async def save_run(self, run):
            return None

    monkeypatch.setattr(m, "_ledger", FakeLedger())

    async def _boom(run, *a, **k):
        raise ps.ModelPolicyRefusal(
            stage="assessor", model="bad-model", reason="not on allowlist",
            rule_ref="models/allowlist/bad-model",
        )
        yield  # make it an async generator

    monkeypatch.setattr(m, "stage_ingest", _boom)

    run = RunState(team_id="cardiology", prd_blob_url="x")
    m._runs[run.run_id] = run
    try:
        asyncio.run(m._drive(run.run_id, "some prd"))
    finally:
        m._runs.pop(run.run_id, None)

    assert run.status == RunStatus.FAILED
    assert any(e.autonomy_ref == "models/allowlist/bad-model" for e in captured), \
        "refusal ledger entry must be written when _drive catches the refusal"
