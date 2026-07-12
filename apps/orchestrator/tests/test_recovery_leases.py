from datetime import datetime, timedelta, timezone

import pytest

from apps.orchestrator.leases import LeaseConflict, acquire_lease, release_lease, renew_lease
from apps.orchestrator.models import RunState

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_live_lease_blocks_another_worker():
    run = RunState(lease_owner="worker-a", lease_expires_at=(NOW + timedelta(seconds=30)).isoformat())
    with pytest.raises(LeaseConflict): acquire_lease(run, "worker-b", now=NOW)


def test_expired_lease_can_be_taken_over():
    run = RunState(lease_owner="worker-a", lease_expires_at=(NOW - timedelta(seconds=1)).isoformat())
    acquire_lease(run, "worker-b", now=NOW)
    assert run.lease_owner == "worker-b"


def test_owner_can_renew_and_release():
    run = RunState()
    acquire_lease(run, "worker-a", now=NOW)
    first = run.lease_expires_at
    renew_lease(run, "worker-a", now=NOW + timedelta(seconds=10))
    assert run.lease_expires_at != first
    release_lease(run, "worker-a")
    assert run.lease_owner is None
