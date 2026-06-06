"""Tests for ledger_core models — schema validation, entry_type rules, back-compat."""
from __future__ import annotations
import pytest

from ledger_core import (
    LedgerEntry,
    Actor,
    ReviewerAttribution,
    CanaryMetrics,
    is_phi_change,
    has_high_blast,
    from_legacy_v06_dict,
)


# ---- runtime entry validation -----------------------------------------------

def test_runtime_entry_with_run_id_passes():
    e = LedgerEntry(
        team_id="team-cardiology",
        actor=Actor(kind="agent", id="orchestrator"),
        decision="auth-policy resolved: OAuth2 with vendor registry",
        run_id="run-abc",
        runtime_kind="stage_decision",
        bundle_refs=["security/v0.1.0/AUTH-001"],
    )
    assert e.entry_type == "runtime"
    assert e.run_id == "run-abc"


def test_runtime_entry_with_agent_session_id_passes():
    e = LedgerEntry(
        team_id="team-cardiology",
        actor=Actor(kind="agent", id="github-coding-agent"),
        decision="logging refactor",
        agent_session_id="012345a6-b7c8-9012-de3f-45gh678i9012",
        runtime_kind="ide_tool_call",
    )
    assert e.entry_type == "runtime"
    assert e.agent_session_id is not None


def test_runtime_entry_without_source_attribution_fails():
    with pytest.raises(ValueError, match="run_id, agent_session_id"):
        LedgerEntry(
            team_id="team-cardiology",
            actor=Actor(kind="agent", id="orchestrator"),
            decision="orphan entry",
            entry_type="runtime",
        )


# ---- meta entry validation --------------------------------------------------

def test_meta_entry_full_passes():
    e = LedgerEntry(
        team_id="__org__",
        actor=Actor(kind="human", id="alice@example.com"),
        decision="PHI-001 retention extended to 8 years",
        entry_type="meta",
        bundle_refs=["security/v0.1.0/PHI-001"],
        meta_kind="bundle_change_merged",
        change_ticket_id="CHG-2026-001",
        bundle_version_from="security/v0.1.0",
        bundle_version_to="security/v0.1.1",
        blast_class="HIGH",
        reviewers=[
            ReviewerAttribution(
                actor=Actor(kind="human", id="bob@example.com"),
                role="security_lead",
                approved_at="2026-06-05T12:00:00Z",
            ),
            ReviewerAttribution(
                actor=Actor(kind="human", id="carol@example.com"),
                role="privacy_dpo",
                approved_at="2026-06-05T12:30:00Z",
            ),
        ],
    )
    assert e.entry_type == "meta"
    assert e.blast_class == "HIGH"
    assert len(e.reviewers) == 2


def test_meta_entry_missing_required_fails():
    with pytest.raises(ValueError, match="missing required fields"):
        LedgerEntry(
            team_id="__org__",
            actor=Actor(kind="human", id="alice@example.com"),
            decision="incomplete meta",
            entry_type="meta",
            bundle_refs=["security/v0.1.0/PHI-001"],
            change_ticket_id="CHG-001",
            # missing: bundle_version_from, bundle_version_to, blast_class, reviewers
        )


def test_meta_entry_with_run_id_fails():
    with pytest.raises(ValueError, match="must not set"):
        LedgerEntry(
            team_id="__org__",
            actor=Actor(kind="human", id="alice@example.com"),
            decision="bad meta with run_id",
            entry_type="meta",
            run_id="run-abc",  # forbidden on meta
            change_ticket_id="CHG-001",
            bundle_version_from="security/v0.1.0",
            bundle_version_to="security/v0.1.1",
            blast_class="LOW",
            reviewers=[
                ReviewerAttribution(
                    actor=Actor(kind="human", id="bob@example.com"),
                    role="bundle_owner",
                    approved_at="2026-06-05T12:00:00Z",
                )
            ],
        )


def test_meta_entry_with_stage_fails():
    with pytest.raises(ValueError, match="must not set"):
        LedgerEntry(
            team_id="__org__",
            actor=Actor(kind="human", id="alice@example.com"),
            decision="bad meta with stage",
            entry_type="meta",
            stage="codegen",
            change_ticket_id="CHG-001",
            bundle_version_from="security/v0.1.0",
            bundle_version_to="security/v0.1.1",
            blast_class="LOW",
            reviewers=[
                ReviewerAttribution(
                    actor=Actor(kind="human", id="bob@example.com"),
                    role="bundle_owner",
                    approved_at="2026-06-05T12:00:00Z",
                )
            ],
        )


# ---- helper functions -------------------------------------------------------

def test_is_phi_change_for_PHI_rule():
    e = LedgerEntry(
        team_id="__org__",
        actor=Actor(kind="human", id="alice@example.com"),
        decision="PHI rule change",
        entry_type="meta",
        bundle_refs=["security/v0.1.0/PHI-001"],
        change_ticket_id="CHG-001",
        bundle_version_from="security/v0.1.0",
        bundle_version_to="security/v0.1.1",
        blast_class="HIGH",
        reviewers=[
            ReviewerAttribution(
                actor=Actor(kind="human", id="bob@example.com"),
                role="security_lead",
                approved_at="2026-06-05T12:00:00Z",
            )
        ],
    )
    assert is_phi_change(e) is True


def test_is_phi_change_for_non_PHI_rule():
    e = LedgerEntry(
        team_id="__org__",
        actor=Actor(kind="human", id="alice@example.com"),
        decision="autopilot threshold tuning",
        entry_type="meta",
        bundle_refs=["finops/v0.1.0/AUTOPILOT-THRESHOLD"],
        change_ticket_id="CHG-002",
        bundle_version_from="finops/v0.1.0",
        bundle_version_to="finops/v0.1.1",
        blast_class="LOW",
        reviewers=[
            ReviewerAttribution(
                actor=Actor(kind="human", id="bob@example.com"),
                role="bundle_owner",
                approved_at="2026-06-05T12:00:00Z",
            )
        ],
    )
    assert is_phi_change(e) is False


def test_is_phi_change_for_runtime_entry():
    e = LedgerEntry(
        team_id="team-x",
        actor=Actor(kind="agent", id="orchestrator"),
        decision="phi gate approved",
        run_id="run-1",
        runtime_kind="stage_decision",
        bundle_refs=["security/v0.1.0/PHI-001"],
    )
    assert is_phi_change(e) is False  # runtime entries never report as phi_change


def test_has_high_blast_returns_true_for_high_meta():
    e = LedgerEntry(
        team_id="__org__",
        actor=Actor(kind="human", id="alice@example.com"),
        decision="high blast change",
        entry_type="meta",
        bundle_refs=["security/v0.1.0/PHI-001"],
        change_ticket_id="CHG-001",
        bundle_version_from="security/v0.1.0",
        bundle_version_to="security/v0.1.1",
        blast_class="HIGH",
        reviewers=[
            ReviewerAttribution(
                actor=Actor(kind="human", id="bob@example.com"),
                role="security_lead",
                approved_at="2026-06-05T12:00:00Z",
            )
        ],
    )
    assert has_high_blast(e) is True


# ---- backward compat with v0.6 dicts ----------------------------------------

def test_v06_entry_promotes_to_runtime_default():
    """v0.6 entries lacked entry_type; should auto-default to runtime."""
    legacy = {
        "id": "abc-123",
        "team_id": "team-cardiology",
        "run_id": "run-old",
        "card_id": "card-1",
        "ambiguity_class": "auth-policy",
        "slot_value_hash": "deadbeef",
        "resolution_text": "OAuth2 with vendor registry",
        "decision_kind": "accept",
        "status": "suggest",
        "created_at": "2026-05-01T00:00:00Z",
        "created_by": "demo-user@hca",
        "confidence_source": "human",
    }
    e = from_legacy_v06_dict(legacy)
    assert e.entry_type == "runtime"
    assert e.runtime_kind == "stage_decision"
    assert e.actor.kind == "human"
    assert e.actor.id == "demo-user@hca"
    assert e.decision  # was synthesized from resolution_text
    assert e.bundle_refs == []  # backfilled by Doctor


def test_v06_autopilot_entry_promotes_actor_to_agent():
    legacy = {
        "team_id": "team-x",
        "run_id": "run-2",
        "card_id": "card-2",
        "ambiguity_class": "naming-convention",
        "decision_kind": "accept",
        "confidence_source": "autopilot",
        "created_by": "autopilot-engine",
    }
    e = from_legacy_v06_dict(legacy)
    assert e.actor.kind == "agent"
    assert e.entry_type == "runtime"


def test_v06_orphan_entry_defaults_run_id():
    legacy = {
        "team_id": "team-x",
        "decision": "ancient orphan",
        "ambiguity_class": "other",
        "decision_kind": "accept",
    }
    e = from_legacy_v06_dict(legacy)
    assert e.run_id == "legacy-unknown"
    assert e.entry_type == "runtime"
