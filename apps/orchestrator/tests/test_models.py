"""Unit tests for orchestrator data models.

Covers the option-aware AmbiguityCard contract (design.md §3 + assessor/spec.md REQ-4*):
- ResolutionOption shape
- AmbiguityCard carries prd_quote / prd_section / gap_description / options
- GateDecision accepts option_index OR resolution_text OR neither (default-to-recommended)
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from apps.orchestrator.models import (
    AmbiguityCard,
    GateDecision,
    LedgerEntry,
    ResolutionOption,
    RunState,
    Stage,
    StageEvent,
)


# ---- ResolutionOption --------------------------------------------------------

class TestResolutionOption:
    def test_minimal_option(self):
        opt = ResolutionOption(
            label="HIPAA 7-year retention",
            resolution="Retain PHI for 7 years per §164.530(j).",
            rationale="HIPAA §164.530(j) sets the retention floor.",
            downstream_impact="Architect adds TTL infra; CodeGen wires retention module.",
        )
        assert opt.recommended is False  # default

    def test_recommended_flag(self):
        opt = ResolutionOption(
            label="x", resolution="y", rationale="z", downstream_impact="w",
            recommended=True,
        )
        assert opt.recommended is True

    def test_missing_fields_rejected(self):
        with pytest.raises(ValidationError):
            ResolutionOption(label="only-label")  # type: ignore


# ---- AmbiguityCard -----------------------------------------------------------

class TestAmbiguityCard:
    def test_carries_new_fields(self):
        """Every card MUST expose prd_quote/prd_section/gap_description/options
        per assessor/spec.md REQ-4."""
        card = AmbiguityCard(title="t", detail="d")
        assert hasattr(card, "prd_quote")
        assert hasattr(card, "prd_section")
        assert hasattr(card, "gap_description")
        assert hasattr(card, "options")
        assert hasattr(card, "team_occurrence_count")
        assert card.options == []
        assert card.team_occurrence_count == 0

    def test_card_with_two_options(self):
        rec = ResolutionOption(
            label="Azure SSO", resolution="Use Azure SSO.",
            rationale="Enterprise default.", downstream_impact="Replace JWT.",
            recommended=True,
        )
        alt = ResolutionOption(
            label="Keep JWT", resolution="Continue JWT.",
            rationale="Simpler.", downstream_impact="No changes.",
        )
        card = AmbiguityCard(
            title="Auth method", detail="d", ambiguity_class="auth-policy",
            prd_quote='Authentication: JWT | [change to Azure SSO]',
            prd_section="9.1 Backend Stack",
            gap_description="Does prod use JWT or Azure SSO?",
            options=[rec, alt],
        )
        assert len(card.options) == 2
        recommended = [o for o in card.options if o.recommended]
        assert len(recommended) == 1, "exactly one option carries recommended=True"


# ---- GateDecision ------------------------------------------------------------

class TestGateDecision:
    def test_accept_with_option_index(self):
        d = GateDecision(card_id="abc", decision_kind="accept", option_index=0)
        assert d.option_index == 0
        assert d.resolution_text == ""  # default; server fills from option

    def test_swap_with_text(self):
        d = GateDecision(card_id="abc", decision_kind="swap",
                         resolution_text="user wrote this")
        assert d.option_index is None
        assert d.resolution_text == "user wrote this"

    def test_reject_with_text(self):
        d = GateDecision(card_id="abc", decision_kind="reject",
                         resolution_text="not applicable on this team")
        assert d.decision_kind == "reject"

    def test_gate_level_approval(self):
        """Gate-level (whole-stage) decisions carry no card_id."""
        d = GateDecision(decision_kind="accept", gate="design_review")
        assert d.card_id is None
        assert d.gate == "design_review"


# ---- LedgerEntry -------------------------------------------------------------

class TestLedgerEntry:
    def test_ledger_entry_defaults(self):
        e = LedgerEntry(
            team_id="cardiology", run_id="r1", card_id="c1",
            ambiguity_class="data-retention", decision_kind="accept",
        )
        assert e.status == "suggest"  # v1 writes only ever land as suggest
        assert e.sample_count == 1
        assert e.accuracy_score == 0.0
        assert e.id  # auto-generated


# ---- StageEvent + RunState ---------------------------------------------------

class TestRunState:
    def test_minimal_run(self):
        run = RunState(team_id="cardiology", run_id="r1", prd_blob_url="b")
        assert run.status.value == "running"
        assert run.cards == []
        assert run.decisions == []

    def test_stage_event(self):
        ev = StageEvent(run_id="r1", stage=Stage.ASSESSOR, status="completed")
        assert ev.payload == {}
        assert ev.ts  # auto-stamped
