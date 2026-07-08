"""Tests for the 3 review-loop ledger kinds (PR-3, task 0.3).

review_remediation / loop_converged / loop_escalated must exist on BOTH
LedgerEntry models (the known two-model drift) and round-trip cleanly.

Run:
    (cd packages/ledger-core && python -m pytest -q)
    python -m pytest apps/orchestrator/tests/test_review_loop_ledger.py -q
"""
from __future__ import annotations

from apps.orchestrator.models import LedgerEntry as OrchLedgerEntry


LOOP_KINDS = ("review_remediation", "loop_converged", "loop_escalated")


def test_orchestrator_ledger_entry_accepts_loop_kinds():
    for kind in LOOP_KINDS:
        e = OrchLedgerEntry(
            team_id="t1", run_id="r1", entry_type="runtime", runtime_kind=kind,
            decision=f"{kind} test", rationale="unit test",
        )
        assert e.runtime_kind == kind


def test_ledger_core_runtime_kind_includes_loop_kinds():
    from ledger_core.models import RuntimeKind
    import typing
    allowed = set(typing.get_args(RuntimeKind))
    for kind in LOOP_KINDS:
        assert kind in allowed, f"{kind} missing from ledger-core RuntimeKind"


def test_ledger_core_entry_round_trips_a_loop_entry():
    from ledger_core.models import LedgerEntry as CoreLedgerEntry
    e = CoreLedgerEntry(
        entry_type="runtime",
        runtime_kind="loop_converged",
        team_id="t1",
        run_id="r1",
        actor={"kind": "agent", "id": "review-loop-controller"},
        decision="loop converged, merged",
        rationale="1 remediation attempt, PASS",
    )
    dumped = e.model_dump()
    assert dumped["runtime_kind"] == "loop_converged"
    # re-validate the dumped dict
    again = CoreLedgerEntry(**dumped)
    assert again.runtime_kind == "loop_converged"
