# Proposal: ship operator-grade pipeline workflow (gates, observability, audit, durability)

> **Status:** SHIPPED 2026-06-16 (this is a retroactive openspec for the work
> covered by commits ce65195, 70f6530, c43a7db, 3d0af6c, 7aa5d99, b3e0068,
> 6bc3621, 946cf03, 1a74382, f441c00, 95c8473 — all on origin/main).
> **Capability:** orchestrator + ledger-insights-ui
> **Related:**
>   - `add-multi-persona-prompt-library` (sibling change shipped same session; covers prompts/* + chain pinning)
>   - `redesign-decisions-and-run-drilldown` (predecessor; this change builds on the table+filter+KPI primitives)
>   - `add-teaching-signal-feedback` (this change preserves the existing TeachingSignalBar surface)

## Why

After `add-multi-persona-prompt-library` shipped the prompt-governance loop end-to-end, the operator-facing dashboard still had 11 friction points that blocked a real live demo. Caught operator-side via screenshot and verbal feedback throughout the 2026-06-16 session:

1. **Per-card `/approve` returned HTTP 500** — `LedgerEntry` was missing the `entry_type` field that `ledger-core.write_entry()` reads on line 1, causing AttributeError on every operator decision. Caught live; fix: default `entry_type: str = "runtime"`.

2. **Resolver gate "could not parse gating card payload" + HTTP 422 on Approve** — three-bug stack: UI sent `{decision, rationale}` but backend expects pydantic `GateDecision` shape; event matcher used `(assessor, awaiting_gate)` but orchestrator emits `(resolver, gate_open)`; no `finalize` call after per-card approve (orchestrator requires explicit close for resolver gate).

3. **Sample PRDs returned 500 on `/samples/<file>.md`** — Next.js standalone static-file bug; 2 of 4 markdown files served 500 with valid headers. Worked around with `/api/samples/[file]/route.ts` server-side `fs.readFile` bypass.

4. **Operator couldn't see live pipeline progress** — `useRunStream` opened the SSE connection but didn't invalidate the React Query cache on each event, so stage pills and status badges lagged 3 seconds behind every transition. Also events from polling + SSE rendered duplicated (no dedup key).

5. **Operator missed the gate** — single non-sticky gate card scrolled off-screen as soon as the operator looked at the event stream below. No visual ping that the pipeline needed them.

6. **Design Review (Gate 2) had no operator surface** — only the resolver gate had a custom UI component. Runs sitting at `design_review` showed "awaiting_gate" with no buttons. Run `404b4fc1` was stuck there with no way to advance from the dashboard.

7. **Design Review approve returned HTTP 409** — orchestrator's audit-safety guard rejected any `/approve` with a `card_id` once the resolver gate was closed. The new `DesignReviewGate` component sent a synthetic `card_id` to satisfy pydantic schema, triggering the guard for legitimate gate-level approvals.

8. **Decision pages showed no prompt attribution** — Phase 2.6 pinned `prompt_resolution_path` on every `LedgerEntry` in Cosmos, but the UI rendered none of it. `grep prompt_resolution_path` across the frontend returned zero hits before this change. Operator had no way to answer "which prompt produced this decision?" without curling Cosmos.

9. **Run artifacts rendered as plain `<pre>` blocks** — Architecture / Test plan / Code tabs showed raw text with no line numbers, no syntax color, no copy/download. CodeGen outputs of 200-400 lines pushed the rest of the page off-screen.

10. **8 zombie "running" runs on `/runs`** — orchestrator only called `_ledger.save_run()` in its `finally` block, so every pod death between submit and completion (revision rollover, OOM, scale-to-zero idle eviction) left runs at the ingest snapshot. The list showed 8 rows stuck at `running · 0 dec · $0.0000` for hours.

11. **`/api/economics` returned 404** — the `/economics` page existed and was wired but the API route was missing. Page rendered empty charts + "fetch error" toast.

## What changes

### Orchestrator API (`apps/orchestrator/main.py` + `models.py`)

- **`LedgerEntry.entry_type: str = "runtime"`** — schema-drift surgical fix; documented in docstring to prevent regression.
- **`LedgerEntry.prompt_resolution_path: Optional[list[dict]] = None`** — every ledger entry now pins the full prompt chain.
- **`RunState.prompt_chain_by_stage: dict[str, list[dict]]`** — per-run chain map, populated by each wired stage.
- **`_push(run_id, ev)` calls `_ledger.save_run(run)` on every event** — durable persistence so pod restarts don't zombie runs. Failure-tolerant (log + continue).
- **`POST /api/runs/{run_id}/finalize`** — explicit gate close for resolver (UI must call after last per-card approve).
- **`GET /api/runs/{run_id}/ledger`** — proxy endpoint returning ledger entries written for a run, bypassing ledger-mcp's per-token RBAC.
- **`POST /api/admin/runs/{run_id}/mark_failed`** — one-off cleanup endpoint for pre-fix zombies (NOT permanent admin surface; v1.0 needs RBAC).
- **`approve()` is-gate-level detection extended** — accepts `card_id=None` OR `decision.gate != "resolver"` for gate-level approvals; preserves audit-safety invariant for resolver per-card path.

### UI components (`apps/ledger-insights-ui/src/`)

- **`/runs/<id>` sticky "needs your attention" banner** — pinned to viewport top when `status === "awaiting_gate"`, with pulsing dot + "Jump to gate ↓" smooth-scroll button.
- **`useRunStream` invalidates React Query on every SSE event + dedups by `(stage, status, ts)` + auto-reconnects on revision-rollover drops.**
- **`<ResolverGate>` rewritten** — fixed event matcher, per-card approve loop + finalize call, per-card "Use this" buttons for each option (operator can override recommendation per-card).
- **`<DesignReviewGate>` (new)** — whole-stage Approve/Reject buttons + collapsible architecture preview inline. Page routes to it when `current_stage === "design_review"`.
- **`<PromptChainBadge>` (new)** — 3 render variants (inline / card / full); renders on every `DecisionCard` + `decision-table` drilldown; click → `/prompts` catalog.
- **`<ArtifactView>` rewritten** — line numbers, Copy/Download buttons, light syntax color (Python keywords purple, strings green, decorators orange, markdown headers blue, comments italic grey), collapse-to-200-lines for long output.
- **`/prompts` page rewritten** — replaces legacy localStorage-seed view with live catalog browse: KPI strip, persona+stage+scope filters, sortable table, drawer with full template + version history, "Edit + open PR" deep-link to GitHub web editor.
- **`/api/prompts/catalog` + `/api/prompts/{prompt_id}` orchestrator endpoints** — surface the lazy-loaded `PromptCatalog` for the UI.
- **`/api/economics` Next.js route (new)** — aggregates ledger entries via `lib/economics` pure functions, returns `{summary, by_team, trend, sample_size, limit_applied}`. Source data fetched from orchestrator's `/api/telemetry/decisions`.
- **`/decisions` Team filter** — distinct-teams derivation + Select dropdown + filter predicate; completes the multi-team partitioning UX (`/runs/new` + `/runs` already had team scoping).

### Tests

- `test_approve_entry_type_drift.py` — 3 cases on the schema-drift fix
- `test_prompt_chain_in_ledger.py` — 3 cases on chain pinning
- `test_run_ledger_endpoint.py` — 3 cases on `/api/runs/{id}/ledger`
- `test_prompt_catalog_endpoints.py` — 5 cases on `/api/prompts/*`
- `test_design_review_approve.py` — 2 cases (positive + counter-test preserving audit-safety invariant)

137 / 137 orchestrator tests pass (was 105 at session start, +32 new across all phases). UI `pnpm tsc --noEmit` clean throughout.

## Impact

- **Affected capabilities:** orchestrator-pipeline-workflow, ledger-decision-audit, ledger-insights-ui-runs, ledger-insights-ui-decisions, ledger-insights-ui-economics, ledger-insights-ui-prompts
- **No breaking changes** — every API addition is additive; the `entry_type` schema fix preserves existing reads (default `"runtime"` is what every pre-fix entry already was implicitly).
- **No customer-name leakage** — all changes ship customer-neutral; only `cardiology` as the seeded team_id, which is a generic specialty not a customer.
- **Cost impact:** +~$0.001/run from per-event Cosmos writes (~30 events/run × $0.000033/write). Future hardening should debounce to one write per 500ms.
- **Deploy cadence:** 21 ACR builds + container app revisions this session. Per-event persistence (Phase 6.1) now prevents the revision-rollover zombie pattern from recurring.

## Out of scope

- **RBAC on admin endpoints** — `/api/admin/runs/{id}/mark_failed` is one-off; v1.0 needs proper team-scoped admin.
- **Hot-reload prompts** — every prompt change is still a versioned image tag; auditable; hot-reload deferred.
- **Per-event-save debounce** — correctness wins over cost during demo posture; production-scale should batch 6x.
- **Run state migration** — pre-Phase-6.1 zombies stayed zombie until cleaned via admin endpoint; no retroactive replay.
- **Cosmos private endpoint flip** — `add-cosmos-private-endpoint-v07` is the durable fix for the demo posture where Cosmos firewall has `0.0.0.0` open; separate change.
