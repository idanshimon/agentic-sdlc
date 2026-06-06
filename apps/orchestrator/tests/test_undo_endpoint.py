"""Tests for the /undo endpoint — re-opens a resolved Resolver card."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from apps.orchestrator.main import app, _runs, _gate_events
from apps.orchestrator.models import (
    AmbiguityCard, GateDecision, ResolutionOption, RunState, RunStatus, Stage,
)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def seeded_run():
    rec = ResolutionOption(
        label="HIPAA 7yr", resolution="Retain 7 years.",
        rationale="HIPAA floor.", downstream_impact="TTL infra.", recommended=True,
    )
    card = AmbiguityCard(
        card_id="X", title="t", detail="d", ambiguity_class="data-retention",
        slot_value_hash="hash-1", options=[rec],
    )
    run = RunState(
        team_id="cardiology", run_id="run-undo-test", prd_blob_url="x",
        status=RunStatus.AWAITING_GATE, current_stage=Stage.RESOLVER,
        cards=[card],
    )
    _runs[run.run_id] = run
    yield run
    _runs.pop(run.run_id, None)
    _gate_events.pop(run.run_id, None)


def test_undo_removes_decision(client, seeded_run):
    seeded_run.decisions.append(GateDecision(
        card_id="X", decision_kind="accept", resolution_text="Retain 7 years.",
        option_index=0,
    ))
    resp = client.post(f"/api/runs/{seeded_run.run_id}/undo", json={"card_id": "X"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True
    assert body["card_id"] == "X"
    assert body["decisions_count"] == 0
    assert seeded_run.decisions == []


def test_undo_clears_autopilot_tracking(client, seeded_run):
    seeded_run.autopilot_decisions.append("X")
    seeded_run.autopilot_overrides.append("X")
    seeded_run.decisions.append(GateDecision(
        card_id="X", decision_kind="accept", resolution_text="auto",
        confidence_source="autopilot", actor="autopilot:hybrid",
    ))
    resp = client.post(f"/api/runs/{seeded_run.run_id}/undo", json={"card_id": "X"})
    assert resp.status_code == 200
    assert "X" not in seeded_run.autopilot_decisions
    assert "X" not in seeded_run.autopilot_overrides


def test_undo_404_when_run_missing(client):
    resp = client.post("/api/runs/does-not-exist/undo", json={"card_id": "X"})
    assert resp.status_code == 404


def test_undo_404_when_card_id_unknown(client, seeded_run):
    resp = client.post(
        f"/api/runs/{seeded_run.run_id}/undo", json={"card_id": "ghost"},
    )
    assert resp.status_code == 404


def test_undo_409_when_not_in_resolver_gate(client, seeded_run):
    seeded_run.status = RunStatus.RUNNING
    seeded_run.current_stage = Stage.ARCHITECT
    resp = client.post(
        f"/api/runs/{seeded_run.run_id}/undo", json={"card_id": "X"},
    )
    assert resp.status_code == 409
    assert "resolver gate" in resp.text.lower()


def test_undo_does_not_release_gate(client, seeded_run):
    import asyncio
    seeded_run.decisions.append(GateDecision(
        card_id="X", decision_kind="accept", resolution_text="r",
    ))
    ev = asyncio.Event()
    _gate_events[seeded_run.run_id] = ev
    try:
        resp = client.post(
            f"/api/runs/{seeded_run.run_id}/undo", json={"card_id": "X"},
        )
        assert resp.status_code == 200
        # gate event MUST still be unset — undo does NOT release the gate
        assert not ev.is_set()
        assert seeded_run.run_id in _gate_events
    finally:
        _gate_events.pop(seeded_run.run_id, None)
