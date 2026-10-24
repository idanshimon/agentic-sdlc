# Proposal: add-mission-control-cockpit

## Why

Operators can read individual runs and individual decisions, but nothing shows the
whole governed system at once: which agents are working, where runs are piling up in
the pipeline, and where a human gate is holding work. The Agents page shows static
persona definitions with no evidence of what each agent has actually done.

## What Changes

- ADD a `/mission` route: an orbital cockpit. The pipeline stages form the center
  dial, runs orbit on rings ordered by consequence (blocked, failed, in flight,
  done), and each agent persona is a satellite whose size and activity reflect its
  real ledger record. Selecting a run or agent opens an inspector with evidence and
  a link to the full record.
- ADD a pure projection module (`src/lib/mission.ts`) that derives stage occupancy,
  ring placement and per-agent activity from existing `RunState` and `LedgerEntry`
  fields only. No new producer fields.
- UPGRADE the Agents page into a roster with live per-agent telemetry (decisions,
  autonomy share, flagged, spend, last active, 14-day activity bars). Editing stays.
- ADD a pipeline flow strip on the dashboard showing live stage occupancy.

## Impact

- UI only (`apps/ledger-insights-ui`). Read-only. No ledger writes, no schema change.
- Entries whose stage cannot be attributed to an agent are counted as unattributed,
  never guessed.

## Phase 2 — Decisions command deck and motion

- ADD a shared Decisions command deck (autonomy gauge, daily human/agent
  timeline, autonomy-by-class matrix) above all four Decisions views; the Run
  flow view scopes it to the selected run.
- ADD a HyperFrames-style motion layer: one paused GSAP timeline per surface
  (entrance, count-up, arc draw), a Cytoscape motion loop (node entrance,
  flowing reuse/teaching edges, pulsing flagged nodes) and HUD-framed canvases.
  Presentation only; disabled under prefers-reduced-motion.
- ADD a dashboard "governed loop" strip (agents decided → gates holding →
  human calls → policy blocks), each beat linking to its filtered view.
- FIX: live ledger rows with no actor object were normalized as agent; the
  producer's `confidence_source` now decides human vs agent.
- FIX: derived lineage reuse required no ordering, so an autopilot proposal
  later re-decided by a human was drawn as the agent learning from the human.
  Derived reuse now requires the autopilot entry to follow the human ruling.
- FIX: the Table view read 50 entries while Map/Lineage/Run flow read 1000, so
  the same deck showed different numbers per tab; all now read 1000.

## Phase 3 — Grounded assistant (live mode)

- FIX: the shared Sheet rendered a Radix dialog with no Title (console
  error, unnamed for screen readers). `SheetContent` now requires a `title`
  and renders it visually hidden, so no sheet can ship without one.
- CHANGE: the assistant is a docked, non-modal panel with no backdrop — the
  page behind stays sharp and clickable while the operator asks about it.
- ADD: `POST /api/assist/chat` and `POST /api/assist/context` (preview).
  Server-side grounding assembles: the current view, derived facts computed
  from the record, keyword-ranked ledger entries (scoped to the viewed run
  BEFORE ranking), runs, the standards-bundle rules those records cite,
  OpenSpec changes, and recent GitHub PRs/commits of the repo.
- ADD: PHI guard at the LLM boundary — ledger/run excerpts are classified by
  the ledger's own classifier; high-PHI excerpts are withheld and counted
  ([security/v0.1.0/PHI-001]); classifier failure withholds (fail closed).
- ADD: keyless Azure OpenAI (DefaultAzureCredential / managed identity).
  With no endpoint configured or on model failure, the deterministic
  composer answers and the reply is labelled "offline composer".
- The assistant stays a reading layer: no ledger writes, no gate approvals.

## Phase 4 — Settings fix and About

- FIX: Settings was blank because the deployed orchestrator predates
  `/api/config/settings`. The UI now composes governance, bundle pins and repo
  autonomy from the older endpoints, labels the view as composed, and marks
  sections it cannot serve as unavailable. Other failures still show an error.
- ADD: Settings → About (last tab): version, commit, build time, mode, and live
  backend probes, with a copy-for-bug-report button. The sidebar version label
  now reads the real package version.
- CHANGE: Dockerfile and build script pass `BUILD_GIT_SHA` to the build.
