import asyncio

from apps.orchestrator.decision_outbox import enqueue_decision, flush_decision_outbox
from apps.orchestrator.models import LedgerEntry, RunState


class Ledger:
    def __init__(self): self.ids = []
    async def write_decision_strict(self, entry): self.ids.append(entry.id)


def test_outbox_retries_and_delivers_once():
    run = RunState()
    entry = LedgerEntry(team_id="t", run_id=run.run_id, decision="x")
    enqueue_decision(run, entry)
    enqueue_decision(run, entry)
    ledger = Ledger()
    assert asyncio.run(flush_decision_outbox(run, ledger)) == 1
    assert asyncio.run(flush_decision_outbox(run, ledger)) == 0
    assert ledger.ids == [entry.id]
    assert run.decision_outbox[0]["status"] == "delivered"
