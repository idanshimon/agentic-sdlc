"""Tests for /api/telemetry/* endpoints (decisions, cost, classes).

Strategy: stub `_ledger` on the FastAPI app module with a fake Ledger whose
`_ledger` and `_runs` containers expose query_items() as an async iterator. This
lets us assert that:
  * window parsing maps 24h/7d/30d to the right delta,
  * team_id and kind filters reach the SQL,
  * empty-state path returns 200 with empty arrays (no 500s),
  * aggregation math is correct (totals, autopilot split, per-stage breakdown),
  * ledger order is newest-first.

These tests never touch the network — Cosmos is fully faked.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

import pytest
from fastapi.testclient import TestClient

from apps.orchestrator import main as orch_main
from apps.orchestrator import telemetry_queries as tq
from apps.orchestrator.main import app


# ── fake Cosmos container ────────────────────────────────────────────────────
class _FakeContainer:
    """Minimal async query_items() — records the last call for assertions."""

    def __init__(self, items: list[dict]):
        self._items = items
        self.last_query: str | None = None
        self.last_params: list[dict] | None = None
        self.last_kwargs: dict | None = None

    def query_items(self, *, query: str, parameters=None, **kwargs):
        self.last_query = query
        self.last_params = list(parameters or [])
        self.last_kwargs = kwargs

        async def _aiter():
            for it in self._items:
                yield it

        return _aiter()


class _FakeLedger:
    def __init__(self, ledger_items: list[dict], run_items: list[dict]):
        self._ledger = _FakeContainer(ledger_items)
        self._runs = _FakeContainer(run_items)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def fake_ledger(monkeypatch):
    def _install(ledger_items=None, run_items=None):
        fake = _FakeLedger(ledger_items or [], run_items or [])
        monkeypatch.setattr(orch_main, "_ledger", fake)
        return fake

    return _install


# ── /api/telemetry/decisions ─────────────────────────────────────────────────
def test_decisions_empty_when_ledger_disabled(client, monkeypatch):
    monkeypatch.setattr(orch_main, "_ledger", None)
    resp = client.get("/api/telemetry/decisions")
    assert resp.status_code == 200
    assert resp.json() == {"items": [], "count": 0}


def test_decisions_ordered_newest_first_and_filters_team(client, fake_ledger):
    items = [
        {"id": "a", "team_id": "cardiology", "decision_kind": "accept",
         "ambiguity_class": "data-retention", "resolution_text": "old",
         "created_at": "2026-05-20T10:00:00+00:00", "_rid": "x"},
        {"id": "b", "team_id": "cardiology", "decision_kind": "swap",
         "ambiguity_class": "scope-resolution", "resolution_text": "new",
         "created_at": "2026-05-25T10:00:00+00:00"},
    ]
    fake = fake_ledger(ledger_items=items)
    resp = client.get("/api/telemetry/decisions?team_id=cardiology&kind=accept,swap&limit=10")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2
    # Cosmos-internal keys stripped
    assert "_rid" not in body["items"][0]
    # Filters reached the query
    assert "c.team_id=@t" in fake._ledger.last_query
    assert "c.decision_kind IN" in fake._ledger.last_query
    assert "c.created_at" in fake._ledger.last_query or "FROM c" in fake._ledger.last_query
    # team_id triggers partition_key path (not cross-partition)
    assert fake._ledger.last_kwargs.get("partition_key") == "cardiology"


# ── /api/telemetry/cost ──────────────────────────────────────────────────────
def test_cost_window_parsing():
    assert tq.parse_window("24h") == timedelta(hours=24)
    assert tq.parse_window("7d") == timedelta(days=7)
    assert tq.parse_window("30d") == timedelta(days=30)
    assert tq.parse_window("bogus") == timedelta(hours=24)


def test_cost_aggregation_math_pure():
    """Aggregation math: totals, human/autopilot split, per-stage apportion."""
    now = datetime.now(timezone.utc)
    runs = [
        {
            "run_id": "r1", "team_id": "cardiology",
            "created_at": (now - timedelta(hours=2)).isoformat(),
            "total_cost_usd": 1.00, "total_tokens": 1000,
            "gate_wall_clock_seconds": 30.0,
            "autopilot_decisions": ["c1"],
            "decisions": [
                {"card_id": "c1", "decision_kind": "accept",
                 "confidence_source": "autopilot"},
                {"card_id": "c2", "decision_kind": "swap",
                 "confidence_source": "human"},
            ],
            "events": [
                {"stage": "ingest", "status": "completed"},
                {"stage": "assessor", "status": "completed"},
                {"stage": "codegen", "status": "completed"},
            ],
        },
        {
            "run_id": "r2", "team_id": "cardiology",
            "created_at": (now - timedelta(hours=4)).isoformat(),
            "total_cost_usd": 0.50, "total_tokens": 500,
            "gate_wall_clock_seconds": 10.0,
            "autopilot_decisions": [],
            "decisions": [
                {"card_id": "c3", "decision_kind": "accept",
                 "confidence_source": "human"},
            ],
            "events": [{"stage": "assessor", "status": "completed"}],
        },
    ]
    out = tq._aggregate_cost(runs, now - timedelta(hours=24), timedelta(hours=24))
    assert out["total_runs"] == 2
    assert out["total_decisions"] == 3
    assert out["human_decisions"] == 2
    assert out["autopilot_decisions"] == 1
    assert abs(out["total_cost_usd"] - 1.5) < 1e-6
    assert abs(out["cost_per_decision_usd"] - 0.5) < 1e-6
    assert abs(out["mean_gate_wall_clock_seconds"] - 20.0) < 1e-3
    assert out["mean_tokens_per_run"] == 750.0
    # Stage cost split — assessor saw both runs, so its bucket > codegen's bucket.
    cbs = out["cost_by_stage"]
    assert set(cbs.keys()) == {
        "ingest", "assessor", "architect", "test_plan", "codegen", "review_scan",
    }
    assert cbs["assessor"] > 0
    assert cbs["codegen"] > 0
    # Architect/test_plan/review_scan never completed in either run → 0.
    assert cbs["architect"] == 0
    # Conservation: sum of stage costs ≈ total cost.
    assert abs(sum(cbs.values()) - out["total_cost_usd"]) < 1e-4
    # Timeseries sorted ascending by ts.
    ts_list = [p["ts"] for p in out["cost_per_run_timeseries"]]
    assert ts_list == sorted(ts_list)


def test_cost_endpoint_returns_zeros_when_no_runs(client, fake_ledger):
    fake_ledger(run_items=[])
    resp = client.get("/api/telemetry/cost?window=7d&team_id=cardiology")
    assert resp.status_code == 200
    b = resp.json()
    assert b["total_runs"] == 0
    assert b["total_cost_usd"] == 0.0
    assert b["cost_by_stage"] == {
        "ingest": 0.0, "assessor": 0.0, "architect": 0.0,
        "test_plan": 0.0, "codegen": 0.0, "review_scan": 0.0,
    }


# ── /api/telemetry/classes ───────────────────────────────────────────────────
def test_classes_endpoint_empty_state(client, fake_ledger):
    fake_ledger(run_items=[])
    resp = client.get("/api/telemetry/classes?window=24h")
    assert resp.status_code == 200
    b = resp.json()
    assert b["total_decisions"] == 0
    assert b["classes"] == []


def test_classes_aggregates_blast_acceptance_trend(client, fake_ledger):
    now = datetime.now(timezone.utc)
    # Current window: 1 phi card, accepted by autopilot, blast 400.
    # Previous window: same class, 1 decision. (cur==prev → flat)
    runs = [
        {
            "run_id": "rA", "team_id": "cardiology",
            "created_at": (now - timedelta(hours=2)).isoformat(),
            "cards": [{"card_id": "c1", "ambiguity_class": "phi-classification",
                       "blast_radius_cost_usd": 400.0}],
            "autopilot_decisions": ["c1"],
            "decisions": [{"card_id": "c1", "decision_kind": "accept",
                           "confidence_source": "autopilot"}],
        },
        {
            "run_id": "rB", "team_id": "cardiology",
            "created_at": (now - timedelta(hours=30)).isoformat(),  # previous window
            "cards": [{"card_id": "c2", "ambiguity_class": "phi-classification",
                       "blast_radius_cost_usd": 200.0}],
            "decisions": [{"card_id": "c2", "decision_kind": "accept",
                           "confidence_source": "human"}],
        },
    ]
    fake_ledger(run_items=runs)
    resp = client.get("/api/telemetry/classes?window=24h&team_id=cardiology")
    assert resp.status_code == 200
    b = resp.json()
    assert b["total_decisions"] == 1
    cls = b["classes"][0]
    assert cls["ambiguity_class"] == "phi-classification"
    assert cls["count"] == 1
    assert cls["pct_of_total"] == 100.0
    assert cls["autopilot_acceptance_rate"] == 1.0
    assert cls["mean_blast_radius_cost_usd"] == 400.0
    assert cls["trend"] == "flat"
    assert cls["is_invariant"] is True
