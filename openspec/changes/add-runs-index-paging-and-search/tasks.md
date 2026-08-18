# Tasks: add-runs-index-paging-and-search

**Test target:** `apps/orchestrator/tests/test_runs_pagination.py`.
Run with `.venv/bin/python -m pytest apps/orchestrator/tests/ -q`.

## Phase 0 — Establish what was actually broken

- [x] 0.1 Reproduce from the operator's view: the footer reads `Showing 50 runs` with no pager and no search.
- [x] 0.2 Trace the ceiling: `/api/runs` accepted `limit` but no `offset`, so run 51 was unreachable by any means.
- [x] 0.3 Trace the count: the footer rendered `runs.length`, the length of the fetched page. `visibleCount !== runs.length` was therefore false and a bare `50` was printed whether the container held 50 or 214.
- [x] 0.4 Separate this from the bug that WAS fixed. `SELECT TOP {limit}` with no `ORDER BY` made the newest run structurally unreachable; the over-fetch/sort/trim fix is correct and is preserved.
- [x] 0.5 Find the gap that fix left: its comment claims `truncated` "is reported so the caller can tell 'these are the newest N' from 'this is everything'", but no such value was ever computed or returned. Documented intent, missing mechanism.

## Phase 1 — Backend

- [x] 1.1 Return an envelope: `{items, count, total, offset, limit, truncated}`.
- [x] 1.2 `offset` — slice after sorting, so paging cannot reorder or skip.
- [x] 1.3 `search` — server-side over `run_id`, `team_id`, `status`, `mode`, `current_stage`, `model`, `namespace`, applied after the sort so paging stays stable.
- [x] 1.4 `total` = matches within the window; `truncated` = window saturated, so `total` is a floor.
- [x] 1.5 Thread `offset` and `search` through `/api/runs`; return the envelope on the no-ledger path too.

## Phase 2 — Tests

- [x] 2.1 Paging: no overlap, full coverage, partial last page, offset past the end is empty not an error, order holds across boundaries.
- [x] 2.2 Search: **finds a match planted at index 173 that page one cannot see**; case-insensitive; matches status/team; `total` counts matches not the corpus; no-match returns empty rather than everything.
- [x] 2.3 Truncation: false when everything fits, true when the window saturates.
- [x] 2.4 13/13 green.

## Phase 3 — Frontend

- [x] 3.1 `useRuns(params)` takes limit/offset/search; params in the query key so a page change refetches; `placeholderData` keeps the previous page visible instead of flashing empty.
- [x] 3.2 `listRuns` builds the query string; demo mode filters and pages client-side to match the server contract so the footer stays truthful there too.
- [x] 3.3 Debounced search box (300ms), resetting to page 1 on a new query.
- [x] 3.4 Footer reads `Showing 1–50 of 214`, renders `214+` when truncated, and says the archive holds more.
- [x] 3.5 Prev/Next pager with page N of M.
- [x] 3.6 **Bug caught while wiring:** `runs.length === 0` rendered the "No runs yet — start a run" onboarding state, which would also have shown for a search that simply matched nothing. Empty-result and empty-corpus are now distinct.

## Phase 4 — Verify

- [x] 4.1 Fix the caller my return-type change broke: `test_runs_empty_when_ledger_disabled` asserted the exact old dict. Rewritten against the envelope — a shape assertion, not a behaviour regression.
- [x] 4.2 `npx tsc --noEmit` clean; `pnpm build` passes, all 30 routes.
- [x] 4.3 653 tests pass, zero failures. `enforce_bundles.py` clean.
- [ ] 4.4 Deploy and confirm on the live page. A green build is not evidence that the screen is right — the whole point of this change is what the operator sees.
