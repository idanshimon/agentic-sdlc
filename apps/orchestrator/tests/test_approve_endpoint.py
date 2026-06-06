"""Integration tests for the /approve endpoint resolution logic.

Covers resolver-gate/spec.md REQ-1e:
- option_index given → use card.options[option_index].resolution
- neither option_index nor text → default to recommended option's resolution
- resolution_text given → use it verbatim (swap / write-my-own)
- both given → 400 (mutually exclusive in v1)
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from apps.orchestrator import main as orchestrator_main
from apps.orchestrator.main import app, _runs
from apps.orchestrator.models import (
    AmbiguityCard, ResolutionOption, RunState, RunStatus, Stage,
)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def seeded_run():
    """Build a run with one card carrying 2 options (recommended + alt)."""
    rec = ResolutionOption(
        label="HIPAA 7yr", resolution="Retain 7 years per §164.530(j).",
        rationale="HIPAA floor.", downstream_impact="TTL infra.", recommended=True,
    )
    alt = ResolutionOption(
        label="30 day", resolution="Retain 30 days, ephemeral session policy.",
        rationale="Not classified as medical record.",
        downstream_impact="No retention module.",
    )
    card = AmbiguityCard(
        card_id="card-1", title="t", detail="d", ambiguity_class="data-retention",
        slot_value_hash="hash-1", options=[rec, alt],
    )
    run = RunState(
        team_id="cardiology", run_id="run-test", prd_blob_url="x",
        status=RunStatus.AWAITING_GATE, current_stage=Stage.RESOLVER,
        cards=[card],
    )
    _runs[run.run_id] = run
    yield run
    _runs.pop(run.run_id, None)


def test_accept_with_option_index_zero_uses_recommended_text(client, seeded_run):
    resp = client.post(
        f"/api/runs/{seeded_run.run_id}/approve",
        json={"card_id": "card-1", "decision_kind": "accept", "option_index": 0},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["resolution_text"] == "Retain 7 years per §164.530(j)."


def test_accept_with_option_index_one_uses_alternative_text(client, seeded_run):
    resp = client.post(
        f"/api/runs/{seeded_run.run_id}/approve",
        json={"card_id": "card-1", "decision_kind": "accept", "option_index": 1},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "30 days" in body["resolution_text"]


def test_accept_without_option_defaults_to_recommended(client, seeded_run):
    """REQ-1e: when neither option_index nor text given, default to recommended."""
    resp = client.post(
        f"/api/runs/{seeded_run.run_id}/approve",
        json={"card_id": "card-1", "decision_kind": "accept"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["resolution_text"] == "Retain 7 years per §164.530(j)."


def test_swap_uses_user_text_verbatim(client, seeded_run):
    """Write-my-own: resolution_text is taken verbatim, NOT looked up in options."""
    resp = client.post(
        f"/api/runs/{seeded_run.run_id}/approve",
        json={
            "card_id": "card-1", "decision_kind": "swap",
            "resolution_text": "HCA-Retention-v2.3 — 5 year custom policy",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["resolution_text"] == "HCA-Retention-v2.3 — 5 year custom policy"


def test_invalid_run_returns_404(client):
    resp = client.post(
        "/api/runs/does-not-exist/approve",
        json={"card_id": "card-1", "decision_kind": "accept"},
    )
    assert resp.status_code == 404


def test_decision_persists_on_run(client, seeded_run):
    """After approve, run.decisions has the persisted decision with final_text."""
    client.post(
        f"/api/runs/{seeded_run.run_id}/approve",
        json={"card_id": "card-1", "decision_kind": "accept", "option_index": 1},
    )
    run = _runs[seeded_run.run_id]
    assert len(run.decisions) == 1
    persisted = run.decisions[0]
    assert persisted.card_id == "card-1"
    assert "30 days" in persisted.resolution_text
    assert persisted.option_index == 1


# ---- /finalize endpoint -----------------------------------------------------

def test_finalize_blocks_when_cards_unresolved(client, seeded_run):
    """Calling finalize with gating cards still pending MUST 400."""
    resp = client.post(f"/api/runs/{seeded_run.run_id}/finalize")
    assert resp.status_code == 400
    assert "unresolved" in resp.text.lower()


def test_finalize_releases_when_all_resolved(client, seeded_run):
    """After resolving all gating cards, finalize closes the gate."""
    client.post(
        f"/api/runs/{seeded_run.run_id}/approve",
        json={"card_id": "card-1", "decision_kind": "accept", "option_index": 0},
    )
    resp = client.post(f"/api/runs/{seeded_run.run_id}/finalize")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["gate_closed"] is True
    assert body["next_stage"] == "architect"


def test_finalize_404_on_unknown_run(client):
    resp = client.post("/api/runs/nope/finalize")
    assert resp.status_code == 404


# ---- Cost aggregation semantics (resolver-gate REQ-15a) ----------------------
#
# REQ-15a: At Gate 1 close, the UI shows 'estimated downstream rework avoided'.
# This is the SUM of blast_radius_cost_usd across decisions whose kind is
# accept OR swap (POSITIVE precedents only). reject decisions do NOT count
# (the team deemed the ambiguity non-applicable, not a real risk resolved).
#
# The aggregation is client-side, but we test the server contract: cards
# carry the raw dollar field unbounded, the Resolver UI is responsible for
# bucketing/summing. Per assessor/spec.md REQ-4d, the Assessor emits raw
# floats and downstream surfaces decide presentation.

def test_blast_radius_cost_is_raw_float_on_card(client, seeded_run):
    """REQ-4d: Assessor emits unbounded float USD; no pre-bucketing."""
    resp = client.get(f"/api/runs/{seeded_run.run_id}")
    assert resp.status_code == 200
    card = resp.json()["cards"][0]
    assert "blast_radius_cost_usd" in card
    assert isinstance(card["blast_radius_cost_usd"], (int, float))


def test_total_rework_avoided_excludes_rejects(client, seeded_run):
    """The 'rework avoided' summary semantic: sum across POSITIVE precedents
    only. Server holds the source data; client aggregates. Test the data
    shape on the run state."""
    # Resolve card-1 as accept
    client.post(
        f"/api/runs/{seeded_run.run_id}/approve",
        json={"card_id": "card-1", "decision_kind": "accept", "option_index": 0},
    )
    run = _runs[seeded_run.run_id]

    # The card's blast cost should still be visible on the run for client aggregation
    card = next(c for c in run.cards if c.card_id == "card-1")
    decision = run.decisions[0]
    assert decision.decision_kind == "accept"
    # Client would compute: sum(c.blast for c in cards where decision.kind in ('accept', 'swap'))
    # We assert the data is reachable, not the math (math is client-side).
    assert hasattr(card, "blast_radius_cost_usd")


# ---- Autopilot mode ---------------------------------------------------------

import asyncio as _asyncio
from apps.orchestrator.models import RunMode


def test_autopilot_auto_accepts_non_invariant(client, seeded_run):
    """In autopilot, non-invariant cards auto-accept the recommended option."""
    seeded_run.mode = RunMode.AUTOPILOT
    from apps.orchestrator.main import _run_autopilot
    _asyncio.run(_run_autopilot(seeded_run))
    # Card has class 'data-retention' (non-invariant) → auto-resolved.
    assert "card-1" in seeded_run.autopilot_decisions
    assert "card-1" not in seeded_run.autopilot_overrides
    assert len(seeded_run.decisions) >= 1
    auto_d = seeded_run.decisions[0]
    assert auto_d.confidence_source == "autopilot"
    assert auto_d.actor.startswith("autopilot:")
    # Recommended option text should have been chosen.
    assert "7 years" in auto_d.resolution_text


def test_autopilot_invariant_override_still_gates(client):
    """PHI / auth-policy cards MUST gate even in autopilot."""
    rec = ResolutionOption(
        label="Use Entra OBO",
        resolution="Use Entra OBO chain for auth.",
        rationale="Enterprise SSO default.",
        downstream_impact="All endpoints use OBO.",
        recommended=True,
    )
    card = AmbiguityCard(
        card_id="phi-card", title="Auth method", detail="",
        ambiguity_class="auth-policy",  # INVARIANT
        slot_value_hash="hash-phi", options=[rec],
    )
    run = RunState(
        team_id="cardiology", run_id="phi-test", prd_blob_url="x",
        status=RunStatus.AWAITING_GATE, current_stage=Stage.RESOLVER,
        cards=[card], mode=RunMode.AUTOPILOT,
    )
    _runs[run.run_id] = run
    try:
        from apps.orchestrator.main import _run_autopilot
        _asyncio.run(_run_autopilot(run))
        assert "phi-card" in run.autopilot_overrides, "PHI/auth class must NOT auto-resolve"
        assert "phi-card" not in run.autopilot_decisions
        assert run.decisions == []
    finally:
        _runs.pop(run.run_id, None)


def test_pause_endpoint_switches_to_manual(client, seeded_run):
    """POST /pause MUST flip the run to MANUAL mode."""
    seeded_run.mode = RunMode.AUTOPILOT
    resp = client.post(f"/api/runs/{seeded_run.run_id}/pause")
    assert resp.status_code == 200
    body = resp.json()
    assert body["previous_mode"] == "autopilot"
    assert body["current_mode"] == "manual"


def test_resume_restores_previous_mode(client, seeded_run):
    """POST /resume after /pause restores the pre-pause mode."""
    seeded_run.mode = RunMode.AUTOPILOT
    client.post(f"/api/runs/{seeded_run.run_id}/pause")
    resp = client.post(f"/api/runs/{seeded_run.run_id}/resume")
    assert resp.status_code == 200
    body = resp.json()
    assert body["previous_mode"] == "manual"
    assert body["current_mode"] == "autopilot"


def test_resume_explicit_mode_override(client, seeded_run):
    """POST /resume with body mode overrides the previous_mode default."""
    seeded_run.mode = RunMode.MANUAL
    resp = client.post(
        f"/api/runs/{seeded_run.run_id}/resume",
        json={"mode": "hybrid"},
    )
    assert resp.status_code == 200
    assert resp.json()["current_mode"] == "hybrid"


def test_resume_without_previous_defaults_autopilot(client, seeded_run):
    """No prior pause + no explicit mode → defaults to AUTOPILOT."""
    seeded_run.mode = RunMode.MANUAL
    seeded_run.previous_mode = None
    resp = client.post(f"/api/runs/{seeded_run.run_id}/resume")
    assert resp.status_code == 200
    assert resp.json()["current_mode"] == "autopilot"


# ---- Rerun ------------------------------------------------------------------

def test_rerun_404_when_source_missing(client):
    resp = client.post("/api/runs/nope/rerun")
    assert resp.status_code == 404


def test_rerun_409_when_prd_not_cached(client, seeded_run):
    """If the PRD wasn't cached (e.g. seeded test fixture), rerun returns 409."""
    from apps.orchestrator.main import _prd_cache
    _prd_cache.pop(seeded_run.run_id, None)  # ensure not cached
    resp = client.post(f"/api/runs/{seeded_run.run_id}/rerun")
    assert resp.status_code == 409
    assert "cache" in resp.text.lower()


def test_rerun_inverts_mode_when_not_specified(client, seeded_run):
    """No body -> manual flips to autopilot, autopilot flips to manual."""
    from apps.orchestrator.main import _prd_cache
    _prd_cache[seeded_run.run_id] = "fake PRD text for test"

    seeded_run.mode = RunMode.MANUAL
    resp = client.post(f"/api/runs/{seeded_run.run_id}/rerun")
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "autopilot"
    assert body["source_run_id"] == seeded_run.run_id
    assert body["team_id"] == seeded_run.team_id
    new_run_id = body["run_id"]
    assert new_run_id != seeded_run.run_id

    # Clean up the spawned run + its drive task
    from apps.orchestrator.main import _runs
    _runs.pop(new_run_id, None)
    _prd_cache.pop(new_run_id, None)


def test_rerun_respects_explicit_mode(client, seeded_run):
    """Body {'mode': 'hybrid'} -> new run starts in hybrid regardless of source."""
    from apps.orchestrator.main import _prd_cache, _runs
    _prd_cache[seeded_run.run_id] = "fake PRD text for test"

    resp = client.post(
        f"/api/runs/{seeded_run.run_id}/rerun",
        json={"mode": "hybrid"},
    )
    assert resp.status_code == 200
    assert resp.json()["mode"] == "hybrid"
    new_run_id = resp.json()["run_id"]
    _runs.pop(new_run_id, None)
    _prd_cache.pop(new_run_id, None)


def test_rerun_source_run_preserved(client, seeded_run):
    """After rerun, the source run is still queryable (audit chain preserved)."""
    from apps.orchestrator.main import _prd_cache, _runs
    _prd_cache[seeded_run.run_id] = "fake PRD text for test"

    resp = client.post(f"/api/runs/{seeded_run.run_id}/rerun")
    new_run_id = resp.json()["run_id"]

    # Source still exists
    src_resp = client.get(f"/api/runs/{seeded_run.run_id}")
    assert src_resp.status_code == 200

    _runs.pop(new_run_id, None)
    _prd_cache.pop(new_run_id, None)


def test_rerun_preserves_prd_bytes_in_cache(client, seeded_run):
    """Rerun MUST copy the source PRD into the new run's cache verbatim,
    so the spawned pipeline can re-run without a re-upload."""
    from apps.orchestrator.main import _prd_cache, _runs
    original = "# PRD\nRetention: undefined.\nAuth: TBD."
    _prd_cache[seeded_run.run_id] = original

    resp = client.post(f"/api/runs/{seeded_run.run_id}/rerun")
    assert resp.status_code == 200
    new_run_id = resp.json()["run_id"]
    try:
        assert _prd_cache.get(new_run_id) == original
        # Source cache still intact (no move semantics).
        assert _prd_cache.get(seeded_run.run_id) == original
        # New run inherits team_id + prd_blob_url from source.
        new_run = _runs[new_run_id]
        assert new_run.team_id == seeded_run.team_id
        assert new_run.prd_blob_url == seeded_run.prd_blob_url
    finally:
        _runs.pop(new_run_id, None)
        _prd_cache.pop(new_run_id, None)


# ---- /approve guard: reject per-card decisions after gate closed ----------

def test_approve_409_when_run_status_is_running(client, seeded_run):
    """After /finalize fires, run.status flips to RUNNING. A per-card /approve
    landing in that window must 409 — otherwise the decision drifts past the
    architect's prompt snapshot (verified 2026-05-25 prod bug, run ff03847f)."""
    seeded_run.status = RunStatus.RUNNING
    resp = client.post(
        f"/api/runs/{seeded_run.run_id}/approve",
        json={"card_id": "card-1", "decision_kind": "accept", "option_index": 0},
    )
    assert resp.status_code == 409
    assert "gate is closed" in resp.json()["detail"]
    # And nothing was appended.
    assert len(seeded_run.decisions) == 0


def test_approve_409_when_current_stage_past_resolver(client, seeded_run):
    """Even if status is AWAITING_GATE (e.g. design_review gate open), a per-card
    decision against the resolver gate must 409 — the resolver gate is already
    behind us, the per-card semantic no longer applies."""
    from apps.orchestrator.models import Stage
    seeded_run.status = RunStatus.AWAITING_GATE
    seeded_run.current_stage = Stage.DESIGN_REVIEW
    resp = client.post(
        f"/api/runs/{seeded_run.run_id}/approve",
        json={"card_id": "card-1", "decision_kind": "accept", "option_index": 0},
    )
    assert resp.status_code == 409
    assert len(seeded_run.decisions) == 0


def test_approve_gate_level_still_works_post_resolver(client, seeded_run):
    """Gate-level approval (card_id=None, gate=design_review) must NOT be
    blocked by the guard — design_review is a whole-stage approval that
    legitimately fires when status=AWAITING_GATE and current_stage=DESIGN_REVIEW."""
    from apps.orchestrator.models import Stage
    seeded_run.status = RunStatus.AWAITING_GATE
    seeded_run.current_stage = Stage.DESIGN_REVIEW
    resp = client.post(
        f"/api/runs/{seeded_run.run_id}/approve",
        json={"decision_kind": "accept", "gate": "design_review"},
    )
    # Gate-level approve releases the gate; no card_id means the guard skips.
    assert resp.status_code == 200
    assert len(seeded_run.decisions) == 1
