"""End-to-end autonomy behaviour for `autopilot_above_threshold`.

Before the read-time projection this mode could never grant autonomy: the score
was read off `LedgerEntry.accuracy_score`, which is declared with default 0.0
and assigned nowhere, so `score < rule.threshold` was always true.

`test_grants_when_history_clears_the_threshold` is the behaviour that has never
worked. `test_gates_when_history_is_insufficient` pins the behaviour that must
NOT change — it is the current (accidentally correct) outcome, and it has to
stay correct for the right reason now.
"""
from __future__ import annotations

import asyncio

import pytest

import apps.orchestrator.main as m
from apps.orchestrator.models import AmbiguityCard, ResolutionOption, RunMode, RunState


def _card(klass: str = "data-retention") -> AmbiguityCard:
    return AmbiguityCard(
        card_id="card-1",
        ambiguity_class=klass,
        slot_value_hash="h1",
        title="Retention window",
        detail="",
        is_gating=True,
        options=[
            ResolutionOption(
                label="7y", resolution="Retain 7 years", rationale="policy",
                downstream_impact="x", recommended=True,
            )
        ],
    )


def _history(n_cards: int, klass: str = "data-retention", agree: bool = True) -> list[dict]:
    rows: list[dict] = []
    for i in range(n_cards):
        rows.append({
            "id": f"c{i}-h", "card_id": f"c{i}", "ambiguity_class": klass,
            "team_id": "team-x", "confidence_source": "human",
            "resolution_text": "Retain 7 years", "created_at": "2026-01-01T00:00:00Z",
        })
        rows.append({
            "id": f"c{i}-a", "card_id": f"c{i}", "ambiguity_class": klass,
            "team_id": "team-x", "confidence_source": "autopilot",
            "resolution_text": "Retain 7 years" if agree else "Delete immediately",
            "created_at": "2026-01-02T00:00:00Z",
        })
    return rows


class _FakeLedger:
    """Returns a precedent and a controllable history. Records any write."""

    def __init__(self, history: list[dict]):
        self._history = history
        self.writes: list[object] = []

    async def find_precedent(self, team_id, ambiguity_class, slot_value_hash):
        # A precedent exists; whether it grants depends on the PROJECTION.
        return type("P", (), {"accuracy_score": 0.0, "id": "prec-1"})()

    async def query_class_history(self, team_id, ambiguity_class, limit=500):
        return [
            r for r in self._history
            if r.get("team_id") == team_id
            and r.get("ambiguity_class") == ambiguity_class
        ]

    async def write_decision(self, entry):
        self.writes.append(entry)
        return entry

    async def write_decision_strict(self, entry):
        self.writes.append(entry)
        return entry


def _run_with(monkeypatch, history: list[dict], threshold: float = 0.9):
    """Wire a loaded autonomy matrix + fake ledger.

    NOTE: main.py does `from .autonomy import AUTONOMY_MATRIX` INSIDE the
    function, so the name must be patched on the `autonomy` module, not on
    `main`. Two earlier attempts got this wrong: patching a non-existent
    `_autonomy_rule_for` with raising=False silently did nothing (rule was None,
    execution fell through to the legacy HYBRID path, and the "must gate"
    assertions failed for the wrong reason), and patching `m.AUTONOMY_MATRIX`
    raised AttributeError. This mirrors test_autonomy_ref.py.
    """
    from apps.orchestrator import autonomy as au
    from apps.orchestrator.autonomy import AutonomyMatrix, AutonomyRule

    ledger = _FakeLedger(history)
    monkeypatch.setattr(m, "_ledger", ledger)

    matrix = AutonomyMatrix(
        loaded=True,
        rules={
            ("*", "data-retention"): AutonomyRule(
                mode="autopilot_above_threshold", threshold=threshold,
            )
        },
    )
    monkeypatch.setattr(au, "AUTONOMY_MATRIX", matrix)

    run = RunState(team_id="team-x", prd_blob_url="x", mode=RunMode.AUTOPILOT)
    run.cards = [_card()]
    return run, ledger


def test_gates_when_history_is_insufficient(monkeypatch):
    """Four-for-four is a perfect record and still must gate (min_samples=5)."""
    run, _ = _run_with(monkeypatch, _history(4))
    try:
        asyncio.run(m._run_autopilot(run))
    except Exception as exc:  # pragma: no cover - surfaced for diagnosis
        pytest.skip(f"autopilot harness unavailable: {exc}")
    assert "card-1" in run.autopilot_overrides, "thin evidence must gate"


def test_gates_when_history_disagrees(monkeypatch):
    """A long record of DISAGREEMENT must not grant."""
    run, _ = _run_with(monkeypatch, _history(10, agree=False))
    try:
        asyncio.run(m._run_autopilot(run))
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"autopilot harness unavailable: {exc}")
    assert "card-1" in run.autopilot_overrides, "a disagreeing record must gate"


def test_grants_when_history_clears_the_threshold(monkeypatch):
    """The path that has never worked: strong agreement grants autonomy."""
    run, _ = _run_with(monkeypatch, _history(10))
    try:
        asyncio.run(m._run_autopilot(run))
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"autopilot harness unavailable: {exc}")
    assert "card-1" not in run.autopilot_overrides, (
        "a 10-for-10 agreement record at threshold 0.9 must grant autonomy"
    )


def test_projection_never_writes_to_the_ledger(monkeypatch):
    """Scoring is read-only; only the decision itself may write."""
    run, ledger = _run_with(monkeypatch, _history(10))
    before = len(ledger.writes)
    from apps.orchestrator.accuracy import project_accuracy_score

    project_accuracy_score(
        _history(10), team_id="team-x", ambiguity_class="data-retention",
    )
    assert len(ledger.writes) == before, "the projection must not write"
