# Known issues

Tracked, reproduced issues that are diagnosed but not yet fully resolved. Each
entry names the symptom, the grounding done, the suspected root cause, and the
next step — so the next session (or the next engineer) starts from evidence, not
a blank page.

---

## KI-1 · Decisions table does not show a just-completed run's decisions

**Status:** root-caused. Bug A (merge ordering) FIXED; Bug B (team scoping) is
by-design tenant isolation — mitigation is a visibility/UX change, tracked below.

**Symptom (reported 2026-07-08):** After finishing a live run and deciding all
resolver-gate cards, the `/decisions` page still shows a stale set (33 entries,
newest "2d ago"). The fresh decisions do not appear even when sorting by *When*
descending.

**Root cause — CONFIRMED (two compounding bugs):**

The deployment runs with **`NEXT_PUBLIC_DEMO_MODE=1`** (hardcoded in
`infra/apps.bicep:199`, `infra/apps-vnet.bicep:199`, `apps/ledger-insights-ui/Dockerfile:23`).
In demo mode the Decisions view blends the demo seed store with live Cosmos
entries. Two independent defects made fresh decisions invisible:

- **Bug A — the blend didn't sort or de-dupe (FIXED 2026-07-08).**
  `ledgerMcp.query()` did `[...demoEntries, ...live.entries]` — live rows were
  appended *below* the 33-entry demo seed block and never re-sorted, so a
  just-written decision sank to the bottom (and dupes showed twice). Fixed by
  `src/lib/api/merge-ledger.ts::mergeLedgerEntries()` — de-dupes by id (live
  wins) and sorts newest-first. 6 unit tests. Now a fresh live entry surfaces at
  the top regardless of demo seed timestamps.

- **Bug B — live query is single-team by design (NOT a code bug).** The MCP
  proxy attaches one bearer token (`LEDGER_MCP_TOKEN`); the MCP server maps each
  token to exactly one `team_id` and refuses cross-team reads (tenant isolation,
  `apps/decision-ledger-mcp/src/server.ts`). The `/decisions` page calls
  `ledgerMcp.query()` with no `team_id`, so live results come back only for the
  dashboard token's team. A run created under a *different* `team_id` (e.g. a
  PRD upload that set its own team) writes to a partition the dashboard token
  cannot read — so those entries are genuinely absent, not just mis-sorted.

**Why the "sort by When" test still showed 2d-ago:** the decision *table* does
sort by `created_at` desc (`decision-table.tsx`), so if live entries had been in
the dataset they'd have surfaced. They weren't — Bug B kept them out of the
result entirely, and Bug A guaranteed that even when present they'd sink. Both
had to be addressed.

**Remaining (Bug B mitigation — UX, not a security change):** don't weaken
isolation. Instead make the scoping *visible and adjustable*:
1. ✅ DONE (2026-07-08) — Show which team the Decisions view is querying. The MCP
   `ledger.query` now echoes `team_id`; the `/decisions` page shows a "team: …"
   chip plus "demo + live blended" / "live unreachable" chips, so an empty or
   stale result is explained, not silent. `useDecisions` also refetches every
   10s, so a fresh decision surfaces without a manual reload.
2. Let the operator scope Decisions to a specific run (run detail already knows
   its `team_id`) so cross-team runs are reachable when intended. (open)
3. ✅ DONE (2026-07-08) — Runs now write decisions under the same team the
   dashboard token reads. `/api/run` defaulted `team_id` to a hardcoded
   `"cardiology"` while the dashboard token maps to `team-demo`, so every run's
   decisions landed in a partition the dashboard could not read — the root cause
   of the reported symptom. Fixed: `team_id` defaults from the `LEDGER_TEAM_ID`
   env (fallback `team-demo`); `infra/apps.bicep` + `infra/apps-vnet.bicep` set
   `LEDGER_TEAM_ID=team-demo` on the orchestrator container. Regression-guarded
   by `test_run_team_alignment.py` (3 tests). NOTE: corrects NEW runs after
   redeploy; decisions already written under `cardiology` remain in that
   partition (historical, one-time data consideration).

**KI-2** (resolver-gate button) — fixed earlier, see below.

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
