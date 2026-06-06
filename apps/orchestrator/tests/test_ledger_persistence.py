"""Tests for Ledger.save_run / get_run — covers the v0.6.7 Cosmos id-field bug.

The bug: save_run was calling `_runs.upsert_item(run.model_dump())` without
setting an `id` field. Cosmos rejected the upsert with BadRequest, but the
outer try/except swallowed the error and silently logged a warning.
RunState was therefore never persisted, so /runs and /api/runs always
returned an empty list.

These tests pin the fix:
  1. save_run sets doc["id"] = run.run_id
  2. save_run uses model_dump(mode="json") so datetimes/enums round-trip
  3. save_run upserts via the _runs container (not _ledger)
  4. save_run failure is logged but never raises
  5. get_run reads back a RunState that survives round-trip
"""
from __future__ import annotations
import asyncio
import logging
from datetime import datetime

from apps.orchestrator import ledger as ledger_module
from apps.orchestrator.models import RunMode, RunState, RunStatus, Stage


def _run(coro):
    return asyncio.run(coro)


class _FakeRunsContainer:
    def __init__(self, *, raise_on_upsert: Exception | None = None):
        self.upserts: list[dict] = []
        self._raise = raise_on_upsert
        self._store: dict[tuple[str, str], dict] = {}

    async def upsert_item(self, doc: dict):
        if self._raise is not None:
            raise self._raise
        # Mimic Cosmos: requires `id` to land.
        if "id" not in doc:
            raise RuntimeError("Cosmos rejected upsert: missing 'id' field")
        self.upserts.append(doc)
        self._store[(doc["id"], doc.get("run_id", doc["id"]))] = doc
        return doc

    async def read_item(self, *, item: str, partition_key: str):
        return self._store[(item, partition_key)]


class _FakeLedger:
    """Mirror just enough of Ledger for save_run / get_run under test."""

    def __init__(self, *, raise_on_upsert: Exception | None = None):
        self._runs = _FakeRunsContainer(raise_on_upsert=raise_on_upsert)

    # Bind the real methods — we only stub the container, not the methods.
    save_run = ledger_module.Ledger.save_run
    get_run = ledger_module.Ledger.get_run


def _sample_run() -> RunState:
    """Build a RunState with the field types that previously broke serialization
    — datetime and Enum members."""
    return RunState(
        run_id="run-abc-123",
        team_id="cardiology",
        status=RunStatus.AWAITING_GATE,
        current_stage=Stage.RESOLVER,
        mode=RunMode.HYBRID,
        total_cost_usd=0.42,
        total_tokens=1234,
        gate_wall_clock_seconds=12.5,
    )


def test_save_run_sets_cosmos_id_field():
    fake = _FakeLedger()
    run = _sample_run()
    _run(fake.save_run(run))
    assert len(fake._runs.upserts) == 1
    doc = fake._runs.upserts[0]
    assert doc["id"] == "run-abc-123", "Cosmos requires `id`; save_run must set it from run_id"
    assert doc["run_id"] == "run-abc-123"


def test_save_run_serializes_enums_and_datetimes_as_json():
    """model_dump(mode='json') must be used so Cosmos receives ISO datetimes
    and string enum values, not Python repr() of Enum members."""
    fake = _FakeLedger()
    run = _sample_run()
    _run(fake.save_run(run))
    doc = fake._runs.upserts[0]
    # Enum → string, not "<RunStatus.AWAITING_GATE: 'awaiting_gate'>"
    assert doc["status"] == "awaiting_gate"
    assert doc["current_stage"] == "resolver"
    assert doc["mode"] == "hybrid"
    # Datetimes → ISO strings, not datetime objects
    assert isinstance(doc["created_at"], str)
    assert isinstance(doc["updated_at"], str)
    # Cheap sanity: ISO-8601 round-trips
    datetime.fromisoformat(doc["created_at"])


def test_save_run_failure_is_logged_not_raised(caplog):
    """Demo-resilience invariant: a Cosmos failure must never crash the
    FastAPI request handler that called save_run."""
    fake = _FakeLedger(raise_on_upsert=RuntimeError("cosmos throttled"))
    run = _sample_run()
    with caplog.at_level(logging.WARNING, logger="orchestrator.ledger"):
        _run(fake.save_run(run))  # MUST NOT raise
    assert any("Run save failed" in rec.message for rec in caplog.records)
    assert any("run-abc-123" in rec.message for rec in caplog.records)


def test_save_run_then_get_run_round_trips():
    """End-to-end: persistence shape produced by save_run must be readable
    back into a valid RunState by get_run."""
    fake = _FakeLedger()
    run = _sample_run()
    _run(fake.save_run(run))
    loaded = _run(fake.get_run("run-abc-123"))
    assert loaded is not None
    assert loaded.run_id == "run-abc-123"
    assert loaded.team_id == "cardiology"
    assert loaded.status == RunStatus.AWAITING_GATE
    assert loaded.current_stage == Stage.RESOLVER
    assert loaded.mode == RunMode.HYBRID
    assert loaded.total_cost_usd == 0.42
