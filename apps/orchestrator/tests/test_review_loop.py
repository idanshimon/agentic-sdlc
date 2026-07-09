"""Tests for the bounded autonomous review-loop controller (PR-3).

The pure decision core `plan_next_loop_action` is the governor: given a review
verdict, the attempt index, the repo's autonomy tier, accumulated cost, and
whether a PHI/deny blocker is present, it returns exactly one LoopAction. Every
branch of the truth table is tested with zero I/O.

Contract: openspec/changes/add-autonomous-review-loop spec deltas.

Run:
    source .venv/bin/activate
    python -m pytest apps/orchestrator/tests/test_review_loop.py -q
"""
from __future__ import annotations

import pytest

from apps.orchestrator import review_loop as rl
from apps.orchestrator.models import Blocker, ReviewVerdict


PASS = ReviewVerdict(status="PASS")
FAIL = ReviewVerdict(status="FAIL", blockers=[
    Blocker(check="secret-scan", rule="security/v0.1.0/SECRET-001",
            detail="hardcoded secret", file="a.py", line=1, phi=False)])
FAIL_PHI = ReviewVerdict(status="FAIL", blockers=[
    Blocker(check="privacy-scan", rule="security/v0.1.0/PHI-001",
            detail="MRN in logs", file="a.py", line=2, phi=True)])


# --------------------------------------------------------------------------
# PASS verdicts -> merge behavior depends on tier
# --------------------------------------------------------------------------

def test_pass_on_tier_a_auto_merges():
    action = rl.plan_next_loop_action(PASS, attempt=1, tier="A", cost_usd=0.1)
    assert action == rl.LoopAction.MERGE


def test_pass_on_tier_b_awaits_human_merge():
    action = rl.plan_next_loop_action(PASS, attempt=1, tier="B", cost_usd=0.1)
    assert action == rl.LoopAction.AWAIT_HUMAN_MERGE


def test_pass_on_tier_c_comments_only():
    action = rl.plan_next_loop_action(PASS, attempt=1, tier="C", cost_usd=0.1)
    assert action == rl.LoopAction.COMMENT_ONLY


# --------------------------------------------------------------------------
# FAIL verdicts -> remediate on A/B (within bounds), comment on C
# --------------------------------------------------------------------------

def test_fail_on_tier_a_remediates_within_attempt_bound():
    action = rl.plan_next_loop_action(FAIL, attempt=1, tier="A", cost_usd=0.1)
    assert action == rl.LoopAction.REMEDIATE


def test_fail_on_tier_b_remediates_within_attempt_bound():
    action = rl.plan_next_loop_action(FAIL, attempt=2, tier="B", cost_usd=0.1)
    assert action == rl.LoopAction.REMEDIATE


def test_fail_on_tier_c_comments_only_never_remediates():
    action = rl.plan_next_loop_action(FAIL, attempt=1, tier="C", cost_usd=0.1)
    assert action == rl.LoopAction.COMMENT_ONLY


# --------------------------------------------------------------------------
# Attempt bound -> exhaustion escalates, never merges, never loops forever
# --------------------------------------------------------------------------

def test_fail_at_max_attempts_escalates():
    action = rl.plan_next_loop_action(
        FAIL, attempt=rl.MAX_ATTEMPTS, tier="A", cost_usd=0.1)
    assert action == rl.LoopAction.ESCALATE


def test_fail_beyond_max_attempts_escalates():
    action = rl.plan_next_loop_action(
        FAIL, attempt=rl.MAX_ATTEMPTS + 1, tier="A", cost_usd=0.1)
    assert action == rl.LoopAction.ESCALATE


# --------------------------------------------------------------------------
# Cost ceiling -> escalates regardless of tier/attempt
# --------------------------------------------------------------------------

def test_cost_over_ceiling_escalates():
    action = rl.plan_next_loop_action(
        FAIL, attempt=1, tier="A", cost_usd=rl.COST_CEILING_USD + 1)
    assert action == rl.LoopAction.ESCALATE


def test_cost_exactly_at_ceiling_still_remediates():
    action = rl.plan_next_loop_action(
        FAIL, attempt=1, tier="A", cost_usd=rl.COST_CEILING_USD)
    assert action == rl.LoopAction.REMEDIATE


# --------------------------------------------------------------------------
# PHI/deny floor -> escalate regardless of tier, NEVER remediate or merge
# --------------------------------------------------------------------------

def test_phi_blocker_escalates_even_on_tier_a():
    action = rl.plan_next_loop_action(FAIL_PHI, attempt=1, tier="A", cost_usd=0.1)
    assert action == rl.LoopAction.ESCALATE


def test_phi_blocker_escalates_on_tier_b():
    action = rl.plan_next_loop_action(FAIL_PHI, attempt=1, tier="B", cost_usd=0.1)
    assert action == rl.LoopAction.ESCALATE


def test_phi_floor_beats_everything_even_a_pass_is_moot():
    """A PHI blocker means status is FAIL by construction; the floor fires
    before tier/attempt/cost are even consulted."""
    action = rl.plan_next_loop_action(FAIL_PHI, attempt=1, tier="A", cost_usd=0.0)
    assert action == rl.LoopAction.ESCALATE


def test_has_phi_or_deny_helper():
    assert rl.has_phi_or_deny(FAIL_PHI) is True
    assert rl.has_phi_or_deny(FAIL) is False
    assert rl.has_phi_or_deny(PASS) is False


# --------------------------------------------------------------------------
# Structured citation for the controller's decision (grep-able)
# --------------------------------------------------------------------------

def test_citation_format_for_each_action():
    assert rl.loop_citation("A", "delivery-repo", rl.LoopAction.MERGE, attempt=2) == \
        "reviewloop/A/delivery-repo/merge@attempt=2"
    assert rl.loop_citation("A", "r", rl.LoopAction.ESCALATE, attempt=3,
                            reason="max_attempts") == \
        "reviewloop/A/r/escalate@attempt=3:max_attempts"


def test_invalid_tier_defaults_to_safest_comment_only():
    """An unknown tier must never auto-act — treat as advisory (safe by absence)."""
    action = rl.plan_next_loop_action(FAIL, attempt=1, tier="Z", cost_usd=0.1)
    assert action == rl.LoopAction.COMMENT_ONLY
