# Independent review disposition — Mission Control foundation

## Review identity and boundary

Completed Claude Opus 5.5 through GitHub Copilot CLI with `--reasoning-effort high`. Actual model/provider verified in `usage-opus55.json`; 9,236 reasoning tokens reported, zero code changes. The initial Opus 4.8 attempt was unavailable and made no inference call; both attempts are preserved. The reviewer received the numbered frozen 17-file change plus selected baseline source, not a full private implementation audit. Manifest SHA-256 hashes still match every reviewed change file.

Raw critique: `raw-review-opus55.txt`. Frozen inputs: `snapshot/`, `source-evidence/`, `review-prompt.md`. Execution evidence: `execution-verification.json`.

**Verdict:** the intended outcome survives, but the draft is not ready to implement as an integration blueprint. Some load-bearing contracts are named rather than resolved, and the expanded product journey was not reconciled into milestone gates. Structural validation did not catch those semantic defects.

## Findings and parent adjudication

### F1 — Automatic admission versus human-only merge evaluator

**Confirmed baseline/design mismatch.** `merge_authorization.py:254–275` counts independent humans and refuses agent-authored work without one, even `required_approvers=0`. OP-03 promises a qualifying automatic release path; wiring this evaluator unchanged cannot supply it. The pure local probe returned `agent_self_approval`.

**Additional confirmed API weakness, not a demonstrated live exploit:** `provenance_verified=True`, `budget_remaining=1`, `active_remediations=1` are defaults. A valid human approval with all three omitted is permitted by the pure function. This contradicts a blanket claim that missing evidence is always refused. Production call-path reachability was not established; local search found test uses and the definition rather than verified runtime wiring.

**Recommended: ADOPT WITH MODIFICATION.** Define an explicitly authorized policy-admission path bound to exact target/change/policy/envelope state, distinct from human approval; retain hard human-required classes. Missing trust/budget/concurrency evidence must refuse. Reconcile owning requirements before implementation, never fabricate human approvals or relabel an agent as a human. Do not adopt an unsigned generic policy record as sufficient authority merely because the reviewer proposed it.

### F2 — Initial acceptance-oracle ownership

**Confirmed present design omission.** PB-02 generates tests and GD-02 protects changes to already protected tests, but the draft does not say who approves initial acceptance, how it becomes protected, or how a weak generated test fails readiness. Protecting test edits does not solve self-authored success criteria.

**Recommended: ADOPT WITH MODIFICATION.** Review/attribute product acceptance and register the authoritative evaluation artifacts, their versions and change ownership before they can establish completion. Demonstrate tests detect the intended missing/incorrect behavior. Agent-generated unit/regression tests remain useful and may count after independent review/validation; do not blanket-discard all implementation-PR tests or require a human signature on every test file. Review depth must follow selected policy, not silently impose a Governed profile on Simple.

### F3 — Admission/check authority and execution credential separation

**Confirmed missing normative boundary; remote exploit NOT demonstrated.** GH-04 names trusted publishers but does not prohibit giving authoring work the publisher/merge credential. App-bound does not inherently mean independent. The reviewer describes a credible failure scenario, not an observed active credential configuration.

**Recommended: ADOPT WITH MODIFICATION.** Specify author versus verifier/admission versus executor capability boundaries, trusted workloads and who can obtain credentials. Prove the agent environment cannot mint an accepted admission result or perform an unauthorized merge/deploy. Three separately deployed services or three GitHub Apps are not automatically required; select a topology after capability discovery and test its actual boundaries. A permitted mechanical output handler is not the same as giving the reasoning process merger credentials.

### F4 — Simple has no concrete reference topology

**Confirmed deliverability gap; PARTIAL on the reviewer's framing.** The draft explicitly permits independent module selection, so Simple does not categorically forbid monitoring/repair. However it still postpones selecting its minimum receipt backend/topology and leaves adaptation of existing mandatory requirements unresolved. Claiming a light footprint without choosing/proving a supported composition is premature.

**Recommended: ADOPT the topology/conformance obligation; MODIFY profile interpretation.** Choose one deployable Simple reference with components GitHub supplies versus components we host, receipt append/conditional-write/restart/export guarantees, owner/usage footprint and absent-module proof. Keep optional test-target monitoring/repair available without forcing Team. No claim that GitHub comments/branches natively supply the required concurrency contract until tested.

### F5 — Target-aware precedent must gate recording/eligibility, not only later reuse

**Confirmed baseline defect plus sequencing risk, not evidence of actual production data contamination.** The existing target-blind tests deliberately pass while preserving this defect. The expanded preview/production journey could create mixed history before target-aware reuse is implemented.

**Recommended: ADOPT WITH MODIFICATION.** Resolve/stamp application/environment/target-policy scope at decision creation. Unknown-scope records remain auditable but ineligible to grant scoped autonomy; do not delete or manufacture their history. Make this a prerequisite before multi-target precedent-forming collection/use, not a vague future cross-target automation step. Use compatibility rules rather than assuming all production targets or all repos are equivalent.

### F6 — Expanded journey is not in the milestone gates

**Confirmed present planning defect.** D12–D15 and task groups 10–12 describe greenfield bootstrap, continued backlog work and operational repair; D10/acceptance exits still define only the earlier M0–M4 repair roadmap. Both lists are plausible individually but their dependencies/completion conditions are not joined.

**Recommended: ADOPT.** Reconcile explicit gates for greenfield readiness, approved-task continuation, incident-to-repair/retest and one qualifying automatic release on a test target. Keep initial human-merged proof as a separate earlier gate. Do not label that gate the full self-propelled product. Production automatic release remains later, with explicit owner approval and recovery proof.

## Changes I would reject or defer

- Reject blanket exclusion of agent-authored tests; protect the authority/independent evidence, not the ability to generate useful tests.
- Reject requiring three Apps/services solely to satisfy an identity diagram; require tested privilege isolation and choose the smallest supported implementation.
- Reject dropping Archify/graph experience from the product by default. Keep a source-grounded authored explainer in the first integrated slice; expand live exploration with actual evidence. Pure UI decoration must not displace control correctness.
- Defer production automatic release until test-target admission/identity/target/rollback proofs and explicit permission pass. Do not permanently replace the requested autonomous outcome with human-only PRs.
- Defer optional custom model hosting, Doctor execution and broad discovery until their measured need/readiness trigger. Do not impose them on Simple.
- Retention/privacy/access obligations remain applicable from the start; optional advanced compliance UI/export integrations can wait for their adopter trigger. Do not interpret the review's deferred Governed overlay as permission to postpone required data controls.

## Minimum coherent integrated release to specify

One repo and one known app template; one concrete light topology and conforming receipt backend; approved goal/acceptance ownership; scoped author/admission/executor capabilities; target-stamped decision evidence; single-concurrency eligible backlog controller; CI/preview/external health; incident-to-regression/fix/review/retest; list/workbench plus one Archify explanation. Prove human-merged flow first, then a separately approved automatic merge/release class on the test target. This preserves the user's vision while making the first delivery falsifiable.

## Verification performed

- Read strongest findings against current source/spec text rather than accept the review as authority.
- Executed pure evaluator probes: zero-human agent merge is refused; omitted provenance/budget/concurrency inputs with valid human evidence are accepted by defaults.
- Ran `test_merge_authorization.py` and `test_precedent_target_blindness.py`: **34 passed in 2.46s**. Passing target-blindness guards documents the defect; it does not fix it.
- Reviewed input artifact hashes unchanged. No underlying spec/code, remote setting, commit, push or deployment was modified by this review.

These are recommendations for user review. No automatic merge of the critique into the specification has occurred.
