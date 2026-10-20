# GitHub-first execution and the Decision Ledger

Status: source-grounded exploration; proposed integration, not a deployed capability claim.

## Finding

GitHub-first adoption is not a separate product idea. The repository already has an active `adopt-github-native-execution-substrate` change and source for decision recording, autonomy, remediation lifecycle and exact-state merge authorization. The new work should prove a small end-to-end integration rather than add another platform or duplicate those contracts.

Use GitHub for execution and repository controls; retain the project's decision-governance contracts. Persisting an agent's explanation is not itself governance. Governance exists when authorization and execution consult the applicable policy and evidence, and enforcement at the target boundary is demonstrated.

## Four-plane connection

- **Standards:** versioned bundles specify applicable policy and review requirements. GitHub workflow/agent versions are execution provenance; bundle versions are policy provenance. Instructions are not substitutes for enforced controls.
- **Pipeline:** a GitHub workflow, Copilot session or existing external pipeline can perform work. Do not require every adopter to run the nine-stage PRD generator. Existing CI/CD is the starting integration point.
- **Ledger + Doctor:** preserve decisions, alternatives, actor, policy references, gate reasons and links to external evidence; evaluate scoped precedent and propose governed improvements. The Doctor's live config apply path is currently a logging stub, not proven operational self-healing.
- **Agent runtime:** let the selected runtime own model/tool sessions. The ledger is neither a replacement conversation transcript nor a general-purpose vector memory service.

## Three decision families

1. **Engineering choice:** which diagnosis/repair approach should be used? Agent can propose options; record the material choice and concise justification with evidence.
2. **Authorization choice:** may this actor take this action on this target under this policy version? Derive authority from identity/policy and current state, not the agent's self-confidence or remembered preference. Observation, branch/PR creation, merge and production execution are separate permissions.
3. **Improvement choice:** does observed history justify reusing a precedent, changing a prompt, or proposing an autonomy/policy update? Improvement is itself governed work. A favorable history does not automatically grant new permissions.

Record meaningful choices and consequential actions, not every model token or internal thought. Preserve audit history; derive current state and lifecycle from records and external evidence.

## Illustrative integration slice: a failing CI job

This is a proposed scenario, not an already executed workflow.

1. Existing CI fails. An adapter records the source repository, workflow run, triggering commit, target environment and sanitized failure evidence.
2. A decision identifies whether the failure is actionable code, flaky testing, infrastructure, or a governance-sensitive change. An explicit permission envelope determines diagnosis-only versus proposed repair.
3. Copilot or another configured engine investigates and proposes a repair. Record the selected approach, alternatives presented, agent/session identity, policy citations and actual external artifact links. Do not invent machine-readable internal model reasoning when the runtime does not expose it.
4. GitHub contains the actual branch/PR and runs independent tests/scans. Repair findings can trigger a bounded follow-up, with a separate decision/action record for materially different attempts.
5. Admission evaluates the exact change and policy state. New commits, base changes or policy rotation invalidate the applicable prior authorization. Sensitive changes require the appropriate humans.
6. A deployment to a test target and original-failure retest provide verification evidence. Merge is not verification of production resolution.
7. An operator sees the original task, current blocker, responsible actor and safe next action from the combined evidence. Start with linked PR/check summaries; add a dedicated view only for a demonstrated navigation gap.
8. Outcomes can inform precedent evaluation. Separate agreement with a human decision from test success, deployed correctness, incident recovery and business impact.

## Memory versus the ledger

- **Runtime memory:** how to work in the repository, relevant conversation, prior investigation context. Useful context; may be incomplete or stale.
- **Decision record:** who chose what, alternatives, applicable policy, permission and evidence. A stored claim is not independent proof it happened.
- **Precedent:** a prior decision eligible for reuse in a comparable scope. Similar wording alone is insufficient.
- **Outcome projection:** what independently observed history says now. Do not overwrite prior decisions to make a metric appear populated.

Copilot memory does not replace governance history. Conversely, the ledger does not make a coding agent remember implementation context without a retrieval/tool integration.

## Verified local source and test evidence

Inspected on local `main` at `f9b0233`. No cloud or live GitHub state was inspected during this pass.

- `packages/ledger-core/ledger_core/models.py`: runtime/meta records; actor, bundle citations, typed gate reasons and rejected options.
- `apps/orchestrator/decision_record.py`: option and gate-reason helpers; confidence is evidence rather than admission authority.
- `apps/orchestrator/main.py`, `_run_autopilot`: classification/precedent-based resolution and read-time score integration.
- `apps/orchestrator/accuracy.py`: read-only agreement projection using replay scoring. This is NOT measured escaped-defect rate or proof of production correctness.
- `apps/orchestrator/merge_authorization.py`: exact-state authorization, drift refusal and supplied-snapshot governance checks. The module explicitly does not configure live GitHub protections.
- `apps/orchestrator/evaluation_path.py`: classification of governance-sensitive evaluation files; supplied inputs, not proof the protections are active remotely.
- `apps/orchestrator/remediation_lifecycle.py`: lifecycle, idempotency and reconciliation decision surface. Pure state behavior alone is not a running periodic reconciler or cross-system transaction.
- `.github/workflows/autonomous-review-loop.yml`: PR event dispatch to the existing external controller; no-op when its URL is absent. This is not evidence of an all-GitHub implementation.
- `apps/pipeline-doctor/pipeline_doctor/auto_fixer.py`: `_apply_config_change` logs a stub, while its ledger decision text says `auto-fix applied`. This path must not be presented as confirmed application. Future work should distinguish intent/proposal from executed and independently verified outcomes.

Executed:

```bash
PYTHONPATH=apps:packages/ledger-core .venv/bin/python -m pytest -q \
  apps/orchestrator/tests/test_decision_record.py \
  apps/orchestrator/tests/test_merge_authorization.py \
  apps/orchestrator/tests/test_evaluation_path.py \
  apps/orchestrator/tests/test_remediation_lifecycle.py \
  apps/orchestrator/tests/test_precedent_target_blindness.py \
  apps/orchestrator/tests/test_autonomy_threshold_grant.py
```

Result: **108 passed in 7.13s**. Local tests cover specified contracts; they do not establish live enforcement, successful deployment or incident repair. The target-blindness tests deliberately preserve evidence of a current defect; their passing is not closure of that defect.

## Priority finding: precedent is target-blind

The latest commit and source guards identify that precedent lookup uses `(team, ambiguity_class, slot_value_hash)` and class history uses `(team, ambiguity_class)`. The delivery target is resolved later than autonomy decisions. Therefore successful sandbox decisions can be indistinguishable from decisions for consequential destinations in the current lookup model.

Before extending to multiple applications or environments:

- resolve the target before the first autonomy decision;
- distinguish repository identity from a policy-defined target/risk class and environment;
- define when policy-version, action, data-sensitivity and target changes invalidate reuse;
- prefer deliberate scope compatibility rather than assuming either global reuse or one history per repository;
- preserve unknown historical scope as unknown; do not retroactively invent it.

A policy-defined `target_class` is a candidate, not an approved complete key. It must be specified and tested against concrete false-transfer and legitimate-reuse scenarios before implementation.

## Recommended sequence

**KEEP:** decision contracts, versioned standards, useful lifecycle/authorization logic, existing pipeline and audit UI.

**SWAP:** only the selected execution responsibility after its GitHub path passes the same acceptance checks. No wholesale orchestrator migration now.

**ADD:** a thin verified GitHub-event/evidence adapter; target-aware autonomy contract; real bounded repair handoff; exact-head check publishing; operator correlation; independently observed outcome ingestion.

**OUT:** new generic runtime/dashboard, automatic promotion from human-agreement scores alone, production auto-remediation before a bounded test-target proof, and reimplementing existing modules.

First implementation proposal should update the existing GitHub-substrate and delivery-target changes, reconcile their stale tasks with actual source, and define one CI-repair proof. Do not begin by migrating all generative stages. The first proof should include a stale-head rejection, duplicate event, human-required class and a target-change scenario, not just a happy-path fix.

## Open product decisions

1. First adopter: a fresh starter or an existing pipeline? Default proof: an existing ordinary CI pipeline in an approved disposable target.
2. First agent surface: choose supported trigger/identity/budget behavior after current product and organization-policy verification; do not assume cloud agent, CLI and Agentic Workflows share identical contracts.
3. Operator home: PR-first with deep-linked decisions and a precise check summary; retain the cross-run decision view rather than rebuild a session console.
4. Authority: begin with proposed repairs and human merge. Extend permissions per tested action/target class.
5. Success: resolved original defect, maintained gates, bounded spend/retries, reduced human effort and traceable evidence—not PR volume.

No code, workflows, settings, commits, pushes or deployments were changed during this exploration. Documentation was added only.
