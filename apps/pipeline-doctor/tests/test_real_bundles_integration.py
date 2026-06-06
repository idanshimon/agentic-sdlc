"""Integration tests: load real standards bundles, run validator against them.

This is the smoke test that proves the bundle schema + envelope validator
work together against the real reference bundles.
"""
import pytest
from pathlib import Path

from pipeline_doctor.envelope_validator import (
    EnvelopeValidator, load_envelope, load_rules,
)
from pipeline_doctor.models import AutoFixProposal


REPO_ROOT = Path(__file__).resolve().parents[3]
STANDARDS = REPO_ROOT / "standards-bundles"


def _load_bundle(dept: str, version: str = "v0.1.0"):
    base = STANDARDS / dept / version
    return EnvelopeValidator(
        envelope_yaml=load_envelope(str(base / "envelope.yaml")),
        bundle_rules=load_rules(str(base / "rules.yaml")),
    )


# ---- security: every rule is read-only --------------------------------------
def test_security_bundle_blocks_all_auto_fixes():
    """Security envelope is empty; ANY auto-fix attempt is rejected."""
    v = _load_bundle("security")
    p = AutoFixProposal(
        triggered_by="s1", bundle_ref="security/v0.1.0/SECRET-001",
        rule_id="SECRET-001", field_path="severity",
        current_value="BLOCK", proposed_value="WARN",
        rationale="false positives",
    )
    result = v.validate(p, recent_fix_count_for_dept=0,
                        precondition_state={"drift_signal_present_for_days": 30,
                                            "phi_class_not_high": True})
    assert result.allowed is False


def test_security_phi_rule_hard_blocked():
    v = _load_bundle("security")
    p = AutoFixProposal(
        triggered_by="s2", bundle_ref="security/v0.1.0/PHI-001",
        rule_id="PHI-001", field_path="severity",
        current_value="BLOCK", proposed_value="WARN",
        rationale="redaction works",
    )
    result = v.validate(p)
    assert result.allowed is False
    assert any(viol.reason == "phi_rule_forbidden" for viol in result.violations)


# ---- privacy: every rule is read-only --------------------------------------
def test_privacy_bundle_blocks_all_auto_fixes():
    v = _load_bundle("privacy")
    p = AutoFixProposal(
        triggered_by="p1", bundle_ref="privacy/v0.1.0/RETENTION-OPS-001",
        rule_id="RETENTION-OPS-001", field_path="years",
        current_value=3, proposed_value=2,
        rationale="storage cost",
    )
    result = v.validate(p)
    assert result.allowed is False


# ---- architect: bounded auto-fix on retry counts ---------------------------
def test_architect_retry_count_in_bounds_passes():
    v = _load_bundle("architect")
    p = AutoFixProposal(
        triggered_by="a1", bundle_ref="architect/v0.1.0/RETRY-COUNT-001",
        rule_id="RETRY-COUNT-001",
        field_path="RETRY-COUNT-001.defaults.retry_count",
        current_value=3, proposed_value=4,
        rationale="transient errors observed",
    )
    result = v.validate(p, recent_fix_count_for_dept=0,
                        precondition_state={"drift_signal_present_for_days": 9})
    assert result.allowed is True, result.violations


def test_architect_retry_count_out_of_bounds_fails():
    v = _load_bundle("architect")
    p = AutoFixProposal(
        triggered_by="a2", bundle_ref="architect/v0.1.0/RETRY-COUNT-001",
        rule_id="RETRY-COUNT-001",
        field_path="RETRY-COUNT-001.defaults.retry_count",
        current_value=3, proposed_value=10,  # > max 5
        rationale="x",
    )
    result = v.validate(p, recent_fix_count_for_dept=0,
                        precondition_state={"drift_signal_present_for_days": 9})
    assert result.allowed is False
    assert any(viol.reason == "out_of_bounds" for viol in result.violations)


def test_architect_allowed_stacks_forbidden_by_rule_id():
    """ALLOWED-STACKS-001 is in `forbidden.rule_id`; auto-fix must fail."""
    v = _load_bundle("architect")
    p = AutoFixProposal(
        triggered_by="a3", bundle_ref="architect/v0.1.0/ALLOWED-STACKS-001",
        rule_id="ALLOWED-STACKS-001",
        field_path="ALLOWED-STACKS-001.allowed_values",
        current_value=["python>=3.11"], proposed_value=["python>=3.12"],
        rationale="x",
    )
    result = v.validate(p)
    assert result.allowed is False


# ---- finops: bounded auto-fix on autopilot thresholds ----------------------
def test_finops_threshold_in_bounds_passes():
    v = _load_bundle("finops")
    p = AutoFixProposal(
        triggered_by="f1", bundle_ref="finops/v0.1.0/AUTOPILOT-THRESHOLD-AUTH",
        rule_id="AUTOPILOT-THRESHOLD-AUTH",
        field_path="AUTOPILOT-THRESHOLD-AUTH.defaults.threshold",
        current_value=0.85, proposed_value=0.82,  # delta 0.03 within max_delta 0.05
        rationale="rejection rate climbing",
    )
    result = v.validate(p, recent_fix_count_for_dept=0,
                        precondition_state={"drift_signal_present_for_days": 9,
                                            "phi_class_not_high": True})
    assert result.allowed is True, result.violations


def test_finops_budget_change_forbidden():
    """BUDGET-MONTHLY-001 is in finops envelope's `forbidden.rule_id`."""
    v = _load_bundle("finops")
    p = AutoFixProposal(
        triggered_by="f2", bundle_ref="finops/v0.1.0/BUDGET-MONTHLY-001",
        rule_id="BUDGET-MONTHLY-001",
        field_path="BUDGET-MONTHLY-001.defaults.monthly_budget_usd",
        current_value=5000, proposed_value=10000,
        rationale="x",
    )
    result = v.validate(p)
    assert result.allowed is False


def test_finops_threshold_max_delta_violation():
    v = _load_bundle("finops")
    p = AutoFixProposal(
        triggered_by="f3", bundle_ref="finops/v0.1.0/AUTOPILOT-THRESHOLD-AUTH",
        rule_id="AUTOPILOT-THRESHOLD-AUTH",
        field_path="AUTOPILOT-THRESHOLD-AUTH.defaults.threshold",
        current_value=0.85, proposed_value=0.95,  # delta 0.10 > max_delta 0.05
        rationale="x",
    )
    result = v.validate(p, recent_fix_count_for_dept=0,
                        precondition_state={"drift_signal_present_for_days": 9,
                                            "phi_class_not_high": True})
    assert result.allowed is False
    assert any(viol.reason == "out_of_bounds" for viol in result.violations)
