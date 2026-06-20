"""Tier-2 governance tests — hard-gate classes (PHI/auth) cannot be bulk-approved.

Covers the plan's Task 7:
- HARD_GATE_CLASSES defaults to INVARIANT_CLASSES
- env EXTENDS the floor but can never shrink it (PHI/auth always present)
- /approve rejects approval_path="bulk" on a hard-gated card with 409
- /approve accepts approval_path="individual" on the same card
- non-hard-gated classes accept bulk freely
- GET /api/config/hard-gate-classes surfaces the posture

Run: PYTHONPATH=. .venv/bin/python -m pytest apps/orchestrator/tests/test_hard_gate.py -v
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from apps.orchestrator import config as cfg
from apps.orchestrator.main import app, _runs
from apps.orchestrator.models import (
    INVARIANT_CLASSES, AmbiguityCard, ResolutionOption, RunState, RunStatus, Stage,
)


@pytest.fixture
def client():
    return TestClient(app)


def _seed_run(ambiguity_class: str, card_id: str = "hg-card-1") -> RunState:
    rec = ResolutionOption(
        label="rec", resolution="Recommended resolution text.",
        rationale="why", downstream_impact="impact", recommended=True,
    )
    alt = ResolutionOption(
        label="alt", resolution="Alternative resolution text.",
        rationale="why2", downstream_impact="impact2",
    )
    card = AmbiguityCard(
        card_id=card_id, title="t", detail="d",
        ambiguity_class=ambiguity_class, slot_value_hash="h", options=[rec, alt],
    )
    run = RunState(
        team_id="cardiology", run_id=f"run-{card_id}", prd_blob_url="x",
        status=RunStatus.AWAITING_GATE, current_stage=Stage.RESOLVER, cards=[card],
    )
    _runs[run.run_id] = run
    return run


# --- config resolution -------------------------------------------------------
def test_hard_gate_defaults_to_invariant_classes(monkeypatch):
    monkeypatch.delenv("HARD_GATE_CLASSES", raising=False)
    resolved = cfg.reload_hard_gate_classes()
    assert resolved == set(INVARIANT_CLASSES)
    # PHI + auth specifically present
    assert "phi-classification" in resolved
    assert "auth-policy" in resolved


def test_env_extends_floor_never_shrinks(monkeypatch):
    monkeypatch.setenv("HARD_GATE_CLASSES", "sla-binding,identifier-format")
    resolved = cfg.reload_hard_gate_classes()
    # extras added
    assert "sla-binding" in resolved
    assert "identifier-format" in resolved
    # floor still immovable
    assert "phi-classification" in resolved
    assert "auth-policy" in resolved
    monkeypatch.delenv("HARD_GATE_CLASSES", raising=False)
    cfg.reload_hard_gate_classes()


def test_env_cannot_remove_floor(monkeypatch):
    # Even a deliberately empty / unrelated env keeps PHI + auth gated.
    monkeypatch.setenv("HARD_GATE_CLASSES", "naming-convention")
    resolved = cfg.reload_hard_gate_classes()
    assert "phi-classification" in resolved
    assert "auth-policy" in resolved
    monkeypatch.delenv("HARD_GATE_CLASSES", raising=False)
    cfg.reload_hard_gate_classes()


# --- server-enforced bulk block ----------------------------------------------
def test_bulk_approve_on_phi_class_rejected_409(client, monkeypatch):
    monkeypatch.delenv("HARD_GATE_CLASSES", raising=False)
    cfg.reload_hard_gate_classes()
    run = _seed_run("phi-classification", "hg-phi")
    try:
        resp = client.post(
            f"/api/runs/{run.run_id}/approve",
            json={
                "card_id": "hg-phi", "decision_kind": "accept",
                "option_index": 0, "approval_path": "bulk",
            },
        )
        assert resp.status_code == 409, resp.text
        assert "hard-gated" in resp.text
    finally:
        _runs.pop(run.run_id, None)


def test_individual_approve_on_phi_class_allowed(client, monkeypatch):
    monkeypatch.delenv("HARD_GATE_CLASSES", raising=False)
    cfg.reload_hard_gate_classes()
    run = _seed_run("phi-classification", "hg-phi-ind")
    try:
        resp = client.post(
            f"/api/runs/{run.run_id}/approve",
            json={
                "card_id": "hg-phi-ind", "decision_kind": "accept",
                "option_index": 0, "approval_path": "individual",
            },
        )
        assert resp.status_code == 200, resp.text
    finally:
        _runs.pop(run.run_id, None)


def test_bulk_approve_on_non_hardgate_class_allowed(client, monkeypatch):
    monkeypatch.delenv("HARD_GATE_CLASSES", raising=False)
    cfg.reload_hard_gate_classes()
    run = _seed_run("sla-binding", "hg-sla")
    try:
        resp = client.post(
            f"/api/runs/{run.run_id}/approve",
            json={
                "card_id": "hg-sla", "decision_kind": "accept",
                "option_index": 0, "approval_path": "bulk",
            },
        )
        assert resp.status_code == 200, resp.text
    finally:
        _runs.pop(run.run_id, None)


def test_default_approval_path_is_individual(client, monkeypatch):
    """Omitting approval_path must default to individual (safe) — a client that
    doesn't know about the field can still decide a PHI card explicitly."""
    monkeypatch.delenv("HARD_GATE_CLASSES", raising=False)
    cfg.reload_hard_gate_classes()
    run = _seed_run("phi-classification", "hg-default")
    try:
        resp = client.post(
            f"/api/runs/{run.run_id}/approve",
            json={"card_id": "hg-default", "decision_kind": "accept", "option_index": 0},
        )
        assert resp.status_code == 200, resp.text
    finally:
        _runs.pop(run.run_id, None)


# --- config endpoint ---------------------------------------------------------
def test_get_hard_gate_classes_endpoint(client, monkeypatch):
    monkeypatch.delenv("HARD_GATE_CLASSES", raising=False)
    cfg.reload_hard_gate_classes()
    resp = client.get("/api/config/hard-gate-classes")
    assert resp.status_code == 200
    body = resp.json()
    assert "phi-classification" in body["hard_gate_classes"]
    assert "auth-policy" in body["hard_gate_classes"]
    assert set(body["floor"]) == set(INVARIANT_CLASSES)
    assert "standards-change" in body["explainer"]
