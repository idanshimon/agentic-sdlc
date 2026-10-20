# GitHub-first incremental agentic SDLC adoption

Status: exploration direction and proposed proof slices; not an implemented capability inventory or approved architecture change.

## Objective

Develop a reusable foundation for deploying agentic SDLC into new projects and incrementally adapting existing pipelines. Prefer GitHub workflows and GitHub Copilot where they meet the requirement. Preserve useful architectural patterns independently of the original runtime or vendor. Do not treat prior reservations about migration or fragmented interfaces as reasons to stop evaluating GitHub-native execution.

Long-term direction: increasingly agent-driven application delivery and operations. Near-term method: narrow, measured delegation with explicit permissions, independent evidence and recoverable execution. Autonomy is graduated per action and risk class, not one repository-wide switch.

## Two adoption paths

- **Existing pipeline:** discover the real pipeline and owner boundaries; retain working CI/CD and controls; add one bounded agent loop at a verified integration point.
- **New project:** offer a minimal starter of workflow contracts, agent instructions, admission checks, evidence links and operator guidance. Reuse the canonical project's proven components where appropriate; do not assume its entire orchestrator/UI is required.

## Scope

- **KEEP:** working CI/CD, tests, scanners, repository controls, deployment ownership, and existing governed-remediation contracts after inspecting their implementation.
- **SWAP:** custom execution/orchestration only when a GitHub-supported alternative proves equivalent requirements and allows retirement of the old responsibility.
- **ADD:** selected event-to-agent handoffs, bounded review/repair, exact-head evidence, useful memory, operator correlation and progressive permission envelopes.
- **OUT:** immediate production autonomy, a new generic agent runtime/dashboard, assumed native feature support, wholesale replacement of an incumbent pipeline, or customer-specific implementation details.

## Research questions

Map every component to native GitHub, Copilot-specific, Agentic Workflows, custom integration or external runtime. Verify current documentation and actual repository/organization settings before adopting a claim. Cover event triggers, agent execution, review-to-repair handoff, permission identity, memory/state, limits/recovery, admission, deployment/retest and the operator experience. Identify preview/license/policy restrictions and residual external services. Avoid combining multiple product benefits into a fictional single turnkey system.

## Proposed proof sequence

1. **Observe and explain:** analyze a real pipeline failure, correlate logs and commits, and produce an evidence-backed diagnosis. No code/deployment write authority.
2. **Propose a repair:** for a selected failure category, create a PR with a regression check and recorded evidence. Human merge remains required. Treat flaky tests, infrastructure outages and untrusted logs separately from reproducible code defects.
3. **Bounded review and repair:** route explicit blocking findings back to the author, rerun appropriate checks on new commits, stop on an enforced budget and escalate. Do not allow the author to redefine its admission policy.
4. **Restricted automatic admission:** only for an explicitly approved low-risk class with independent checks, current-head evidence and a revoke/stop path. First audit whether the canonical governed-remediation implementation already supplies this contract.
5. **Controlled operational remediation:** start with an approved runbook action, canary/sandbox and verified recovery condition. Distinguish runbook execution from source-code repair and production deployment. Rollback authority must itself be scoped and tested.

Do not advance automatically based on a successful demonstration. Advancement needs an explicit policy decision supported by comparable outcomes for the chosen action class.

## First candidate experiment

Use a disposable repository or approved test target with an existing ordinary CI pipeline and a known reproducible code defect. Attempt: failed CI → diagnosis → fix PR → independent regression checks → review → bounded repair if needed → human merge → test-environment verification.

This is a proposed experiment, not an executed result. Discover current product triggers and permissions before selecting the mechanism. A failed workflow must not be blindly rerun with privileged credentials or trusted as agent instructions.

Acceptance evidence: correct original-task resolution; before/after regression result; traceable task/session/PR/commit/check links; stale-evidence rejection after a new commit; enforced attempt/time/cost limits; duplicate-event safety; visible stop/escalation; no agent control of its own gate. Record actual human intervention and total accepted-change cost rather than claiming success from PR count or green aggregates alone.

## Expected reusable outputs

- Current GitHub/Copilot capability and integration map, with native/bridged/unsupported distinctions.
- Incremental-adoption assessment for an existing pipeline.
- Small verified starter/workflow patterns rather than another monolithic platform.
- Permission/autonomy envelopes and executable acceptance/failure scenarios.
- Evidence-backed demonstrations and an operator runbook explaining status, blockers and safe next actions.

## Relationship to current implementation

This direction extends the canonical customer-neutral project; it does not reset its roadmap or assert existing features are missing. Inspect active and archived OpenSpec changes and current source before implementation. Architecture/stage/schema changes require the repository's proposal and validation process. No workflow, repository setting, cloud resource, commit, push or deployment was changed by recording this direction.
