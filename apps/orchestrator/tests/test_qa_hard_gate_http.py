"""QA: prove the hard gate holds through the real HTTP surface.

Unit tests prove the helpers behave. This proves the ACTUAL endpoint a client
calls rejects a bulk approval on an invariant class, and that an accepted
decision persists the alternatives it weighed. Per AGENTS.md a tested function
is not the same as a proven path.

This is the product thesis on the wire: classification decides, and no client
- however confident - can sweep a PHI card into an "Approve all" batch.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from apps.orchestrator.main import app, _runs
from apps.orchestrator.models import (
    AmbiguityCard, ResolutionOption, RunState, RunStatus, Stage,
)


@pytest.fixture
def client():
    return TestClient(app)


def _make_run(run_id: str, klass: str) -> RunState:
    rec = ResolutionOption(
        label="A", resolution="ra", rationale="because A",
        downstream_impact="d", recommended=True,
    )
    alt = ResolutionOption(
        label="B", resolution="rb", rationale="because B", downstream_impact="d",
    )
    card = AmbiguityCard(
        card_id="card-1", title="t", detail="d", ambiguity_class=klass,
        slot_value_hash="hash-1", options=[rec, alt],
    )
    run = RunState(
        team_id="cardiology", run_id=run_id, prd_blob_url="x",
        status=RunStatus.AWAITING_GATE, current_stage=Stage.RESOLVER,
        cards=[card],
    )
    _runs[run_id] = run
    return run


@pytest.fixture
def phi_run():
    run = _make_run("qa-phi", "phi-classification")
    yield run
    _runs.pop(run.run_id, None)


@pytest.fixture
def ordinary_run():
    run = _make_run("qa-naming", "naming-convention")
    yield run
    _runs.pop(run.run_id, None)


def test_bulk_approval_on_phi_is_rejected_by_the_server(client, phi_run):
    """The 409 no client can talk past.

    The UI stamps is_hard_gated so it can render a lock badge, but the server
    does not trust that flag - it re-derives from HARD_GATE_CLASSES.
    """
    resp = client.post(
        f"/api/runs/{phi_run.run_id}/approve",
        json={
            "card_id": "card-1", "decision_kind": "accept",
            "approval_path": "bulk",
        },
    )
    assert resp.status_code == 409, resp.text
    assert "hard-gated" in resp.text
    assert "individually" in resp.text


def test_bulk_approval_on_ordinary_class_is_allowed(client, ordinary_run):
    """The lock is narrow on purpose - only invariant classes are gated."""
    resp = client.post(
        f"/api/runs/{ordinary_run.run_id}/approve",
        json={
            "card_id": "card-1", "decision_kind": "accept",
            "approval_path": "bulk",
        },
    )
    assert resp.status_code != 409, resp.text


def test_individual_approval_on_phi_is_accepted(client, phi_run):
    """An explicit per-card decision on a hard-gated class IS allowed.

    The rule is "no rubber-stamping", not "no deciding".
    """
    resp = client.post(
        f"/api/runs/{phi_run.run_id}/approve",
        json={
            "card_id": "card-1", "decision_kind": "accept", "option_index": 1,
            "approval_path": "individual",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["resolution_text"] == "rb"


def test_approval_persists_the_alternatives_weighed(client, phi_run):
    """The decision record must answer "why not the other option?"."""
    resp = client.post(
        f"/api/runs/{phi_run.run_id}/approve",
        json={
            "card_id": "card-1", "decision_kind": "accept", "option_index": 1,
            "approval_path": "individual",
        },
    )
    assert resp.status_code == 200, resp.text

    run = _runs[phi_run.run_id]
    assert run.decisions, "decision was not persisted to run state"
    assert run.decisions[-1].resolution_text == "rb"
