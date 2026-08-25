"""Paging, search and honest counts on /api/runs.

The dashboard showed a bare "Showing 50 runs" with no way to reach run 51 and
no way to tell that number from "there are only 50 runs". The underlying
over-fetch/sort/trim fix (see test_recent_runs_ordering.py) made the newest run
reachable again, but the window was still a hard ceiling with no paging, no
server-side search, and no signal that more existed.

These tests pin the three things an operator needs: get the next page, search
the whole window rather than the current page, and be told when the number
being shown is a floor rather than a total.
"""
from __future__ import annotations

import pytest

from apps.orchestrator.telemetry_queries import query_recent_runs


class _FakeLedger:
    def __init__(self, docs):
        self._runs = _FakeContainer(docs)


class _FakeContainer:
    def __init__(self, docs):
        self._docs = docs
        self.last_query = None

    def query_items(self, query=None, parameters=None, **kw):
        self.last_query = query
        docs = self._docs

        async def _gen():
            # Mimic Cosmos TOP: honour the literal in the query text.
            cap = None
            if query and "TOP" in query:
                try:
                    cap = int(query.split("TOP", 1)[1].split()[0])
                except (ValueError, IndexError):
                    cap = None
            for d in (docs[:cap] if cap else docs):
                yield d

        return _gen()


def _docs(n: int, team: str = "team-cardiology"):
    """n runs, oldest first, so any correct impl must sort to return newest."""
    return [
        {
            "run_id": f"run-{i:04d}",
            "team_id": team,
            "status": "completed" if i % 2 else "awaiting_gate",
            "updated_at": f"2026-01-{(i % 28) + 1:02d}T00:00:{i % 60:02d}Z",
            "created_at": "2026-01-01T00:00:00Z",
            "total_cost_usd": 0.01,
            "total_tokens": 100,
        }
        for i in range(n)
    ]


@pytest.mark.asyncio
async def test_reports_total_not_just_page_size():
    """The core complaint: '50' must be distinguishable from 'only 50 exist'."""
    res = await query_recent_runs(_FakeLedger(_docs(214)), limit=50)
    assert res["count"] == 50, "page is capped at limit"
    assert res["total"] == 214, "total must reflect everything matching"
    assert res["total"] > res["count"], "UI needs both numbers to say '50 of 214'"


@pytest.mark.asyncio
async def test_offset_returns_the_next_page():
    all_docs = _docs(120)
    page1 = await query_recent_runs(_FakeLedger(all_docs), limit=50, offset=0)
    page2 = await query_recent_runs(_FakeLedger(all_docs), limit=50, offset=50)

    ids1 = [r["run_id"] for r in page1["items"]]
    ids2 = [r["run_id"] for r in page2["items"]]
    assert len(ids2) == 50
    assert not set(ids1) & set(ids2), "pages must not overlap"
    assert page2["offset"] == 50


@pytest.mark.asyncio
async def test_paging_covers_every_run_exactly_once():
    all_docs = _docs(130)
    seen: list[str] = []
    for off in range(0, 150, 50):
        page = await query_recent_runs(_FakeLedger(all_docs), limit=50, offset=off)
        seen += [r["run_id"] for r in page["items"]]
    assert len(seen) == 130
    assert len(set(seen)) == 130, "no duplicates across pages"


@pytest.mark.asyncio
async def test_last_page_is_partial_not_padded():
    res = await query_recent_runs(_FakeLedger(_docs(130)), limit=50, offset=100)
    assert res["count"] == 30
    assert res["total"] == 130


@pytest.mark.asyncio
async def test_offset_past_the_end_is_empty_not_an_error():
    res = await query_recent_runs(_FakeLedger(_docs(10)), limit=50, offset=500)
    assert res["items"] == []
    assert res["total"] == 10


@pytest.mark.asyncio
async def test_paging_preserves_newest_first_order():
    all_docs = _docs(120)
    page1 = await query_recent_runs(_FakeLedger(all_docs), limit=50, offset=0)
    page2 = await query_recent_runs(_FakeLedger(all_docs), limit=50, offset=50)
    stamps = [r["updated_at"] for r in page1["items"] + page2["items"]]
    assert stamps == sorted(stamps, reverse=True), "order must hold across pages"


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_matches_beyond_the_first_page():
    """Search must run server-side over the window, not over the visible page.

    Filtering in the browser would search 50 rows and silently miss matches
    that exist further down — an empty result that looks authoritative.
    """
    docs = _docs(200)
    docs[173]["run_id"] = "run-needle-xyz"
    res = await query_recent_runs(_FakeLedger(docs), limit=50, search="needle")
    assert [r["run_id"] for r in res["items"]] == ["run-needle-xyz"]
    assert res["total"] == 1


@pytest.mark.asyncio
async def test_search_is_case_insensitive():
    docs = _docs(20)
    docs[3]["run_id"] = "run-NEEDLE-1"
    res = await query_recent_runs(_FakeLedger(docs), limit=50, search="needle")
    assert res["total"] == 1


@pytest.mark.asyncio
async def test_search_matches_status_and_team():
    res = await query_recent_runs(_FakeLedger(_docs(40)), limit=100, search="awaiting_gate")
    assert res["total"] == 20
    assert all(r["status"] == "awaiting_gate" for r in res["items"])


@pytest.mark.asyncio
async def test_search_total_reflects_matches_not_corpus():
    docs = _docs(100)
    docs[5]["run_id"] = "run-unique-marker"
    res = await query_recent_runs(_FakeLedger(docs), limit=50, search="unique-marker")
    assert res["total"] == 1, "total must count matches, not the whole corpus"


@pytest.mark.asyncio
async def test_no_match_returns_empty_not_everything():
    res = await query_recent_runs(_FakeLedger(_docs(50)), limit=50, search="zzz-no-such-run")
    assert res["items"] == []
    assert res["total"] == 0


# ---------------------------------------------------------------------------
# Truncation honesty
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_total_is_independent_of_page_size():
    """The same corpus must report the same total at any limit.

    Caught on the live deployment: the scan window was sized `limit * 10`, so
    limit=5 reported total=50 while limit=200 reported the true 69, and
    `truncated` fired spuriously on small pages. A count that changes when you
    change the page size is not a count.
    """
    docs = _docs(69)
    small = await query_recent_runs(_FakeLedger(docs), limit=5)
    large = await query_recent_runs(_FakeLedger(docs), limit=200)
    assert small["total"] == large["total"] == 69
    assert small["truncated"] is False, "69 runs fit the window; nothing is truncated"


@pytest.mark.asyncio
async def test_truncated_does_not_fire_on_small_pages():
    docs = _docs(80)
    for lim in (1, 5, 10, 50):
        res = await query_recent_runs(_FakeLedger(docs), limit=lim)
        assert res["total"] == 80, f"total wrong at limit={lim}"
        assert res["truncated"] is False, f"spurious truncation at limit={lim}"


@pytest.mark.asyncio
async def test_truncated_is_false_when_everything_fits():
    res = await query_recent_runs(_FakeLedger(_docs(60)), limit=50)
    assert res["truncated"] is False, "60 runs fit inside the scan window"


@pytest.mark.asyncio
async def test_truncated_is_true_when_the_window_saturates():
    """When the window is full, `total` is a floor and must be labelled as such."""
    res = await query_recent_runs(_FakeLedger(_docs(5000)), limit=50)
    assert res["truncated"] is True
    assert res["total"] < 5000, "the window bounds the scan; total is not the archive"
