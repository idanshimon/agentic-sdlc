# Proposal: redesign the decision lifecycle as the enterprise control plane

> **Status:** DRAFT
> **Capabilities:** pipeline, ledger, agent-hq-integration, telemetry

## Why

The current product exposes the right primitives, but as separate implementation-shaped surfaces: a run timeline, gate cards, a global ledger table, a review-loop page, GitHub pull requests, and configuration catalogs. Operators must reconstruct the actual decision lifecycle themselves.

A governed enterprise workflow needs one coherent answer to five questions:

1. What needs a decision now?
2. Why did the system stop or continue?
3. What evidence and policy bound the choice?
4. What changed downstream because of it?
5. Where is the durable GitHub artifact and approval record?

The live run surface currently demonstrates the gap. It can show a terminal `failed` status while completed stages remain green, without a prominent failure explanation or recovery action. Generated test/code payloads can remain labeled `(pending)` because the artifact panel reads demo fixtures rather than the live event contract. The global Decisions page cannot be deep-linked to one run. Gate decisions and after-the-fact audit entries use different visual models. GitHub Agent sessions and pull requests are adjacent rather than linked as the durable execution backend.

The platform should not replace GitHub's agent/session, branch, pull request, checks, ruleset, Actions, model, or repository administration surfaces. It should provide the differentiated governance control plane above them: typed decisions, policy evidence, autonomy envelopes, cross-repository posture, and durable lineage.

## What changes

### 1. One decision lifecycle contract

Every decision becomes a lifecycle object with stable identity and linked phases:

- `proposed`: agent recommendation, alternatives, confidence, evidence, policy citations
- `required`: gate class, deadline, owner/role, autonomy tier, blocking reason
- `resolved`: selected option or operator-authored resolution, actor, timestamp, approval path
- `applied`: downstream stages/artifacts/checks affected by the resolution
- `verified`: tests, policy checks, review verdict, and GitHub check/PR references
- `learned`: precedent reuse, flag, replay, pause, or autonomy-policy consequence

Existing append-only ledger rows remain the source evidence. The lifecycle object is a derived read model, not a mutable replacement for audit history.

### 2. Runtime UX becomes an operator workspace

The run page is reorganized into:

- a compact run command bar with terminal status, current/failed stage, owner/team, autonomy posture, GitHub session/PR, and the one next action
- a stage rail where each stage expands to its inputs, agent/model, prompt version, decisions, output artifact, checks, duration, and cost
- an attention queue that appears above chronology and groups required decisions by risk and deadline
- a decision workbench with Evidence / Options / Policy / Downstream impact / History tabs
- a terminal outcome panel for failed, escalated, or completed runs with explicit reason and recovery action
- artifact availability derived from the live producer contract, never demo-only fixture state

Raw events remain available as diagnostics, but are not the primary operating surface.

### 3. Post-runtime UX becomes a decision registry

The Decisions page becomes a URL-addressable master-detail registry:

- URL state for team, repo, run, stage, lifecycle state, risk, policy, actor, and time range
- saved views such as `Needs attention`, `Recently resolved`, `Policy exceptions`, `Reused precedents`, and `Failed verification`
- a stable detail pane that renders the same decision workbench used at runtime, plus applied/verified/learned lineage
- links to the exact GitHub session, branch, commit, pull request, check run, ruleset result, agent profile SHA, prompt SHA, and standards bundle versions

### 4. GitHub remains the execution and collaboration backend

Delegate to GitHub:

- agent session research/planning/implementation
- ephemeral or self-hosted runner environments
- branches, commits, pull requests, reviews, checks, Actions, rulesets, CODEOWNERS, and merge queue
- custom-agent distribution, repository instructions, skills, hooks, MCP configuration, model selection, and repository settings
- native agent session tracking and automation where its visibility/versioning constraints are acceptable

Retain in this control plane:

- cross-repository policy and autonomy posture
- typed enterprise gates and hard-gate classes
- decision-level audit and policy evidence
- bounded review/remediation loops and escalation floors
- cross-surface lineage between runtime decisions and GitHub evidence
- enterprise reporting on decision quality, exceptions, rework, cost, and autonomy graduation

GitHub-native automations are not the canonical enterprise workflow definition because they are user-private and not versioned in Git. Deterministic work remains GitHub Actions. Agentic automation definitions that require shared governance are represented as repository files and/or generated from governed configuration.

### 5. First production slice

This change begins with the highest-trust defects visible in the live system:

1. Derive architecture, test plan, implementation, tests, decisions document, and delivery references from live stage events.
2. Never label an emitted artifact `(pending)`.
3. Surface terminal failure cause and recovery action above the event stream.
4. Add run-scoped deep links from a run to Decisions and make the Decisions filters URL-backed.
5. Ensure delivery writes generated pytest code to `tests/test_main.py`, not the markdown test plan.

## KEEP / SWAP / ADD / OUT

### KEEP

- four-plane architecture
- append-only runtime/meta ledger
- hard-gate and graduated-autonomy enforcement on the server
- standards bundles, prompt/version chain, custom agents, hooks, MCP, and OpenSpec
- GitHub pull requests and checks as durable collaboration evidence
- SSE plus polling fallback
- dense table-first operator surfaces

### SWAP

- implementation-shaped event feed as the main run UX → decision-first stage workspace
- demo-fixture artifact lookup → canonical live artifact projection
- global in-memory-only decision filters → URL-backed scoped registry
- disconnected run, ledger, review-loop, and PR views → shared lifecycle lineage
- generic `failed` badge → classified terminal outcome with cause and recovery

### ADD

- derived decision lifecycle read model
- attention queue and ownership/SLA metadata
- GitHub evidence references on decisions and stages
- cross-repository governance posture and saved views
- outcome/recovery panel
- producer/consumer contract tests for live artifacts

### OUT

- rebuilding GitHub Agent HQ/session management
- replacing pull requests, Actions, rulesets, checks, or merge queue
- mutating historical ledger entries to improve display
- customer-specific terminology or policy
- changing canonical standards bundles in this change

## Risks and rollback

- **Risk:** a derived lifecycle projection hides raw evidence. **Mitigation:** every lifecycle field links to its source ledger/event/GitHub record; raw events remain available.
- **Risk:** GitHub preview surfaces change. **Mitigation:** isolate GitHub adapters and persist stable URLs/IDs plus source type; never model preview UI labels as domain truth.
- **Risk:** URL filters expose unsupported cross-team reads. **Mitigation:** server-side token/team enforcement remains authoritative; the UI can only narrow the readable scope.
- **Risk:** broad redesign delays visible value. **Mitigation:** ship the first production slice independently behind existing routes and preserve current raw-event fallback.
- **Rollback:** remove the new projections/components and restore the prior event/artifact renderers. No ledger history or GitHub artifact is rewritten.

## Test targets

- UI pure-function tests for event-to-artifact projection and terminal outcome classification
- UI tests for URL decision filter parsing/serialization
- orchestrator tests proving generated test code is delivered to `tests/test_main.py`
- TypeScript typecheck and production build
- OpenSpec strict validation
- live browser proof against an existing failed run and a fresh run
