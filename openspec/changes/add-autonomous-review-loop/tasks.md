# Tasks: add-autonomous-review-loop

Phased so an early slice is demonstrable before the full loop is wired. Each
phase ends green (tests + `tsc --noEmit`) before the next starts. YOU are the
CI — there is no `.github/workflows/` on this repo; run suites locally.

## Phase 0 — Vertical slice (the demonstrable core)

Goal: one real failed PR → autonomous remediation → re-review → PASS →
`loop_converged`, on a Tier-A test repo, end to end. This is the demo asset.

- [ ] 0.1 `apps/orchestrator/review_loop.py` — pure core `plan_next_loop_action(verdict, attempt, tier, cost, has_phi_or_deny) -> LoopAction` (enum: REMEDIATE | MERGE | AWAIT_HUMAN_MERGE | COMMENT_ONLY | ESCALATE). Zero I/O.
- [ ] 0.2 Unit tests for `plan_next_loop_action` — the full truth table (tier × verdict × attempt × phi/deny × cost). RED first.
- [ ] 0.3 `review_remediation` / `loop_converged` / `loop_escalated` added to BOTH LedgerEntry models (`apps/orchestrator/models.py` AND `packages/ledger-core/ledger_core/models.py`) + `decision-ledger-mcp/src/schema.ts`. Test the two-model round-trip.
- [ ] 0.4 Async glue `run_review_loop(pr_ref, run)` — calls review-scan, dispatches codegen remediation, re-reviews, writes ledger hops. Stubbed scanners/codegen acceptable for the slice.
- [ ] 0.5 E2E (stubbed): FAIL → remediate → PASS → `loop_converged{merged:true}`; assert the 2-entry chain + structured citations. RED first.
- [ ] 0.6 `openspec validate add-autonomous-review-loop --strict` → Valid.

## Phase 1 — Per-repo autonomy tier (the "move the dial" control)

- [ ] 1.1 `config/repo_autonomy.yaml.example` — customer-neutral topology (a Tier-A demo repo, a Tier-B repo, an implicit Tier-C).
- [ ] 1.2 `apps/orchestrator/repo_autonomy.py` — opt-in loader mirroring `model_policy.py` exactly (`_candidate_paths` env-first, bootstrap on absence, singleton + `reload_`). `tier_for(repo) -> Tier`.
- [ ] 1.3 `test_default_singleton_is_opt_in_not_auto_loaded` — deploying the image = all repos Tier C.
- [ ] 1.4 Governance teeth: `RepoTierUnlockError` — Tier A refused at load for a repo with a PHI/deny blocker in its recent history; forced escalation at runtime. Tests for both halves.
- [ ] 1.5 `.gitignore` the activated filenames (`config/repo_autonomy.yaml`, `/repo_autonomy.yaml`); `config/README.md` bootstrap-vs-activated row.
- [ ] 1.6 `GET /api/config/repo-autonomy` — surface tier posture + why-capped per repo.

## Phase 2 — Real remediation + real re-review

- [ ] 2.1 `.github/agents/codegen.agent.md` — documented remediation entry mode (verdict in → commit resolving only cited blockers → same-rule citation → no unrelated edits).
- [ ] 2.2 `.github/agents/review-scan.agent.md` — verdict gains `attempt` + `prior_verdict_ref` for chainable re-reviews.
- [ ] 2.3 Wire real codegen remediation dispatch in `run_review_loop` (drop the Phase-0 stub); full re-scan on the updated branch.
- [ ] 2.4 Attempt bound (`REVIEW_LOOP_MAX_ATTEMPTS`, default 3, unbounded rejected) + cost ceiling reusing the model-policy seam. Tests for exhaustion→escalate and cost→escalate.

## Phase 3 — Real GitHub merge + trigger

- [ ] 3.1 Tier-A auto-merge via the same Git Data API path `swap-deliver-ado-to-github` uses (real merge, never fabricated). `loop_converged{merged:true}` gates the merge call.
- [ ] 3.2 `POST /api/review-loops/{id}/merge` — the single Tier-B human touch-point; refuses on Tier-C/unlisted.
- [ ] 3.3 `.github/hooks/pull_request.opened` (+ `scripts/`) — trigger `run_review_loop` when a Coding Agent opens a PR on an opted-in repo. Hook frontmatter validates.
- [ ] 3.4 `.github/agents/review-loop-controller.agent.md` — Foundry persona (allowed actions, ledger kinds, read-only security/privacy subscriptions); validates against `agent-frontmatter.schema.json`. AGENTS.md persona-table row added.

## Phase 4 — UX (observable dark factory)

- [ ] 4.1 `apps/ledger-insights-ui/src/app/review-loop/page.tsx` — live loop table, attempt-timeline stepper, terminal-state chips, hop→ledger + PR/commit deep links. Mirror `app/decisions/page.tsx`; URL-state filters; tonal buttons; `var(--*)` tokens.
- [ ] 4.2 `/autonomy` per-repo tier panel (beside per-class): tier, why-capped, who-graduated, last-10 outcomes sparkline.
- [ ] 4.3 Escalation inbox — unresolved blockers + PR + "take it from here".
- [ ] 4.4 API client method + types (`URLSearchParams`, skip empty); sidebar nav entry (Agent-HQ plane) + lucide icon import.
- [ ] 4.5 DEMO MODE fixtures so the loop renders offline (parity with demo store).
- [ ] 4.6 `cd apps/ledger-insights-ui && npm run build` (or `npx tsc --noEmit`) clean — do NOT claim UI works from a green Python suite alone.

## Phase 5 — Compliance + hardening

- [ ] 5.1 Confirm the three new kinds flow through the Phase-5 compliance query with NO loop-specific branch (add a fixture row per kind; assert attribution completeness).
- [ ] 5.2 Full-suite regression: orchestrator + ledger-core + pipeline-doctor all green; record counts.
- [ ] 5.3 Live-deploy E2E: a real Coding-Agent PR on the Tier-A demo repo heals to a real merge; ledger pins the full chain; screenshot the `/review-loop` page for the demo.
- [ ] 5.4 Honest-disclaimers pass: attempt bound, PHI/deny floor, model-variance-contained-not-solved, demo-vs-live parity — surfaced in the UI and README.

## Completion gate

- [ ] `openspec validate add-autonomous-review-loop --strict` → Valid.
- [ ] The Phase-0 slice works on the live deploy (real PR → autonomous remediate → real merge on a Tier-A repo; 2+ entry chain in the ledger).
- [ ] PHI/auth/deny blockers are provably escalated, never auto-merged (tests + a manual attempt that gets refused).
- [ ] No repository is auto-merged unless explicitly graduated to Tier A in config; a fresh deploy changes no repo's behavior.
- [ ] Every loop hop is a ledger entry with a `reviewloop/...` structured citation, reconstructable by the compliance query.
