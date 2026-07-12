"""Durable cross-container Decision Ledger outbox."""
from __future__ import annotations

from .models import LedgerEntry, RunState


def enqueue_decision(run: RunState, entry: LedgerEntry) -> None:
    if any(item.get("entry", {}).get("id") == entry.id for item in run.decision_outbox):
        return
    run.decision_outbox.append({"entry": entry.model_dump(mode="json"), "status": "pending"})


async def flush_decision_outbox(run: RunState, ledger) -> int:
    delivered = 0
    for item in run.decision_outbox:
        if item.get("status") == "delivered":
            continue
        entry = LedgerEntry.model_validate(item["entry"])
        await ledger.write_decision_strict(entry)
        item["status"] = "delivered"
        delivered += 1
    return delivered
