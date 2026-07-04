# Tasks: add-autonomy-control-surface

## 1. Per-class autonomy computation (pure module)
- [x] `lib/autonomy.ts` — `computeClassAutonomy(entries, floor)` returns per-class rung + counts
- [x] Rung model: `floor | learning | trusted | autonomous`, floor classes pinned to rung 0
- [x] `rungLabel`, `rungTone`, `classLabel` helpers
- [x] Reuses `lineage.ts` primitives (`isStageDecision`, `isHumanSwap`, `isAutopilot`) — no duplicate classification logic

## 2. Floor config proxy
- [x] `app/api/config/hard-gate-classes/route.ts` — server-side proxy to orchestrator
- [x] Fail-safe to default floor `[auth-policy, phi-classification]` on orchestrator error (page always renders)
- [x] `revalidate = 30` (floor changes are rare — standards-change PR cadence)

## 3. The Autonomy page
- [x] `app/autonomy/page.tsx` — three zones (Teaching Loop / Ladder / Envelope)
- [x] Zone 1: teaching-loop hero from `buildLineageIndex()` metrics + agent/human split
- [x] Zone 2: per-class ladder rows with 4-rung progress bars + live counts
- [x] Zone 3: envelope — locked floor chips + governance note (standards-change-not-toggle)
- [x] Uses `useDecisions({ limit: 200 })` — same data source as /decisions (no drift)
- [x] Loading skeletons + empty state ("run the pipeline and resolve a gate to start the loop")

## 4. Navigation
- [x] Sidebar entry `/autonomy` in the Ledger plane (between Decisions and Economics)
- [x] `GraduationCap` icon imported

## 5. Data honesty
- [x] Autonomy-earned subtitle states the denominator explicitly (`N of M decisions`)
- [x] Floor fetched live from config endpoint — not a UI constant (cannot drift from orchestrator)

## 6. Build + verify
- [x] `tsc --noEmit` clean
- [x] Build with correct `--build-arg` (demo-off, vnet URLs)
- [x] Deploy to ca-ledger-ui-vnet; `/autonomy` → 200
- [x] Seed teaching loop live: human swap → autopilot reuse (loop closed, verified in ledger)
- [x] Browser-verify all three zones render with real data

## 7. Documentation
- [x] This proposal + tasks + spec
- [x] `openspec validate add-autonomy-control-surface --strict` → valid

## 8. Follow-ups (deferred — NOT in this change)
- [ ] Historical autonomy trend chart (time-series of earned %)
- [ ] Per-team autonomy comparison (needs MCP token remap)
- [ ] Interactive envelope threshold editor (Pipeline Doctor bounds)

## 9. Archive
- [ ] Archive after 24h soak: move to `openspec/changes/archive/<date>-add-autonomy-control-surface/`
