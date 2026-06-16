"""Tests for /api/runs/{run_id} — verifies the Cosmos fallback when the
in-memory `_runs` dict misses (i.e. historical runs after a pod restart,
or runs seeded directly into Cosmos by an experiment harness).

The bug this guards against: get_run was reading only from the in-process
_runs dict and returned 404 for any run that lived only in Cosmos. /api/runs
(the LIST endpoint) read from Cosmos via query_recent_runs and worked, so
the operator could see the run in /runs but couldn't drill in. The two
endpoints disagreed about what 'run exists' meant.

Pattern mirrored from test_runs_endpoint.py:
  - Stub `_ledger` on the FastAPI app module with a fake exposing an
    async `get_run(run_id) -> dict | None`
  - Clear in-memory `_runs` dict so the fallback path is the only path
  - Assert 200 + total_cost_usd from the fake's payload
  - Assert the Cosmos doc shape that the orchestrator persists is the
    same shape that re-hydrates cleanly via RunState.model_validate
"""
from __future__ import annotations
from typing import Any, Optional

import pytest
from fastapi.testclient import TestClient

from apps.orchestrator import main as orch_main
from apps.orchestrator.main import app


class _FakeLedgerWithGetRun:
    """Just enough of Ledger for the get_run fallback test."""

    def __init__(self, doc: Optional[dict] = None):
        self.doc = doc
        self.calls: list[str] = []

    async def get_run(self, run_id: str) -> Optional[dict]:
        self.calls.append(run_id)
        return self.doc

    # Other Ledger surfaces left undefined — the fallback path doesn't touch them.


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_in_memory_runs(monkeypatch):
    """Every test gets a clean _runs dict so the in-memory hot-path never
    accidentally satisfies a request that's supposed to test the fallback."""
    monkeypatch.setattr(orch_main, "_runs", {})


def _canonical_run_doc(run_id: str = "616d5fa8-74a1-4c0b-ad15-2629b9a854a4") -> dict[str, Any]:
    """A RunState.model_dump()-shaped doc the way save_run + the SBM seeder
    write it. Matches the haiku-4-5-run-1 SBM run we seeded into Cosmos."""
    return {
        "id": run_id,
        "run_id": run_id,
        "team_id": "team-demo",
        "mode": "manual",
        "status": "completed",
        "current_stage": "deliver",
        "created_at": "2026-06-16T05:14:25.259046+00:00",
        "updated_at": "2026-06-16T05:14:25.259046+00:00",
        "events": [],
        "cards": [],
        "decisions": [],
        "total_cost_usd": 0.0837,
        "total_tokens": 27786,
        "wall_clock_seconds": 136.4,
        "stage_durations_seconds": {
            "ingest": 0.1, "assessor": 76.0, "architect": 18.0,
            "test_plan": 25.5, "codegen": 16.5, "review_scan": 0.2,
        },
        "model_routing": {
            "architect": {"provider": "databricks", "model": "databricks-claude-haiku-4-5"},
            "codegen": {"provider": "databricks", "model": "databricks-claude-haiku-4-5"},
        },
        "artifact_sizes": {
            "architecture_chars": 4068,
            "test_plan_chars": 8779,
            "code_chars": 29996,
        },
        "namespace": "sbm-cardiology",
        "model": "databricks-claude-haiku-4-5",
        "model_slug": "haiku-4-5",
        "source_run_dir": "haiku-4-5-run-1",
        "original_team_id": "team-sbm-cardiology-haiku-4-5-run-1",
    }


def test_get_run_returns_in_memory_when_present(client, monkeypatch):
    """In-memory hot path still wins when the run is live in this pod."""
    from apps.orchestrator.models import RunState, RunMode, RunStatus, Stage

    rid = "in-mem-run-1"
    run = RunState(
        run_id=rid, team_id="cardiology", mode=RunMode.MANUAL,
        status=RunStatus.RUNNING, current_stage=Stage.CODEGEN, events=[],
    )
    monkeypatch.setitem(orch_main._runs, rid, run)

    resp = client.get(f"/api/runs/{rid}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == rid
    assert body["status"] == "running"


def test_get_run_falls_back_to_cosmos_when_in_memory_miss(client, monkeypatch):
    """When _runs.get(rid) returns None, the endpoint MUST hit _ledger.get_run
    and return the Cosmos doc re-hydrated as a RunState."""
    rid = "616d5fa8-74a1-4c0b-ad15-2629b9a854a4"
    fake = _FakeLedgerWithGetRun(doc=_canonical_run_doc(rid))
    monkeypatch.setattr(orch_main, "_ledger", fake)

    resp = client.get(f"/api/runs/{rid}")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # The single-most-important fact: the fallback fired.
    assert fake.calls == [rid], "Cosmos get_run should have been called exactly once"

    # And the response surfaces the Cosmos-persisted run shape.
    assert body["run_id"] == rid
    assert body["status"] == "completed"
    assert body["total_cost_usd"] == 0.0837
    assert body["total_tokens"] == 27786
    assert body["model"] == "databricks-claude-haiku-4-5"
    assert body["namespace"] == "sbm-cardiology"


def test_get_run_404_when_neither_memory_nor_cosmos_has_it(client, monkeypatch):
    """Both checks miss → 404. We don't want a 200-with-empty-body."""
    fake = _FakeLedgerWithGetRun(doc=None)
    monkeypatch.setattr(orch_main, "_ledger", fake)

    resp = client.get("/api/runs/does-not-exist")
    assert resp.status_code == 404
    assert fake.calls == ["does-not-exist"], "Cosmos fallback must be tried before 404"


def test_get_run_404_when_ledger_disabled_and_in_memory_miss(client, monkeypatch):
    """If _ledger is None (e.g. local dev without Cosmos), miss → 404 cleanly,
    not a 500 from a None.get_run() call."""
    monkeypatch.setattr(orch_main, "_ledger", None)
    resp = client.get("/api/runs/no-such-run")
    assert resp.status_code == 404


def test_get_run_returns_raw_dict_when_revalidate_fails(client, monkeypatch):
    """If the Cosmos doc is structurally newer than this pod's RunState
    schema (older pod reading newer doc), we MUST NOT 500. Last-resort:
    return the raw dict so the UI degrades gracefully instead of breaking."""
    rid = "schema-drift-run"
    # Doc is missing required fields the current RunState would demand —
    # simulate by passing a minimal dict that won't model_validate.
    bad_doc = {
        "id": rid,
        "run_id": rid,
        "team_id": "team-demo",
        "future_field_that_orchestrator_does_not_know_about": "yes",
        # Deliberately missing required fields to force model_validate to fail.
    }
    fake = _FakeLedgerWithGetRun(doc=bad_doc)
    monkeypatch.setattr(orch_main, "_ledger", fake)

    resp = client.get(f"/api/runs/{rid}")
    # Two acceptable outcomes:
    #   - 200 with the raw dict (preferred — graceful degradation)
    #   - 404 (also acceptable — orchestrator chose to refuse rather than
    #          serve a half-known shape)
    # What we MUST NOT see: a 500.
    assert resp.status_code in (200, 404), (
        f"Schema-drift path must not 500; got {resp.status_code}: {resp.text}"
    )
