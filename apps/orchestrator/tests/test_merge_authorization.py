"""Tests for merge authorization (6d.1, 6d.8, 6d.10) and protection drift (6a.4).

Every case here is an attack or a failure mode the adversarial review named.
The happy path is one test; the rest is everything that must be refused.
"""
from __future__ import annotations

import pytest

from orchestrator.merge_authorization import (
    Approval,
    MergeState,
    ProtectionFinding,
    Refusal,
    authorize,
    evaluate_merge,
    scan_ref_protection,
)

SHA_OK = "a" * 40
SHA_OTHER = "b" * 40
PATCH = "digest-1"


def _state(**kw) -> MergeState:
    base = dict(
        repository_id="repo-1",
        root_gate_instance="gate-1",
        parent_pr="36",
        parent_head_sha="p" * 40,
        target_base_sha="t" * 40,
        policy_bundle_digest="bundle-v1",
        remediation_head_sha=SHA_OK,
    )
    base.update(kw)
    return MergeState(**base)


def _human(i="reviewer@x.com", sha=SHA_OK, roles=()):
    return Approval(i, "human", PATCH, sha, roles)


def _ok(**kw):
    st = kw.pop("state", _state())
    auth = kw.pop("auth", authorize(st, gate_instance="gate-1", classification="scope-resolution"))
    args = dict(
        current_state=st, authorization=auth, attempted_sha=SHA_OK,
        approvals=[_human()], patch_digest=PATCH, requester_id="bot@x.com",
    )
    args.update(kw)
    return evaluate_merge(**args)


# --- the one happy path ------------------------------------------------------

def test_authorized_merge_with_independent_human_approval_is_permitted():
    v = _ok()
    assert v.permitted and v.refusal is None
    assert v.gate_reason is None


# --- the chokepoint ----------------------------------------------------------

def test_no_authorization_refuses():
    v = _ok(auth=None)
    assert v.refusal is Refusal.NO_AUTHORIZATION
    assert "advisory" in v.detail


def test_authorization_does_not_transfer_to_another_sha():
    """The base moved, so the merge produces a different commit."""
    v = _ok(attempted_sha=SHA_OTHER)
    assert v.refusal is Refusal.SHA_MISMATCH


def test_force_push_to_parent_invalidates_authorization():
    st = _state()
    auth = authorize(st, gate_instance="gate-1", classification="scope-resolution")
    moved = MergeState(**{**st.__dict__, "parent_head_sha": "z" * 40})
    v = evaluate_merge(current_state=moved, authorization=auth, attempted_sha=SHA_OK,
                       approvals=[_human()], patch_digest=PATCH, requester_id="bot@x.com")
    assert v.refusal is Refusal.STATE_DRIFT


def test_base_branch_movement_invalidates_authorization():
    st = _state()
    auth = authorize(st, gate_instance="gate-1", classification="scope-resolution")
    moved = MergeState(**{**st.__dict__, "target_base_sha": "z" * 40})
    v = evaluate_merge(current_state=moved, authorization=auth, attempted_sha=SHA_OK,
                       approvals=[_human()], patch_digest=PATCH, requester_id="bot@x.com")
    assert v.refusal is Refusal.STATE_DRIFT


def test_policy_rotation_mid_review_invalidates_authorization():
    st = _state()
    auth = authorize(st, gate_instance="gate-1", classification="scope-resolution")
    rotated = MergeState(**{**st.__dict__, "policy_bundle_digest": "bundle-v2"})
    v = evaluate_merge(current_state=rotated, authorization=auth, attempted_sha=SHA_OK,
                       approvals=[_human()], patch_digest=PATCH, requester_id="bot@x.com")
    assert v.refusal is Refusal.POLICY_ROTATED


# --- an agent must not close its own loop ------------------------------------

def test_agent_approval_does_not_count():
    v = _ok(approvals=[Approval("agent:bot", "agent", PATCH, SHA_OK)])
    assert v.refusal is Refusal.AGENT_SELF_APPROVAL


def test_requester_cannot_approve_their_own_remediation():
    v = _ok(approvals=[_human("bot@x.com")], requester_id="bot@x.com")
    assert v.refusal is Refusal.AGENT_SELF_APPROVAL


def test_agent_operator_cannot_approve_the_agents_work():
    v = _ok(approvals=[_human("operator@x.com")], agent_operator_id="operator@x.com")
    assert v.refusal is Refusal.AGENT_SELF_APPROVAL


def test_unverified_provenance_refuses_before_anything_else():
    v = _ok(provenance_verified=False)
    assert v.refusal is Refusal.UNVERIFIED_PROVENANCE


# --- approval binds to the exact diff and result -----------------------------

def test_approval_of_a_different_patch_does_not_count():
    v = _ok(approvals=[Approval("reviewer@x.com", "human", "digest-OTHER", SHA_OK)])
    assert v.refusal is Refusal.AGENT_SELF_APPROVAL


def test_approval_of_a_different_merge_sha_does_not_count():
    v = _ok(approvals=[_human(sha=SHA_OTHER)])
    assert v.refusal is Refusal.AGENT_SELF_APPROVAL


# --- quorum ------------------------------------------------------------------

def test_one_approval_fails_a_two_approver_quorum():
    v = _ok(required_approvers=2)
    assert v.refusal is Refusal.QUORUM_SHORT
    assert "one-of-six" in v.detail


def test_two_distinct_humans_satisfy_a_two_approver_quorum():
    v = _ok(approvals=[_human("a@x.com"), _human("b@x.com")], required_approvers=2)
    assert v.permitted


def test_the_same_human_twice_is_one_approval():
    v = _ok(approvals=[_human("a@x.com"), _human("a@x.com")], required_approvers=2)
    assert v.refusal is Refusal.QUORUM_SHORT


def test_missing_required_role_refuses():
    v = _ok(approvals=[_human("a@x.com", roles=("security_lead",))],
            must_include_roles=("privacy_dpo",))
    assert v.refusal is Refusal.QUORUM_SHORT
    assert "privacy_dpo" in v.detail


def test_required_roles_satisfied_permits():
    v = _ok(approvals=[_human("a@x.com", roles=("security_lead", "privacy_dpo"))],
            must_include_roles=("privacy_dpo",))
    assert v.permitted


# --- concurrency and budget --------------------------------------------------

def test_sibling_remediations_refuse():
    v = _ok(active_remediations=2)
    assert v.refusal is Refusal.CONCURRENT_REMEDIATION


def test_exhausted_budget_refuses_and_maps_to_budget_exceeded():
    v = _ok(budget_remaining=0)
    assert v.refusal is Refusal.BUDGET_EXCEEDED
    assert v.gate_reason == "budget_exceeded"


# --- refusals map onto the ledger vocabulary ---------------------------------

def test_every_refusal_yields_a_typed_gate_reason():
    valid = {"invariant_class", "autonomy_tier", "low_precedent", "budget_exceeded",
             "verification_failed", "stalled", "operator_requested"}
    for kw in ({"auth": None}, {"attempted_sha": SHA_OTHER}, {"budget_remaining": 0},
               {"active_remediations": 3}, {"provenance_verified": False},
               {"required_approvers": 5}):
        v = _ok(**kw)
        assert not v.permitted
        assert v.gate_reason in valid, f"{v.refusal} produced {v.gate_reason}"


def test_refusal_details_are_operator_readable():
    for kw in ({"auth": None}, {"attempted_sha": SHA_OTHER}, {"budget_remaining": 0}):
        v = _ok(**kw)
        assert len(v.detail) > 40, "a refusal must explain itself"


# --- protection drift (6a.4) -------------------------------------------------

def _snapshot(**kw):
    base = dict(
        enforce_admins=True, prevent_self_review=True, allow_force_pushes=False,
        required_status_checks={"contexts": ["bundle-enforce"],
                                "checks": [{"context": "bundle-enforce", "app_id": 1}]},
        required_pull_request_reviews={"required_approving_review_count": 1},
    )
    base.update(kw)
    return base


def test_a_correctly_configured_ref_has_no_findings():
    assert scan_ref_protection(_snapshot()) == []


def test_admin_bypass_enabled_is_a_finding():
    f = scan_ref_protection(_snapshot(enforce_admins=False))
    assert any(x.control == "admin_bypass" for x in f)


def test_missing_admin_setting_is_treated_as_enabled():
    """ON by default in GitHub — absence must read as the dangerous case."""
    snap = _snapshot()
    del snap["enforce_admins"]
    assert any(x.control == "admin_bypass" for x in scan_ref_protection(snap))


def test_name_only_required_checks_is_a_finding():
    f = scan_ref_protection(_snapshot(
        required_status_checks={"contexts": ["bundle-enforce"], "checks": []}))
    assert any(x.control == "unbound_checks" for x in f)


def test_force_push_allowed_is_a_finding():
    f = scan_ref_protection(_snapshot(allow_force_pushes=True))
    assert any(x.control == "force_push" for x in f)


def test_no_review_requirement_is_a_finding():
    f = scan_ref_protection(_snapshot(required_pull_request_reviews=None))
    assert any(x.control == "no_review_requirement" for x in f)


def test_empty_snapshot_reports_every_control_missing():
    """An unreachable or empty snapshot must not read as compliant."""
    assert len(scan_ref_protection({})) >= 4


# --- honesty -----------------------------------------------------------------

def test_module_states_it_does_not_configure_the_ref():
    """This proves a merge SHOULD be refused. Only a governed ref proves one WAS."""
    import inspect

    from orchestrator import merge_authorization

    doc = inspect.getdoc(merge_authorization) or ""
    assert "NOT" in doc
    assert "ruleset" in doc.lower() or "repository settings" in doc.lower()
