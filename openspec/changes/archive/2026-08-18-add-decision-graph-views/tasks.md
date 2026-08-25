# Tasks: add-decision-graph-views

## 0. Grounding and specification

- [x] Inspect current `/decisions` surface, ledger read hook (`useDecisions`), and `LedgerEntry` shape.
- [x] Record KEEP / SWAP / ADD / OUT (KEEP: table+feed+ledger read; ADD: 3 graph routes + shared engine; SWAP: none; OUT: backend/schema/bundle changes).
- [x] Author proposal, spec delta, tasks.
- [x] Validate with `openspec validate add-decision-graph-views --strict`.

## 1. Shared graph engine (pure, tested)

- [x] RED: `build-graph.test.ts` — governance network nodes/edges, hub sizing, reuse edges, flag glow, same-slot chaining, stats.
- [x] GREEN: `src/lib/graph/build-graph.ts` (`buildGovernanceNetwork`).
- [x] Deterministic cluster layout `src/lib/graph/layout.ts`.
- [x] RED+GREEN: `build-lineage.ts` + `build-lineage.test.ts` — precedent DAG, roots, teaching attach.
- [x] Dagre L→R layout `src/lib/graph/layout-lineage.ts`.
- [x] RED+GREEN: `build-runflow.ts` + `build-runflow.test.ts` — per-run stage/bucket flow, run-id enumeration.
- [x] RED+GREEN: `map-filters.ts` + `map-filters.test.ts` — edge-family toggle, flag focus, bundle scope, node budget.

## 2. Graph routes (thin renderers, click-through)

- [x] `/decisions/graph` — Decision Map with filter chips + minimap.
- [x] `/decisions/lineage` — Precedent Lineage DAG.
- [x] `/decisions/runflow` — Run Flow with run picker.
- [x] Every node click-throughs to `/decisions#decision-<id>`.
- [x] All three read `useDecisions` (auto-refresh), no writes.
- [x] Sidebar nav entries (+3) under Ledger plane.

## 3. Verification

- [x] `pnpm vitest run src/lib/graph/` green (22 tests).
- [x] `pnpm tsc --noEmit` clean.
- [x] `pnpm build` succeeds; all three routes in the manifest.
- [x] Seed graph-shaped sample data (`scripts/seed_graph_demo.py`) and screenshot-verify all three views render legibly against live data.
- [x] Deploy the UI image and verify the three routes return 200 on the live stack.

## 4. Docs

- [x] `CHANGELOG.md` version entry.
- [x] Demo runbook note: lead the graph story with Precedent Lineage.
