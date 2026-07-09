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
- [x] 0.6 `openspec validate add-autonomous-review-loop --strict` → Valid.

## Phase 1 — Per-repo autonomy tier (the "move the dial" control)

- [x] 1.1 `config/repo_autonomy.yaml.example` — customer-neutral topology (a Tier-A demo repo, a Tier-B repo, an implicit Tier-C).
- [x] 1.2 `apps/orchestrator/repo_autonomy.py` — opt-in loader written fresh against the `config.py::_hard_gate_classes()` floor idiom + the fail-closed `heal.py::validate_heal_action` validator shape (there is NO `model_policy.py` triad to copy). `tier_for(repo) -> Tier`; bootstrap-on-absence singleton + `reload_`.
- [x] 1.3 `test_default_singleton_is_opt_in_not_auto_loaded` — deploying the image = all repos Tier C.
- [x] 1.4 Governance teeth: `RepoTierUnlockError` (NEW error class, fail-closed like `heal.py`) — Tier A refused at load for a repo with a PHI/deny blocker in its recent history; forced escalation at runtime. Tests for both halves.
- [~] 1.4b **rule-ref → PHI/deny resolver — PARTIAL.** The Blocker already carries `phi:true` from the verdict builder (PR-2, sourced from the bundle rule), and the loop's PHI floor keys on `blocker.phi` + deny-path convention (has_phi_or_deny). A dedicated `envelope.yaml: forbidden` reader is DEFERRED — the current phi flag already closes the bypass for the shipped rules. Blockers cite bundle rule-ids (`security/v0.1.0/PHI-001`); the floor must resolve those to `phi:true`/deny by reading `rules.yaml` + `envelope.yaml: forbidden`. Unit-test against the actual bundle files. This is the airtight link that stops an autonomous PHI merge from bypassing the resolver-gate tier-2.
- [x] 1.4c **clean-history graduation precondition.** DONE — loader refuses Tier A when `recent_phi_or_deny_blocker: true` (test_tier_a_refused_at_load_for_phi_history). The loader refuses Tier A unless the repo has no `phi:true`/deny blocker in the last 30d — graduation is earned, not asserted.
- [x] 1.5 `.gitignore` the activated filenames (`config/repo_autonomy.yaml`, `/repo_autonomy.yaml`); `config/README.md` bootstrap-vs-activated row.
- [x] 1.6 `GET /api/config/repo-autonomy` — DONE (2 endpoint tests). — surface tier posture + why-capped per repo.

## Phase 2 — Real remediation + real re-review

- [x] 2.1 `.github/agents/codegen.agent.md` — documented remediation entry mode (verdict in → commit resolving only cited blockers → same-rule citation → no unrelated edits, never a phi:true blocker). DONE (PR-3).
- [x] 2.2 `attempt` + `prior_verdict_ref` for chainable re-reviews — DONE in the `ReviewVerdict` model (PR-2/3); build_review_verdict threads both. for chainable re-reviews.
- [~] 2.3 Real codegen remediation dispatch — the loop calls an injected `remediate` callable (tested with a stub); wiring it to the LIVE codegen agent + real branch re-scan is the live-deploy step (deferred, same as the slice's 'stubbed codegen acceptable'). (drop the Phase-0 stub); full re-scan on the updated branch.
- [x] 2.4 Attempt bound (`REVIEW_LOOP_MAX_ATTEMPTS`, default 3, unbounded rejected via max(1,...)) + per-run cost ceiling (`REVIEW_LOOP_COST_CEILING_USD`) — both enforced in `plan_next_loop_action`; exhaustion→escalate + cost→escalate tested (PR-3). (`REVIEW_LOOP_MAX_ATTEMPTS`, default 3, unbounded rejected) + **net-new per-run cost ceiling** (`total_cost_usd` accumulates today but never gates — build the enforcement). Tests for exhaustion→escalate and cost→escalate.

## Phase 3 — Real GitHub merge + trigger

- [x] 3.1 **Net-new merge primitive** — DONE. `apps/orchestrator/merge_pr.py` `merge_pull_request()` PUT /pulls/{n}/merge, branch-protection-aware (405/409/auth → escalate, never silent), injectable client. 5 tests. — Tier-A auto-merge via `PUT /pulls/{n}/merge` with a merge-scoped token (NOT the `deliver_pr.py` open-PR path, which never merges). Branch-protection-aware: a merge blocked by required-reviews/status-checks MUST escalate explicitly, never silent-no-op. `loop_converged{merged:true}` gates the call.
- [x] 3.2 `POST /api/review-loops/merge` — DONE. The Tier-B human merge touch-point; enforces tier server-side (409 on Tier-C/unlisted), calls the branch-protection-aware merge primitive, returns merged/escalate honestly. 4 tests (test_review_loop_merge_endpoint.py).
- [x] 3.3 `.github/workflows/autonomous-review-loop.yml` — PR-opened/synchronize/reopened trigger; guarded no-op where ORCHESTRATOR_URL unset (safe by absence). (Realized as a GitHub Actions workflow, not a Copilot session hook — the trigger surface is a PR event, not an IDE session.) (+ `scripts/`) — trigger `run_review_loop` when a Coding Agent opens a PR on an opted-in repo. Hook frontmatter validates.
- [x] 3.4 `.github/agents/review-loop-controller.agent.md` — DONE. Persona: allowed actions, 3 ledger kinds, read-only security/privacy subscriptions, PHI-floor + never-silent-merge hard rules. Parses cleanly (test_agent_bundles green). — Foundry persona (allowed actions, ledger kinds, read-only security/privacy subscriptions); validates against `agent-frontmatter.schema.json`. AGENTS.md persona-table row added.

## Phase 4 — UX (observable dark factory)

- [x] 4.1 `apps/ledger-insights-ui/src/app/review-loop/page.tsx` — DONE (PR-5). Live loop table, attempt-timeline stepper (parses `reviewloop/<tier>/<repo>/<action>@attempt=N` citations), terminal-state chips (MERGED/ESCALATED/ADVISORY/IN-PROGRESS), grouped by repo. `var(--*)` theme tokens (corrected to the real vocabulary: --text/--text-secondary/--surface/--border/--danger/--warning/--success/--info/--accent).
- [x] 4.2 Per-repo tier panel — DONE (rendered on /review-loop rather than /autonomy): tier badge + why-capped per repo, bootstrap message when no repo graduated. Reads `GET /api/config/repo-autonomy` via `useRepoAutonomy()`.
- [x] 4.3 Escalation inbox — DONE. First-class section listing escalated loops with repo, attempt count, escalation reason, and terminal chip. Surfaces only when escalations exist.
- [x] 4.4 API client method (`orchestrator.repoAutonomy()`) + types (`RepoTier`, `RepoAutonomyPosture`, 3 loop runtime_kinds + `autonomy_ref`/`detail` on LedgerEntry); `useReviewLoops()` + `useRepoAutonomy()` hooks; sidebar nav entry (Agent-HQ plane, GitMerge icon already imported). DONE.
- [~] 4.5 DEMO MODE — the loop page reads live ledger loop-hops via `ledgerMcp.query` (which already merges demo-store entries in demo mode). Dedicated loop fixtures in the demo store are DEFERRED (no demo loop run exists yet); the page renders an honest EmptyState offline. Parity comes when a demo loop run is added.
- [x] 4.6 `npm run build` — DONE, CLEAN. `/review-loop` appears in the route table as a static page; `npx tsc --noEmit` exits 0 (after clearing stale .next/types cache from deleted autonomy/compliance pages — not from this change).

## Phase 5 — Compliance + hardening

- [x] 5.1 DONE. No dedicated compliance_query module exists in this repo; the generic newest-first reader is `telemetry_queries.query_decisions`, which filters only on team_id/decision_kind/created_at and returns any entry unmodified — that genericity IS the no-loop-specific-branch property. `test_review_loop_compliance.py` (3 tests) proves the 3 kinds flow through, a converged loop is reconstructable from its `reviewloop/...` citations alone, and an escalation cites its reason.
- [x] 5.2 DONE. Full suite green: orchestrator 268, scripts 26 (PR-1 enforcer), ledger-core 20, pipeline-doctor 32 = 346 pass. Plus 1 PRE-EXISTING unrelated failure (`test_providers.py::test_stub_fallback_on_provider_error`, stale patch target — fails on clean main too, untouched).
- [~] 5.3 DEFERRED (live-deploy step). Requires a real Tier-A delivery repo + running orchestrator + a real Coding-Agent PR. The full loop is proven end-to-end in-process (test_run_review_loop.py: FAIL→remediate→PASS→loop_converged{merged:true}, PHI→escalate) with injected review/remediate/merge; wiring to the live deploy is the operational follow-up, not a code gap.
- [x] 5.4 DONE. The /review-loop page header states model variance is contained not solved + PHI/auth/deny always escalate; the review-loop-controller persona's 'What you contain, not what you solve' section + hard rules cover attempt bound, PHI floor, never-silent-merge; docs/CI-ENFORCEMENT.md carries the necessary-not-sufficient caveat.

## Completion gate

- [x] `openspec validate add-autonomous-review-loop --strict` → Valid.
- [~] The Phase-0 slice is proven IN-PROCESS (test_run_review_loop.py: 2+ entry chain, real merge via injected client). Live-deploy verification is the deferred 5.3 operational step.
- [x] PHI/auth/deny provably escalated, never auto-merged — test_review_loop.py (plan returns ESCALATE for PHI on Tier A/B) + test_run_review_loop.py (PHI blocker escalates immediately, remediation never called, merge never called).
- [x] No repo auto-merged unless graduated to Tier A — test_repo_autonomy.py (absence=Tier C, deploying the image = all Tier C; Tier A refused at load for PHI history).
- [x] Every hop cites `reviewloop/<tier>/<repo>/<action>@attempt=N[:reason]` — test_run_review_loop.py asserts every hop's autonomy_ref; test_review_loop_compliance.py proves reconstruction from citations alone.
