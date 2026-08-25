# PR Plan — Autonomous Governed Review Loop (dark-factory engine)

**Author:** Idan Shimon · **Date:** 2026-07-08

Grounded in a full re-read of the OpenSpec changes + the real orchestrator/UI
implementation. Every claim below was verified against code, not the specs'
self-description. This is a customer-neutral reference system (see AGENTS.md) —
changes are motivated by architectural need, never by any engagement.

---

## The two PR streams (do not conflate)

| Stream | Repo | What lands there | Who reviews |
|---|---|---|---|
| **DEV** — building the engine | `idanshimon/agentic-sdlc` (public) | Our capability PRs (this plan). PR #9 already here. | Copilot reviewer + Idan admin-merge |
| **DELIVERY** — what the factory produces | `idanshimon/agentic-sdlc-delivery` (private) | Real pipeline-produced code PRs (#3, #4 exist today) | The autonomous loop we're building |

- **Decisions/ledger** (resolver-gate choices, PHI cards, autonomy calls) → **Cosmos**, shown in the Ledger UI. Never a GitHub PR.
- **`agentic-sdlc-demo`** → **does not exist** (404). It's a hardcoded fake `Math.random()` URL string in the demo-replay engine only. Demo-mode "PCI Clean" opens nothing real.
- The governance loop + CI floor OPERATE on the **delivery** repo; we DEVELOP them on the **engine** repo. Decision **C**: install the CI floor on BOTH (dogfood on engine, demonstrate on delivery).

---

## Verified ground truth (what's real vs stub)

- ✅ `stage_deliver` opens a **REAL** GitHub PR via Git Data API → `agentic-sdlc-delivery` (proven: PRs #3/#4). Emits generated `code`/`test_plan`/`architecture` into run events — the exact diff surface an enforcer scans.
- ❌ `stage_review_scan` = 8-line **stub** (`findings = 0  # demo: stubbed clean`). No scanners. This is the #1 honesty gap and the loop's load-bearing input.
- ⚠️ Bundle BLOCK rules: **16 total, only 2 carry a machine-checkable `pattern`** (security PHI-in-logs, security hardcoded-secret). The other 14 are semantic → only an LLM verdict can judge them.
- ❌ No structured blocker/verdict type in `models.py`. No merge primitive (`github_app_client.py` only does JWT auth). No `.github/workflows/` at all.
- ✅ Fail-closed validator to mirror: `heal.py::validate_heal_action` + `config.py::_hard_gate_classes()` (env-extends-never-shrinks). `INVARIANT_CLASSES = {phi-classification, auth-policy}`.

**Architectural consequence (the honest selling point):** the CI floor enforces the 2 deterministic rules un-bypassably on any PR; the review-loop is the ONLY thing that enforces the 14 semantic BLOCK rules. Neither alone covers the standard — that's genuine defense-in-depth, not marketing.

---

## The 5 dev PRs (dependency-ordered, each independently shippable + demoable)

### PR-1 · The deterministic floor  ·  `add-bundle-ci-enforcement` (+ folds `add-standards-bundles` docs)
**Build:** `scripts/enforce_bundles.py` (stdlib + PyYAML only — no orchestrator, no Cosmos, no LLM). Loads resolved bundles honoring `PINS.yaml`, selects `severity: BLOCK` rules with a `pattern`, runs them on a changed-files set, exits non-zero printing `file:line [dept/vX/RULE-ID] title`. Adds `enforcement.ci_checks` schema key. `.github/workflows/bundle-enforce.yml` (triggers on `pull_request`, diffs vs base, runs the enforcer).
**Install (decision C):** the workflow on BOTH `agentic-sdlc` (dogfood — also closes the repo's ironic no-CI gap) AND `agentic-sdlc-delivery` (demonstrate — gates factory output).
**Value:** first real **red-X-on-a-PR** — the instant "governed" signal. Un-bypassable (fires even on a Coding Agent PR that skips the orchestrator). Zero-dependency, ships in isolation. Highest value-per-effort in the repo.
**Verify:** open a PR adding `password = "AKIA…16+chars"` → check fails red, cites `security/v0.1.0/SECRET-001`.

### PR-2 · The real verdict  ·  `add-autonomous-review-loop` task 0.0 + models
**Build:** replace the `findings = 0` stub in `stage_review_scan` with a real structured verdict. Reuse PR-1's matcher for the 2 deterministic rules; add `ReviewVerdict` + `Blocker` types to `models.py` (`status: PASS|FAIL`, `blockers[]` = check, rule-id, detail, file:line, `phi:bool`).
**Value:** kills the biggest honesty gap (the stub) AND produces the loop's load-bearing input. Shares the matcher with PR-1 (zero duplication — the reason floor-first is correct, not just "smallest first").
**Verify:** a run with a seeded violation shows a real FAIL verdict + cited blocker in the ledger, not a hardcoded pass.

### PR-3 · The bounded loop controller  ·  `add-autonomous-review-loop` Phase 0–2
**Build:** pure `plan_next_loop_action(verdict, attempt, tier, cost, has_phi_or_deny) -> {REMEDIATE|MERGE|AWAIT_HUMAN_MERGE|COMMENT_ONLY|ESCALATE}` (full truth-table unit tests, zero I/O). `run_review_loop` async glue. 3 ledger kinds (`review_remediation`, `loop_converged`, `loop_escalated`) added to BOTH LedgerEntry models. Attempt bound (`REVIEW_LOOP_MAX_ATTEMPTS`=3, unbounded rejected) + net-new per-run cost ceiling. `codegen.agent.md` remediation entry mode (verdict in → commit resolving only cited blockers → same-rule citation). Rule-ref→PHI/deny resolver (net-new; bridges blocker rule-ids to the `phi:true`/deny floor).
**Value:** the actual dark-factory engine — review→remediate→re-review, bounded, escalating. The showcase capability. Contains model variance (attempt bound + escalation), does not solve it.
**Verify:** seeded FAIL → remediation commit → re-review PASS → `loop_converged` chain in ledger (stubbed codegen OK for the slice). PHI blocker → `loop_escalated` (reason `tier_floor_phi`), never merged.

### PR-4 · Per-repo tier + merge primitive  ·  `add-autonomous-review-loop` Phase 1 + 3
**Build:** `config/repo_autonomy.yaml.example` + `repo_autonomy.py` (opt-in loader mirroring `config.py`/`heal.py` idioms; `tier_for(repo)`; `RepoTierUnlockError` fail-closed — Tier A refused for a repo with recent PHI/deny history, forced escalation at runtime; clean-history graduation precondition REQUIRED). Net-new merge primitive `PUT /pulls/{n}/merge` (branch-protection-aware; a blocked merge escalates, never silent-no-ops). `.github/hooks/pull_request.opened` trigger on the delivery repo. `review-loop-controller.agent.md` Foundry persona.
**Value:** "move the dial per repo" + human-out auto-merge on Tier-A. This is where it becomes genuinely autonomous where the customer decided it's safe.
**Verify:** Tier-A converged PR on delivery repo auto-merges; Tier-B awaits human; Tier-C/unlisted comments only. PHI blocker forces escalation regardless of tier.

### PR-5 · Observability (watch the dark factory)  ·  `add-autonomous-review-loop` Phase 4
**Build:** `/review-loop` page (live loops, attempt-timeline stepper, terminal-state chips, hop→ledger + real PR/commit deep-links). `/autonomy` per-repo tier panel (tier, why-capped, who-graduated, last-10 outcomes). Escalation inbox. DEMO-MODE fixtures for offline. LEFT-sidebar nav, URL-state filters, tonal buttons, `var(--*)` tokens.
**Value:** makes the human-out loop auditable/watchable without being in the merge path. The operator's demo surface. `npm run build` must pass — don't claim UI works from a green Python suite.

---

## Cross-cutting rules

- **CI on `agentic-sdlc` is missing** — YOU are the CI. Run full pytest suites (orchestrator/ledger-core/pipeline-doctor) + `tsc --noEmit`/`npm run build` locally before "green". PR-1 partly fixes this by adding the first workflow.
- **`gh pr create/edit` breaks on this repo** (Projects-classic `projectCards` deprecation). Use `gh api -X POST/PATCH repos/idanshimon/agentic-sdlc/pulls...`.
- **Copilot is the only reviewer** (solo repo, no CODEOWNERS). Request via REST.
- **Honesty guardrail:** every artifact labels net-new as net-new. Model variance is CONTAINED (bound + escalation), not SOLVED. Demo-mode replay is a fixture, not a live loop — say so.

## POST-IMPLEMENTATION (required, do not skip)
- [ ] Update the external presentation deck + talking-points (they live OUTSIDE this repo, in the customer-hub tree — never in this customer-neutral repo) — move the loop from "the frontier we'd build together" to "shipped, here it is running." Re-verify every live URL. The story changes from concept → working artifact once PR-3 lands.

## Sequencing
PR-1 → PR-2 (share the matcher) → PR-3 (the engine) → PR-4 (autonomy+merge) → PR-5 (UI) → deck/talking-points refresh.
PR-1 alone yields a demoable governed-PR signal in the first build session.
