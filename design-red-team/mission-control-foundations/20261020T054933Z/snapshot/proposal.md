# Agentic Mission Control foundations

Status: DRAFT — foundation sketch for review, not approval to implement or deploy.

## Why

Progressively agent-driven applications need more than issue-to-PR automation. An operator needs to understand what is happening, what requires a decision, what an agent may do, and whether an intervention actually helped. The existing project supplies substantial decision/governance contracts but still exposes disconnected execution and evidence surfaces. GitHub-first execution should compose with these contracts rather than create a parallel platform.

The product promise is: **describe the application, define success, select capabilities and grant bounded authority; receive a verified application-development-operating loop, not just a scaffold.** Bootstrap creates three connected foundations: the application and acceptance criteria, the development loop advancing approved goals, and the post-deployment loop detecting, repairing and verifying problems. Existing applications can adopt the same contracts incrementally.

Mission Control is the operator home for that lifecycle, with explorable architecture and decision graphs, an attention-first queue and attributable commands. A diagram is an explanation, not authority. Autonomous repair may include merge and deployment only where an explicit action/target policy permits it; other changes stop at a proposed PR or require human decisions. Initial proof remains bounded and human-merged before production autonomy is enabled.

## What Changes

- Define a plain-language project request and reviewed success/authority contract, with a concrete walkthrough in `bootstrap-journey.md`.
- Bootstrap application code/specs, an approved milestone backlog, test/deployment workflows, runtime monitoring and a versioned resource/permission plan together.
- Specify continued development from eligible backlog tasks, not merely a one-time issue-to-PR request.
- Specify post-release incident diagnosis, code/runbook remediation, policy-permitted release and original-symptom verification.
- Define shared foundation infrastructure versus per-application resources, ownership and a readiness certificate based on executed probes—not file generation.

- Define a mission-control workspace that composes existing runs, decisions, review loops, repository posture and external evidence.
- Define a scoped GitHub connection and command boundary, with explicit permissions, revocation, event reconciliation and capability discovery.
- Define typed decision-model routing alongside generative investigation, deterministic facts and policy authorization.
- Define target-aware autonomy envelopes and a durable propose/authorize/execute/verify action lifecycle.
- Define useful memory and comparable precedent without letting remembered preferences override policy.
- Define source-grounded architecture, execution and decision graphs using Content Creator/Archify for authored explanations and suitable existing graph components for live data.
- Define adoption assessment, progressive proof slices, outcome evaluation and rollback.
- Add composable operating profiles, dependency-resolved feature activation and a bootstrap-generated instruction/workflow set. Simple teams can run a small foundation; stronger governance is an explicit overlay rather than a universal deployment burden.
- Reconcile adjacent OpenSpec work rather than assuming draft task counts represent implementation status.

## Capabilities

### New Capabilities

- `mission-control-workspace`: coherent attention queue, decision workbench, repository operations and accountable user interaction.
- `github-repository-control`: installation-scoped connection, evidence adapters, reconciliation and governed GitHub commands.
- `governed-decision-routing`: typed judgment, investigation, deterministic authority and independently evaluated model selection.
- `autonomy-action-execution`: target-aware permission envelopes and bounded, recoverable action execution.
- `decision-memory-outcomes`: scoped context, precedent and independently observed outcome feedback.
- `evidence-graph-views`: provenance-backed architecture/decision/execution projections and safe presentation integration.
- `foundation-configuration`: composable profiles, activation/dependency validation, threshold semantics and reproducible instruction/workflow bootstrap.
- `incremental-adoption`: existing-pipeline assessment, progressive delivery slices and acceptance evidence.

- `project-bootstrap`: intent-to-plan-to-generated-application lifecycle, infrastructure plan and executed readiness proof.
- `goal-driven-development`: bounded progression through an approved dependency-aware backlog, independent acceptance and product escalation.
- `operational-repair`: external monitoring, incident correlation, code/runbook repair, policy-permitted release, recovery proof and outcome feedback.

These are composition contracts. They do not supersede existing ledger, pipeline, standards-bundle or delivery requirements. Existing behavior changes must be reconciled in their owning changes before implementation.

### Modified Capabilities

None in this draft. Ledger schema, target classification, auth, runtime and existing route changes will receive explicit deltas in the owning changes when concrete integration contracts are selected.

## Impact

Proposed integration seams include `apps/ledger-insights-ui`, `apps/orchestrator`, `packages/ledger-core`, `.github/workflows`, existing GitHub adapters and the adjacent changes listed in design.md. Specific routes/schema fields remain design decisions, not invented existing APIs. Content Creator is build-time/presentation tooling, not a new mandatory production service. No dependency, workflow or repository setting changes in this drafting pass.

## KEEP / SWAP / ADD / OUT

- **KEEP:** four planes, append-only decision evidence, standards bundles, proven local decision/authorization contracts, current UI theme and working adopter CI/CD.
- **SWAP:** disconnected operational projections and selected execution responsibility only after equivalent proof; never wholesale backend replacement.
- **ADD:** scoped GitHub adapter, target-aware permissions, cross-system correlation, model judgment contracts, graph projections and adoption/evaluation guidance.
- **OUT:** a replacement Git forge/session console, a new agent framework, unrestricted self-modification, initial production auto-remediation, model training or a single-vendor mandate.

## Safety Impact

This dashboard is a privileged command surface. Server-side identity, tenant/repository scope, independent admission, protected evaluation paths and explicit action authority are required. Untrusted reports, logs, repository content and recalled memory cannot authorize actions. Explain/tour/export/graph-selection paths never mutate a repository or start paid work. Future write authorization is separate from this proposal's documentation-only scope.

## Rollback Plan

Draft rollback removes this change only; it does not alter existing evidence. Implementation uses per-adopter/per-pattern flags with observe-only fallback, disconnect/revoke and event reconciliation. Disabling the UI must not disable required checks or strand already-dispatched actions. A pending accepted command remains tracked to an acknowledged terminal disposition; rollback never erases its history.

## Test Targets

Requirement-linked adapter/authorization/projector/model-contract tests; existing decision and merge-authorization tests; browser interaction and graph-verification suites; controlled GitHub test-repository acceptance; deployment/original-task retest. See acceptance.md. Structural OpenSpec validation is not runtime proof.
