"""rerun endpoint — Cosmos fallback when the source run isn't in-memory.

Regression: POST /api/runs/{id}/rerun only checked the in-memory _runs dict.
After a pod restart (deploy/scale) the source run is gone from memory but still
durable in Cosmos, so rerun 404'd ("source run not found") and the UI's retry
button silently no-op'd. rerun must hydrate from Cosmos like get_run does.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from apps.orchestrator import main as orch_main
from apps.orchestrator.main import app
from apps.orchestrator.models import RunState, RunMode


class _FakeLedger:
    """Minimal ledger: get_run returns a durable doc; create_run_strict is a noop."""
    def __init__(self, doc: dict | None):
        self._doc = doc
        self.created: list = []

    async def get_run(self, run_id: str):
        return self._doc

    async def create_run_strict(self, run):
        self.created.append(run)


@pytest.fixture
def client():
    return TestClient(app)


def _durable_doc(run_id: str) -> dict:
    return RunState(
        run_id=run_id,
        team_id="cardiology",
        mode=RunMode.MANUAL,
        status="failed",
    ).model_dump(mode="json")


def test_rerun_hydrates_source_from_cosmos_when_not_in_memory(client, monkeypatch):
    run_id = "11111111-1111-4111-8111-111111111111"
    monkeypatch.setattr(orch_main, "_runs", {})           # empty in-memory (post-restart)
    monkeypatch.setattr(orch_main, "_queues", {})
    monkeypatch.setattr(orch_main, "_prd_cache", {run_id: "# PRD\nsynthetic body"})
    monkeypatch.setattr(orch_main, "_input_store", None)  # skip blob restore
    monkeypatch.setattr(orch_main, "_ledger", _FakeLedger(_durable_doc(run_id)))
    # Don't actually drive a pipeline in the test.
    monkeypatch.setattr(orch_main.asyncio, "create_task", lambda *a, **k: None)

    resp = client.post(f"/api/runs/{run_id}/rerun", json={})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["source_run_id"] == run_id
    assert body["team_id"] == "cardiology"
    # Inverted mode: manual -> autopilot.
    assert body["mode"] == "autopilot"


def test_rerun_404_when_source_absent_everywhere(client, monkeypatch):
    run_id = "22222222-2222-4222-8222-222222222222"
    monkeypatch.setattr(orch_main, "_runs", {})
    monkeypatch.setattr(orch_main, "_ledger", _FakeLedger(None))  # not in Cosmos either
    resp = client.post(f"/api/runs/{run_id}/rerun", json={})
    assert resp.status_code == 404
    assert "source run not found" in resp.text
