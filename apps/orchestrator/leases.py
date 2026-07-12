"""Lease helpers for bounded single-service restart recovery."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from .models import RunState


class LeaseConflict(RuntimeError):
    pass


def _parse(value: str | None) -> datetime | None:
    if not value: return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def acquire_lease(run: RunState, owner: str, *, now: datetime | None = None, ttl_seconds: int = 60) -> None:
    now = now or datetime.now(timezone.utc)
    expiry = _parse(run.lease_expires_at)
    if run.lease_owner and run.lease_owner != owner and expiry and expiry > now:
        raise LeaseConflict(f"run leased by {run.lease_owner} until {run.lease_expires_at}")
    run.lease_owner = owner
    run.lease_expires_at = (now + timedelta(seconds=ttl_seconds)).isoformat()
    run.run_version += 1


def renew_lease(run: RunState, owner: str, *, now: datetime | None = None, ttl_seconds: int = 60) -> None:
    if run.lease_owner != owner:
        raise LeaseConflict("cannot renew a lease owned by another worker")
    now = now or datetime.now(timezone.utc)
    run.lease_expires_at = (now + timedelta(seconds=ttl_seconds)).isoformat()
    run.run_version += 1


def release_lease(run: RunState, owner: str) -> None:
    if run.lease_owner != owner:
        raise LeaseConflict("cannot release a lease owned by another worker")
    run.lease_owner = None
    run.lease_expires_at = None
    run.run_version += 1


async def maintain_lease(
    ledger, *, run_id: str, owner: str, stop: asyncio.Event,
    lost: asyncio.Event | None = None,
    interval_seconds: float = 20.0, ttl_seconds: int = 60,
) -> None:
    """Renew an owned lease with ETag CAS until execution stops or ownership changes."""
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
            break
        except TimeoutError:
            pass
        doc = await ledger.get_run(run_id)
        if not doc or doc.get("lease_owner") != owner:
            if lost: lost.set()
            return
        etag = doc.get("_etag")
        if not etag:
            if lost: lost.set()
            return
        run = RunState.model_validate(doc)
        renew_lease(run, owner, ttl_seconds=ttl_seconds)
        try:
            await ledger.replace_run_strict(run, expected_etag=etag)
        except Exception:
            # A competing writer or takeover won; continuing would risk split brain.
            if lost: lost.set()
            return
