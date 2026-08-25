# Paging, search and honest counts on the runs index

> **Status:** PROPOSED (filed 2026-08-18)
> **Capability:** runs-index (MODIFIED)

## Why

The runs index rendered `Showing 50 runs` with no pager, no search, and no way
to reach run 51. Three separate problems hid behind that one line.

**1. The page size was a hard ceiling.** `/api/runs` accepted `limit` but no
`offset`. Whatever was not in the newest 50 was unreachable from the UI at any
price — not by scrolling, not by filtering, not by a URL parameter.

**2. The count could not be interpreted.** The footer rendered
`runs.length` — the length of the *fetched page*. When the container held 214
runs it said `50`, and when it held exactly 50 it also said `50`. An operator
had no way to tell "you are seeing a slice" from "this is everything", which is
the same class of defect as an empty view that renders as healthy.

**3. Search only ever saw the current page.** The existing filter bar narrows
the rows already in the browser. Searching for a run that sat at position 173
returned nothing, and returned it *confidently* — an empty result that looks
authoritative is worse than an error, because the operator concludes the run
does not exist.

There is prior art for the honest version in this same UI: the decisions graph
already says "Showing the 1,000 most-recent decisions — the ledger holds more.
This map is a recent-history view, not the complete archive." The runs index
simply never got the same treatment.

### What was already fixed, and what was not

A previous change fixed a genuinely serious bug in this code path: the query ran
`SELECT TOP {limit}` with **no `ORDER BY`**, so Cosmos applied `TOP` before any
sort and returned an arbitrary window. Once the container exceeded `limit`, the
newest run became structurally unreachable — fetchable by ID, absent from the
list. That fix (over-fetch a bounded window, sort, then trim) is correct and is
preserved here.

But its own comment states that `truncated` "is reported so the caller can tell
'these are the newest N' from 'this is everything'", and **no such value was
ever computed or returned**. The function returned a bare list. The intent was
documented and the mechanism was missing — the same shape of gap this repository
exists to catch.

## What changes

`query_recent_runs` returns an envelope instead of a list:

```
{"items", "count", "total", "offset", "limit", "truncated"}
```

- **`offset`** — real paging. `/api/runs?offset=50` returns the next page.
- **`search`** — free-text match over `run_id`, `team_id`, `status`, `mode`,
  `current_stage`, `model`, `namespace`, applied **server-side over the scanned
  window**, not over the current page.
- **`total`** — how many runs match the filters, so the footer can say
  "Showing 1–50 of 214".
- **`truncated`** — `true` when the scan window saturated, meaning `total` is a
  floor rather than the true count. The UI renders `214+` and says the archive
  holds more, rather than presenting a bounded scan as a complete census.

The UI gains a debounced search box and a Prev/Next pager, and the footer
reports the range against the total.

## Honesty constraints

- **Search is server-side by construction.** Client-side filtering would search
  only the fetched page and report a confident empty result for a run that
  exists two pages down.
- **`total` is never presented as complete when the window saturated.** A
  bounded scan reports a floor and says so.
- **An empty search result is distinguished from an empty corpus.** Previously
  `runs.length === 0` rendered "No runs yet — start a run", which would have
  been shown for a search that simply matched nothing.
- **Paging does not reorder.** Sorting happens before the page is cut, so a run
  cannot appear on two pages or be skipped between them.

## What this does NOT do

- It does not add cursor-based paging. Offset paging over a bounded, sorted
  window is sufficient at this scale and keeps a single query per page.
- It does not raise the scan-window cap. That bound is what keeps this one
  query rather than an unbounded scan as the container grows; `truncated`
  exists precisely because the bound is real.
- It does not change the filter bar, which still narrows the current page.

## Verification

- Paging: pages do not overlap, cover every run exactly once, the last page is
  partial rather than padded, an offset past the end is empty rather than an
  error, and newest-first order holds across page boundaries.
- Search: matches a run at position 173 that page one cannot see; is
  case-insensitive; `total` reflects matches rather than the corpus; a
  non-matching query returns empty rather than everything.
- Truncation: `false` when everything fits, `true` when the window saturates.
- The pre-existing ordering regression tests continue to pass.
