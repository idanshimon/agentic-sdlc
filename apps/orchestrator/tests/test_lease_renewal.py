import asyncio
from datetime import datetime, timedelta, timezone

from apps.orchestrator.leases import maintain_lease
from apps.orchestrator.models import RunState


class Ledger:
    def __init__(self, run):
        self.run = run
        self.etag = "v1"
        self.renewals = 0

    async def get_run(self, run_id):
        return self.run.model_dump(mode="json") | {"_etag": self.etag}

    async def replace_run_strict(self, run, *, expected_etag):
        assert expected_etag == self.etag
        self.renewals += 1
        self.etag = f"v{self.renewals + 1}"
        self.run = run
        return run.model_dump(mode="json") | {"_etag": self.etag}


def test_lease_maintainer_renews_until_stopped():
    run = RunState(
        run_id="r1", lease_owner="worker-1",
        lease_expires_at=(datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat(),
    )
    ledger = Ledger(run)

    async def scenario():
        stop = asyncio.Event()
        task = asyncio.create_task(maintain_lease(
            ledger, run_id="r1", owner="worker-1", stop=stop,
            interval_seconds=0.01, ttl_seconds=1,
        ))
        await asyncio.sleep(0.035)
        stop.set()
        await task

    asyncio.run(scenario())
    assert ledger.renewals >= 2


def test_lease_maintainer_stops_if_ownership_changes():
    run = RunState(run_id="r2", lease_owner="other-worker")
    ledger = Ledger(run)

    async def scenario():
        stop = asyncio.Event()
        await maintain_lease(
            ledger, run_id="r2", owner="worker-1", stop=stop,
            interval_seconds=0.001, ttl_seconds=1,
        )

    asyncio.run(scenario())
    assert ledger.renewals == 0
