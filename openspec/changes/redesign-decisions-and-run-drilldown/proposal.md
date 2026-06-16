# Proposal: redesign /decisions and /runs as operator-grade surfaces

> **Status:** DRAFT (in progress, 2026-06-16)
> **Capability:** ledger-insights-ui (extends the dashboard's read surface)
> **Related:**
>   - `add-teaching-signal-feedback` (the write path this redesign exposes — TeachingSignalBar moves into the row-detail panel)
>   - `fix-decision-card-defensive-normalize` (this redesign keeps the same defensive normalize() at the boundary; extends it to StagePill which had the same lurking bug)
>   - `add-pipeline-eval-harness` / `customer-engagement/hca-agentic-sdlc-demo` skill (the SBM cardiology POC that surfaced the operator UX gaps)

## Why

The v0.7 dashboard renders the Decision Ledger as a 2-column card grid (`md:grid-cols-2`) and the runs index as a similar card grid. Both surfaces fall apart the moment the operator wants to **actually operate** from them:

1. **Cards-stacked-vertically isn't dense enough.** With 25 ledger entries from a single A/B comparison run (5 ambiguity classes × 5 model runs), the operator has to scroll 12+ screens to compare decisions across runs. Cards work for skim + sentiment, not for cross-run correlation.

2. **No actor + model + cost columns aligned.** The most-asked operator question — *"how much did this cost, which model produced it, who signed off?"* — requires reading three different positions inside each card. With a table, all three become a single horizontal scan.

3. **No filtering or sorting.** Every entry is visible, in fixed reverse-chronological order, regardless of whether the operator is debugging one run or comparing two. Filter-by-stage, sort-by-cost, search-rationale-text are all blocking gaps.

4. **No KPI summary above the data.** *"How many decisions, what % were autonomous, total spend, how many flagged"* are the four numbers a Solution Engineer cites in every customer conversation about the system. They exist nowhere on `/decisions`.

5. **Per-run drilldown is sparse.** `/runs/<id>` has 3 stat cards (Spend / Decisions / Created) and an event stream. It says nothing about *which model produced which artifact*, *how long each stage took*, *whether the architect output got truncated*. After running an A/B comparison, the operator has to grep run summaries on disk to answer those questions — the dashboard is mute.

6. **Stage display crashed on unknown stage names.** `StagePill`'s typed `Record<Stage, {label, abbr}>` lookup returned `undefined` for any stage the canonical map didn't know (`resolver`, `gate`, etc.) and crashed the whole page on `meta.abbr`. Same defense-in-depth gap as `fix-decision-card-defensive-normalize` — never render off `undefined.field`.

7. **Persistent runs were unreachable.** `/api/runs/{run_id}` only checked the in-process `_runs` dict; runs that live only in Cosmos (after a pod restart, or when seeded by an experiment harness) returned 404 even though `/api/runs` (the list) read them correctly. Click any historical run from `/runs` → 404. The two endpoints disagreed about what "run" meant.

8. **`/api/ledger/bundle` returned ENOENT in production.** `standards-bundles/` was missing from the UI's docker image — `.dockerignore` whitelisted only `apps/ledger-insights-ui` and `openspec`, and the Dockerfile never `COPY`'d the bundles. `/bundles` and `/changes` rendered but every rule-citation lookup crashed.

The cumulative effect: the dashboard *looked* right but couldn't actually be used to operate the system. The SBM cardiology POC made every gap visible because it was the first run with enough data to pressure-test the surface.

## What changes

### `/decisions` — table-first, with KPI strip and operator action panel

Add three new components and a view toggle:

1. **`DecisionsInsights`** — a 5-card KPI strip above the entries view:
   - Decisions count
   - Autonomy split (% agent vs % human)
   - PHI exposure (high / low / none)
   - Spend (total + avg per decision)
   - Teaching coverage (% of stage decisions that have at least one teaching signal pointing at them, plus flagged + paused-class counts)
   - Numbers derived in-memory from the same entries list as the table — no separate API call, KPIs always match the data.

2. **`DecisionTable`** — a sortable, filterable table:
   - Columns: Stage / Decision (truncated, with shortId + ambiguity_class chip + "↳ refers-to" chip) / Actor (icon + id) / Model / PHI (icon) / Cost / When / Signals
   - Sortable by created_at, cost, stage, actor (header click)
   - Filter bar with full-text search + stage / actor kind / PHI / runtime kind / has-feedback selects + active-filter count + Clear button
   - **Click any row to expand inline** — full Rationale, Provenance grid (entry id, run id, agent session, actor full, model, created_at, cost USD, PHI class), Classification grid (entry type, stage, runtime kind, ambiguity class, references_entry_id, feedback_kind, paused_class), Bundle citations as chips, Teaching signals against this entry (kind badge + actor + relativeTime + rationale), and the **TeachingSignalBar** for one-click 👍 / 👎 / Flag / Replay / Pause-class

3. **View toggle** Table (default) / Cards on `/decisions`, persisted in `localStorage["li.decisions.view"]`. Cards remain available for mobile / embedded contexts; table is the operating view.

### `/runs/<id>` — replace sparse stat cards with `RunSummaryPanel`

A single component that surfaces:

- KPI row: Spend / Tokens / Wall clock / Decisions (with derived ratios — cost per 1k tokens, tokens per second)
- **Stage durations** as horizontal proportional bars — instantly visible if any one stage dominates wall clock (e.g. assessor 96s of 411s = 23%)
- **Model routing** per stage — provider + model for ingest / assessor / architect / test_plan / codegen / review_scan / deliver. The most-asked operator question on an A/B run.
- **Output artifact sizes** — chars per artifact (architecture, test_plan, code, etc.). With a `⚠` flag when any field looks suspiciously truncated (under 1500 chars on a `*_chars` field), so the operator catches a regression of the `[:1200]` / `[:6000]` truncation footguns we removed in `feat(orchestrator): remove payload truncations`.
- **Experiment provenance** when present — namespace, model, source_run_dir, original_team_id. Set by the harness seeders so operators can tell live-pipeline runs apart from seeded historical artifacts.

### `/runs` index — model badge + tokens on each card

`RunCard` shows the model that produced the run as a compact mono-font badge (stripped of the `databricks-claude-` / `claude-` prefix), plus token count next to cost. Reads `total_cost_usd ?? cost_usd` so it works on both historical (legacy field) and current data.

### Defensive `StagePill` — never crash on unknown stage

Replace the typed `Record<Stage, ...>` lookup with a fallback that derives a Title-Case label and a 2-letter abbr from any string. Same defense-in-depth lesson as `fix-decision-card-defensive-normalize` — every renderer that touches user/upstream-supplied identifiers must have a non-crashing path.

### Sonner toasts on TeachingSignalBar

Replace the inline-div success/error chrome under the buttons with `toast.success` / `toast.error` / `toast.warning` calls — the `<Toaster>` was already in `app/layout.tsx`. Errors still surface inline inside the Flag / Pause `FormPanel`s where the rationale-required form lives.

### Durable run drilldown — `GET /api/runs/{run_id}` Cosmos fallback

In `apps/orchestrator/main.py::get_run`:

1. Check `_runs.get(run_id)` first (live runs in this pod).
2. On miss, call `_ledger.get_run(run_id)` against Cosmos.
3. Re-hydrate as `RunState` via `model_validate`; raw-dict last-resort if validation throws (so the UI doesn't 500 on a schema drift).
4. Otherwise raise 404.

This unifies what "run exists" means across the two endpoints without changing the in-memory hot path.

### Bundle assets in the UI image — Dockerfile + .dockerignore

Two single-line fixes:

- `.dockerignore` whitelist: `!standards-bundles` (and now `!apps/orchestrator` / `!packages/ledger-core` for the orchestrator's repo-root build context)
- `apps/ledger-insights-ui/Dockerfile`: `COPY --chown=nextjs:nodejs standards-bundles ./standards-bundles` in the runtime stage, paralleling the existing `openspec` copy.

`/api/ledger/bundle` now resolves `/app/standards-bundles/<dept>/<ver>/rules.yaml` at request time instead of returning ENOENT.

### Schema extension on `RunState` (frontend types only)

`apps/ledger-insights-ui/src/lib/types.ts::RunState` adds optional fields the orchestrator was already serializing but the type didn't surface:

- `total_cost_usd`, `total_tokens` (the canonical names; `cost_usd` kept as `@deprecated` alias)
- `stage_durations_seconds`, `wall_clock_seconds`
- `model_routing: Record<stage, { provider, model }>`
- `artifact_sizes: Record<artifact_name, char_count>`
- Experiment provenance: `namespace`, `model`, `model_slug`, `source_run_dir`, `original_team_id`

No backend change — the orchestrator already produces these on `model_dump()`, the UI was just not reading them.

## Impact

- **Unbreaking:** existing DecisionCard view still available via the toggle. Existing card-grid `/runs` index still rendered by `RunCard` (now with model badge added). No URL changes, no API contract changes besides the additive `get_run` fallback.
- **Breaking from a renderer-resilience standpoint:** any component that hard-coded `cost_usd` or `run.events.filter(...)` without `?? []` keeps working but should be migrated to `total_cost_usd ?? cost_usd` and `(run.events ?? []).filter(...)`. RunCard and RunSummaryPanel ship the migration.
- **Trust-building:** the panels show what the system actually did, not just that it did something. A customer asking "which model produced this code?" gets an answer in one click instead of a code dive.

## Verification

- `pnpm tsc --noEmit` clean on `apps/ledger-insights-ui`
- `pnpm build` clean — no new bundle warnings
- 100/100 orchestrator vitest pass (3 pre-existing Cosmos-throttling failures deselected — unrelated to this change)
- New tests: see `tasks.md` for the coverage list (covers fallback path on `get_run`, normalize-on-unknown-stage `StagePill` test, schema-extension type-test)
- Live deploy probe: `/api/runs/616d5fa8-74a1-4c0b-ad15-2629b9a854a4` returns 200 with `total_cost_usd=0.0837` (haiku-4-5-run-1). `/api/ledger/bundle` returns rules instead of `{error: "ENOENT..."}`. `/decisions` renders 25 SBM entries in table view with KPI strip, click-to-expand showing operator action row.

## Out of scope

- Replacing the AgentAssistant (still has its own assist-context payload reading)
- Authoritative auth on the operator action POSTs (still bearer-token; deferred to `add-cosmos-private-endpoint-v07` follow-on)
- Cross-run model A/B comparison view (next change — this one ships the per-run insights that comparison view will aggregate)
