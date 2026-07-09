# Known issues

Tracked, reproduced issues that are diagnosed but not yet fully resolved. Each
entry names the symptom, the grounding done, the suspected root cause, and the
next step — so the next session (or the next engineer) starts from evidence, not
a blank page.

---

## KI-1 · Decisions table does not show a just-completed run's decisions

**Status:** diagnosed, NOT fixed. Read-path bug (writes are correct).

**Symptom (reported 2026-07-08):** After finishing a live run and deciding all
resolver-gate cards, the `/decisions` page still shows a stale set (33 entries,
newest "2d ago"). The fresh decisions do not appear even when sorting by *When*
descending.

**Grounding done:**
- The **write path is correct.** `POST /api/runs/{id}/approve`
  (`apps/orchestrator/main.py`) builds a `LedgerEntry` and calls
  `_ledger.write_decision(entry)`. `LedgerEntry.created_at` defaults to
  `_now()` (UTC ISO), so timestamps are current on write.
- The **demo store path is also correct** — `approveDemoRun()`
  (`apps/ledger-insights-ui/src/lib/demo/index.ts`) stamps
  `created_at: nowIso()` on each entry, and `listDemoLedgerEntries()` sorts
  newest-first.
- The `/decisions` page reads via `ledgerMcp.query()` →
  `/api/ledger/query` → `forwardToLedgerMcp("/tools/ledger.query")` → the
  decision-ledger MCP server.

**Suspected root cause (two candidates, not yet disambiguated):**
1. **Team-partition mismatch (most likely).** If `ledger.query` on the MCP
   server default-scopes to a specific `team_id` partition (the seed data shows
   `team-demo` / `idan@microsoft.com` partitions) but the fresh run wrote under a
   different `team_id`, the new entries live in a partition the page never reads.
   The stable 33-count of only old entries points here.
2. **Demo-mode blending.** If the deployed UI has `NEXT_PUBLIC_DEMO_MODE=1`, the
   page merges demo-store + live entries; a live run's Cosmos writes never enter
   the demo store, and the seed demo entries carry old timestamps.

**Next step:** confirm which by (a) reading the MCP `ledger.query` handler for a
default team filter / cross-partition behavior, (b) checking what `team_id` the
screenshot run (`db0148b7-…`) wrote under vs. what the page queries, and (c)
checking `NEXT_PUBLIC_DEMO_MODE` on the deployment. Fix is then one of: make
`ledger.query` cross-partition (or default to the run's team), have the page pass
the active team, or reconcile demo-vs-live blending.

**Not done in this change** — resolver-gate UX (KI-2) was fixed here; this
read-path bug is filed for a focused follow-up rather than guessed at.

---

## KI-2 · Resolver-gate "Approve" button did not signal it must be pressed — FIXED (2026-07-08)

**Symptom:** After resolving the explicit (hard-gated) decision and with all
other cards recommended-ready, the primary button still read "Approve all
recommended". It was unclear that pressing it was required to advance, and the
label read like it might *revert* the explicit decision the operator just made.

**Fix:** `apps/ledger-insights-ui/src/components/domain/resolver-gate.tsx` now
derives button + guidance state from a pure, unit-tested `gateProgress()`:
- All cards decided → button becomes **"Finalize & advance"** (green ring) with a
  header line: "All N cards decided. Click 'Finalize & advance' to close the gate
  and continue."
- Only a locked (PHI/auth) card remains → button shows **"Decide the locked card
  to continue"** (disabled) with guidance to decide it individually.
- Some decided, none locked → "Approve all recommended" with an
  "N of M decided" progress line.

Covered by 7 new tests in `resolver-gate.test.ts` (16 total green); `npm run
build` clean.
