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
    max_cas_retries: int = 4,
) -> None:
    """Renew an owned lease with ETag CAS until execution stops or ownership
    changes.

    CAS-failure semantics: a failed replace_run_strict does NOT by itself mean a
    competing worker took over — in normal single-writer operation the pipeline's
    own per-event `_push` (save_run_cas) bumps the etag between our get_run and
    our renew CAS. Treating that as "lease lost" aborted every run mid-codegen
    (the etag moves fastest exactly when the LLM stage emits many events). So on
    CAS failure we RE-READ and only declare the lease lost when ``lease_owner``
    has actually changed to someone else (or the run vanished / lease expired
    under us). Otherwise we retry with the fresh etag. A real takeover flips
    lease_owner and is still detected immediately.
    """
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
            break
        except TimeoutError:
            pass
        renewed = False
        for _attempt in range(max_cas_retries):
            doc = await ledger.get_run(run_id)
            if not doc or doc.get("lease_owner") != owner:
                # Genuinely not ours anymore (takeover, release, or gone).
                if lost:
                    lost.set()
                return
            etag = doc.get("_etag")
            if not etag:
                if lost:
                    lost.set()
                return
            run = RunState.model_validate(doc)
            renew_lease(run, owner, ttl_seconds=ttl_seconds)
            try:
                await ledger.replace_run_strict(run, expected_etag=etag)
                renewed = True
                break
            except Exception:
                # Etag moved between our read and write. Could be our own _push
                # (benign — retry) or a real takeover (next get_run reveals it).
                continue
        if not renewed:
            # Exhausted retries without confirming a takeover — re-read once more
            # to make the final call, so we never abort a run we still own just
            # because writes were racing.
            doc = await ledger.get_run(run_id)
            if not doc or doc.get("lease_owner") != owner:
                if lost:
                    lost.set()
                return
            # Still ours: the churn was our own writes. Leave lease as-is (the
            # last successful save already carries a fresh-enough expiry from an
            # earlier renew or from _push preserving lease fields) and continue.
