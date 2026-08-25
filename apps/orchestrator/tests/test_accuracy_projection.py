"""Read-time `accuracy_score` projection.

RED-first. These tests encode the openspec change
`compute-accuracy-score-projection`, one test per scenario in
specs/autonomy-precedent/spec.md.

The load-bearing test is `test_insufficient_evidence_scores_zero`: the entire
value of this feature is that it grants autonomy *only* when the recorded
history supports it. A projection that is generous with thin evidence is worse
than the 0.0 it replaces, because 0.0 at least failed safe.
"""
from __future__ import annotations

import pytest

from apps.orchestrator.accuracy import project_accuracy_score
from apps.orchestrator.replay import ReplayPolicy


def _entry(card: str, source: str, text: str, klass: str = "data-retention") -> dict:
    """A ledger row shaped the way cases_from_ledger expects."""
    return {
        "id": f"{card}-{source}",
        "card_id": card,
        "ambiguity_class": klass,
        "team_id": "team-x",
        "confidence_source": source,
        "resolution_text": text,
        "created_at": "2026-01-01T00:00:00Z",
    }


def _agreeing_history(n: int, klass: str = "data-retention") -> list[dict]:
    """n cards where autopilot matched the human ruling exactly."""
    rows: list[dict] = []
    for i in range(n):
        rows.append(_entry(f"c{i}", "human", "Retain 7 years", klass))
        rows.append(_entry(f"c{i}", "autopilot", "Retain 7 years", klass))
    return rows


# ---------------------------------------------------------------------------
# Scenario: History of full agreement yields a granting score
# ---------------------------------------------------------------------------

def test_full_agreement_scores_one():
    score = project_accuracy_score(
        _agreeing_history(5), team_id="team-x", ambiguity_class="data-retention",
    )
    assert score == 1.0


# ---------------------------------------------------------------------------
# Scenario: Mixed history yields the true agreement rate
# ---------------------------------------------------------------------------

def test_mixed_history_scores_the_true_rate():
    rows = _agreeing_history(4)
    # A fifth card where autopilot diverged from the human.
    rows.append(_entry("c4", "human", "Retain 7 years"))
    rows.append(_entry("c4", "autopilot", "Retain 30 days"))

    score = project_accuracy_score(
        rows, team_id="team-x", ambiguity_class="data-retention",
    )
    assert score == pytest.approx(4 / 5)


def test_rate_is_never_rounded_up():
    """The metric must never err toward granting autonomy."""
    rows = _agreeing_history(5)
    rows.append(_entry("c9", "human", "Retain 7 years"))
    rows.append(_entry("c9", "autopilot", "Delete immediately"))

    score = project_accuracy_score(
        rows, team_id="team-x", ambiguity_class="data-retention",
    )
    assert score == pytest.approx(5 / 6)
    assert score < 1.0


# ---------------------------------------------------------------------------
# Scenario: Insufficient evidence gates  (THE load-bearing test)
# ---------------------------------------------------------------------------

def test_insufficient_evidence_scores_zero():
    """Below min_samples, a perfect record still scores 0.0.

    Four-for-four looks like a 100% agreement rate. Reporting 1.0 here would
    grant autonomy on n=4, which is exactly the "flattering number computed
    from n=2" that replay.py refuses to produce.
    """
    score = project_accuracy_score(
        _agreeing_history(4), team_id="team-x", ambiguity_class="data-retention",
    )
    assert score == 0.0


def test_empty_history_scores_zero():
    assert project_accuracy_score(
        [], team_id="team-x", ambiguity_class="data-retention",
    ) == 0.0


# ---------------------------------------------------------------------------
# Scenario: Unscored history is not treated as agreement
# ---------------------------------------------------------------------------

def test_unscored_history_is_not_agreement():
    """Autopilot rows with no human ruling are excluded, not counted as wins.

    Counting "we never checked" as "we agreed" is how a governance metric
    becomes a lie.
    """
    rows = [_entry(f"c{i}", "autopilot", "Retain 7 years") for i in range(10)]
    assert project_accuracy_score(
        rows, team_id="team-x", ambiguity_class="data-retention",
    ) == 0.0


def test_unscored_rows_do_not_dilute_a_real_rate():
    rows = _agreeing_history(5)
    rows += [_entry(f"u{i}", "autopilot", "Retain 7 years") for i in range(20)]
    assert project_accuracy_score(
        rows, team_id="team-x", ambiguity_class="data-retention",
    ) == 1.0


# ---------------------------------------------------------------------------
# Scenario: scoping
# ---------------------------------------------------------------------------

def test_other_classes_do_not_contribute():
    """A sibling class's perfect record must not lift this class's score."""
    rows = _agreeing_history(2, klass="data-retention")
    rows += _agreeing_history(10, klass="pii-handling")
    assert project_accuracy_score(
        rows, team_id="team-x", ambiguity_class="data-retention",
    ) == 0.0


def test_other_teams_do_not_contribute():
    rows = _agreeing_history(10)
    for r in rows:
        r["team_id"] = "team-other"
    assert project_accuracy_score(
        rows, team_id="team-x", ambiguity_class="data-retention",
    ) == 0.0


# ---------------------------------------------------------------------------
# Scenario: An invariant class never grants autonomy
# ---------------------------------------------------------------------------

def test_invariant_class_scores_zero_despite_perfect_history():
    policy = ReplayPolicy(invariant_classes=frozenset({"data-retention"}))
    assert project_accuracy_score(
        _agreeing_history(10),
        team_id="team-x",
        ambiguity_class="data-retention",
        policy=policy,
    ) == 0.0


# ---------------------------------------------------------------------------
# Scenario: A failed projection gates
# ---------------------------------------------------------------------------

def test_malformed_rows_score_zero_rather_than_raising():
    """A projection failure must gate, never propagate into the autonomy path."""
    assert project_accuracy_score(
        [{"nonsense": True}, None],  # type: ignore[list-item]
        team_id="team-x",
        ambiguity_class="data-retention",
    ) == 0.0


# ---------------------------------------------------------------------------
# Scenario: The ledger is not modified — enforced structurally
# ---------------------------------------------------------------------------

def test_projection_is_pure():
    """The function must not mutate the rows it is given."""
    rows = _agreeing_history(5)
    before = [dict(r) for r in rows]
    project_accuracy_score(rows, team_id="team-x", ambiguity_class="data-retention")
    assert rows == before
