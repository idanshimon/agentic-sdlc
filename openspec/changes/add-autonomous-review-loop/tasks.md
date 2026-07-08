# Tasks: add-autonomous-review-loop

Phased so an early slice is demonstrable before the full loop is wired. Each
phase ends green (tests + `tsc --noEmit`) before the next starts. YOU are the
CI — there is no `.github/workflows/` on this repo; run suites locally.

## Phase 0 — Vertical slice (the demonstrable core)

Goal: one real failed PR → autonomous remediation → re-review → PASS →
`loop_converged`, on a Tier-A test repo, end to end. This is the demo asset.

- [x] 0.0 **CRITICAL PATH — make review-scan emit a real verdict.** DONE (PR-2). `apps/orchestrator/review_verdict.py` builds a structured `ReviewVerdict` (`status: PASS|FAIL` + `blockers[]` with check/rule/detail/file/line/phi) by reusing the PR-1 deterministic matcher (`scripts/enforce_bundles.py`) over the generated code. `stage_review_scan` now delegates to it — the `findings = 0` stub is gone. `Blocker` + `ReviewVerdict` added to `apps/orchestrator/models.py`. 8 tests in `test_review_verdict.py` (RED→GREEN); full orchestrator suite 223 pass (was 215) + 1 pre-existing unrelated fail.
- [x] 0.1 `apps/orchestrator/review_loop.py` — pure core `plan_next_loop_action(verdict, *, attempt, tier, cost_usd) -> LoopAction` (enum: REMEDIATE | MERGE | AWAIT_HUMAN_MERGE | COMMENT_ONLY | ESCALATE). Zero I/O. DONE (PR-3).
- [x] 0.2 Unit tests for `plan_next_loop_action` — the full truth table (tier A/B/C × PASS/FAIL × attempt bound × cost ceiling × PHI floor). 16 tests in `test_review_loop.py`, RED→GREEN. DONE.
- [x] 0.3 `review_remediation` / `loop_converged` / `loop_escalated` added to ledger-core `RuntimeKind` (`packages/ledger-core/ledger_core/models.py`) + the MCP `RuntimeKindSchema` (`apps/decision-ledger-mcp/src/schema.ts`); orchestrator `LedgerEntry.runtime_kind` is a free `Optional[str]` that already accepts them. Round-trip tested (`test_review_loop_ledger.py`, 3 tests). DONE.
- [x] 0.4 Async glue `run_review_loop(*, repo, tier, code_files, review, remediate, do_merge)` — drives review→plan→(remediate|merge|escalate) to a terminal state, writes a ledger hop per action with a `reviewloop/...` citation. Injectable callables so it's testable with zero real codegen/GitHub. DONE.
- [x] 0.5 E2E (stubbed codegen): FAIL → remediate → PASS → `loop_converged{merged:true}`; asserts the remediation+converged hop chain + PHI-floor escalation + tier B/C behavior. 6 tests in `test_run_review_loop.py`. DONE.
- [ ] 0.6 `openspec validate add-autonomous-review-loop --strict` → Valid.

## Phase 1 — Per-repo autonomy tier (the "move the dial" control)

- [ ] 1.1 `config/repo_autonomy.yaml.example` — customer-neutral topology (a Tier-A demo repo, a Tier-B repo, an implicit Tier-C).
- [ ] 1.2 `apps/orchestrator/repo_autonomy.py` — opt-in loader written fresh against the `config.py::_hard_gate_classes()` floor idiom + the fail-closed `heal.py::validate_heal_action` validator shape (there is NO `model_policy.py` triad to copy). `tier_for(repo) -> Tier`; bootstrap-on-absence singleton + `reload_`.
- [ ] 1.3 `test_default_singleton_is_opt_in_not_auto_loaded` — deploying the image = all repos Tier C.
- [ ] 1.4 Governance teeth: `RepoTierUnlockError` (NEW error class, fail-closed like `heal.py`) — Tier A refused at load for a repo with a PHI/deny blocker in its recent history; forced escalation at runtime. Tests for both halves.
- [ ] 1.4b **rule-ref → PHI/deny resolver (net-new).** Blockers cite bundle rule-ids (`security/v0.1.0/PHI-001`); the floor must resolve those to `phi:true`/deny by reading `rules.yaml` + `envelope.yaml: forbidden`. Unit-test against the actual bundle files. This is the airtight link that stops an autonomous PHI merge from bypassing the resolver-gate tier-2.
- [ ] 1.4c **clean-history graduation precondition.** The loader refuses Tier A unless the repo has no `phi:true`/deny blocker in the last 30d — graduation is earned, not asserted.
- [ ] 1.5 `.gitignore` the activated filenames (`config/repo_autonomy.yaml`, `/repo_autonomy.yaml`); `config/README.md` bootstrap-vs-activated row.
- [ ] 1.6 `GET /api/config/repo-autonomy` — surface tier posture + why-capped per repo.

## Phase 2 — Real remediation + real re-review

- [x] 2.1 `.github/agents/codegen.agent.md` — documented remediation entry mode (verdict in → commit resolving only cited blockers → same-rule citation → no unrelated edits, never a phi:true blocker). DONE (PR-3).
- [ ] 2.2 `.github/agents/review-scan.agent.md` — verdict gains `attempt` + `prior_verdict_ref` for chainable re-reviews.
- [ ] 2.3 Wire real codegen remediation dispatch in `run_review_loop` (drop the Phase-0 stub); full re-scan on the updated branch.
- [ ] 2.4 Attempt bound (`REVIEW_LOOP_MAX_ATTEMPTS`, default 3, unbounded rejected) + **net-new per-run cost ceiling** (`total_cost_usd` accumulates today but never gates — build the enforcement). Tests for exhaustion→escalate and cost→escalate.

## Phase 3 — Real GitHub merge + trigger

- [ ] 3.1 **Net-new merge primitive** — Tier-A auto-merge via `PUT /pulls/{n}/merge` with a merge-scoped token (NOT the `deliver_pr.py` open-PR path, which never merges). Branch-protection-aware: a merge blocked by required-reviews/status-checks MUST escalate explicitly, never silent-no-op. `loop_converged{merged:true}` gates the call.
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
