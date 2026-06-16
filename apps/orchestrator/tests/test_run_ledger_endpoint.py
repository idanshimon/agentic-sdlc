"""Phase 2.7: /api/runs/{run_id}/ledger endpoint regression tests.

Validates the proxy endpoint that surfaces ledger entries for a run
through the orchestrator's authenticated Cosmos client — bypassing
ledger-mcp's per-token team-scoped auth so the UI + audit tools can
read any run's decision history without per-team JWT setup.

The endpoint is the verification surface for Phase 2.6 chain pinning:
given any deployed run_id, GET /api/runs/{id}/ledger returns the
entries with prompt_resolution_path populated for every Phase-2 stage_decision.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from orchestrator import main as om


def _client() -> TestClient:
    return TestClient(om.app)


def test_run_ledger_404_when_run_unknown(monkeypatch):
    """Unknown run_id with no ledger → 404 with explanation."""
    monkeypatch.setattr(om, "_ledger", None)
    r = _client().get("/api/runs/does-not-exist/ledger")
    assert r.status_code == 200  # no ledger configured returns empty
    body = r.json()
    assert body == {"entries": [], "run_id": "does-not-exist", "note": "ledger not configured"}


def test_run_ledger_404_when_team_unknown(monkeypatch):
    """Ledger configured but run not in memory and Cosmos has no record → 404."""
    class _StubLedger:
        async def get_run(self, rid):
            return None
    monkeypatch.setattr(om, "_ledger", _StubLedger())
    monkeypatch.setattr(om, "_runs", {})
    r = _client().get("/api/runs/unknown-team/ledger")
    assert r.status_code == 404
    assert "could not infer team_id" in r.json()["detail"]


def test_run_ledger_returns_entries_from_inmemory_run(monkeypatch):
    """When run is in memory, use its team_id and proxy a Cosmos query."""
    from orchestrator.models import RunState
    run = RunState(run_id="rid-1", team_id="cardiology")
    monkeypatch.setattr(om, "_runs", {"rid-1": run})

    captured = {}
    class _StubContainer:
        async def __aiter__(self):
            return self
        async def __anext__(self):
            raise StopAsyncIteration
        def query_items(self, *, query, parameters, partition_key):
            captured["query"] = query
            captured["parameters"] = parameters
            captured["partition_key"] = partition_key
            async def _empty():
                if False:
                    yield None
            return _empty()
    class _StubLedger:
        _ledger = _StubContainer()
        async def get_run(self, rid):
            return None
    monkeypatch.setattr(om, "_ledger", _StubLedger())

    r = _client().get("/api/runs/rid-1/ledger")
    assert r.status_code == 200
    body = r.json()
    assert body["run_id"] == "rid-1"
    assert body["team_id"] == "cardiology"
    assert body["count"] == 0
    assert body["entries"] == []
    # The endpoint MUST scope to the right partition + the right run
    assert captured["partition_key"] == "cardiology"
    assert {"name": "@team", "value": "cardiology"} in captured["parameters"]
    assert {"name": "@run",  "value": "rid-1"}      in captured["parameters"]
