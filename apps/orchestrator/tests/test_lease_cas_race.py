"""Regression: maintain_lease must not abort a run on a CAS failure caused by the
SAME owner's concurrent writes (the pipeline's own per-event _push bumps the
etag). Only a real ownership change (takeover / release) should set lease_lost.

Before the fix, any etag movement between get_run and replace_run_strict was
treated as a takeover, aborting every run mid-codegen (where events — hence
save_run_cas etag bumps — fire fastest)."""
import asyncio
from datetime import datetime, timedelta, timezone

from apps.orchestrator.leases import maintain_lease
from apps.orchestrator.models import RunState


class RacyLedger:
    """Simulates the owner's own _push moving the etag between the lease
    maintainer's read and its CAS write, `fail_first` times, before succeeding.
    Ownership never changes."""

    def __init__(self, run, fail_first: int):
        self.run = run
        self.etag = "v1"
        self.renewals = 0
        self._fail_left = fail_first
        self._counter = 1

    async def get_run(self, run_id):
        return self.run.model_dump(mode="json") | {"_etag": self.etag}

    async def replace_run_strict(self, run, *, expected_etag):
        if self._fail_left > 0:
            # A concurrent _push already advanced the etag → CAS fails, but the
            # run is still owned by the same worker.
            self._fail_left -= 1
            self._counter += 1
            self.etag = f"v{self._counter}"  # etag moved out from under us
            raise RuntimeError("PreconditionFailed: etag mismatch (own write)")
        self.renewals += 1
        self._counter += 1
        self.etag = f"v{self._counter}"
        self.run = run
        return run.model_dump(mode="json") | {"_etag": self.etag}


def _owned_run(rid: str) -> RunState:
    return RunState(
        run_id=rid, lease_owner="worker-1",
        lease_expires_at=(datetime.now(timezone.utc) + timedelta(seconds=5)).isoformat(),
    )


def test_cas_failure_from_own_writes_does_not_lose_lease():
    run = _owned_run("r-race")
    ledger = RacyLedger(run, fail_first=2)  # two self-write races, then succeed

    async def scenario():
        stop = asyncio.Event()
        lost = asyncio.Event()
        task = asyncio.create_task(maintain_lease(
            ledger, run_id="r-race", owner="worker-1", stop=stop, lost=lost,
            interval_seconds=0.01, ttl_seconds=5,
        ))
        await asyncio.sleep(0.05)
        stop.set()
        await task
        return lost.is_set()

    lost = asyncio.run(scenario())
    assert not lost, "own-write CAS churn must NOT declare the lease lost"
    assert ledger.renewals >= 1, "should eventually renew after retrying"


class TakeoverLedger:
    """A different worker owns the run now — a genuine takeover."""

    def __init__(self, run):
        self.run = run
        self.etag = "v1"
        self.renewals = 0

    async def get_run(self, run_id):
        # ownership already flipped to another worker
        d = self.run.model_dump(mode="json")
        d["lease_owner"] = "worker-2"
        return d | {"_etag": self.etag}

    async def replace_run_strict(self, run, *, expected_etag):
        self.renewals += 1
        return run.model_dump(mode="json") | {"_etag": "v2"}


def test_real_takeover_still_declares_lease_lost():
    run = _owned_run("r-takeover")
    ledger = TakeoverLedger(run)

    async def scenario():
        stop = asyncio.Event()
        lost = asyncio.Event()
        await maintain_lease(
            ledger, run_id="r-takeover", owner="worker-1", stop=stop, lost=lost,
            interval_seconds=0.001, ttl_seconds=5,
        )
        return lost.is_set()

    lost = asyncio.run(scenario())
    assert lost, "a genuine ownership change MUST set lease_lost"
    assert ledger.renewals == 0, "must not renew a lease we no longer own"
