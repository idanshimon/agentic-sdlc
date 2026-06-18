"""Tests for the self-heal safety kernel (apps/orchestrator/heal.py).

These pin the spec scenarios from add-self-heal-cowork. The kernel is the
decision-independent core: it holds regardless of whether the executor ends
up being the GitHub Copilot SDK or a Foundry agent.

Run: PYTHONPATH=. .venv/bin/python -m pytest apps/orchestrator/tests/test_heal.py -v
"""
from __future__ import annotations

import pytest

from apps.orchestrator.heal import (
    HealAction,
    HealActionType,
    HealDecision,
    HealExecution,
    HealProposal,
    HealTrigger,
    HealValidationOutcome,
    WRITE_CAUSING_ACTIONS,
    CODE_MUTATING_ACTIONS,
    assert_human_invoked,
    validate_heal_action,
)


# --- PHI / deny / invariant blocking (spec: "MUST never be auto-healed") -----
def test_phi_touching_heal_escalates_not_blocks_silently():
    """A heal that touches a phi:true rule must ESCALATE to a human-authored
    standards change — never auto-applied, never silently dropped."""
    action = HealAction(
        action_type=HealActionType.BUMP_BUNDLE_RULE,
        summary="Loosen PHI logging rule",
        touches_phi_rule=True,
    )
    result = validate_heal_action(action)
    assert result.outcome == HealValidationOutcome.ESCALATE
    assert result.escalation_path == "standards-change"
    assert result.requires_human_approval is True


def test_phi_classification_target_class_escalates():
    action = HealAction(
        action_type=HealActionType.ADJUST_AUTOPILOT,
        summary="Lower autopilot threshold on phi-classification",
        target_class="phi-classification",
    )
    result = validate_heal_action(action)
    assert result.outcome == HealValidationOutcome.ESCALATE


def test_auth_policy_invariant_class_escalates():
    """auth-policy is in INVARIANT_CLASSES alongside phi — also escalates."""
    action = HealAction(
        action_type=HealActionType.ADJUST_AUTOPILOT,
        summary="Tune auth-policy autopilot",
        target_class="auth-policy",
    )
    result = validate_heal_action(action)
    assert result.outcome == HealValidationOutcome.ESCALATE


def test_deny_rule_pattern_is_hard_blocked():
    """Explicit-deny rules can never be loosened — BLOCK, no path forward."""
    action = HealAction(
        action_type=HealActionType.BUMP_BUNDLE_RULE,
        summary="Loosen a deny rule",
        target_rule_pattern="deny/egress-to-public-internet",
    )
    result = validate_heal_action(action)
    assert result.outcome == HealValidationOutcome.BLOCK


# --- the permissive path STILL requires approval -----------------------------
def test_benign_heal_allows_but_always_requires_approval():
    """The most permissive outcome is ALLOW_WITH_APPROVAL. Nothing auto-applies."""
    action = HealAction(
        action_type=HealActionType.RERUN_STAGE,
        summary="Re-run the failed codegen stage with same inputs",
        stage="codegen",
    )
    result = validate_heal_action(action)
    assert result.outcome == HealValidationOutcome.ALLOW_WITH_APPROVAL
    assert result.requires_human_approval is True


def test_no_validator_outcome_ever_bypasses_human_approval():
    """Property: across every action type, requires_human_approval is always True."""
    for at in HealActionType:
        action = HealAction(action_type=at, summary=f"test {at.value}")
        result = validate_heal_action(action)
        assert result.requires_human_approval is True, (
            f"{at.value} produced a result that does not require approval"
        )


def test_assign_code_heal_allows_with_approval_when_no_governed_rule():
    """A pure code heal that touches no governed rule is allowed (with approval)."""
    action = HealAction(
        action_type=HealActionType.ASSIGN_CODE_HEAL,
        summary="Fix the off-by-one in the eligibility check",
        stage="codegen",
    )
    result = validate_heal_action(action)
    assert result.outcome == HealValidationOutcome.ALLOW_WITH_APPROVAL


# --- every action is write-causing (fail-closed contract) --------------------
def test_every_action_type_is_classified_write_causing():
    """If a new action type is added without classifying it, this fails — the
    fail-closed guard that forces a deliberate approval decision per action."""
    for at in HealActionType:
        assert at in WRITE_CAUSING_ACTIONS, (
            f"{at.value} is not in WRITE_CAUSING_ACTIONS — every heal action "
            "must be explicitly classified so none slips past the approval gate"
        )


def test_code_mutating_actions_are_exactly_assign_code_heal():
    assert CODE_MUTATING_ACTIONS == {HealActionType.ASSIGN_CODE_HEAL}


# --- human-invoked-only (spec: "MUST be human-invoked at a gate or run end") -
def test_run_end_heal_requires_terminal_status():
    # valid: completed / failed
    assert_human_invoked(HealTrigger.AT_RUN_END, "completed")  # no raise
    assert_human_invoked(HealTrigger.AT_RUN_END, "failed")     # no raise


def test_run_end_heal_rejects_running_status():
    with pytest.raises(ValueError, match="terminal run"):
        assert_human_invoked(HealTrigger.AT_RUN_END, "running")


def test_gate_heal_requires_awaiting_gate_status():
    assert_human_invoked(HealTrigger.AT_GATE, "awaiting_gate")  # no raise


def test_gate_heal_rejects_completed_status():
    with pytest.raises(ValueError, match="paused at a gate"):
        assert_human_invoked(HealTrigger.AT_GATE, "completed")


# --- the heal_id chain (spec: "pinned to the ledger as a typed decision class")
def test_heal_chain_shares_heal_id():
    """heal_proposed -> heal_decided -> heal_executed must share heal_id so the
    chain is reconstructable."""
    proposal = HealProposal(
        run_id="run-123",
        team_id="cardiology",
        trigger=HealTrigger.AT_RUN_END,
        action=HealAction(
            action_type=HealActionType.ASSIGN_CODE_HEAL,
            summary="Heal red codegen tests",
            stage="codegen",
        ),
    )
    decision = HealDecision(
        heal_id=proposal.heal_id,
        approver_id="idan@microsoft.com",
        approved=True,
    )
    execution = HealExecution(
        heal_id=proposal.heal_id,
        result_ref="https://github.com/idanshimon/agentic-sdlc/pull/42",
        success=True,
    )
    assert proposal.heal_id == decision.heal_id == execution.heal_id
    # the decided step carries a human approver
    assert decision.approver_id == "idan@microsoft.com"
    # the executed step references a PR, not a merged commit
    assert execution.result_ref.startswith("https://github.com/")
    assert "/pull/" in execution.result_ref


def test_heal_proposal_defaults_unique_ids():
    p1 = HealProposal(
        run_id="r1", team_id="t", trigger=HealTrigger.AT_RUN_END,
        action=HealAction(action_type=HealActionType.RERUN_STAGE, summary="x"),
    )
    p2 = HealProposal(
        run_id="r2", team_id="t", trigger=HealTrigger.AT_RUN_END,
        action=HealAction(action_type=HealActionType.RERUN_STAGE, summary="y"),
    )
    assert p1.heal_id != p2.heal_id
