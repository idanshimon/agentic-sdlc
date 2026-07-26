"""Tests for failure classification.

"24 failed / 48% of runs" reads as an outage. On live data most of those are the
governance layer refusing to merge code that violates a BLOCK rule — the system
working. Same number, opposite conclusion. These tests pin the distinction.
"""
from __future__ import annotations

from apps.orchestrator.telemetry_queries import _classify_failure


def _run(*messages, stage="review_scan", status="failed"):
    return {
        "current_stage": stage,
        "events": [{"stage": stage, "status": status, "message": m} for m in messages],
    }


def test_real_policy_gate_message_is_classified_as_a_block():
    """Verbatim message from the live ledger."""
    run = _run("Policy gate FAILED — 38 blocker(s): security/v0.1.0/PHI-001")
    out = _classify_failure(run)
    assert out["failure_kind"] == "policy_block"
    assert out["blocking_rules"] == ["security/v0.1.0/PHI-001"]
    assert out["blocker_count"] == 38
    assert out["failure_stage"] == "review_scan"


def test_multiple_cited_rules_are_all_captured_and_deduped():
    run = _run(
        "Policy gate FAILED — 4 blocker(s): security/v0.1.0/PHI-001, "
        "security/v0.1.0/SECRET-001, security/v0.1.0/PHI-001"
    )
    out = _classify_failure(run)
    assert out["blocking_rules"] == [
        "security/v0.1.0/SECRET-001",
        "security/v0.1.0/PHI-001",
    ] or out["blocking_rules"] == sorted(
        {"security/v0.1.0/PHI-001", "security/v0.1.0/SECRET-001"}
    )
    assert len(out["blocking_rules"]) == 2


def test_technical_failure_is_not_reported_as_a_policy_block():
    """Inflating the policy-block count would be flattering and false."""
    run = _run("Provider timeout after 60s", stage="codegen")
    out = _classify_failure(run)
    assert out["failure_kind"] == "technical"
    assert out["blocking_rules"] == []
    assert out["blocker_count"] == 0


def test_delivery_failure_is_technical():
    run = _run("Delivery blocked — synthetic provider output", stage="deliver")
    out = _classify_failure(run)
    assert out["failure_kind"] == "technical"
    assert out["failure_stage"] == "deliver"


def test_missing_message_is_unknown_not_a_block():
    """The runs API previously returned no message at all for every failure.
    Absence of evidence must not be scored as a policy win."""
    out = _classify_failure({"current_stage": "codegen", "events": []})
    assert out["failure_kind"] == "unknown"
    assert out["failure_reason"] is None
    assert out["blocking_rules"] == []


def test_last_failure_event_wins():
    run = _run(
        "Provider timeout after 60s",
        "Policy gate FAILED — 2 blocker(s): security/v0.1.0/PHI-001",
    )
    assert _classify_failure(run)["failure_kind"] == "policy_block"


def test_policy_gate_without_a_citation_still_classifies_as_block():
    run = _run("Policy gate FAILED — 3 blocker(s)")
    out = _classify_failure(run)
    assert out["failure_kind"] == "policy_block"
    assert out["blocker_count"] == 3


def test_prose_mentioning_a_rule_id_is_matched_but_lowercase_ids_are_not():
    """Guards the citation regex against matching arbitrary slash-separated text."""
    out = _classify_failure(_run("see docs/v1.2.3/notes for details"))
    assert out["blocking_rules"] == []
    assert out["failure_kind"] == "technical"
