"""Regression test: the runs index must surface the NEWEST runs.

The bug: `query_recent_runs` issued `SELECT TOP {limit} ...` with no ORDER BY,
then sorted the results client-side. Cosmos applies TOP *before* any ordering,
so the database returned an arbitrary `limit` documents and the sort could only
order that arbitrary slice.

Once the container held more than `limit` runs, a newly created run was
structurally unreachable from `/api/runs` — fetchable by ID, absent from the
list. The dashboard kept rendering a healthy-looking page of stale runs and
silently stopped showing new activity. This is the "empty/wrong surface that
looks fine" failure class: no error, no empty state, just quietly wrong.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from orchestrator.telemetry_queries import (  # noqa: E402
    _RECENT_RUNS_SCAN_CAP,
    query_recent_runs,
)


class _FakeRunsContainer:
    """Minimal Cosmos container that honours TOP the way Cosmos does.

    The load-bearing behaviour: TOP truncates in STORAGE order, before any
    sort. Storage order here is insertion order (oldest first), which is what
    made the newest runs invisible.
    """

    def __init__(self, docs: list[dict]):
        self._docs = docs
        self.last_query: str | None = None

    def query_items(self, query: str, parameters=None):  # noqa: ANN001
        self.last_query = query
        top = None
        if "TOP " in query:
            top = int(query.split("TOP ", 1)[1].split()[0])
        docs = self._docs[:top] if top is not None else list(self._docs)

        async def _gen():
            for d in docs:
                yield d

        return _gen()


class _FakeLedger:
    def __init__(self, docs: list[dict]):
        self._runs = _FakeRunsContainer(docs)


def _run_doc(i: int) -> dict:
    """Run i, where a HIGHER i is NEWER.

    `updated_at` must be strictly increasing in i AND lexicographically
    sortable, since the production sort is a plain string compare on the ISO
    timestamp. Encoding i as whole seconds since a fixed epoch-day gives both
    properties without any modulo wrap-around (an earlier version used
    `i % 60`, which made run-0119 sort above run-0199 and produced a false
    failure that looked like a code bug).
    """
    hours, rem = divmod(i, 3600)
    minutes, seconds = divmod(rem, 60)
    return {
        "run_id": f"run-{i:04d}",
        "team_id": "team-cardiology",
        "status": "completed",
        "current_stage": "deliver",
        "mode": "autopilot",
        "total_cost_usd": 0.1,
        "total_tokens": 1000,
        "created_at": f"2026-07-01T{hours:02d}:{minutes:02d}:{seconds:02d}+00:00",
        "updated_at": f"2026-07-01T{hours:02d}:{minutes:02d}:{seconds:02d}+00:00",
        "decisions": [],
    }


@pytest.mark.asyncio
async def test_newest_run_is_returned_when_container_exceeds_limit():
    """The regression. 200 runs in storage, ask for 50 — must include the newest.

    Under the bug this failed: TOP 50 returned runs 0-49 (the OLDEST), the sort
    reordered only those, and run-0199 never appeared.
    """
    docs = [_run_doc(i) for i in range(200)]  # oldest-first in storage order
    ledger = _FakeLedger(docs)

    out = await query_recent_runs(ledger, team_id="team-cardiology", limit=50)

    assert len(out) == 50
    assert out[0]["run_id"] == "run-0199", (
        "newest run missing from the runs index — TOP truncated before the sort"
    )
    assert out[-1]["run_id"] == "run-0150"


@pytest.mark.asyncio
async def test_results_are_ordered_newest_first():
    docs = [_run_doc(i) for i in range(120)]
    out = await query_recent_runs(_FakeLedger(docs), limit=25)

    updated = [r["updated_at"] for r in out]
    assert updated == sorted(updated, reverse=True)


@pytest.mark.asyncio
async def test_over_fetch_window_is_bounded():
    """Must not degrade into an unbounded scan as the container grows."""
    docs = [_run_doc(i) for i in range(5000)]
    ledger = _FakeLedger(docs)

    await query_recent_runs(ledger, limit=200)

    top = int(ledger._runs.last_query.split("TOP ", 1)[1].split()[0])
    assert top <= _RECENT_RUNS_SCAN_CAP, "fetch window must stay bounded"
    assert top > 200, "must over-fetch beyond the caller's limit to sort correctly"


@pytest.mark.asyncio
async def test_small_container_returns_everything():
    """Fewer runs than the limit — no truncation, still newest-first."""
    docs = [_run_doc(i) for i in range(7)]
    out = await query_recent_runs(_FakeLedger(docs), limit=50)

    assert len(out) == 7
    assert out[0]["run_id"] == "run-0006"


@pytest.mark.asyncio
async def test_limit_is_still_respected():
    docs = [_run_doc(i) for i in range(300)]
    out = await query_recent_runs(_FakeLedger(docs), limit=10)
    assert len(out) == 10


@pytest.mark.asyncio
async def test_cosmos_error_returns_empty_not_500():
    """Pre-existing contract: the dashboard degrades rather than 500s."""

    class _Boom:
        def query_items(self, query, parameters=None):  # noqa: ANN001
            raise RuntimeError("cosmos unavailable")

    class _L:
        _runs = _Boom()

    assert await query_recent_runs(_L(), limit=50) == []
