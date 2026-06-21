"""Regression tests for CosmosLedger.find_precedent (the teaching-loop query).

Pins the 2026-06-20 fix: `SELECT TOP 1 ... ORDER BY` with a partition-scoped
async query_items returned an EMPTY iterator even when matching rows existed,
silently killing the teaching loop. The fix drops TOP 1 and takes the first
ordered row in Python.

These tests use a fake async container so they run without Cosmos. They assert:
  1. find_precedent returns the (first/most-recent) matching row
  2. the query is partition-scoped to team_id and filters team/class/slot/runtime
  3. the query does NOT use `SELECT TOP 1` (the regression guard)
"""
from __future__ import annotations

import pytest

from ledger_core.cosmos import LedgerClient


class _FakeAsyncItems:
    """Async iterator over a fixed list of dict rows."""
    def __init__(self, rows):
        self._rows = list(rows)

    def __aiter__(self):
        self._it = iter(self._rows)
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration


class _FakeContainer:
    """Captures the query + params and returns canned rows."""
    def __init__(self, rows):
        self._rows = rows
        self.last_query = None
        self.last_params = None
        self.last_kwargs = None

    def query_items(self, query, parameters=None, **kwargs):
        self.last_query = query
        self.last_params = parameters
        self.last_kwargs = kwargs
        return _FakeAsyncItems(self._rows)


def _client_with(rows):
    """Build a LedgerClient without touching Cosmos, inject a fake container."""
    client = LedgerClient.__new__(LedgerClient)  # bypass __init__ (no Cosmos creds)
    client._ledger = _FakeContainer(rows)  # type: ignore[attr-defined]
    return client


def _row(**over):
    base = {
        "id": "e1",
        "entry_type": "runtime",
        "team_id": "team-cardiology",
        "run_id": "run-a",
        "ambiguity_class": "sla-binding",
        "slot_value_hash": "b1a8260738e3",
        "decision_kind": "swap",
        "resolution_text": "Retain 45 days per team policy CO-99.",
        "created_by": "operator@dashboard",
        "created_at": "2026-06-20T06:52:57.402581+00:00",
        "confidence_source": "human",
    }
    base.update(over)
    return base


@pytest.mark.asyncio
async def test_find_precedent_returns_matching_row():
    """A matching runtime row MUST be returned, not dropped (the TOP-1 bug)."""
    client = _client_with([_row()])
    result = await client.find_precedent("team-cardiology", "sla-binding", "b1a8260738e3")
    assert result is not None, "find_precedent dropped a matching row (TOP-1 regression?)"
    assert result.decision_kind == "swap"
    assert result.resolution_text == "Retain 45 days per team policy CO-99."


@pytest.mark.asyncio
async def test_find_precedent_query_is_not_top1():
    """Regression guard: the query MUST NOT use SELECT TOP 1 (returned empty
    under partition-scoped async query_items)."""
    client = _client_with([_row()])
    await client.find_precedent("team-cardiology", "sla-binding", "b1a8260738e3")
    q = client._ledger.last_query.upper()  # type: ignore[attr-defined]
    assert "TOP 1" not in q and "TOP1" not in q, f"find_precedent reintroduced TOP 1: {q!r}"
    assert "ORDER BY" in q, "find_precedent must still order by created_at to get the most recent"


@pytest.mark.asyncio
async def test_find_precedent_is_partition_scoped_and_filtered():
    """The query MUST be partition-scoped to team_id and filter the precedent key."""
    client = _client_with([_row()])
    await client.find_precedent("team-cardiology", "sla-binding", "b1a8260738e3")
    fc = client._ledger  # type: ignore[attr-defined]
    assert fc.last_kwargs.get("partition_key") == "team-cardiology"
    pvals = {p["value"] for p in fc.last_params}
    assert {"team-cardiology", "sla-binding", "b1a8260738e3"} <= pvals
    q = fc.last_query.lower()
    assert "entry_type='runtime'" in q.replace(" ", "") or "entry_type = 'runtime'" in q


@pytest.mark.asyncio
async def test_find_precedent_returns_first_when_multiple_match():
    """ORDER BY created_at DESC + take-first → most recent wins."""
    newest = _row(id="new", created_at="2026-06-20T08:00:00+00:00", resolution_text="newest")
    older = _row(id="old", created_at="2026-06-20T06:00:00+00:00", resolution_text="older")
    client = _client_with([newest, older])  # fake returns in given (DESC) order
    result = await client.find_precedent("team-cardiology", "sla-binding", "b1a8260738e3")
    assert result is not None
    assert result.resolution_text == "newest"


@pytest.mark.asyncio
async def test_find_precedent_returns_none_when_no_match():
    client = _client_with([])
    result = await client.find_precedent("team-cardiology", "sla-binding", "nomatch")
    assert result is None
