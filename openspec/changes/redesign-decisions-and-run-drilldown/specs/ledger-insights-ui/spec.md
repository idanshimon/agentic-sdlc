# Spec delta: redesign-decisions-and-run-drilldown / ledger-insights-ui

## ADDED Requirements

### Requirement: `/decisions` MUST offer a table view as the default operating surface

The `/decisions` page MUST render a sortable, filterable, dense table of ledger entries as its default view. Users MUST be able to toggle between table and card views via a persistent UI control whose choice survives page navigation within the session (`localStorage["li.decisions.view"]`).

The table view MUST surface, at minimum, columns for: stage, decision text (truncated to 2 lines with shortId visible), actor (with kind icon distinguishing human/agent), model (with the `databricks-claude-` / `claude-` prefix stripped for legibility), PHI class, cost USD, relative time, and teaching-signal coverage indicator.

Sortable columns MUST include `created_at` (default descending), `cost_usd`, `stage`, and `actor`. Click on a header MUST toggle direction; click on a different header MUST switch to that key with a sensible default direction.

Click on a row MUST expand an inline detail panel below it, NOT navigate to a separate page. The detail panel MUST surface: full rationale (whitespace-preserved), provenance grid (entry_id, run_id, agent_session_id, actor full, model_used, created_at, cost_usd, phi_class), classification grid (entry_type, stage, runtime_kind, ambiguity_class, references_entry_id, feedback_kind, paused_class), bundle citations as chips, teaching signals against this entry (the inverted index of which other entries reference this one), and the operator action row (TeachingSignalBar).

#### Scenario: 25-entry ledger renders as table by default

- **GIVEN** the deployed `/decisions` page is loaded by an operator who has not previously toggled the view
- **AND** the ledger contains 25 stage_decision entries across 5 ambiguity classes × 5 model runs
- **WHEN** the page mounts
- **THEN** a 5-card KPI strip MUST render at the top showing decisions count, autonomy split, PHI exposure, spend, and teaching coverage
- **AND** a single table MUST render below the KPI strip with one row per entry
- **AND** the rows MUST be sorted newest-first by `created_at`
- **AND** no row MUST require horizontal scrolling at viewport widths ≥ 1024px

#### Scenario: filter combinations narrow the visible row set

- **GIVEN** the table is rendered with 25 entries
- **WHEN** the operator types `auth-policy` into the filter search input
- **AND** selects `databricks-claude-haiku-4-5` from the model filter
- **THEN** only entries whose decision text, rationale, ambiguity_class, OR model_used contains `auth-policy` AND whose model is `databricks-claude-haiku-4-5` MUST remain visible
- **AND** the row count footer MUST display the visible count and "of 25 total"
- **AND** a Clear button MUST appear with the active-filter count

#### Scenario: row expansion shows operator action row

- **GIVEN** the table has at least one row
- **WHEN** the operator clicks a row's expand chevron
- **THEN** an inline detail panel MUST render below the row
- **AND** the detail MUST contain a TeachingSignalBar with at least four buttons (👍 / 👎 / Flag / Replay) and a fifth (Pause autopilot) when the entry has an `ambiguity_class`
- **AND** clicking 👎 MUST POST `feedback_thumbs` with `feedback_kind: "thumbs_down"` to the ledger MCP
- **AND** a Sonner toast `"Recorded 👎"` MUST appear on success

### Requirement: `/decisions` MUST surface a 5-card KPI strip above the entries view

The KPI strip MUST display, at minimum:

1. **Decisions count** — total visible after filters
2. **Autonomy split** — % agent vs % human (excluding teaching-signal entries from the denominator since those are operator events, not pipeline decisions)
3. **PHI exposure** — count of `phi_class=high` and `phi_class=low` entries
4. **Spend** — total cost USD across visible stage_decisions, plus avg per decision
5. **Teaching coverage** — % of stage_decisions that have at least one teaching signal pointing at them via `references_entry_id`, plus counts of `decision_flagged` and `class_paused` entries

All KPI values MUST derive from the same in-memory entries list as the table — no separate API call. The KPIs MUST always match the data below them.

#### Scenario: autonomy split excludes teaching signals from denominator

- **GIVEN** the ledger contains 25 stage_decision entries (all with `actor.kind=human` because they're seeded operator gate decisions) plus 3 `feedback_thumbs` entries (`actor.kind=human`)
- **WHEN** the KPI strip is computed
- **THEN** the autonomy split MUST display `100% human · 0% agent` based on the 25 stage_decisions
- **AND** MUST NOT include the 3 teaching signals in the denominator

### Requirement: `/runs/<id>` MUST show stage durations, model routing, and artifact sizes

The per-run drilldown page MUST render a `RunSummaryPanel` that surfaces:

1. KPI row: spend, tokens, wall clock, decisions
2. **Stage durations** as horizontal proportional bars showing each stage's wall-clock seconds and percentage of total
3. **Model routing** per stage from `run.model_routing`, displayed as `<provider> · <model>` per row
4. **Artifact sizes** keyed by name (e.g. `architecture_chars`, `test_plan_chars`, `code_chars`), with a warning indicator on any `*_chars` field whose value is < 1500 (the lower-bound for a non-truncated output on a non-trivial PRD)
5. **Experiment provenance** when present — `namespace`, `model`, `model_slug`, `source_run_dir`, `original_team_id`

The panel MUST gracefully omit any section whose data is empty or missing — no broken empty states.

#### Scenario: SBM cardiology run drilldown shows model routing

- **GIVEN** a Cosmos-persisted run with `model_routing: { architect: { provider: "databricks", model: "databricks-claude-haiku-4-5" }, codegen: { provider: "databricks", model: "databricks-claude-haiku-4-5" } }`
- **WHEN** the operator navigates to `/runs/<that_run_id>`
- **THEN** the Model routing panel MUST render rows for `architect` and `codegen` showing the provider and model
- **AND** stages without routing entries MUST be omitted from the panel (NOT show as `—`)

#### Scenario: truncation regression catches itself

- **GIVEN** a hypothetical regression that re-introduces a `[:1200]` truncation on the architect output
- **WHEN** an A/B harness run produces `architect_chars: 1200`
- **AND** the operator drills into that run on `/runs/<id>`
- **THEN** the artifact_sizes panel MUST flag `architecture_chars: 1,200 ⚠` with a hover title indicating the value is suspiciously short

### Requirement: `/runs` index MUST show the model that produced each run

The `RunCard` component MUST render a model badge alongside the status badge, derived from `run.model` (set by harness seeders) or the first non-empty model in `run.model_routing` (set by the orchestrator). The badge MUST strip the `databricks-claude-` and `claude-` prefixes for legibility.

The card MUST also display token count next to cost when `run.total_tokens > 0`.

#### Scenario: A/B comparison index distinguishes haiku from sonnet runs at a glance

- **GIVEN** the `/runs` index renders 5 runs from an SBM cardiology A/B comparison
- **WHEN** the operator scans the cards
- **THEN** each card MUST display its model identifier (e.g. `haiku-4-5` or `sonnet-4-6`) without the operator opening any individual run

### Requirement: `StagePill` MUST never crash on unknown stage names

The `StagePill` component MUST render successfully for any string passed as `stage`, including stage names not in the canonical pipeline map (`ingest`, `assessor`, `architect`, `test_plan`, `codegen`, `review_scan`, `deliver`). For unknown stages, it MUST derive a Title-Case label and a 2-letter abbreviation from the input string. The component MUST NOT directly access `meta.label` or `meta.abbr` without a defined fallback.

#### Scenario: seeded resolver-stage entry renders without crashing /decisions

- **GIVEN** a ledger entry with `stage: "resolver"`
- **WHEN** the `/decisions` table renders the row
- **THEN** the StagePill MUST display label `"Resolver"` and abbreviation `"RE"`
- **AND** the page MUST NOT crash with `Cannot read properties of undefined (reading 'abbr')`

### Requirement: TeachingSignalBar MUST surface success/error via Sonner toasts

Each operator action button (👍 thumbs_up, 👎 thumbs_down, Flag, Replay, Pause-class) MUST trigger a Sonner toast on the mutation's `onSuccess` and `onError` callbacks. The toast text MUST describe the action taken (e.g. `"Decision flagged — findPrecedent will skip it next time"` for a flag success). Inline div-based success/error chrome that the toasts replace MUST be removed.

The Flag and Pause action panels — which require a rationale text input — MAY additionally surface their error state inline next to the input (since the user is still focused there).

#### Scenario: flag success removes form panel and shows toast

- **GIVEN** the operator has clicked Flag on a row, typed a rationale, and clicked Submit
- **WHEN** the mutation succeeds
- **THEN** the rationale input MUST clear
- **AND** the Flag form panel MUST collapse
- **AND** a Sonner toast `"Decision flagged — findPrecedent will skip it next time"` MUST appear

### Requirement: `GET /api/runs/{run_id}` MUST resolve from Cosmos when in-memory miss

The orchestrator's `get_run` endpoint MUST, on miss against the in-process `_runs` dict, fall back to `_ledger.get_run(run_id)` against the Cosmos `pipeline-runs` container before returning 404.

The Cosmos result MUST be re-hydrated as `RunState` via `model_validate()`. If validation fails, the endpoint MUST log a warning and return the raw dict so the UI does not 500. Only when both the in-memory check AND the Cosmos lookup return None MUST the endpoint return 404.

This unifies what "run exists" means across `GET /api/runs` (already Cosmos-aware via `query_recent_runs`) and `GET /api/runs/{run_id}` (previously in-memory only).

#### Scenario: historical run from Cosmos resolves after pod restart

- **GIVEN** a run exists in the Cosmos `pipeline-runs` container with `run_id="616d5fa8-74a1-4c0b-ad15-2629b9a854a4"` (the haiku-4-5-run-1 SBM run)
- **AND** the orchestrator pod has restarted, clearing the in-process `_runs` dict
- **WHEN** the operator clicks the row in `/runs`, navigating to `/runs/616d5fa8-74a1-4c0b-ad15-2629b9a854a4`
- **THEN** `GET /api/runs/616d5fa8-74a1-4c0b-ad15-2629b9a854a4` MUST return 200
- **AND** the response body MUST contain `total_cost_usd: 0.0837`

### Requirement: `standards-bundles/` MUST ship inside the deployed UI image

The `apps/ledger-insights-ui` Docker image MUST contain `standards-bundles/` at `/app/standards-bundles/` so that runtime API handlers (`/api/ledger/bundle`, `/bundles` page) can read `<dept>/<version>/rules.yaml` from disk.

The repo-root `.dockerignore` MUST whitelist `!standards-bundles`. The Dockerfile runtime stage MUST `COPY --chown=nextjs:nodejs standards-bundles ./standards-bundles`.

#### Scenario: bundle endpoint returns rules instead of ENOENT

- **GIVEN** the deployed UI image is built from this change
- **WHEN** an authenticated `POST /api/ledger/bundle` arrives with body `{"dept": "security", "version": "v0.1.0"}`
- **THEN** the response MUST contain a `rules` array (not an `error` field)
- **AND** the response MUST NOT contain `"ENOENT: no such file or directory"`
