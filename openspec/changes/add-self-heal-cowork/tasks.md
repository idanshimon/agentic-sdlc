# Tasks — add-self-heal-cowork

> **Status:** DRAFT (2026-06-17). Scope is intentionally staged: the slice
> in section 0 proves the loop end-to-end before any of the broader action
> types or the mid-run gate trigger are built.

## 0 — Thinnest slice: heal a failing codegen stage (prove the loop)

- [x] 0.1 Define the heal-session data model: `HealSession`, `HealProposal`, `HealDecision`, `HealExecution` (heal_id ties the chain)  *(apps/orchestrator/heal.py — HealProposal/HealDecision/HealExecution, heal_id chain)*
- [x] 0.2 Extend `LedgerEntry` kind enum with `heal_proposed`, `heal_decided`, `heal_executed`  *(packages/ledger-core/ledger_core/models.py RuntimeKind)*
- [ ] 0.3 Orchestrator endpoint `POST /api/runs/{run_id}/heal` — opens a heal session scoped to a terminal run, returns heal_id
- [ ] 0.4 Orchestrator endpoint `GET /api/heal/{heal_id}/stream` — SSE stream of the cowork session (reuse run-stream SSE plumbing)
- [ ] 0.5 Orchestrator endpoint `POST /api/heal/{heal_id}/approve` — human approves a specific proposed action
- [ ] 0.6 Cowork-brain integration: Foundry agent that reads ledger + run state, proposes ONE action type (`assign_code_heal`), cites precedent
- [ ] 0.7 Executor integration: dispatch the approved code heal to the GitHub Copilot coding agent (opens a PR), capture the PR URL
- [ ] 0.8 Write `heal_proposed` → `heal_decided` → `heal_executed` chain to the ledger with shared heal_id
- [ ] 0.9 UI: "Review & heal" affordance on the run-detail page for terminal runs
- [ ] 0.10 UI: heal-session panel (extend AssistantPanel) — streaming diagnosis, the proposed diff, an Approve button, an "open in GitHub" link
- [ ] 0.11 E2E: a real failed-codegen run → open heal → approve → real PR opens → ledger pins the chain

## 1 — Action validation + safety

- [x] 1.1 `heal_validator.py` — per-action approval required, PHI-class hard block, deny-rule block (shares the boundary with pipeline-doctor's envelope_validator)  *(apps/orchestrator/heal.py::validate_heal_action — reuses ledger_core INVARIANT_CLASSES; 15 tests green)*
- [ ] 1.2 `onPermissionRequest` enforcement point so no write action executes without explicit human approval
- [ ] 1.3 Feature flag `heal.actions_enabled` — when false, the panel is read-only (graceful degradation to the existing assistant)

## 2 — Tests

- [x] 2.1 `test_heal_validator.py::test_phi_rule_heal_blocked` — failing test first  *(test_heal.py::test_phi_touching_heal_escalates_not_blocks_silently + test_phi_classification_target_class_escalates)*
- [x] 2.2 `test_heal_validator.py::test_deny_rule_heal_blocked`  *(test_heal.py::test_deny_rule_pattern_is_hard_blocked)*
- [x] 2.3 `test_heal_validator.py::test_action_requires_human_approval`  *(test_heal.py::test_no_validator_outcome_ever_bypasses_human_approval — property test across all action types)*
- [x] 2.4 `test_heal_session.py::test_open_session_only_on_terminal_run`  *(test_heal.py::test_run_end_heal_requires_terminal_status + test_run_end_heal_rejects_running_status)*
- [x] 2.5 `test_heal_session.py::test_no_session_from_drift_signal_alone`  *(test_heal.py gate/run-end guards — assert_human_invoked rejects non-human-invoked moments)*
- [x] 2.6 `test_heal_ledger.py::test_proposed_decided_executed_chain_shares_heal_id`  *(test_heal.py::test_heal_chain_shares_heal_id)*
- [x] 2.7 `test_heal_ledger.py::test_heal_decided_carries_human_actor`  *(test_heal.py::test_heal_chain_shares_heal_id asserts approver_id)*
- [x] 2.8 `test_heal_executor.py::test_code_heal_opens_pr_not_direct_commit`  *(test_heal.py::test_heal_chain_shares_heal_id asserts result_ref is a /pull/ URL)*
- [ ] 2.9 `test_heal_executor.py::test_pr_url_pinned_in_heal_executed_entry`  *(needs the executor integration — section 0.7)*
- [ ] 2.10 Integration: synthetic failed run → session → approve rerun_stage → 3-entry chain  *(needs the endpoints — section 0.3–0.5)*

## 3 — Broader action types (after the slice proves out)

- [ ] 3.1 `rerun_stage` — re-run a failed stage with same inputs (idempotent, in-envelope auto-allowed but still human-approved)
- [ ] 3.2 `reprompt_stage` — bump a prompt-library version + re-run (prompt PR + approve)
- [ ] 3.3 `bump_bundle_rule` — route through pipeline-doctor's PROPOSE-CHANGE path (committee merges)
- [ ] 3.4 `adjust_autopilot` — tune a confidence threshold within the finops envelope (PHI never)

## 4 — Mid-run gate trigger (after end-of-run trigger proves out)

- [ ] 4.1 "Heal / cowork" affordance on the resolver gate panel
- [ ] 4.2 "Heal / cowork" affordance on the design-review gate panel
- [ ] 4.3 A heal session opened at a gate can modify the gate's inputs (e.g. fix the prompt that produced a wrong card) before the human approves the gate
- [ ] 4.4 E2E: open a heal at the resolver gate → reprompt the assessor → re-surface corrected cards → approve the gate

## 5 — Learning loop (heal becomes precedent)

- [ ] 5.1 A `heal_executed` entry is queryable as precedent by signal signature
- [ ] 5.2 Graduated autonomy surfaces a prior matching heal at the gate for one-click confirmation
- [ ] 5.3 Within-envelope heals (e.g. rerun_stage) can be auto-proposed (still human-confirmed) when precedent confidence is high

## 6 — Custom agent file + governance

- [ ] 6.1 `.github/agents/heal-cowork.agent.md` — Foundry-registered persona, action allow-list, ledger entry types it can write, bundle subscriptions
- [ ] 6.2 Frontmatter validates against `.github/agents/agent-frontmatter.schema.json`
- [ ] 6.3 AGENTS.md update: document the deliberate, gated relaxation of the "AssistantPanel is read-only" boundary for heal sessions

## Verification (definition of done)

- [ ] `openspec validate add-self-heal-cowork --strict` → Valid
- [ ] The slice (section 0) works end-to-end on the live deploy: a real failed-codegen run heals into a real PR, ledger pins the 3-entry chain
- [ ] PHI-rule and deny-rule heals are provably blocked at the validator (tests + a manual attempt that gets rejected)
- [ ] No heal session can be opened except by explicit human action at a gate or terminal run
- [ ] Every write action in a heal session required an explicit human approval, recorded in the ledger
