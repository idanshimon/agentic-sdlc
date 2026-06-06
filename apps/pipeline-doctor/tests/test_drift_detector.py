"""Tests for drift_detector — 5 signal types over synthetic ledger entries."""
import pytest
from datetime import datetime, timezone, timedelta
from ledger_core import LedgerEntry, Actor
from pipeline_doctor.drift_detector import DriftDetector
from pipeline_doctor.models import DriftSignalKind


def _runtime_entry(**kwargs):
    """Helper to build a runtime entry with defaults filled in."""
    defaults = dict(
        team_id="team-x",
        actor=Actor(kind="agent", id="orchestrator"),
        decision="test decision",
        run_id="run-test",
        runtime_kind="stage_decision",
    )
    defaults.update(kwargs)
    return LedgerEntry(**defaults)


# ---- 1. autopilot rejection rate ---------------------------------------
def test_autopilot_rejection_high_triggers_signal():
    now = datetime(2026, 6, 5, 12, 0, 0, tzinfo=timezone.utc)
    recent = (now - timedelta(days=2)).isoformat()
    entries = [
        _runtime_entry(
            ambiguity_class="auth-policy",
            decision_kind="reject",
            confidence_source="autopilot",
            created_at=recent,
            stage="resolver",
        )
        for _ in range(6)
    ] + [
        _runtime_entry(
            ambiguity_class="auth-policy",
            decision_kind="accept",
            confidence_source="autopilot",
            created_at=recent,
            stage="resolver",
        )
        for _ in range(2)
    ]  # 6/8 = 75% rejection
    d = DriftDetector(rejection_threshold_pct=25.0)
    sigs = d.detect(entries, now=now)
    autopilot_sigs = [s for s in sigs if s.kind == DriftSignalKind.AUTOPILOT_REJECTION_RATE_HIGH]
    assert len(autopilot_sigs) == 1
    assert autopilot_sigs[0].metric_value == 75.0


def test_autopilot_rejection_low_no_signal():
    now = datetime(2026, 6, 5, 12, 0, 0, tzinfo=timezone.utc)
    recent = (now - timedelta(days=2)).isoformat()
    entries = [
        _runtime_entry(
            ambiguity_class="auth-policy",
            decision_kind="accept",
            confidence_source="autopilot",
            created_at=recent,
        )
        for _ in range(10)
    ]
    d = DriftDetector(rejection_threshold_pct=25.0)
    sigs = d.detect(entries, now=now)
    assert not any(s.kind == DriftSignalKind.AUTOPILOT_REJECTION_RATE_HIGH for s in sigs)


# ---- 2. cost climb -----------------------------------------------------
def test_cost_climb_triggers_signal():
    now = datetime(2026, 6, 5, 12, 0, 0, tzinfo=timezone.utc)
    baseline_ts = (now - timedelta(days=15)).isoformat()
    recent_ts = (now - timedelta(days=2)).isoformat()
    entries = [
        _runtime_entry(stage="codegen", cost_usd=0.01, created_at=baseline_ts)
        for _ in range(10)
    ] + [
        _runtime_entry(stage="codegen", cost_usd=0.05, created_at=recent_ts)  # 5x baseline
        for _ in range(5)
    ]
    d = DriftDetector(cost_climb_multiplier=1.5)
    sigs = d.detect(entries, now=now)
    cost_sigs = [s for s in sigs if s.kind == DriftSignalKind.COST_PER_DECISION_CLIMBING]
    assert len(cost_sigs) == 1
    assert cost_sigs[0].stage == "codegen"


# ---- 3. class drift unprecedented -------------------------------------
def test_class_drift_with_no_precedent_triggers():
    entries = (
        [_runtime_entry(ambiguity_class="auth-policy", precedent_refs=["abc"]) for _ in range(15)]
        + [_runtime_entry(ambiguity_class="naming-convention", precedent_refs=[]) for _ in range(2)]
    )
    d = DriftDetector(class_drift_threshold_pct=5.0)
    sigs = d.detect(entries)
    drift_sigs = [s for s in sigs if s.kind == DriftSignalKind.CLASS_DRIFT_UNEXPECTED]
    assert len(drift_sigs) == 1
    assert drift_sigs[0].ambiguity_class == "naming-convention"


def test_class_with_precedent_no_drift_signal():
    entries = [
        _runtime_entry(ambiguity_class="auth-policy", precedent_refs=["abc"])
        for _ in range(15)
    ]
    d = DriftDetector()
    sigs = d.detect(entries)
    assert not any(s.kind == DriftSignalKind.CLASS_DRIFT_UNEXPECTED for s in sigs)


# ---- 4. unused rules --------------------------------------------------
def test_unused_rule_triggers_signal():
    entries = [
        _runtime_entry(bundle_refs=["security/v0.1.0/PHI-001"])
        for _ in range(5)
    ]
    known = ["security/v0.1.0/PHI-001", "security/v0.1.0/AUTH-001", "security/v0.1.0/SBOM-001"]
    d = DriftDetector()
    sigs = d.detect(entries, bundle_rule_ids=known)
    unused_sigs = [s for s in sigs if s.kind == DriftSignalKind.BUNDLE_RULE_UNUSED]
    unused_ids = {s.bundle_ref for s in unused_sigs}
    assert "security/v0.1.0/AUTH-001" in unused_ids
    assert "security/v0.1.0/SBOM-001" in unused_ids
    assert "security/v0.1.0/PHI-001" not in unused_ids


# ---- 5. PHI violation -------------------------------------------------
def test_phi_block_triggers_violation():
    entries = [
        _runtime_entry(
            runtime_kind="phi_block",
            phi_class="high",
            agent_session_id="sess-1",
            run_id=None,
            decision="blocked: raw MRN in log",
            bundle_refs=["security/v0.1.0/PHI-001"],
        )
    ]
    d = DriftDetector()
    sigs = d.detect(entries)
    phi_sigs = [s for s in sigs if s.kind == DriftSignalKind.PHI_CLASS_VIOLATION]
    assert len(phi_sigs) == 1
    assert phi_sigs[0].bundle_ref == "security/v0.1.0/PHI-001"


def test_no_phi_violation_when_phi_low():
    entries = [
        _runtime_entry(phi_class="low", decision_kind="accept", bundle_refs=[])
        for _ in range(3)
    ]
    d = DriftDetector()
    sigs = d.detect(entries)
    assert not any(s.kind == DriftSignalKind.PHI_CLASS_VIOLATION for s in sigs)
