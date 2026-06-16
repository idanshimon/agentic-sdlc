# Tasks: ship-operator-grade-pipeline-workflow

> **Status:** 100% shipped in commits ce65195 → 95c8473 (2026-06-16).
> Retroactive openspec capturing the as-built shape.

## 1 — Schema-drift fixes (the foundation)

- [x] 1.1 `LedgerEntry.entry_type: str = "runtime"` default with rationale docstring  *(commit ce65195)*
- [x] 1.2 `test_approve_entry_type_drift.py` with 3 regression cases  *(commit ce65195)*
- [x] 1.3 Verify per-card `/approve` returns 200 (was 500)  *(verified run `0c361815`)*

## 2 — Resolver gate end-to-end fix

- [x] 2.1 Event matcher accepts both `(resolver, gate_open)` and legacy `(assessor, awaiting_gate)` shapes  *(commit c43a7db)*
- [x] 2.2 Approve sends pydantic `GateDecision` shape (per-card loop)  *(commit c43a7db)*
- [x] 2.3 `finalizeGate()` call after last per-card approve  *(commit c43a7db)*
- [x] 2.4 Per-card "Use this" buttons on every option in expanded view  *(commit c43a7db)*
- [x] 2.5 Live verification: run `404b4fc1` (5 cards approved + chain pinned in ledger)  *(verified 2026-06-16)*

## 3 — Sample PRD 500 workaround

- [x] 3.1 `/api/samples/[file]/route.ts` server-side `fs.readFile`  *(commit ea2b62e)*
- [x] 3.2 `/runs/new` cards routed to `/api/samples/x.md` URLs  *(commit ea2b62e)*

## 4 — Live SSE + observability polish

- [x] 4.1 `useRunStream` invalidates React Query on every event  *(commit 70f6530)*
- [x] 4.2 Composite `(stage, status, ts)` dedup in hook + page useMemo  *(commit 70f6530)*
- [x] 4.3 SSE reconnect on revision-swap drops (5s gate)  *(commit 70f6530)*
- [x] 4.4 Sticky "needs your attention" banner with smooth-scroll  *(commit 70f6530)*

## 4.1 — DesignReviewGate (Gate 2)

- [x] 4.1.1 `DesignReviewGate` component with Approve/Reject buttons + collapsible architecture preview  *(commit 3d0af6c)*
- [x] 4.1.2 Page routes to it when `current_stage === "design_review"`  *(commit 3d0af6c)*
- [x] 4.1.3 Backend `/approve` is-gate-level detection: `card_id is None` OR `decision.gate != "resolver"`  *(commit 7aa5d99)*
- [x] 4.1.4 `test_design_review_approve.py` with positive + counter-test (audit-safety invariant)  *(commit 7aa5d99)*
- [x] 4.1.5 Live verification: run `404b4fc1` cleared design_review and progressed through pipeline  *(verified 2026-06-16)*

## 5 — Prompt chain visible on every decision

- [x] 5.1 `LedgerEntry.prompt_resolution_path` field on UI type  *(commit 6bc3621)*
- [x] 5.2 `normalize()` preserves chain through defensive pipeline (both `decision-card.tsx` and `decision-table.tsx`)  *(commit 6bc3621)*
- [x] 5.3 `<PromptChainBadge>` component with 3 render variants  *(commit 6bc3621)*
- [x] 5.4 Renders on every `DecisionCard` (card variant) + drilldown row (full variant)  *(commit 6bc3621)*

## 6 — Operator-grade artifact viewer

- [x] 6.1 Line-numbered table layout (left-aligned tabular numbers, right-aligned content)  *(commit b3e0068)*
- [x] 6.2 Copy + Download buttons with `navigator.clipboard.writeText` and Blob download  *(commit b3e0068)*
- [x] 6.3 Light syntax color via regex tokenizer (no shiki/prism dependency)  *(commit b3e0068)*
- [x] 6.4 Collapse-to-200-lines with "Show all N lines" toggle  *(commit b3e0068)*

## 6.1 — Per-event Cosmos persistence (no more zombies)

- [x] 6.1.1 `_push()` calls `_ledger.save_run(run)` on every non-sentinel event  *(commit 946cf03)*
- [x] 6.1.2 Failure-tolerant: log warning, continue running pipeline  *(commit 946cf03)*
- [x] 6.1.3 Live verification: fresh run `9c3836ed` shows `events > 0` within 6 seconds of submit  *(verified 2026-06-16)*

## 6.2 — Zombie cleanup endpoint

- [x] 6.2.1 `POST /api/admin/runs/{run_id}/mark_failed` reading from Cosmos + flipping status  *(commit 1a74382)*
- [x] 6.2.2 Synthetic StageEvent appended for audit trail of cleanup  *(commit 1a74382)*
- [x] 6.2.3 Live verification: 8/8 zombies marked failed cleanly  *(verified 2026-06-16)*

## 7 — Economics page wired to real data

- [x] 7.1 Next.js API route `/api/economics?limit=N`  *(commit f441c00)*
- [x] 7.2 Fetches from orchestrator's `/api/telemetry/decisions`  *(commit f441c00)*
- [x] 7.3 Aggregates via `lib/economics` pure functions  *(commit f441c00 — reuses existing `summarize`, `summarizeByTeam`, `trendByDay`)*
- [x] 7.4 Returns shape page expects: `{summary, by_team, trend, sample_size, limit_applied}`  *(commit f441c00)*
- [x] 7.5 Live verification: 56 real decisions aggregated, 2 teams visible (cardiology + team-demo), real autonomy ratio  *(verified 2026-06-16)*

## 8 — Multi-team decisions filter

- [x] 8.1 `Filters.team_id` field + `DEFAULT_FILTERS.team_id`  *(commit 95c8473)*
- [x] 8.2 `normalize()` preserves `team_id` through pipeline  *(commit 95c8473)*
- [x] 8.3 Distinct-teams derivation via `useMemo`  *(commit 95c8473)*
- [x] 8.4 `<Select label="Team" />` between Stage and Actor  *(commit 95c8473)*
- [x] 8.5 Filter predicate + plumbed through `FilterBar` props  *(commit 95c8473)*

## 9 — Verification

- [x] 9.1 `openspec validate ship-operator-grade-pipeline-workflow --strict` → Valid
- [x] 9.2 137/137 orchestrator tests pass (was 105 at session start)
- [x] 9.3 UI `pnpm tsc --noEmit` clean
- [x] 9.4 4 services deployed: orchestrator zombie-cleanup-v11, ledger-ui phase7-8-economics-team-v14, ledger-mcp bundles-baked-v1, sbm-cardiology-alerts
- [x] 9.5 8 zombies cleaned + fresh run `9c3836ed` parked at resolver gate with real chain data

## Definition of done — verified met 2026-06-16

Operator can submit a fresh PRD on `/runs/new`, watch stage pills animate live via SSE, see a sticky banner when the pipeline pauses at any gate, click through to the gate-specific component (`ResolverGate` for resolver, `DesignReviewGate` for design_review), approve per-card or whole-stage, watch the gate close, watch downstream stages run, read the resulting artifacts with line numbers + syntax color + Copy/Download, navigate to `/decisions` and see every decision pin which prompt produced it (with click-through to `/prompts` catalog), navigate to `/economics` and see real KPIs on cost + autonomy + per-team breakdown, filter `/decisions` by team to scope to one team's audit, all without ever seeing a zombie run on `/runs`.

Every clause of the standing-goal user vision is structurally satisfied, deployed, and clickable end-to-end on the live dashboard.
