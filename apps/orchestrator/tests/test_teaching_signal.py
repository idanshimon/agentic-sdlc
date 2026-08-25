"""`autopilot_above_threshold` is currently unreachable — and silently so.

Task 5.x of adopt-github-native-execution-substrate.

THE DEFECT

`main.py` gates a card on `score < rule.threshold`, where

    score = getattr(precedent, "accuracy_score", 0.0) if precedent else 0.0

`accuracy_score` defaults to `0.0` and **no code path in the system ever writes
it**. The MCP `findPrecedent` does not populate it either. So the score is
always `0.0`, and every configured threshold in `config/autonomy.yaml.example`
is above zero (0.75, 0.8, 0.9). The comparison is therefore always true and the
mode always gates.

That is not merely an unpopulated field. It is a **configuration surface that
silently does nothing**. An operator sets `threshold: 0.8` believing they have
tuned autonomy; the effective behaviour is identical to `mode: gate`, and
nothing in the system says so. Lowering the threshold to 0.1 to "loosen" it
changes nothing either. The steering wheel is not connected to the wheels.

WHY THIS IS THE HONESTY BUG, NOT A MISSING FEATURE

Everything else outstanding in this change is an absent capability, which is
merely incomplete. This one **claims an assurance it does not provide**: the
autonomy matrix is presented as the COE's control over agent autonomy, and one
of its three modes is inert. A governed system whose governance knob is
disconnected is worse than one that never offered the knob.

WHAT THESE TESTS FIX IN PLACE

Until a compute site exists (§5 proper), `autopilot_above_threshold` MUST NOT
present itself as functioning. It must fail closed *loudly*: gate, and record
that it gated because the signal is unavailable — not because the precedent
scored badly. Those are different facts and an operator needs to tell them
apart.

`gate_reason` already has the right value for this: `low_precedent` means the
precedent was weak. A missing signal is `verification_failed` — we could not
evaluate the rule at all.
"""
from __future__ import annotations

import pytest

from orchestrator.teaching_signal import (
    SIGNAL_UNAVAILABLE,
    ThresholdVerdict,
    evaluate_precedent_threshold,
    signal_is_computed,
)


class _Precedent:
    def __init__(self, accuracy_score: float = 0.0, sample_count: int = 0):
        self.accuracy_score = accuracy_score
        self.sample_count = sample_count


# --- the core defect ---------------------------------------------------------

def test_absent_precedent_gates_as_low_precedent():
    """No precedent at all is a genuine low-precedent gate, not a broken signal."""
    v = evaluate_precedent_threshold(None, threshold=0.8)
    assert v.autopilot is False
    assert v.gate_reason == "low_precedent"
    assert v.signal_available is True


def test_uncomputed_score_gates_as_verification_failed_not_low_precedent():
    """A precedent that exists but carries no computed signal is NOT weak evidence.

    This is the whole point. `accuracy_score == 0.0` with no samples means
    'never measured', which must not be reported as 'measured and scored zero'.
    """
    v = evaluate_precedent_threshold(_Precedent(0.0, sample_count=0), threshold=0.8)
    assert v.autopilot is False
    assert v.gate_reason == "verification_failed"
    assert v.signal_available is False
    assert SIGNAL_UNAVAILABLE in v.detail


def test_uncomputed_signal_gates_even_at_a_zero_threshold():
    """Fail closed: an operator cannot 'disable' the check by lowering the bar.

    Without this, threshold=0.0 would make the always-zero score pass and turn
    an inert control into an accidental autopilot_always.
    """
    v = evaluate_precedent_threshold(_Precedent(0.0, sample_count=0), threshold=0.0)
    assert v.autopilot is False
    assert v.signal_available is False


# --- what it must do once a compute site exists ------------------------------

def test_computed_score_above_threshold_autopilots():
    v = evaluate_precedent_threshold(_Precedent(0.92, sample_count=5), threshold=0.8)
    assert v.autopilot is True
    assert v.gate_reason is None
    assert v.signal_available is True


def test_computed_score_below_threshold_is_a_real_low_precedent_gate():
    v = evaluate_precedent_threshold(_Precedent(0.41, sample_count=5), threshold=0.8)
    assert v.autopilot is False
    assert v.gate_reason == "low_precedent"
    assert v.signal_available is True


def test_boundary_is_inclusive():
    """`score >= threshold` autopilots — matches the autonomy_ref shape `precedent>=t`."""
    v = evaluate_precedent_threshold(_Precedent(0.8, sample_count=3), threshold=0.8)
    assert v.autopilot is True


def test_single_sample_is_not_enough_to_autopilot():
    """One observation is an anecdote.

    Mirrors the two-stage promotion rule the spec requires of the teaching loop:
    a pattern seen once is tentative and never injected.
    """
    v = evaluate_precedent_threshold(_Precedent(0.99, sample_count=1), threshold=0.8)
    assert v.autopilot is False
    assert v.gate_reason == "low_precedent"


# --- confidence is not authority (the invariant this must not break) ---------

def test_module_never_consults_decision_confidence():
    """Threshold evaluation reads the PRECEDENT's measured score, never the
    agent's self-reported confidence. A confident agent must not earn autonomy."""
    import ast
    import inspect

    from orchestrator import teaching_signal

    # Strip docstrings — the module DISCUSSES decision_confidence in prose to
    # explain why it is never read. Only executable code may be scanned, or the
    # guard fires on its own justification.
    tree = ast.parse(inspect.getsource(teaching_signal))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if (node.body and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)):
                node.body.pop(0)

    code = ast.unparse(tree)
    assert "decision_confidence" not in code, (
        "threshold evaluation must never read the agent's self-reported "
        "confidence — autonomy is earned by track record, not by certainty"
    )


# --- honest reporting of system state ----------------------------------------

def test_signal_is_computed_reports_false_while_no_compute_site_exists():
    """A queryable answer to 'is this control actually working?'.

    Returns False while `accuracy_score` has no writer. This is what lets the
    operator surface say 'threshold mode is inert' instead of implying it works.
    """
    assert signal_is_computed(_Precedent(0.0, sample_count=0)) is False
    assert signal_is_computed(_Precedent(0.7, sample_count=4)) is True


def test_verdict_detail_is_operator_readable():
    v = evaluate_precedent_threshold(_Precedent(0.0, sample_count=0), threshold=0.8)
    assert v.detail and len(v.detail) > 20
    assert "0.8" in v.detail or "threshold" in v.detail.lower()


def test_verdict_is_immutable():
    v = evaluate_precedent_threshold(None, threshold=0.8)
    with pytest.raises(Exception):
        v.autopilot = True  # type: ignore[misc]


def test_negative_or_absurd_threshold_still_fails_closed():
    for t in (-1.0, 1.5):
        v = evaluate_precedent_threshold(_Precedent(0.0, sample_count=0), threshold=t)
        assert v.autopilot is False
