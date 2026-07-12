"""Deeper /finalize endpoint coverage.

Basic happy path / 404 / blocked-on-unresolved already covered in
test_approve_endpoint.py. These tests cover edge semantics:
  - non-gating cards do NOT block finalize
  - the asyncio.Event in _gate_events is actually released
  - error body carries an unresolved count
  - empty body POST is accepted
"""
from __future__ import annotations

import asyncio
import pytest
from fastapi.testclient import TestClient

from apps.orchestrator.main import app, _runs, _gate_events
from apps.orchestrator.models import (
    AmbiguityCard, ResolutionOption, RunState, RunStatus, Stage,
)


@pytest.fixture
def client():
    return TestClient(app)


def _mk_card(card_id: str, *, gating: bool = True) -> AmbiguityCard:
    opt = ResolutionOption(
        label="rec", resolution="resolve it", rationale="r",
        downstream_impact="d", recommended=True,
    )
    return AmbiguityCard(
        card_id=card_id, title="t", detail="d",
        ambiguity_class="data-retention", slot_value_hash=f"h-{card_id}",
        options=[opt], is_gating=gating,
    )


@pytest.fixture
def run_two_cards_one_nongating():
    run = RunState(
        team_id="cardiology", run_id="finalize-mixed", prd_blob_url="x",
        status=RunStatus.AWAITING_GATE, current_stage=Stage.RESOLVER,
        cards=[_mk_card("gating-1", gating=True), _mk_card("ng-1", gating=False)],
    )
    _runs[run.run_id] = run
    yield run
    _runs.pop(run.run_id, None)
    _gate_events.pop(run.run_id, None)


def test_finalize_ignores_non_gating_cards(client, run_two_cards_one_nongating):
    """Cards with is_gating=False should not block /finalize even with no decision."""
    run = run_two_cards_one_nongating
    # Resolve only the gating card.
    client.post(
        f"/api/runs/{run.run_id}/approve",
        json={"card_id": "gating-1", "decision_kind": "accept"},
    )
    resp = client.post(f"/api/runs/{run.run_id}/finalize")
    assert resp.status_code == 200, resp.text
    assert resp.json()["gate_closed"] is True


def test_finalize_releases_gate_event(client, run_two_cards_one_nongating):
    """The asyncio.Event registered in _gate_events MUST be set after finalize."""
    run = run_two_cards_one_nongating
    ev = asyncio.Event()
    _gate_events[run.run_id] = ev

    client.post(
        f"/api/runs/{run.run_id}/approve",
        json={"card_id": "gating-1", "decision_kind": "accept"},
    )
    resp = client.post(f"/api/runs/{run.run_id}/finalize")
    assert resp.status_code == 200
    assert ev.is_set(), "gate event was not released"
    assert run.run_id not in _gate_events


def test_finalize_unresolved_message_carries_count(client, run_two_cards_one_nongating):
    """Error body should describe how many gating cards are still unresolved."""
    resp = client.post(f"/api/runs/{run_two_cards_one_nongating.run_id}/finalize")
    assert resp.status_code == 400
    body = resp.text.lower()
    assert "1" in body
    assert "unresolved" in body


def test_finalize_accepts_empty_body(client, run_two_cards_one_nongating):
    """POST with no JSON body should still work (body is optional)."""
    run = run_two_cards_one_nongating
    client.post(
        f"/api/runs/{run.run_id}/approve",
        json={"card_id": "gating-1", "decision_kind": "accept"},
    )
    resp = client.post(f"/api/runs/{run.run_id}/finalize", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["decisions_count"] >= 1


def test_finalize_uses_atomic_cas_when_ledger_is_authoritative(monkeypatch, client, run_two_cards_one_nongating):
    """Production finalize must commit command+gate state in one ETag CAS."""
    from apps.orchestrator import main as om

    run = run_two_cards_one_nongating
    run.decisions.append(__import__("apps.orchestrator.models", fromlist=["GateDecision"]).GateDecision(
        card_id="gating-1", decision_kind="accept", resolution_text="resolved",
    ))

    class Ledger:
        async def get_run(self, run_id):
            return run.model_dump(mode="json") | {"_etag": "v1"}
        async def replace_run_strict(self, authoritative, *, expected_etag):
            assert expected_etag == "v1"
            assert authoritative.pending_gate is None or authoritative.pending_gate.get("status") == "resolved"
            assert authoritative.command_records
            return authoritative.model_dump(mode="json") | {"_etag": "v2"}

    monkeypatch.setattr(om, "_ledger", Ledger())
    resp = client.post(
        f"/api/runs/{run.run_id}/finalize",
        headers={"Idempotency-Key": "finalize-cas-1"},
        json={},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["gate_closed"] is True