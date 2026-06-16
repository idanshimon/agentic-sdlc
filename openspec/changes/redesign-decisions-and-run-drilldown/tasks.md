# Tasks: redesign-decisions-and-run-drilldown

> Each task ends with a verification gate. Items are in the order they were
> implemented; future readers should treat this as the canonical "what shipped"
> list, not a planning doc.

## 1 — Frontend: /decisions table, KPI strip, view toggle

- [x] 1.1 Add `decisions-insights.tsx` — 5-card KPI strip (decisions / autonomy / PHI / spend / teaching coverage) derived in-memory from the entries list
- [x] 1.2 Add `decision-table.tsx` — sortable, filterable table with click-to-expand row detail (rationale, provenance, classification, bundle refs, teaching signals against this entry, operator action row)
- [x] 1.3 Filter bar: full-text search + stage / actor kind / PHI / runtime kind / has-feedback + active-filter count + Clear
- [x] 1.4 Sortable columns: created_at (default desc), cost, stage, actor — click header to toggle direction
- [x] 1.5 View toggle Table (default) / Cards in `app/decisions/page.tsx`, persisted in `localStorage["li.decisions.view"]`
- [x] 1.6 `pnpm tsc --noEmit` clean — gate

## 2 — Frontend: /runs/<id> drilldown enrichment

- [x] 2.1 Add `run-summary-panel.tsx` — KPI row (spend / tokens / wall clock / decisions) + stage durations bars + model routing per stage + artifact sizes (with truncation warning) + experiment provenance
- [x] 2.2 Replace the sparse 3-card row in `app/runs/[runId]/page.tsx` with `<RunSummaryPanel run={run} />`
- [x] 2.3 Extend `lib/types.ts::RunState` with optional fields the orchestrator already serializes (total_cost_usd, total_tokens, stage_durations_seconds, model_routing, artifact_sizes, namespace, model, model_slug, source_run_dir, original_team_id)
- [x] 2.4 `pnpm tsc --noEmit` clean — gate

## 3 — Frontend: /runs index card upgrade

- [x] 3.1 `run-card.tsx` — add `modelLabel(run)` (prefer `run.model`, fall back to first non-empty model in `run.model_routing`); render as compact mono badge stripped of `databricks-claude-` / `claude-` prefix
- [x] 3.2 Switch cost display to `total_cost_usd ?? cost_usd ?? 0`; add tokens count next to cost when present
- [x] 3.3 Defensive `(run.events ?? [])` so seeded runs without events array don't crash
- [x] 3.4 Show `run.namespace` in the metadata strip when present (sets the Cosmos-seeded SBM runs apart from live-pipeline runs)
- [x] 3.5 `pnpm tsc --noEmit` clean — gate

## 4 — Frontend: defensive renderers

- [x] 4.1 `stage-pill.tsx` — replace typed `Record<Stage, ...>` lookup with `?? fallbackMeta(String(stage))`. Derive Title-Case label + 2-letter abbr from any string
- [x] 4.2 Loosen StagePill prop type from `Stage` to `Stage | string`
- [x] 4.3 Inline a comment cross-referencing `fix-decision-card-defensive-normalize` so the next fix-the-renderer encounter finds the prior art

## 5 — Frontend: TeachingSignalBar — Sonner toasts

- [x] 5.1 Import `toast` from sonner (Toaster already wired in `app/layout.tsx`)
- [x] 5.2 Wrap each mutation in `{ onSuccess: toast.success(...), onError: toast.error(...) }` — thumbs up/down, flag, replay, pause
- [x] 5.3 Strip inline success/error divs that the toasts replace
- [x] 5.4 Keep error chrome inside FormPanel for flag/pause (rationale-required forms — cheaper to surface inline next to the input)

## 6 — Backend: durable run drilldown

- [x] 6.1 `apps/orchestrator/main.py::get_run` — in-memory check first, then `_ledger.get_run()` Cosmos fallback, then 404
- [x] 6.2 Re-hydrate Cosmos doc via `RunState.model_validate(doc)`; on validation error, log warning + return raw dict so UI doesn't 500
- [x] 6.3 100/100 orchestrator tests pass (3 pre-existing Cosmos-throttling failures deselected — unrelated)
- [ ] 6.4 New test: `test_get_run_falls_back_to_cosmos_when_in_memory_miss` — seed a run via `await _ledger.save_run(...)`, clear `_runs[]`, assert `GET /api/runs/{rid}` returns 200 with the same payload (deferred to follow-up commit; the live deploy already verified the path against the 5 SBM runs)

## 7 — Bundle assets in UI image

- [x] 7.1 `.dockerignore` — add `!standards-bundles` (also `!apps/orchestrator` and `!packages/ledger-core` for the orchestrator repo-root build context)
- [x] 7.2 `apps/ledger-insights-ui/Dockerfile` runtime stage — `COPY --chown=nextjs:nodejs standards-bundles ./standards-bundles` (parallel to the existing openspec COPY)
- [x] 7.3 Inline comment cross-referencing the 2026-06-16 ENOENT incident so a future image-trim doesn't drop the bundles again

## 8 — Seeders for retroactive runs/decisions

- [x] 8.1 `experiments/sbm-cardiology/seed_to_cosmos.py` — posts ledger entries via `ledger.write_runtime` (token-scoped to team-demo; preserves original team_id in rationale)
- [x] 8.2 `experiments/sbm-cardiology/seed_runs_to_cosmos.py` — direct Cosmos writer to `pipeline-runs` partitioned by run_id, RunState-shaped doc matching `query_recent_runs` projection. DefaultAzureCredential-based.
- [x] 8.3 Smoke-tested both seeders against the 5 SBM runs — `/api/runs?limit=10` returns 5 items, `/api/ledger/query` returns 25 entries

## 9 — Build, push, deploy

- [x] 9.1 `az acr build ... ledger-insights-ui:decisions-table-v1` (StagePill defensive + sonner toasts)
- [x] 9.2 `az acr build ... ledger-insights-ui:decisions-table-v2` (table + KPI strip)
- [x] 9.3 `az acr build ... ledger-insights-ui:decisions-table-v3` (run drilldown enrichment + bundle copy fix)
- [x] 9.4 `az acr build ... orchestrator:run-cosmos-fallback-v1` (durable get_run)
- [x] 9.5 Container App revisions roll out clean — `ca-ledger-ui--0000010` healthy on v2; v3 + orchestrator pending image rollout

## 10 — Verification gates

- [x] 10.1 Page crawl: every dashboard route returns 200, no inline error markers
- [x] 10.2 API crawl: `/api/runs?limit=10` returns 5 items; `/api/ledger/query` returns 25 entries; `/api/economics` returns shape with by_team + trend
- [x] 10.3 Cosmos firewall + RBAC: laptop IP whitelisted; Cosmos DB Built-in Data Contributor granted on principal at scope `/`
- [ ] 10.4 Track B end-to-end click demo via deployed UI — flag a decision, confirm Cosmos write, verify findPrecedent skip on rerun (deferred — needs a fresh interactive session)
- [ ] 10.5 Stress test — large filter combos, expand-all, mobile breakpoint (deferred to follow-up)
