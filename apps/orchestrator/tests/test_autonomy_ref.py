"""Autonomy-ref audit tests — closing the "why autopilot vs gate" loop.

The autonomy rule that governed each decision must be a stable, queryable field
on the ledger entry (the audit answer the Phase 5 compliance query reads). These
tests cover:
  - autonomy_ref() citation shape per mode (matrix, threshold, invariant, bootstrap)
  - the field survives model_dump(mode="json") to the Cosmos document
  - both ledger models (orchestrator-local + ledger-core) carry the field
  - an autopilot decision through _run_autopilot stamps a non-empty ref
"""
from __future__ import annotations

import asyncio

import pytest

from apps.orchestrator import autonomy as au


# ---- citation shape ---------------------------------------------------------

def test_ref_invariant_is_hard_lock_tagged():
    ref = au.autonomy_ref("cardiology", "phi-classification")
    assert ref == "autonomy/invariant/phi-classification/gate:phi-auth-hard-lock"
    ref2 = au.autonomy_ref("anyteam", "auth-policy")
    assert "invariant" in ref2 and "gate" in ref2


def test_ref_matrix_threshold_encodes_scope_and_threshold(tmp_path):
    p = tmp_path / "autonomy.yaml"
    p.write_text(
        'teams:\n'
        '  cardiology:\n'
        '    sla-binding: { mode: autopilot_above_threshold, threshold: 0.75 }\n'
    )
    m = au.load_autonomy_matrix(str(p))
    ref = au.autonomy_ref("cardiology", "sla-binding", matrix=m, reason="precedent0.9>=t0.75")
    assert ref.startswith("autonomy/matrix/cardiology/sla-binding/autopilot_above_threshold@t=0.75")
    assert ref.endswith(":precedent0.9>=t0.75")


def test_ref_default_row_scope_is_star(tmp_path):
    p = tmp_path / "autonomy.yaml"
    p.write_text('teams:\n  "*":\n    naming-convention: autopilot_always\n')
    m = au.load_autonomy_matrix(str(p))
    ref = au.autonomy_ref("someteam", "naming-convention", matrix=m, reason="autopilot-always")
    # scope resolves to "*" because no exact (someteam, naming-convention) row
    assert ref.startswith("autonomy/matrix/*/naming-convention/autopilot_always")


def test_ref_bootstrap_when_no_matrix():
    empty = au.load_autonomy_matrix("/nonexistent/none.yaml")
    ref = au.autonomy_ref("cardiology", "sla-binding", matrix=empty, reason="autopilot-mode")
    assert ref.startswith("autonomy/mode/bootstrap/sla-binding/gate")
    assert ref.endswith(":autopilot-mode")


# ---- both models carry the field, and it survives serialization ------------

def test_orchestrator_ledgerentry_has_autonomy_ref_and_serializes():
    from apps.orchestrator.models import LedgerEntry
    e = LedgerEntry(team_id="t", run_id="r", autonomy_ref="autonomy/matrix/cardiology/sla-binding/autopilot_always")
    doc = e.model_dump(mode="json")
    assert doc["autonomy_ref"] == "autonomy/matrix/cardiology/sla-binding/autopilot_always"


def test_ledger_core_ledgerentry_has_autonomy_ref_and_serializes():
    from ledger_core import LedgerEntry
    from ledger_core.models import Actor
    e = LedgerEntry(
        team_id="t", run_id="r", actor=Actor(kind="agent", id="autopilot:t"),
        decision="auto", runtime_kind="stage_decision",
        autonomy_ref="autonomy/mode/bootstrap/sla-binding/gate:autopilot-mode",
    )
    doc = e.model_dump(mode="json")
    assert doc["autonomy_ref"].startswith("autonomy/mode/bootstrap/")


def test_default_autonomy_ref_is_empty_string():
    """Pre-Phase-2 / non-decision entries must default to '' (not None) so the
    query can filter on it without null handling."""
    from apps.orchestrator.models import LedgerEntry as OrchEntry
    assert OrchEntry(team_id="t", run_id="r").autonomy_ref == ""


# ---- end-to-end: an autopilot decision stamps a non-empty ref --------------

def test_autopilot_decision_stamps_autonomy_ref(monkeypatch):
    """Through _run_autopilot in bootstrap AUTOPILOT mode, the auto-decision's
    ledger entry must carry a non-empty autonomy_ref explaining the auto-resolve."""
    from apps.orchestrator import main as m
    from apps.orchestrator.models import (
        RunState, RunMode, AmbiguityCard, ResolutionOption,
    )

    # bootstrap (no matrix) so this is the mode-driven autopilot path
    au.reload_autonomy_matrix("/nonexistent/none.yaml")

    captured = []

    class FakeLedger:
        async def write_decision(self, entry):
            captured.append(entry)
            return entry
        async def find_precedent(self, *a, **k):
            return None

    monkeypatch.setattr(m, "_ledger", FakeLedger())

    card = AmbiguityCard(
        card_id="c1", ambiguity_class="data-retention", slot_value_hash="h1",
        title="Retention window", detail="", is_gating=True,
        options=[ResolutionOption(label="7y", resolution="Retain 7 years",
                                  rationale="HIPAA", downstream_impact="x", recommended=True)],
    )
    run = RunState(team_id="cardiology", prd_blob_url="x", mode=RunMode.AUTOPILOT)
    run.cards = [card]

    try:
        asyncio.run(m._run_autopilot(run))
    finally:
        au.reload_autonomy_matrix()  # restore default singleton

    assert len(captured) == 1, "expected one auto-decision ledger write"
    ref = captured[0].autonomy_ref
    assert ref, "autopilot decision must carry a non-empty autonomy_ref"
    assert ref.startswith("autonomy/"), f"unexpected ref shape: {ref!r}"
    assert "data-retention" in ref
