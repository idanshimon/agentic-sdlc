"""Governance regression tests for the decision record.

These protect the load-bearing claim of this system: **classification decides,
confidence does not.** A platform that gates on a confidence threshold can be
cleared by a sufficiently confident agent. Gating here is a property of the
subject matter (`ambiguity_class`), not of the actor's certainty.

If `test_confidence_is_not_a_gate` ever fails, the product thesis is broken —
do not "fix" it by relaxing the assertion.

Spec: openspec/changes/adopt-github-native-execution-substrate/specs/ledger/spec.md
"""
from __future__ import annotations

import pytest

from ledger_core import INVARIANT_CLASSES, LedgerEntry as CoreEntry, RejectedOption
from ledger_core.models import Actor

from orchestrator.decision_record import (
    approval_satisfies_quorum,
    classify_gate_reason,
    collect_rejected_options,
    is_hard_gated,
)
from orchestrator.models import LedgerEntry as OrchEntry, ResolutionOption


def _opts() -> list[ResolutionOption]:
    return [
        ResolutionOption(
            label="A", resolution="ra", rationale="because A",
            downstream_impact="d", recommended=True,
        ),
        ResolutionOption(
            label="B", resolution="rb", rationale="because B", downstream_impact="d",
        ),
        ResolutionOption(
            label="C", resolution="rc", rationale="because C", downstream_impact="d",
        ),
    ]


# --- the thesis test ---------------------------------------------------------

@pytest.mark.parametrize("klass", sorted(INVARIANT_CLASSES))
def test_confidence_is_not_a_gate(klass: str) -> None:
    """Maximum confidence MUST NOT clear an invariant class.

    This is the axis on which this system differs from confidence-threshold
    gating. `decision_confidence` is recorded evidence; it is never consulted
    when deciding whether a human is required.
    """
    assert is_hard_gated(klass) is True

    entry = OrchEntry(
        team_id="t", run_id="r1", ambiguity_class=klass,
        decision_confidence=1.0,
        gate_reason=classify_gate_reason(klass),
    )
    # Confidence is recorded...
    assert entry.decision_confidence == 1.0
    # ...and the gate holds anyway.
    assert is_hard_gated(entry.ambiguity_class) is True
    assert entry.gate_reason == "invariant_class"


def test_invariant_class_reason_wins_over_other_reasons() -> None:
    """A PHI gate reports `invariant_class` even when other reasons apply.

    Reporting it as `low_precedent` would understate why it is unbypassable.
    """
    reason = classify_gate_reason(
        "phi-classification", had_precedent=False, autonomy_says_gate=True,
    )
    assert reason == "invariant_class"


def test_non_invariant_class_is_not_hard_gated() -> None:
    assert is_hard_gated("naming-convention") is False
    assert is_hard_gated(None) is False


# --- rejected alternatives ---------------------------------------------------

def test_rejected_options_captured_by_index() -> None:
    rejected = collect_rejected_options(_opts(), 1, "rb")
    assert [r.option_index for r in rejected] == [0, 2]
    assert [r.resolution for r in rejected] == ["ra", "rc"]
    # rationale is retained — the "why not" is the point of the field
    assert rejected[0].rationale == "because A"


def test_rejected_options_captured_by_text_when_index_absent() -> None:
    rejected = collect_rejected_options(_opts(), None, "rc")
    assert [r.option_index for r in rejected] == [0, 1]


def test_rejected_options_falls_back_to_recommended() -> None:
    """Mirrors how /approve resolves final_text when nothing identifies a choice."""
    rejected = collect_rejected_options(_opts(), None, None)
    assert [r.option_index for r in rejected] == [1, 2]


def test_single_option_card_yields_empty_not_missing() -> None:
    """Empty is legitimate and MUST NOT be read as missing data."""
    one = [_opts()[0]]
    assert collect_rejected_options(one, 0, "ra") == []
    assert collect_rejected_options([], None, None) == []
    assert collect_rejected_options(None, None, None) == []


def test_rejected_options_round_trip_through_both_models() -> None:
    """The two LedgerEntry models must accept the same shape.

    Model drift between ledger-core and the orchestrator is a documented
    failure class in this repo (it once broke every /approve in production).
    """
    rejected = collect_rejected_options(_opts(), 1, "rb")

    orch = OrchEntry(team_id="t", run_id="r1", rejected_options=rejected)
    core = CoreEntry(
        team_id="t", run_id="r1", actor=Actor(kind="human", id="u@example.com"),
        decision="d", rejected_options=rejected,
    )

    assert len(orch.rejected_options) == 2
    assert len(core.rejected_options) == 2
    assert orch.model_dump()["rejected_options"] == core.model_dump()["rejected_options"]


def test_both_models_carry_the_same_governance_fields() -> None:
    """Lockstep guard against the two-model drift."""
    for field in ("rejected_options", "decision_confidence", "gate_reason"):
        assert field in OrchEntry.model_fields, f"orchestrator model missing {field}"
        assert field in CoreEntry.model_fields, f"ledger-core model missing {field}"


# --- backward compatibility --------------------------------------------------

def test_pre_existing_entry_deserializes_without_new_fields() -> None:
    """Historical rows MUST remain valid; we do not mutate history."""
    legacy = {
        "team_id": "team-demo", "actor": {"kind": "human", "id": "u@example.com"},
        "decision": "legacy decision", "entry_type": "runtime", "run_id": "legacy-run-1",
    }
    entry = CoreEntry(**legacy)
    assert entry.rejected_options == []
    assert entry.decision_confidence is None
    assert entry.gate_reason is None


# --- quorum (what GitHub Environments cannot express) ------------------------

def test_single_approval_does_not_satisfy_high_blast_quorum() -> None:
    """GitHub accepts 1-of-6 with no role binding; the control plane decides."""
    ok, reason = approval_satisfies_quorum(
        approver_roles=["security_lead"],
        required_approvers=3,
        must_include_roles=["security_lead", "privacy_dpo"],
    )
    assert ok is False
    assert "privacy_dpo" in reason


def test_quorum_count_met_but_required_role_missing() -> None:
    ok, reason = approval_satisfies_quorum(
        approver_roles=["security_lead", "architect_lead", "legal"],
        required_approvers=3,
        must_include_roles=["security_lead", "privacy_dpo"],
    )
    assert ok is False
    assert "privacy_dpo" in reason


def test_quorum_satisfied() -> None:
    ok, reason = approval_satisfies_quorum(
        approver_roles=["security_lead", "privacy_dpo", "legal"],
        required_approvers=3,
        must_include_roles=["security_lead", "privacy_dpo"],
    )
    assert ok is True
    assert reason == ""
