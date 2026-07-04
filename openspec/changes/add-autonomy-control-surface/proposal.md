# Proposal: add the Autonomy Control surface (/autonomy)

> **Status:** DRAFT (2026-07-04)
> **Capability:** ledger-insights-ui (new operator-facing read surface + one config proxy)
> **Related:**
>   - `add-graduated-autonomy-tier2` (the teaching-loop capability this page visualizes — human swap → precedent → autopilot reuse)
>   - `add-teaching-signal-feedback` (the swap/flag write path that feeds the loop; `lineage.ts` materializes those edges)
>   - `add-pipeline-doctor` (the envelope/bounded-auto-fix control plane referenced in Zone 3)
>   - `feat(orchestrator): honor confidence_source on gate decisions` (the fix that makes human-vs-agent attribution real, without which every autonomy number reads 0)

## Why

The dashboard could show WHAT the agent decided (Decisions page) but never told the operator the three questions every customer asks in the autonomy pitch:

1. **How does the agent improve?** The teaching loop — human overrides become precedent, later hybrid runs reuse them — was latent in the ledger (`lineage.ts` computed `taughtCount` / `reusedCount` / `autonomyEarnedPct`) but never surfaced as a first-class story. It appeared only as one small tile on the Decisions page.

2. **Where do I see it?** There was no per-ambiguity-class view of autonomy maturity. An operator could not answer "is `sla-binding` earning autonomy while `phi-classification` stays locked?" without hand-querying the ledger.

3. **How do I control it?** The immovable PHI/auth floor (`/api/config/hard-gate-classes`, `INVARIANT_CLASSES`) and the Pipeline-Doctor envelope existed in the backend but were invisible in the UI. The control story was untold.

Customer signal (SBM cardiology POC / HCA workshop): "how does the agent get better, where do I watch that happen, and how do I keep it away from PHI?" — three questions, no single screen answered them.

## What changes

A new client-rendered page at `/autonomy` (Ledger plane, sidebar between Decisions and Economics) with three zones, all derived from the SAME ledger entries the Decisions page reads (no new source of truth):

- **Zone 1 — Teaching Loop (hero):** `Human decides → Taught (precedent) → Agent reuses → Autonomy earned %`, wired to `buildLineageIndex()` metrics.
- **Zone 2 — Autonomy Ladder:** per-ambiguity-class rows on a 4-rung curve (`floor → learning → trusted → autonomous`) computed by a new pure module `lib/autonomy.ts::computeClassAutonomy(entries, floor)`. Floor classes (PHI/auth) pinned to rung 0.
- **Zone 3 — Envelope:** the immovable floor rendered as locked chips, with the honest statement that changing it is a standards-change PR (governed, not a toggle), and that Pipeline Doctor may tune thresholds within — never relax — a floor class.

New server-side proxy route `GET /api/config/hard-gate-classes` forwards to the orchestrator's existing endpoint (keeps the orchestrator URL + future auth server-side, matching `/api/economics`), fail-safe to the default floor `[auth-policy, phi-classification]` if the orchestrator is unreachable so the page always renders.

```
apps/ledger-insights-ui/src/
├── app/autonomy/page.tsx                        NEW — the surface
├── app/api/config/hard-gate-classes/route.ts    NEW — floor proxy (fail-safe)
├── lib/autonomy.ts                              NEW — per-class rung computation (pure)
└── components/layout/sidebar.tsx                MOD — nav entry (Ledger plane)
```

## Why this design

- **Pure computation module, no new API.** `lib/autonomy.ts` mirrors `lib/lineage.ts` — pure functions over the entries list, unit-testable, and the numbers cannot drift from the Decisions page because they read the same `useDecisions()` data.
- **Floor comes from the live config endpoint, not a UI constant.** The page fetches `/api/config/hard-gate-classes` so the locked set always reflects the orchestrator's actual `HARD_GATE_CLASSES` (which honors the `HARD_GATE_CLASSES` env extension). Hardcoding it in the UI would let the two drift.
- **The envelope is presented as read-only-with-governance, not a control toggle.** Honest to the model: the floor is changed by a standards-change PR, not a switch. Building a live toggle would misrepresent the governance posture (and would need a write path that doesn't and shouldn't exist for PHI/auth).

## Why we did NOT do the alternative

- **Extend the Decisions page instead of a new route** — rejected: the teaching loop, per-class ladder, and envelope are a distinct operator job (autonomy governance) from browsing the decision log. Cramming them onto `/decisions` buries both.
- **Add a live "promote class to autopilot" button** — rejected: autonomy is earned through precedent, not switched on. A promote button would contradict `add-graduated-autonomy-tier2` and invite exactly the PHI/auth bypass the floor exists to prevent.
- **Compute autonomy server-side in a new endpoint** — rejected: the client already has the full entries list via `useDecisions()`; a server rollup would add a second source of truth that could disagree with the table.

## Out of scope

- Editing the floor from the UI (it's a standards-change PR by design — deferred, and arguably should never be a UI action for PHI/auth).
- Live Pipeline-Doctor threshold tuning controls (Zone 3 references the envelope; the interactive envelope editor is a separate change).
- Per-team autonomy comparison (the MCP token is single-team scoped; multi-team view needs the token-remap tracked elsewhere).
- Historical autonomy trend chart (the loop shows current state; time-series is a follow-up).

## Receipts (filled in at archive time)

- Commit: TBD
- Image: `ledger-insights-ui:autonomy-page-20260704-*`
- Revision: ca-ledger-ui-vnet (live, /autonomy → 200)
- Seed: teaching loop verified live — 1 human swap on sla-binding → 4 autopilot reuses of the taught slot (loop closed)
- tsc: clean
- Build time: ~1m40s
