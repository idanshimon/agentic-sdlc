# Tasks: defensive input normalization for DecisionCard renderer

## 1. Renderer-side normalization
- [x] 1.1 Add `RawEntry` permissive type that includes legacy fixture fields (`created_by`, `resolution_text`, `ambiguity_class`)
- [x] 1.2 Add `normalize(raw)` function in `apps/ledger-insights-ui/src/components/domain/decision-card.tsx`
- [x] 1.3 `normalize` MUST never return an entry with undefined `actor.kind` or undefined `actor.id`
- [x] 1.4 `normalize` MUST fall back through `decision → resolution_text → ambiguity_class → "(no decision text)"` for the title
- [x] 1.5 `normalize` MUST coerce non-array `bundle_refs` / `precedent_refs` to `[]`
- [x] 1.6 `DecisionCard` calls `normalize(raw)` BEFORE reading any field

## 2. Test coverage (regression guards)
- [x] 2.1 NEW `apps/ledger-insights-ui/src/components/domain/decision-card.test.ts`
- [x] 2.2 Test: legacy resolver-decision shape coerces (created_by + resolution_text)
- [x] 2.3 Test: empty input `{}` produces "unknown" actor + "(no decision text)"
- [x] 2.4 Test: canonical LedgerEntry shape passes through unchanged
- [x] 2.5 Stress test: every degenerate `actor` shape (undefined, null, `{}`, non-object) returns valid `kind`
- [x] 2.6 Test: non-array `bundle_refs` doesn't throw on `.map()`
- [x] 2.7 All 34/34 tests passing (was 29 + 5 new)
- [x] 2.8 `tsc --noEmit` clean

## 3. Build + deploy
- [x] 3.1 ACR build `ledger-insights-ui:1457801` (digest `sha256:549afde17…`) — 84s
- [x] 3.2 Container App update: `ca-ledger-ui` revision `--0000008` healthy + running
- [x] 3.3 Tactical Cosmos firewall fix (re-enabled `publicNetworkAccess: Enabled`, added `0.0.0.0` wildcard alongside existing rules) — separate operational action, not in commit
- [x] 3.4 Smoke 5 routes → all 200
- [x] 3.5 Smoke `/api/ledger/query {}` → 200 `{"entries":[]}` (was 400)

## 4. Documentation
- [x] 4.1 In-file JSDoc explaining both sources (Cosmos canonical + demo legacy) and the 2026-06-10 crash trigger
- [ ] 4.2 Update `customer-engagement/hca-agentic-sdlc-demo` skill — add new standing rule: any renderer over typed network input MUST normalize-first
- [ ] 4.3 Cross-link from `assistant-context-render-storm-debugging.md` reference (same crash class — renderer SIGKILL with empty exception)

## 5. Follow-ups (deferred)
- [ ] 5.1 Apply same normalize pattern to other card renderers in the dashboard: `RunSummaryCard`, `AgentActivityCard`, `BundleVersionCard`, `PromptVariantCard` — when added or modified
- [ ] 5.2 Promote `normalize()` to a shared utility in `lib/normalizers/` if a second card renderer needs the same coercion
- [ ] 5.3 Demo fixtures schema migration (`lib/demo/fixtures.ts` → canonical LedgerEntry shape) — defer until a customer asks for richer demo data on `/decisions`

## 6. Archive
- [ ] 6.1 Move to `openspec/changes/archive/fix-decision-card-defensive-normalize/` after `git push origin main` succeeds and the deploy soaks for 24h
