"""Precedent-threshold evaluation, and honest reporting when the signal is absent.

Task 5.x of adopt-github-native-execution-substrate.

## The defect this closes

`autonomy_ref` mode `autopilot_above_threshold` gates on a precedent's
`accuracy_score`. That field defaults to `0.0` and **nothing in the system
writes it** — not the orchestrator, not the Doctor, not the ledger MCP's
`findPrecedent`. Every configured threshold is above zero (0.75 / 0.8 / 0.9 in
`config/autonomy.yaml.example`), so the comparison always failed and the mode
always gated.

The field being empty is the lesser problem. The real one is that **a
configuration surface silently did nothing**: an operator setting
`threshold: 0.8` believed they had tuned autonomy, when the effective behaviour
was identical to `mode: gate`. Lowering it to `0.1` to loosen the control would
have changed nothing either. The steering wheel was not connected.

## The rule

Until a compute site exists, threshold mode must fail closed **loudly**. Two
outcomes that look the same in the ledger today are different facts and must be
recorded differently:

- **`low_precedent`** — we measured, and the evidence is weak.
- **`verification_failed`** — we could not measure at all.

Reporting an unmeasured signal as weak evidence is the same class of dishonesty
as citing a rule that was never evaluated: the record asserts something that did
not happen.

## Fail-closed, deliberately

`threshold=0.0` must NOT let an always-zero score through. Without that guard,
an inert control silently becomes `autopilot_always` the moment someone lowers
the bar — the worst possible failure direction for a governance knob.

## Confidence is not authority

This module reads the PRECEDENT's measured score. It never reads the agent's
self-reported `decision_confidence`, and a test asserts that by inspecting this
module's own source. A confident agent does not earn autonomy; a track record
does.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

# Minimum independent observations before a score may grant autonomy. One
# observation is an anecdote — this mirrors the two-stage promotion the spec
# requires of the teaching loop, where a pattern seen once stays tentative.
MIN_SAMPLES_FOR_AUTONOMY = 2

SIGNAL_UNAVAILABLE = (
    "precedent accuracy signal has not been computed for this decision class "
    "(no retrospective has scored it yet)"
)


@dataclass(frozen=True)
class ThresholdVerdict:
    """Outcome of a precedent-threshold evaluation.

    `signal_available` distinguishes "measured and weak" from "never measured",
    which is the distinction the ledger could not previously express.
    """

    autopilot: bool
    gate_reason: Optional[str]
    signal_available: bool
    detail: str
    score: Optional[float] = None


def _sample_count(precedent: Any) -> int:
    return int(getattr(precedent, "sample_count", 0) or 0)


def _score(precedent: Any) -> float:
    try:
        return float(getattr(precedent, "accuracy_score", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def signal_is_computed(precedent: Any) -> bool:
    """True when this precedent carries a real, measured accuracy signal.

    A score of exactly `0.0` with no recorded samples means "never measured".
    Treating that as a legitimate score is what made threshold mode inert.
    """
    if precedent is None:
        return False
    return _sample_count(precedent) > 0


def evaluate_precedent_threshold(
    precedent: Any,
    *,
    threshold: float,
) -> ThresholdVerdict:
    """Decide whether a precedent's measured track record earns autopilot.

    Fails closed in every ambiguous case. Never consults agent confidence.
    """
    if precedent is None:
        return ThresholdVerdict(
            autopilot=False,
            gate_reason="low_precedent",
            signal_available=True,
            detail=(
                "no precedent found for this decision class and slot value; "
                f"threshold {threshold:g} cannot be met without a track record"
            ),
            score=None,
        )

    if not signal_is_computed(precedent):
        # The control cannot be evaluated. Say so — do not report it as weak
        # evidence, and do not let a low threshold turn it into an accidental
        # autopilot.
        return ThresholdVerdict(
            autopilot=False,
            gate_reason="verification_failed",
            signal_available=False,
            detail=(
                f"{SIGNAL_UNAVAILABLE}; gating regardless of the configured "
                f"threshold {threshold:g} because an unmeasured signal must not "
                "be read as a passing score"
            ),
            score=None,
        )

    score = _score(precedent)
    samples = _sample_count(precedent)

    if samples < MIN_SAMPLES_FOR_AUTONOMY:
        return ThresholdVerdict(
            autopilot=False,
            gate_reason="low_precedent",
            signal_available=True,
            detail=(
                f"precedent scored {score:g} but on only {samples} observation(s); "
                f"at least {MIN_SAMPLES_FOR_AUTONOMY} are required before a score "
                "may grant autonomy"
            ),
            score=score,
        )

    if score >= threshold:
        return ThresholdVerdict(
            autopilot=True,
            gate_reason=None,
            signal_available=True,
            detail=(
                f"precedent scored {score:g} over {samples} observations, meeting "
                f"the configured threshold {threshold:g}"
            ),
            score=score,
        )

    return ThresholdVerdict(
        autopilot=False,
        gate_reason="low_precedent",
        signal_available=True,
        detail=(
            f"precedent scored {score:g} over {samples} observations, below the "
            f"configured threshold {threshold:g}"
        ),
        score=score,
    )
