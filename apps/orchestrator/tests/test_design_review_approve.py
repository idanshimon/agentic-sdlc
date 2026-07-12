"""Phase 4.1 regression: design_review gate-level approve must NOT be
blocked by the resolver-gate-closed check even when card_id is set.

Caught live on run 404b4fc1 (2026-06-16): operator clicked
"Approve architecture" on the new DesignReviewGate component, request
included a synthetic card_id="design-review-<runId>" to satisfy
GateDecision pydantic schema validation, and the orchestrator
rejected it with HTTP 409:
  "resolver gate is closed; cannot accept per-card decisions"

The check was overscoped: any approve with a card_id was assumed to
be a resolver-card decision regardless of which gate it targeted.
Design review approvals are gate-level (target=design_review, no card
data), and synthetic card_ids on those requests should not trigger
the resolver-closed guard.

Fix: a request is gate-level if EITHER card_id is None OR decision.gate
is set and != "resolver". Both contracts converge so the UI and the
orchestrator stop fighting over card_id presence.
"""
from __future__ import annotations
import pytest
from fastapi.testclient import TestClient

from orchestrator import main as om
from orchestrator.models import GateDecision, RunMode, RunState, RunStatus, Stage


def _client():
    return TestClient(om.app)


def _make_run(state: RunStatus, stage: Stage) -> RunState:
    return RunState(
        run_id="r1",
        team_id="cardiology",
        mode=RunMode.MANUAL,
        status=state,
        current_stage=stage,
    )


def test_design_review_approve_with_synthetic_card_id_passes(monkeypatch):
    """When the design_review gate is open and operator approves it via
    the DesignReviewGate UI, the request carries a synthetic card_id
    (to satisfy GateDecision validation) plus gate="design_review".
    The orchestrator MUST NOT reject this as a "per-card decision on a
    closed resolver gate" — it's a gate-level approval.
    """
    run = _make_run(RunStatus.AWAITING_GATE, Stage.DESIGN_REVIEW)
    monkeypatch.setattr(om, "_runs", {"r1": run})

    captured: dict = {}

    def fake_release(rid: str) -> None:
        captured["released"] = rid

    monkeypatch.setattr(om, "_release_gate", fake_release)
    monkeypatch.setattr(om, "_ledger", None)  # skip ledger write for unit isolation

    r = _client().post(
        "/api/runs/r1/approve",
        json={
            "card_id": "design-review-r1",
            "decision_kind": "accept",
            "actor": "operator@dashboard",
            "confidence_source": "human",
            "gate": "design_review",
            "resolution_text": "Architecture reviewed and approved.",
        },
    )
    # MUST NOT 409 — the request explicitly tags itself as a design_review
    # gate-level approval; the resolver-closed check should defer.
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True


def test_resolver_per_card_after_gate_closed_still_blocks(monkeypatch):
    """Counter-test: when the resolver gate IS closed and an operator
    tries to send a per-card resolver approve (no gate field), the
    orchestrator still rejects it. This is the audit-safety invariant
    from the existing comment about ff03847f (decision land 5s after
    finalize, architect LLM running from older snapshot)."""
    run = _make_run(RunStatus.RUNNING, Stage.ARCHITECT)  # past resolver
    monkeypatch.setattr(om, "_runs", {"r1": run})
    monkeypatch.setattr(om, "_ledger", None)

    r = _client().post(
        "/api/runs/r1/approve",
        json={
            "card_id": "some-resolver-card-id",
            "decision_kind": "accept",
            "actor": "late-decider@example.com",
            "option_index": 0,
        },
    )
    assert r.status_code == 409
    assert "resolver gate is closed" in r.json()["detail"]
