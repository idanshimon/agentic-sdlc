"""The compute site for `accuracy_score` (tasks 5.1-5.9).

Closes the audit's most serious finding: `accuracy_score` was declared on the
schema and `0.0` on every live row — a learning loop that was a schema with no
behaviour, while `autopilot_above_threshold` read it as if it meant something.

DESIGN CONSTRAINTS UNDER TEST

The spec requires this loop to be MORE conservative than a naive memory system,
because a wrong lesson injected into a governed pipeline is worse than no lesson
at all:

  * two-stage promotion  — a pattern seen once is tentative and never grants autonomy
  * asymmetric weighting — a lesson that misleads loses more than a helpful one gains
  * decay                — unread lessons fade; below a floor they are archived with a reason
  * random sampling      — never most-recent, which would re-teach whatever happened last week
  * invariants excluded  — a class that always gates cannot earn a score that implies autonomy

The scoring INPUT is `replay.py`, which already computes per-class
`autopilot_disagreement_rate` — "when the agent acted alone, how often was it
wrong" — and deliberately refuses to write to the ledger. That boundary is
correct and this module preserves it: replay measures, this module promotes,
and the caller writes. Nothing here touches Cosmos.
"""
from __future__ import annotations

import pytest

from orchestrator.accuracy_compute import (
    ARCHIVE_FLOOR,
    PromotionState,
    ScoreUpdate,
    apply_decay,
    compute_accuracy_update,
    select_sample,
)


class _Score:
    """Minimal stand-in for a replay ClassScore."""

    def __init__(self, cls, autopiloted=0, autopilot_disagreements=0, scored=0, invariant=False):
        self.ambiguity_class = cls
        self.autopiloted = autopiloted
        self.autopilot_disagreements = autopilot_disagreements
        self.scored = scored
        self._invariant = invariant

    @property
    def autopilot_disagreement_rate(self):
        if self.autopiloted < 2:
            return None
        return self.autopilot_disagreements / self.autopiloted


# --- stage 1: a single observation is tentative ------------------------------

def test_first_observation_is_tentative_and_grants_nothing():
    u = compute_accuracy_update(_Score("scope-resolution", autopiloted=4, autopilot_disagreements=0),
                                prior=None)
    assert u.state == PromotionState.TENTATIVE
    assert u.sample_count == 1
    assert u.grants_autonomy is False


def test_tentative_score_is_recorded_not_suppressed():
    """Tentative still writes a score — it is evidence, just not authority."""
    u = compute_accuracy_update(_Score("scope-resolution", autopiloted=4, autopilot_disagreements=0),
                                prior=None)
    assert u.accuracy_score > 0.0
    assert u.grants_autonomy is False


# --- stage 2: recurrence promotes --------------------------------------------

def test_recurrence_at_same_class_promotes():
    first = compute_accuracy_update(_Score("scope-resolution", autopiloted=4, autopilot_disagreements=0),
                                    prior=None)
    second = compute_accuracy_update(_Score("scope-resolution", autopiloted=5, autopilot_disagreements=0),
                                     prior=first)
    assert second.state == PromotionState.PROMOTED
    assert second.sample_count == 2
    assert second.grants_autonomy is True


def test_promotion_requires_the_same_class():
    first = compute_accuracy_update(_Score("scope-resolution", autopiloted=4, autopilot_disagreements=0),
                                    prior=None)
    with pytest.raises(ValueError, match="class"):
        compute_accuracy_update(_Score("sla-binding", autopiloted=4, autopilot_disagreements=0),
                                prior=first)


# --- asymmetric weighting: harm costs more than help gains -------------------

def test_a_bad_outcome_costs_more_than_a_good_one_gains():
    base = compute_accuracy_update(_Score("sla-binding", autopiloted=4, autopilot_disagreements=0),
                                   prior=None)
    good = compute_accuracy_update(_Score("sla-binding", autopiloted=4, autopilot_disagreements=0),
                                   prior=base)
    bad = compute_accuracy_update(_Score("sla-binding", autopiloted=4, autopilot_disagreements=4),
                                  prior=base)
    gained = good.accuracy_score - base.accuracy_score
    lost = base.accuracy_score - bad.accuracy_score
    assert lost > gained, "a misleading lesson must cost more than a helpful one gains"


def test_helpful_then_harmful_nets_below_the_start():
    base = compute_accuracy_update(_Score("sla-binding", autopiloted=4, autopilot_disagreements=0),
                                   prior=None)
    up = compute_accuracy_update(_Score("sla-binding", autopiloted=4, autopilot_disagreements=0),
                                 prior=base)
    down = compute_accuracy_update(_Score("sla-binding", autopiloted=4, autopilot_disagreements=4),
                                   prior=up)
    assert down.accuracy_score < base.accuracy_score


def test_score_is_bounded_to_unit_interval():
    prior = None
    for _ in range(20):
        prior = compute_accuracy_update(
            _Score("naming-convention", autopiloted=6, autopilot_disagreements=0), prior=prior)
    assert 0.0 <= prior.accuracy_score <= 1.0
    for _ in range(20):
        prior = compute_accuracy_update(
            _Score("naming-convention", autopiloted=6, autopilot_disagreements=6), prior=prior)
    assert 0.0 <= prior.accuracy_score <= 1.0


# --- insufficient evidence ---------------------------------------------------

def test_unmeasurable_class_does_not_produce_a_score():
    """`autopilot_disagreement_rate is None` means replay could not measure it.

    That must not be silently converted into a score — the same dishonesty the
    threshold fix closed on the read side.
    """
    u = compute_accuracy_update(_Score("other", autopiloted=1, autopilot_disagreements=0), prior=None)
    assert u.state == PromotionState.UNSCORED
    assert u.accuracy_score is None
    assert u.grants_autonomy is False


def test_unscored_update_does_not_advance_sample_count():
    first = compute_accuracy_update(_Score("other", autopiloted=4, autopilot_disagreements=0), prior=None)
    stalled = compute_accuracy_update(_Score("other", autopiloted=1, autopilot_disagreements=0), prior=first)
    assert stalled.sample_count == first.sample_count


# --- invariants: measurable, never autonomous --------------------------------

def test_invariant_class_never_grants_autonomy_however_well_it_scores():
    prior = None
    for _ in range(6):
        prior = compute_accuracy_update(
            _Score("phi-classification", autopiloted=8, autopilot_disagreements=0), prior=prior)
    # Converges high but deliberately slowly — reward is weighted at 0.12, so a
    # perfect record approaches 1.0 asymptotically rather than snapping to it.
    assert prior.accuracy_score > 0.85
    assert prior.state == PromotionState.PROMOTED
    assert prior.grants_autonomy is False, "an invariant class can never earn autopilot"


def test_invariant_is_still_scored_because_bad_suggestions_are_worth_knowing():
    u = compute_accuracy_update(
        _Score("auth-policy", autopiloted=8, autopilot_disagreements=8), prior=None)
    assert u.accuracy_score is not None


# --- decay and archival ------------------------------------------------------

def test_unread_score_decays():
    base = compute_accuracy_update(_Score("sla-binding", autopiloted=4, autopilot_disagreements=0),
                                   prior=None)
    decayed = apply_decay(base, periods_unread=3)
    assert decayed.accuracy_score < base.accuracy_score


def test_decay_below_floor_archives_with_a_recorded_reason():
    base = compute_accuracy_update(_Score("sla-binding", autopiloted=4, autopilot_disagreements=0),
                                   prior=None)
    dead = apply_decay(base, periods_unread=99)
    assert dead.state == PromotionState.ARCHIVED
    assert dead.tombstone_reason
    assert "decay" in dead.tombstone_reason.lower()


def test_archived_score_grants_nothing():
    base = compute_accuracy_update(_Score("sla-binding", autopiloted=6, autopilot_disagreements=0),
                                   prior=None)
    promoted = compute_accuracy_update(_Score("sla-binding", autopiloted=6, autopilot_disagreements=0),
                                       prior=base)
    assert promoted.grants_autonomy is True
    dead = apply_decay(promoted, periods_unread=99)
    assert dead.grants_autonomy is False


def test_decay_is_a_no_op_when_recently_read():
    base = compute_accuracy_update(_Score("sla-binding", autopiloted=4, autopilot_disagreements=0),
                                   prior=None)
    same = apply_decay(base, periods_unread=0)
    assert same.accuracy_score == base.accuracy_score


def test_archive_floor_is_above_zero():
    """A score must be archived while still nonzero, so 'archived' and 'never
    measured' remain distinguishable in the record."""
    assert ARCHIVE_FLOOR > 0.0


# --- sampling: random, not most-recent ---------------------------------------

def test_sample_is_not_the_most_recent_slice():
    runs = [{"run_id": f"r{i}"} for i in range(100)]
    picked = select_sample(runs, size=10, seed=7)
    assert len(picked) == 10
    newest_ten = {r["run_id"] for r in runs[-10:]}
    assert {r["run_id"] for r in picked} != newest_ten


def test_sampling_is_deterministic_under_a_seed():
    """An audit must be able to reproduce which runs a retrospective examined."""
    runs = [{"run_id": f"r{i}"} for i in range(50)]
    assert select_sample(runs, size=8, seed=3) == select_sample(runs, size=8, seed=3)


def test_sample_never_exceeds_population():
    runs = [{"run_id": "r0"}, {"run_id": "r1"}]
    assert len(select_sample(runs, size=10, seed=1)) == 2


def test_empty_population_yields_empty_sample():
    assert select_sample([], size=5, seed=1) == []


# --- the module must not become a ledger writer ------------------------------

def test_module_performs_no_persistence():
    """Replay measures, this module promotes, the caller writes.

    `replay.py` deliberately refuses to write to the ledger; that boundary is
    load-bearing and this module must not quietly cross it.
    """
    import inspect

    from orchestrator import accuracy_compute

    src = inspect.getsource(accuracy_compute)
    for forbidden in ("write_entry", "cosmos", "upsert", "CosmosClient"):
        assert forbidden not in src, f"compute site must not persist ({forbidden!r} found)"


def test_update_is_immutable():
    u = compute_accuracy_update(_Score("sla-binding", autopiloted=4, autopilot_disagreements=0),
                                prior=None)
    with pytest.raises(Exception):
        u.accuracy_score = 1.0  # type: ignore[misc]
