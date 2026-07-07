"""Phase 5 compliance-query tests — the acceptance query (THE hero).

openspec: add-configuration-plane / Requirement "unified compliance query
surface". The definition of done for the whole capability:

  "Every AI decision on PHI-classified data in the last 30 days, the governing
   rule version, the deciding actor (human UPN or agent principal), and the cost"
   returns complete, real, cross-surface rows.

These tests exercise the PURE row-builder (build_compliance_rows) — deterministic,
no Cosmos — over ledger-entry dicts. The endpoint + Cosmos wiring is thin glue
on top (covered by an endpoint test separately).

RED first: apps/orchestrator/compliance_query.py does not exist yet.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from apps.orchestrator import compliance_query as cq


def _iso(days_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


# A representative cross-surface ledger: pipeline stage decision, an autopilot
# decision, a human PHI gate, an IDE/agent-hq session entry, and an old one.
LEDGER = [
    {
        "id": "e1", "team_id": "cardiology", "run_id": "r1",
        "created_at": _iso(2), "phi_class": "high",
        "decision": "PHI classification resolved to high", "resolution_text": "treat as PHI",
        "ambiguity_class": "phi-classification", "decision_kind": "accept",
        "created_by": "idan@microsoft.com", "confidence_source": "human",
        "actor": {"kind": "human", "id": "idan@microsoft.com"},
        "autonomy_ref": "autonomy/invariant/phi-classification/gate:phi-auth-hard-lock",
        "bundle_refs": ["security/v0.1.0/PHI-001"],
        "model_used": "gpt-4-1", "cost_usd": 0.021,
    },
    {
        "id": "e2", "team_id": "cardiology", "run_id": "r1",
        "created_at": _iso(2), "phi_class": "none",
        "decision": "naming convention auto-resolved", "resolution_text": "snake_case",
        "ambiguity_class": "naming-convention", "decision_kind": "accept",
        "created_by": "pipeline-doctor@agent", "confidence_source": "autopilot",
        "actor": {"kind": "agent", "id": "pipeline-doctor@agent"},
        "autonomy_ref": "autonomy/matrix/*/naming-convention/autopilot_always:autopilot-always",
        "bundle_refs": ["architect/v0.1.0/NAMING-001"],
        "model_used": "gpt-4-1-mini", "cost_usd": 0.004,
    },
    {
        "id": "e3", "team_id": "radiology", "run_id": None,
        "agent_session_id": "gh-sess-9", "created_at": _iso(5), "phi_class": "high",
        "decision": "IDE session touched PHI mapping", "resolution_text": "",
        "created_by": "dev@microsoft.com", "confidence_source": "human",
        "actor": {"kind": "human", "id": "dev@microsoft.com"},
        "autonomy_ref": "", "bundle_refs": ["security/v0.1.0/PHI-002"],
        "model_used": "claude-sonnet-4-6", "cost_usd": 0.05,
    },
    {
        "id": "e4", "team_id": "cardiology", "run_id": "r0",
        "created_at": _iso(45), "phi_class": "high",  # OLD — outside 30d
        "decision": "stale phi decision", "created_by": "idan@microsoft.com",
        "actor": {"kind": "human", "id": "idan@microsoft.com"},
        "autonomy_ref": "autonomy/invariant/phi-classification/gate",
        "bundle_refs": ["security/v0.1.0/PHI-001"], "model_used": "gpt-4-1",
        "cost_usd": 0.03,
    },
]


# ---- row shape --------------------------------------------------------------

def test_row_carries_what_why_rule_actor_model_cost():
    rows = cq.build_compliance_rows(LEDGER)
    r = next(r for r in rows if r["id"] == "e1")
    assert r["decision"]                      # WHAT
    assert r["autonomy_ref"]                   # WHY (governing autonomy rule)
    assert r["bundle_refs"] == ["security/v0.1.0/PHI-001"]  # rule VERSION
    assert r["actor_kind"] == "human"
    assert r["actor_id"] == "idan@microsoft.com"
    assert r["model_used"] == "gpt-4-1"
    assert r["cost_usd"] == 0.021
    assert r["phi_class"] == "high"


def test_actor_synthesized_from_legacy_created_by_when_actor_absent():
    entry = {
        "id": "x", "team_id": "t", "run_id": "r", "created_at": _iso(1),
        "phi_class": "high", "decision": "d",
        "created_by": "pipeline-doctor@agent", "confidence_source": "autopilot",
    }
    rows = cq.build_compliance_rows([entry])
    assert rows[0]["actor_kind"] == "agent"
    assert rows[0]["actor_id"] == "pipeline-doctor@agent"


# ---- filters ----------------------------------------------------------------

def test_filter_phi_class_high():
    rows = cq.build_compliance_rows(LEDGER, phi_class="high")
    assert {r["id"] for r in rows} == {"e1", "e3", "e4"}  # all phi=high (no date filter here)


def test_filter_since_last_30d_excludes_old():
    since = _iso(30)
    rows = cq.build_compliance_rows(LEDGER, phi_class="high", since_iso=since)
    ids = {r["id"] for r in rows}
    assert "e4" not in ids           # 45d old, excluded
    assert ids == {"e1", "e3"}


def test_filter_actor_kind_agent():
    rows = cq.build_compliance_rows(LEDGER, actor_kind="agent")
    assert {r["id"] for r in rows} == {"e2"}


def test_filter_team():
    rows = cq.build_compliance_rows(LEDGER, team_id="radiology")
    assert {r["id"] for r in rows} == {"e3"}


def test_rows_sorted_newest_first():
    rows = cq.build_compliance_rows(LEDGER)
    ts = [r["created_at"] for r in rows]
    assert ts == sorted(ts, reverse=True)


# ---- THE ACCEPTANCE TEST ----------------------------------------------------

def test_acceptance_phi_high_30d_returns_complete_nonnull_rows():
    """The capability's definition of done: phi_class=high over 30d returns rows
    where WHY (rule version), WHO (actor), model, and cost are all present and
    non-null — no placeholders, no fabricated values."""
    since = _iso(30)
    rows = cq.build_compliance_rows(LEDGER, phi_class="high", since_iso=since)
    assert rows, "acceptance query must return rows"
    for r in rows:
        assert r["bundle_refs"], f"row {r['id']} missing governing rule version"
        assert r["actor_id"], f"row {r['id']} missing actor identity"
        assert r["actor_kind"] in ("human", "agent")
        assert r["model_used"], f"row {r['id']} missing model"
        assert r["cost_usd"] is not None, f"row {r['id']} missing cost"
        assert r["phi_class"] == "high"
    # completeness summary the UI banner asserts on
    summary = cq.completeness_summary(rows)
    assert summary["total"] == len(rows)
    assert summary["complete"] == len(rows)
    assert summary["incomplete"] == 0
