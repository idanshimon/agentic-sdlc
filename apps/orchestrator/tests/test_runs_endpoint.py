"""Tests for /api/runs (recent runs index, powers the /runs page in resolver-ui).

Same faking strategy as test_telemetry_endpoints.py — stub `_ledger` on the
FastAPI app module with a fake whose `_runs` container exposes async
query_items(). We assert empty-state, ordering, team_id and status filters
reach the SQL, and the response shape matches what the UI expects.
"""
from __future__ import annotations
from typing import Any

import pytest
from fastapi.testclient import TestClient

from apps.orchestrator import main as orch_main
from apps.orchestrator.main import app


class _FakeContainer:
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
    def __init__(self, run_items: list[dict]):
        self._ledger = _FakeContainer([])
        self._runs = _FakeContainer(run_items)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def fake_ledger(monkeypatch):
    def _install(run_items=None):
        fake = _FakeLedger(run_items or [])
        monkeypatch.setattr(orch_main, "_ledger", fake)
        return fake

    return _install


def test_runs_empty_when_ledger_disabled(client, monkeypatch):
    monkeypatch.setattr(orch_main, "_ledger", None)
    resp = client.get("/api/runs")
    assert resp.status_code == 200
    assert resp.json() == {"items": [], "count": 0}


def test_runs_returns_summaries_and_orders_by_updated_at_desc(client, fake_ledger):
    # Order in Cosmos response = order we hand back (Cosmos does the ORDER BY).
    items = [
        {
            "run_id": "newer", "team_id": "cardiology", "status": "running",
            "current_stage": "codegen", "mode": "manual",
            "total_cost_usd": 0.42, "total_tokens": 1234,
            "gate_wall_clock_seconds": 12.5, "decisions_count": 3,
            "created_at": "2026-05-25T09:00:00+00:00",
            "updated_at": "2026-05-25T10:00:00+00:00",
            "_rid": "x",
        },
        {
            "run_id": "older", "team_id": "finance", "status": "completed",
            "current_stage": "deliver", "mode": "autopilot",
            "total_cost_usd": 1.10, "total_tokens": 5000,
            "gate_wall_clock_seconds": 0.0, "decisions_count": 7,
            "created_at": "2026-05-20T09:00:00+00:00",
            "updated_at": "2026-05-20T10:00:00+00:00",
        },
    ]
    fake = fake_ledger(run_items=items)
    resp = client.get("/api/runs?limit=10")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2
    assert [r["run_id"] for r in body["items"]] == ["newer", "older"]
    # Sort is now client-side, not in SQL (Cosmos cross-partition ORDER BY needs index).
    assert "FROM c" in fake._runs.last_query
    # azure-cosmos 4.7+ auto-detects cross-partition; kwarg removed.
    # Internal Cosmos keys stripped.
    assert "_rid" not in body["items"][0]
    # Required summary fields present.
    for key in (
        "run_id", "team_id", "status", "current_stage", "mode",
        "decisions_count", "total_cost_usd", "total_tokens",
        "gate_wall_clock_seconds", "created_at", "updated_at",
    ):
        assert key in body["items"][0], f"missing {key}"


def test_runs_team_filter_reaches_query(client, fake_ledger):
    fake = fake_ledger(run_items=[])
    resp = client.get("/api/runs?team_id=cardiology")
    assert resp.status_code == 200
    assert "c.team_id=@t" in fake._runs.last_query
    assert any(p["name"] == "@t" and p["value"] == "cardiology"
               for p in fake._runs.last_params)


def test_runs_status_filter_supports_multi_value(client, fake_ledger):
    fake = fake_ledger(run_items=[])
    resp = client.get("/api/runs?status=running,awaiting_gate")
    assert resp.status_code == 200
    assert "c.status IN" in fake._runs.last_query
    vals = {p["value"] for p in fake._runs.last_params if p["name"].startswith("@st")}
    assert vals == {"running", "awaiting_gate"}


def test_runs_single_status_uses_equality(client, fake_ledger):
    fake = fake_ledger(run_items=[])
    resp = client.get("/api/runs?status=failed&team_id=finance&limit=25")
    assert resp.status_code == 200
    assert "c.status=@st" in fake._runs.last_query
    assert any(p["name"] == "@st" and p["value"] == "failed"
               for p in fake._runs.last_params)


def test_runs_admin_no_team_lists_all_without_team_filter(client, fake_ledger):
    """Regression: an admin/all-teams principal (teams={'*'}) must NOT produce a
    literal team_id='*' filter — no run is stored under '*', so that empties the
    /runs page. With no concrete team the SQL carries no team clause and lists
    across all teams (cosmos 4.x async auto-handles cross-partition)."""
    fake = fake_ledger(run_items=[])
    resp = client.get("/api/runs")
    assert resp.status_code == 200
    assert "c.team_id=@t" not in fake._runs.last_query
    # No invalid SDK kwargs (enable_cross_partition_query / partition_key) — they
    # raise TypeError on azure-cosmos async 4.x.
    assert "enable_cross_partition_query" not in (fake._runs.last_kwargs or {})
    assert "partition_key" not in (fake._runs.last_kwargs or {})


def test_runs_team_scoped_applies_where_clause(client, fake_ledger):
    """When team_id is given, scope via the WHERE clause (this container is
    partitioned on /run_id, so partition_key= would be wrong)."""
    fake = fake_ledger(run_items=[])
    resp = client.get("/api/runs?team_id=cardiology")
    assert resp.status_code == 200
    assert "c.team_id=@t" in fake._runs.last_query
    assert "partition_key" not in (fake._runs.last_kwargs or {})
