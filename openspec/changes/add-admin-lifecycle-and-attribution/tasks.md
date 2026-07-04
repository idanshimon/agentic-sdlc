# Tasks: add-admin-lifecycle-and-attribution

## 1. Ledger-core deletion primitive
- [x] `LedgerClient.delete_run(run_id)` — hard-delete pipeline-runs doc (PK /run_id)
- [x] Mirrors existing `delete_entry` shape; returns bool (False on not-found)

## 2. Orchestrator admin endpoints
- [x] `DELETE /api/admin/runs/{run_id}` — delete run doc + drop in-memory handles
- [x] `DELETE /api/admin/ledger/{team_id}` — delete all decision entries for one team partition
- [x] Ledger-clear is partition-scoped (never cross-team); returns {found, deleted}
- [x] Run-delete leaves decision-ledger entries intact (audit preserved)

## 3. Attribution fix (orchestrator)
- [x] `/approve` passes `confidence_source=decision.confidence_source` into LedgerEntry
- [x] Defaults to "human" on the model when the client omits the field

## 4. Attribution fix (UI)
- [x] `decision-table.tsx` normalize() derives actor kind from confidence_source
- [x] `decisions-insights.tsx` autonomy-split tile derives kind from confidence_source (not un-normalized actor.kind)

## 5. Verify
- [x] DELETE run → 200, subsequent GET → 404 (real Cosmos delete)
- [x] DELETE ledger/{team} → {found, deleted} counts; Decisions page confirmed cleared
- [x] Import-smoke green on each orchestrator build
- [x] Decisions autonomy split reads correct human/agent counts (55% agent · 45% human · 11/9)
- [x] Rows show correct human/agent icons

## 6. Documentation
- [x] This proposal + tasks + ledger spec
- [ ] `openspec validate add-admin-lifecycle-and-attribution --strict` → valid

## 7. Follow-ups (deferred — NOT in this change)
- [ ] Auth on admin endpoints (VNET-internal today)
- [ ] Structured `actor {kind,id}` object on ledger entries (derive-from-confidence_source is the compatible fix for now)

## 8. Archive
- [ ] Archive after soak: `openspec/changes/archive/<date>-add-admin-lifecycle-and-attribution/`
