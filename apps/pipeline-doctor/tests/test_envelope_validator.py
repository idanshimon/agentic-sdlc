"""Tests for envelope_validator — PHI block, deny block, bounds, preconditions, rate limit."""
import pytest
from pipeline_doctor.envelope_validator import EnvelopeValidator
from pipeline_doctor.models import AutoFixProposal


# ---- fixtures ---------------------------------------------------------------
@pytest.fixture
def finops_envelope():
    return {
        "allowed_auto_fixes": [
            {
                "rule_pattern": "autopilot.threshold.*",
                "bounds": {"min": 0.80, "max": 0.95, "max_delta_per_run": 0.05},
                "requires": [
                    {"drift_signal_present_for_days": 7},
                    {"phi_class_not_high": True},
                ],
            },
        ],
        "rate_limits": {"max_per_dept_per_window": 5},
        "forbidden": [],
    }


@pytest.fixture
def finops_rules():
    return {
        "metadata": {"bundle": "finops", "version": "0.1.0"},
        "rules": [
            {
                "id": "AUTOPILOT-THRESHOLD-AUTH",
                "title": "Autopilot threshold for auth-policy class",
                "phi": False,
                "severity": "WARN",
            },
            {
                "id": "AUTOPILOT-THRESHOLD-PHI",
                "title": "Autopilot threshold for phi-classification (forbidden auto)",
                "phi": True,
                "severity": "BLOCK",
            },
            {
                "id": "DENY-PII-LOG",
                "title": "Deny PII in logs",
                "phi": False,
                "severity": "BLOCK",
                "rule_pattern": "deny/pii-log",
            },
        ],
    }


@pytest.fixture
def validator(finops_envelope, finops_rules):
    return EnvelopeValidator(finops_envelope, finops_rules)


# ---- HARD RULES -------------------------------------------------------------
def test_phi_rule_always_blocked(validator):
    p = AutoFixProposal(
        triggered_by="signal-1",
        bundle_ref="finops/v0.1.0/AUTOPILOT-THRESHOLD-PHI",
        rule_id="AUTOPILOT-THRESHOLD-PHI",
        field_path="autopilot.threshold.phi-classification",
        current_value=0.85,
        proposed_value=0.83,
        rationale="rejection rate climbing",
    )
    result = validator.validate(p, recent_fix_count_for_dept=0,
                                precondition_state={"drift_signal_present_for_days": 9,
                                                    "phi_class_not_high": True})
    assert result.allowed is False
    assert any(v.reason == "phi_rule_forbidden" for v in result.violations)


def test_deny_pattern_blocked(validator):
    p = AutoFixProposal(
        triggered_by="signal-2",
        bundle_ref="finops/v0.1.0/DENY-PII-LOG",
        rule_id="DENY-PII-LOG",
        field_path="deny.pii-log.severity",
        current_value="BLOCK",
        proposed_value="WARN",
        rationale="false positives",
    )
    result = validator.validate(p)
    assert result.allowed is False
    assert any(v.reason in ("deny_pattern_forbidden",) for v in result.violations)


# ---- ENVELOPE BOUNDS --------------------------------------------------------
def test_within_bounds_passes(validator):
    p = AutoFixProposal(
        triggered_by="signal-3",
        bundle_ref="finops/v0.1.0/AUTOPILOT-THRESHOLD-AUTH",
        rule_id="AUTOPILOT-THRESHOLD-AUTH",
        field_path="autopilot.threshold.auth-policy",
        current_value=0.85,
        proposed_value=0.82,  # delta 0.03, within max_delta 0.05
        rationale="rejection rate climbing for auth-policy",
    )
    result = validator.validate(
        p, recent_fix_count_for_dept=0,
        precondition_state={"drift_signal_present_for_days": 9, "phi_class_not_high": True},
    )
    assert result.allowed is True
    assert result.violations == []


def test_below_min_bound_fails(validator):
    p = AutoFixProposal(
        triggered_by="s4",
        bundle_ref="finops/v0.1.0/AUTOPILOT-THRESHOLD-AUTH",
        rule_id="AUTOPILOT-THRESHOLD-AUTH",
        field_path="autopilot.threshold.auth-policy",
        current_value=0.85,
        proposed_value=0.70,  # below min 0.80
        rationale="x",
    )
    result = validator.validate(
        p, recent_fix_count_for_dept=0,
        precondition_state={"drift_signal_present_for_days": 9, "phi_class_not_high": True},
    )
    assert result.allowed is False
    assert any(v.reason == "out_of_bounds" for v in result.violations)


def test_above_max_delta_fails(validator):
    p = AutoFixProposal(
        triggered_by="s5",
        bundle_ref="finops/v0.1.0/AUTOPILOT-THRESHOLD-AUTH",
        rule_id="AUTOPILOT-THRESHOLD-AUTH",
        field_path="autopilot.threshold.auth-policy",
        current_value=0.85,
        proposed_value=0.92,  # delta 0.07, > max_delta 0.05
        rationale="x",
    )
    result = validator.validate(
        p, recent_fix_count_for_dept=0,
        precondition_state={"drift_signal_present_for_days": 9, "phi_class_not_high": True},
    )
    assert result.allowed is False
    assert any(v.reason == "out_of_bounds" for v in result.violations)


def test_field_not_in_envelope_fails(validator):
    p = AutoFixProposal(
        triggered_by="s6",
        bundle_ref="finops/v0.1.0/AUTOPILOT-THRESHOLD-AUTH",
        rule_id="AUTOPILOT-THRESHOLD-AUTH",
        field_path="some.unrelated.config",  # doesn't match autopilot.threshold.*
        current_value=1,
        proposed_value=2,
        rationale="x",
    )
    result = validator.validate(p)
    assert result.allowed is False
    assert any(v.reason == "rule_not_in_envelope" for v in result.violations)


# ---- PRECONDITIONS ----------------------------------------------------------
def test_precondition_unmet_fails(validator):
    p = AutoFixProposal(
        triggered_by="s7",
        bundle_ref="finops/v0.1.0/AUTOPILOT-THRESHOLD-AUTH",
        rule_id="AUTOPILOT-THRESHOLD-AUTH",
        field_path="autopilot.threshold.auth-policy",
        current_value=0.85,
        proposed_value=0.82,
        rationale="x",
    )
    result = validator.validate(
        p, recent_fix_count_for_dept=0,
        precondition_state={"drift_signal_present_for_days": 3,  # < 7 required
                            "phi_class_not_high": True},
    )
    assert result.allowed is False
    assert any(v.reason == "preconditions_unmet" for v in result.violations)


# ---- RATE LIMIT -------------------------------------------------------------
def test_rate_limit_exceeded_fails(validator):
    p = AutoFixProposal(
        triggered_by="s8",
        bundle_ref="finops/v0.1.0/AUTOPILOT-THRESHOLD-AUTH",
        rule_id="AUTOPILOT-THRESHOLD-AUTH",
        field_path="autopilot.threshold.auth-policy",
        current_value=0.85,
        proposed_value=0.82,
        rationale="x",
    )
    result = validator.validate(
        p, recent_fix_count_for_dept=5,  # at the limit
        precondition_state={"drift_signal_present_for_days": 9, "phi_class_not_high": True},
    )
    assert result.allowed is False
    assert any(v.reason == "rate_limit_exceeded" for v in result.violations)


def test_rate_limit_under_limit_passes(validator):
    p = AutoFixProposal(
        triggered_by="s9",
        bundle_ref="finops/v0.1.0/AUTOPILOT-THRESHOLD-AUTH",
        rule_id="AUTOPILOT-THRESHOLD-AUTH",
        field_path="autopilot.threshold.auth-policy",
        current_value=0.85,
        proposed_value=0.82,
        rationale="x",
    )
    result = validator.validate(
        p, recent_fix_count_for_dept=4,  # under limit 5
        precondition_state={"drift_signal_present_for_days": 9, "phi_class_not_high": True},
    )
    assert result.allowed is True
