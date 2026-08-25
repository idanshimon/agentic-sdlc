"""Compute site for `accuracy_score` — tasks 5.1-5.9.

## What this closes

The audit's most serious finding: `accuracy_score` was declared on `LedgerEntry`
and `0.0` on all 229 live rows. Nothing computed it, yet
`autopilot_above_threshold` read it as though it meant something. A governed
system claiming an assurance it does not provide is the one failure this design
cannot tolerate — so this is the honesty debt, not merely a missing feature.

## Where the signal comes from

`replay.py` already produces it. Replay takes decisions whose real-world outcome
is known — merged PRs, human rulings already in the ledger — hides the outcome,
asks the pipeline to decide, and compares. Its `autopilot_disagreement_rate` is
precisely the number that matters: **when the agent acted alone, how often was
it wrong.**

Replay deliberately refuses to write to the ledger, because inventing rows to
make a metric look populated would corrupt the audit substrate. That boundary is
load-bearing, so this module preserves it:

    replay measures  ->  this module promotes  ->  the caller writes

Nothing here touches Cosmos, and a test asserts it.

## Why this is deliberately more conservative than a memory system

A wrong lesson injected into a governed pipeline is worse than no lesson. The
loop must degrade toward silence, never toward confident nonsense:

**Two-stage promotion.** A pattern observed once is TENTATIVE. It is recorded —
it is evidence — but it grants no autonomy. Promotion requires the same class to
recur on a separate retrospective. One observation is an anecdote.

**Asymmetric weighting.** A misleading lesson loses more than a helpful one
gains (`_PENALTY > _REWARD`). A bad memory costs more than a missing one, so a
class that alternates good and bad outcomes trends *down*, not sideways.

**Decay and tombstones.** An unread score fades. Below `ARCHIVE_FLOOR` it is
archived with a recorded reason rather than deleted — the ledger is append-only,
and "archived because it decayed unread" is a different fact from "never
measured". The floor is above zero precisely so those two remain
distinguishable.

**Random sampling with a recorded seed.** Most-recent sampling re-teaches
whatever happened last week. Random avoids recency bias; the seed makes the
retrospective reproducible, which an audit requires — "which runs did you look
at?" must have an answer.

**Invariants are scored but never autonomous.** `phi-classification` and
`auth-policy` can never earn autopilot however well they score. Measuring them
is still worth doing: a high disagreement rate on a gated class means the
agent's *suggestions* are poor, which is worth knowing even though a human
decides regardless.

**Unmeasurable stays unmeasured.** When replay cannot compute a rate, the result
is UNSCORED with `accuracy_score = None` — never `0.0`. Converting "could not
measure" into a number is the same dishonesty the threshold fix closed on the
read side, and it is what made this field misleading in the first place.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Optional, Sequence

# Classes that may never earn autonomy, however well they score. Mirrors
# INVARIANT_CLASSES in ledger_core; duplicated as a literal set here only to
# keep this module import-light and pure.
_INVARIANT_CLASSES = {"phi-classification", "auth-policy"}

# Asymmetry is the point: harm must cost more than help gains.
_REWARD = 0.12
_PENALTY = 0.30

# Observations required before a score may grant autonomy (two-stage promotion).
MIN_PROMOTION_SAMPLES = 2

# Per-period decay applied to a score nobody read.
_DECAY_PER_PERIOD = 0.15

# Below this, a score is archived with a tombstone. Deliberately > 0.0 so an
# archived score stays distinguishable from one that was never measured.
ARCHIVE_FLOOR = 0.05

# Seed value for a promoted score's first measurement.
_SEED_SCORE = 0.5


class PromotionState(str, Enum):
    UNSCORED = "unscored"      # replay could not measure this class
    TENTATIVE = "tentative"    # measured once; evidence, not authority
    PROMOTED = "promoted"      # recurred; may grant autonomy
    ARCHIVED = "archived"      # decayed below the floor, with a reason


@dataclass(frozen=True)
class ScoreUpdate:
    """One retrospective's verdict on one ambiguity class.

    `accuracy_score is None` means "not measured" and must never be coerced to
    `0.0` by a consumer.
    """

    ambiguity_class: str
    accuracy_score: Optional[float]
    sample_count: int
    state: PromotionState
    detail: str
    tombstone_reason: Optional[str] = None

    @property
    def grants_autonomy(self) -> bool:
        """Whether this score may be consulted to grant autopilot.

        Fails closed: only a PROMOTED, non-invariant, sufficiently-sampled score
        with a real value qualifies.
        """
        if self.state is not PromotionState.PROMOTED:
            return False
        if self.ambiguity_class in _INVARIANT_CLASSES:
            return False
        if self.accuracy_score is None:
            return False
        return self.sample_count >= MIN_PROMOTION_SAMPLES


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, v))


def compute_accuracy_update(
    class_score: Any,
    *,
    prior: Optional[ScoreUpdate] = None,
) -> ScoreUpdate:
    """Fold one replay measurement into a class's running accuracy score.

    `class_score` is a `replay.ClassScore` (or anything exposing
    `ambiguity_class` and `autopilot_disagreement_rate`).
    """
    cls = getattr(class_score, "ambiguity_class", "") or ""

    if prior is not None and prior.ambiguity_class != cls:
        raise ValueError(
            f"cannot fold a {cls!r} measurement into a {prior.ambiguity_class!r} "
            "score — promotion requires recurrence of the SAME class"
        )

    rate = getattr(class_score, "autopilot_disagreement_rate", None)

    if rate is None:
        # Replay could not measure this class. Preserve any prior score
        # untouched; do NOT let absence of evidence move the number.
        if prior is not None:
            return replace(
                prior,
                detail=(
                    f"{cls}: not measurable this cycle (too few autopiloted "
                    f"decisions); prior score retained unchanged"
                ),
            )
        return ScoreUpdate(
            ambiguity_class=cls,
            accuracy_score=None,
            sample_count=0,
            state=PromotionState.UNSCORED,
            detail=(
                f"{cls}: replay could not compute a disagreement rate — recorded "
                "as unscored rather than as a zero score"
            ),
        )

    agreement = _clamp(1.0 - float(rate))

    if prior is None or prior.accuracy_score is None:
        # First real measurement. Seed toward the observed agreement rather than
        # adopting it outright: a single cycle should not mint a 1.0.
        seeded = _clamp(_SEED_SCORE + (agreement - _SEED_SCORE) * _REWARD * 4)
        return ScoreUpdate(
            ambiguity_class=cls,
            accuracy_score=seeded,
            sample_count=1,
            state=PromotionState.TENTATIVE,
            detail=(
                f"{cls}: first measurement, agreement {agreement:.2f} — tentative, "
                "grants no autonomy until it recurs on a separate retrospective"
            ),
        )

    # Recurrence. Move toward the observation, asymmetrically.
    delta = agreement - prior.accuracy_score
    weight = _REWARD if delta >= 0 else _PENALTY
    updated = _clamp(prior.accuracy_score + delta * weight)

    samples = prior.sample_count + 1
    state = (
        PromotionState.PROMOTED
        if samples >= MIN_PROMOTION_SAMPLES
        else PromotionState.TENTATIVE
    )
    direction = "up" if delta >= 0 else "down"
    return ScoreUpdate(
        ambiguity_class=cls,
        accuracy_score=updated,
        sample_count=samples,
        state=state,
        detail=(
            f"{cls}: agreement {agreement:.2f} over {samples} retrospectives; "
            f"score moved {direction} to {updated:.2f} "
            f"(weight {weight:g} — harm is weighted heavier than help)"
        ),
    )


def apply_decay(update: ScoreUpdate, *, periods_unread: int) -> ScoreUpdate:
    """Fade a score nobody consulted; archive it with a reason below the floor."""
    if periods_unread <= 0 or update.accuracy_score is None:
        return update

    decayed = _clamp(update.accuracy_score - _DECAY_PER_PERIOD * periods_unread)

    if decayed < ARCHIVE_FLOOR:
        return replace(
            update,
            accuracy_score=decayed,
            state=PromotionState.ARCHIVED,
            detail=(
                f"{update.ambiguity_class}: archived after {periods_unread} "
                f"period(s) unread; score fell below the {ARCHIVE_FLOOR:g} floor"
            ),
            tombstone_reason=(
                f"decay: unread for {periods_unread} retrospective period(s), "
                f"score {decayed:.3f} below archive floor {ARCHIVE_FLOOR:g}"
            ),
        )

    return replace(
        update,
        accuracy_score=decayed,
        detail=(
            f"{update.ambiguity_class}: decayed to {decayed:.2f} after "
            f"{periods_unread} period(s) unread"
        ),
    )


def select_sample(
    runs: Sequence[dict],
    *,
    size: int,
    seed: int,
) -> list[dict]:
    """Pick runs to examine at RANDOM, reproducibly.

    Most-recent sampling would re-teach whatever happened last week. The seed is
    recorded by the caller so an auditor can reproduce which runs a given
    retrospective examined.
    """
    if not runs or size <= 0:
        return []
    population = list(runs)
    if size >= len(population):
        return population
    rng = random.Random(seed)
    return rng.sample(population, size)
