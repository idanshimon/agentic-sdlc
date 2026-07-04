# Proposal: admin run/ledger deletion + honest decision attribution

> **Status:** DRAFT (2026-07-04) · shipped to ca-orchestrator-vnet + ca-ledger-ui-vnet
> **Capability:** ledger (admin lifecycle endpoints + attribution correctness)
> **Related:**
>   - `add-graduated-autonomy-tier2` (the human-vs-agent split this makes real; without honest `confidence_source` the autonomy numbers read 0)
>   - `add-autonomy-control-surface` (consumes the corrected attribution — the Autonomy page's whole premise depends on it)
>   - `fix-decisions-page-empty-on-cold-load` (sibling ledger-read fix)

## Why

Three defects surfaced while cleaning the demo environment and building the Autonomy surface. All three block an honest autonomy story:

1. **No way to delete a run.** The `/runs` dashboard accumulated ~29 demo-seed / zombie / test runs with no removal path. Cosmos `publicNetworkAccess` is Disabled (private endpoints only), so the docs could not be purged from outside the VNET. The orchestrator is the one component inside the VNET.

2. **No way to clear stale ledger decisions.** The Decisions page (Ledger MCP, token-scoped to one team) showed only stale June seed entries. There was no endpoint to purge a team partition's decisions so the page could show a clean, current set.

3. **`/approve` silently dropped `confidence_source`.** The human-facing approve handler hard-omitted the field when writing the `LedgerEntry`, so a decision POSTed with `confidence_source=autopilot` was recorded as `human`. The Decisions autonomy-split tile read `0% agent · 0% human` and every human decision showed a bot icon. The entire human-vs-agent governance story was unattributable.

## What changes

Orchestrator (inside the VNET, holds Cosmos RBAC):

```
DELETE /api/admin/runs/{run_id}       -> hard-delete a pipeline-runs doc
                                         (ledger entries in the separate
                                          decision-ledger container untouched)
DELETE /api/admin/ledger/{team_id}    -> delete all decision-ledger entries
                                         for one team partition (scoped, never
                                         cross-team); returns {found, deleted}
```

- New `LedgerClient.delete_run(run_id)` in ledger-core (mirrors `delete_entry`).
- `admin_delete_run` also drops in-memory handles (`_runs`, `_queues`, `_gate_events`, `_gate_started`, `_prd_cache`) idempotently.
- `POST /api/runs/{id}/approve` now passes `confidence_source=decision.confidence_source` into the `LedgerEntry` (defaults to `human` on the model when omitted).

UI (`ledger-insights-ui`):
- `decision-table.tsx` and `decisions-insights.tsx` derive actor kind from `confidence_source` (`autopilot` → agent, else human) instead of hard-defaulting to `agent`.

## Why this design

- **Delete lives on the orchestrator, not a direct-Cosmos admin script.** Private-network posture means only the in-VNET orchestrator can reach Cosmos. Adding the endpoint (mirroring `admin_mark_failed`) is the sanctioned path and gives the reference app a reusable capability.
- **Run-delete and ledger-clear are separate endpoints on separate containers.** A run doc and its decision entries live in different containers with different partition keys; conflating them would risk deleting audit records when only clearing the runs table.
- **`confidence_source` defaults to `human`.** The operator-decision case is the common one; an omitted field should attribute to the human, never silently to the agent.

## Why we did NOT do the alternative

- **Purge via a local `az cosmosdb` script** — rejected: Cosmos is private-endpoint-only; a laptop script cannot reach it. The endpoint is the only route.
- **Fix attribution only in the row normalizer** — rejected initially, then caught: the split *tile* computes independently on un-normalized entries, so both the table and the tile needed the `confidence_source` derivation. Fixing one left the tile at 0/0.
- **Add a structured `actor` object to every ledger write** — deferred: larger schema change; deriving kind from the existing `confidence_source` field is backward-compatible and sufficient.

## Out of scope

- Auth on the admin endpoints (VNET-internal; EasyAuth deferred).
- Bulk/multi-team ledger clear (single-team-partition scoped by design).
- A structured `actor {kind,id}` object on ledger entries (derive-from-confidence_source is the compatible fix).

## Receipts

- Commits: `73d7de0` (run-delete + confidence_source), `bea8910` (clear-ledger + actor-kind)
- Images: `orchestrator:admin-delete-run-*`, `orchestrator:clear-ledger-*`, `ledger-insights-ui:autonomy-split-fix-*`
- Verified: DELETE 200 → GET 404 (real Cosmos delete); Decisions split reads 55% agent · 45% human · 11/9; 107 stale seed entries purged
- Tests: import-smoke green per build
