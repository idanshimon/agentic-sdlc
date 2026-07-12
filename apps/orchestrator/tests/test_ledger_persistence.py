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
        self.replacements: list[dict] = []
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

    async def query_items(self, *, query: str, parameters: list, **kwargs):
        loop_id = next((p["value"] for p in parameters if p["name"] == "@loop"), None)
        for (_, _), doc in list(self._store.items()):
            if loop_id is None or doc.get("loop_id") == loop_id:
                yield dict(doc)

    async def create_item(self, doc: dict):
        key = (doc["id"], doc.get("run_id", doc["id"]))
        if key in self._store:
            raise RuntimeError("conflict")
        doc = {**doc, "_etag": "v1"}
        self._store[key] = doc
        return doc

    async def replace_item(self, *, item: str, body: dict, **kwargs):
        key = (item, body["run_id"])
        current = self._store[key]
        if kwargs.get("etag") != current.get("_etag"):
            raise RuntimeError("precondition failed")
        next_version = int(current["_etag"].lstrip("v")) + 1
        body = {**body, "_etag": f"v{next_version}"}
        self._store[key] = body
        self.replacements.append(body)
        return body


class _FakeLedger:
    """Mirror just enough of Ledger for save_run / get_run under test."""

    def __init__(self, *, raise_on_upsert: Exception | None = None):
        self._runs = _FakeRunsContainer(raise_on_upsert=raise_on_upsert)

    # Bind the real methods — we only stub the container, not the methods.
    save_run = ledger_module.Ledger.save_run
    save_run_cas = ledger_module.Ledger.save_run_cas
    create_run_strict = ledger_module.Ledger.create_run_strict
    replace_run_strict = ledger_module.Ledger.replace_run_strict
    create_review_loop_strict = ledger_module.Ledger.create_review_loop_strict
    save_review_loop_strict = ledger_module.Ledger.save_review_loop_strict
    get_review_loop = ledger_module.Ledger.get_review_loop
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
    back by get_run.

    Note: get_run returns the raw Cosmos dict (NOT a re-hydrated RunState).
    Callers that need a RunState validate it themselves (e.g.
    main.py::admin_mark_failed does RunState.model_validate(doc)). This
    test pins the dict contract so the round-trip keys are guaranteed.
    """
    fake = _FakeLedger()
    run = _sample_run()
    _run(fake.save_run(run))
    loaded = _run(fake.get_run("run-abc-123"))
    assert loaded is not None
    assert loaded["run_id"] == "run-abc-123"
    assert loaded["team_id"] == "cardiology"
    # Enums round-trip as their string values (model_dump(mode="json"))
    assert loaded["status"] == "awaiting_gate"
    assert loaded["current_stage"] == "resolver"
    assert loaded["mode"] == "hybrid"
    assert loaded["total_cost_usd"] == 0.42
    # And the dict re-hydrates into a valid RunState for callers that need it
    rehydrated = RunState.model_validate(loaded)
    assert rehydrated.run_id == "run-abc-123"
    assert rehydrated.status == RunStatus.AWAITING_GATE
    assert rehydrated.current_stage == Stage.RESOLVER
    assert rehydrated.mode == RunMode.HYBRID


def test_strict_create_and_conditional_replace_surface_conflicts():
    fake = _FakeLedger()
    run = _sample_run()
    created = _run(fake.create_run_strict(run))
    assert created["_etag"] == "v1"

    run.run_version = 2
    replaced = _run(fake.replace_run_strict(run, expected_etag="v1"))
    assert replaced["_etag"] == "v2"
    assert replaced["run_version"] == 2

    import pytest
    with pytest.raises(RuntimeError, match="precondition failed"):
        _run(fake.replace_run_strict(run, expected_etag="v1"))


def test_cas_snapshot_preserves_authoritative_command_records():
    fake = _FakeLedger()
    authoritative = _sample_run()
    authoritative.command_records = {"winner": {"request_hash": "h", "result": {"ok": True}}}
    _run(fake.create_run_strict(authoritative))
    stale = _sample_run()
    stale.events = []
    _run(fake.save_run_cas(stale))
    restored = _run(fake.get_run(stale.run_id))
    assert restored["command_records"]["winner"]["result"] == {"ok": True}


def test_review_loop_record_round_trips_durably():
    fake = _FakeLedger()
    record = {
        "loop_id": "loop-abc", "repo": "owner/repo", "pr_number": 7,
        "head_sha": "a" * 40, "disposition": "SNAPSHOT_READY",
        "ledger_hops": [],
    }
    created = _run(fake.create_review_loop_strict(record))
    assert created["_etag"] == "v1"
    loaded = _run(fake.get_review_loop("loop-abc"))
    assert loaded["repo"] == "owner/repo"

    record["disposition"] = "PASSED_AWAITING_MERGE"
    saved = _run(fake.save_review_loop_strict(record, expected_etag="v1"))
    assert saved["_etag"] == "v2"
    assert _run(fake.get_review_loop("loop-abc"))["disposition"] == "PASSED_AWAITING_MERGE"
