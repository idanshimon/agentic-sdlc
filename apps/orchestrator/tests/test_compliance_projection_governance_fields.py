"""The compliance projection must surface the governance fields it stores.

Two defects found during live QA of the deployed revision (rev 43):

1. `_row()` is an EXPLICIT projection dict. `rejected_options`,
   `gate_reason`, and `decision_confidence` were written to the ledger but
   omitted from the projection, so the audit surface returned them as null.
   A field that exists in schema but reads back null is not delivered.

2. `run_id` was projected onto every row but was not a filter, so
   "show me the decisions for THIS run" silently returned zero rows while
   the same query filtered by team returned hundreds.

Both are the same failure class the repo already knows: a surface that
returns an honest-looking empty answer instead of the data it holds.
"""
from __future__ import annotations

from apps.orchestrator.compliance_query import build_compliance_rows


def _entry(**over) -> dict:
    base = {
        "id": "e1",
        "created_at": "2026-08-12T12:00:00+00:00",
        "team_id": "team-cardiology",
        "run_id": "run-1",
        "ambiguity_class": "phi-classification",
        "decision_kind": "accept",
        "resolution_text": "chosen",
        "autonomy_ref": "autonomy/invariant/phi-classification/gate:phi-auth-hard-lock",
        "bundle_refs": ["security/v0.1.0/PHI-001"],
        "created_by": "operator@example.com",
        "model_used": "gpt-4.1",
        "cost_usd": 0.01,
        "phi_class": "high",
    }
    base.update(over)
    return base


def test_projection_surfaces_rejected_options() -> None:
    """The "why not the other option?" evidence must reach the audit surface."""
    rejected = [
        {"resolution": "ra", "rationale": "because A", "option_index": 0,
         "recommended": True},
    ]
    rows = build_compliance_rows([_entry(rejected_options=rejected)])
    assert len(rows) == 1
    assert rows[0]["rejected_options"] == rejected
    assert rows[0]["rejected_options"][0]["rationale"] == "because A"


def test_projection_surfaces_gate_reason_and_confidence() -> None:
    rows = build_compliance_rows(
        [_entry(gate_reason="invariant_class", decision_confidence=0.93)]
    )
    assert rows[0]["gate_reason"] == "invariant_class"
    assert rows[0]["decision_confidence"] == 0.93
    # autonomy_ref still carries the specific rule — gate_reason complements it
    assert "phi-auth-hard-lock" in rows[0]["autonomy_ref"]


def test_missing_new_fields_are_null_not_absent() -> None:
    """Legacy rows must project the keys, so the UI renders a column not a crash."""
    rows = build_compliance_rows([_entry()])
    assert rows[0]["rejected_options"] == []
    assert rows[0]["gate_reason"] is None
    assert rows[0]["decision_confidence"] is None


def test_confidence_absence_does_not_make_a_row_incomplete() -> None:
    """A human decision with no confidence score is still fully auditable.

    decision_confidence is evidence, not a completeness requirement — it must
    never be part of _is_complete().
    """
    rows = build_compliance_rows([_entry(decision_confidence=None)])
    assert rows[0]["complete"] is True


def test_run_id_filter_selects_only_that_run() -> None:
    entries = [
        _entry(id="a", run_id="run-1"),
        _entry(id="b", run_id="run-2"),
        _entry(id="c", run_id="run-1"),
    ]
    rows = build_compliance_rows(entries, run_id="run-1")
    assert {r["id"] for r in rows} == {"a", "c"}


def test_run_id_filter_absent_returns_all() -> None:
    entries = [_entry(id="a", run_id="run-1"), _entry(id="b", run_id="run-2")]
    assert len(build_compliance_rows(entries)) == 2


def test_run_id_and_team_filters_are_and_combined() -> None:
    entries = [
        _entry(id="a", run_id="run-1", team_id="team-cardiology"),
        _entry(id="b", run_id="run-1", team_id="team-other"),
    ]
    rows = build_compliance_rows(entries, run_id="run-1", team_id="team-cardiology")
    assert [r["id"] for r in rows] == ["a"]
