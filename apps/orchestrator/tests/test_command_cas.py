"""Optimistic command commits permit one durable winner and replay safely."""
from __future__ import annotations

import asyncio
from copy import deepcopy

from apps.orchestrator.commands import cas_command
from apps.orchestrator.models import RunState


class Conflict(RuntimeError):
    pass


class Ledger:
    def __init__(self):
        self.doc = RunState(run_id="run-cas").model_dump(mode="json") | {"_etag": "v1"}
        self.replaces = 0

    async def get_run(self, run_id: str):
        await asyncio.sleep(0)
        return deepcopy(self.doc)

    async def replace_run_strict(self, run, *, expected_etag: str):
        await asyncio.sleep(0)
        if expected_etag != self.doc["_etag"]:
            raise Conflict("precondition failed")
        version = int(self.doc["_etag"][1:]) + 1
        self.doc = run.model_dump(mode="json") | {"_etag": f"v{version}"}
        self.replaces += 1
        return deepcopy(self.doc)


def test_concurrent_identical_commands_have_one_durable_winner():
    ledger = Ledger()

    def mutate(run: RunState) -> dict:
        run.total_tokens += 1
        return {"ok": True, "total_tokens": run.total_tokens}

    async def scenario():
        return await asyncio.gather(
            cas_command(ledger, "run-cas", record_key="actor|route|key", payload={"x": 1}, mutate=mutate),
            cas_command(ledger, "run-cas", record_key="actor|route|key", payload={"x": 1}, mutate=mutate),
        )

    first, second = asyncio.run(scenario())
    assert first == second == {"ok": True, "total_tokens": 1}
    assert ledger.doc["total_tokens"] == 1
    assert ledger.replaces == 1


def test_same_key_with_different_payload_conflicts_after_retry():
    ledger = Ledger()

    async def scenario():
        await cas_command(
            ledger, "run-cas", record_key="actor|route|key", payload={"x": 1},
            mutate=lambda run: {"ok": True},
        )
        try:
            await cas_command(
                ledger, "run-cas", record_key="actor|route|key", payload={"x": 2},
                mutate=lambda run: {"ok": False},
            )
        except Exception as exc:
            return exc
        raise AssertionError("expected conflict")

    exc = asyncio.run(scenario())
    assert getattr(exc, "status_code", None) == 409
    assert getattr(exc, "detail", None) == "idempotency_conflict"
