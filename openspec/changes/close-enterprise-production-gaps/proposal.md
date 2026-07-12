# Proposal: close enterprise production gaps

> **Status:** DRAFT
> **Capabilities:** pipeline, ledger, agent-hq-integration, deployment, telemetry
> **Composes:** `redesign-decision-lifecycle-control-plane`, `add-autonomous-review-loop`, `add-bundle-ci-enforcement`, `add-agent-hq-integration`, `swap-deliver-ado-to-github`

## Why

The reference design now presents a coherent decision lifecycle, but several executable paths remain weaker than the product contract:

1. Mutating APIs do not establish authoritative user/workload identity and can trust client-supplied actors.
2. Provider failures can become synthetic stub output and continue to GitHub delivery.
3. The GitHub autonomous-review workflow calls a missing dispatch endpoint and does not use its configured token correctly.
4. Persisted run snapshots do not provide resumable execution because input, gate signals, cursor ownership, and leases remain process-local.
5. Gate decisions lack command idempotency and optimistic concurrency.
6. SSE reconnect does not guarantee a new connection.
7. Review-loop identity and terminal disposition are not structured strongly enough for multiple PRs/commits in one repository.
8. Workflow files exist, but the repository does not prove that GitHub requires their checks.
9. Reviewed and delivered artifacts lack one immutable manifest/hash contract.
10. Assurance dimensions are collapsed into overly broad PASS/failed language.

These are product gaps, not polish. Closing them makes the reference safe to adopt as an enterprise operating pattern while retaining GitHub as the execution and repository-control backend.

## KEEP / SWAP / ADD / OUT

### KEEP

- GitHub for agent sessions, branches, pull requests, Actions, checks, rulesets, reviews, and merge.
- Four-plane architecture and immutable Decision Ledger.
- Existing standards bundles, hard-gate floor, model policy, prompt lineage, and review-loop policy kernel.
- Current FastAPI/Container Apps deployment for this production-hardening phase.

### SWAP

- Client-supplied actor identity → authenticated principal derived server-side.
- Implicit permissive local access → explicit `AUTH_MODE=disabled|headers|entra` execution profile, with production refusing disabled mode.
- Unconditional provider stub fallback → production fail-closed plus explicit demo/test stub profile.
- Process-local gate release as authority → durable gate command/checkpoint with local event only as a wake-up optimization.
- Duplicate/unversioned approval writes → idempotent commands with expected run/gate version.
- Repository-only review-loop grouping → structured loop ID keyed by repo, PR, and head SHA.
- SSE close-on-error → explicit reconnect state machine.

### ADD

- Role/team authorization for operator, persona owner, standards reviewer, release manager, admin, and GitHub workload.
- Authenticated review-loop dispatch endpoint with replay-safe idempotency.
- Durable run input/checkpoints, leases, and resume worker contract.
- Immutable artifact manifest and SHA-256 verification from review through delivery.
- Separate assurance dimensions: deterministic policy, build/tests, dependency/SBOM/secrets/SAST, semantic review, mandatory-human requirements.
- GitHub governance files and verification tooling: CODEOWNERS, cloud-agent setup workflow, required-check/ruleset verifier, immutable Action references.
- Security, operations, deployment, recovery, and known-limit documentation.

### OUT

- Rebuilding GitHub Agent HQ, Actions, rulesets, pull requests, or merge queue.
- Claiming live branch protection/rulesets are configured until verified through GitHub APIs.
- Replacing the orchestrator with a new external workflow engine in one change.
- Weakening PHI/auth/deny escalation floors.
- Encoding customer-specific identities, policy, or deployment names.

## Delivery plan

### Phase 0 — Contract and baseline

- Strict OpenSpec artifacts and acceptance tests.
- Record clean package test/build baselines.
- Add a production-readiness report command that distinguishes code-complete from live-admin configuration.

### Phase 1 — Trust boundary

- Add authentication middleware/dependencies and typed principal/role model.
- Derive actor/team from principal claims.
- Authorize every mutating route.
- Add separate GitHub workload authentication for review-loop dispatch.
- Keep local tests explicit via `AUTH_MODE=disabled`; production manifests set a non-disabled mode.

### Phase 2 — Fail-closed execution and artifact integrity

- Add execution profiles (`production`, `demo`, `test`).
- Production provider failure emits typed failure evidence and terminates the run.
- Stub/synthetic results carry explicit provenance and delivery refuses them.
- Build a typed artifact manifest with content hashes shared by review and delivery.

### Phase 3 — Durable commands and resumability

- Persist PRD input/reference, stage cursor, run version, gate version, pending gate, and checkpoint metadata.
- Add lease owner/expiry and idempotent stage transition commands.
- Approval/finalize commands require idempotency key and expected gate version.
- Startup/recovery worker can resume from persisted checkpoints; local queues/events are not authoritative.

### Phase 4 — GitHub autonomous review loop

- Add authenticated `POST /api/review-loops` dispatch.
- Key loop by repository, PR number, and head SHA.
- Fetch exact PR files, run the bounded controller, write durable hops, and publish GitHub check/comment outcomes.
- Preserve Tier A/B/C and PHI/auth/deny escalation.
- Fix workflow token use and fail visibly without merging.

### Phase 5 — Runtime/operator correctness

- Implement tested SSE reconnection with backoff and new `EventSource` creation.
- Render review loops by structured loop identity and accurate terminal disposition.
- Render assurance dimensions separately.
- Surface stale-version/idempotency conflicts to parallel operators.

### Phase 6 — GitHub-native enforcement package

- Add CODEOWNERS and deterministic cloud-agent setup workflow.
- Pin third-party Actions to immutable SHAs.
- Add a script/report that verifies required rulesets/checks/environment protection via GitHub API.
- Document that ruleset activation is an admin external action; report it as blocked/unverified until actually configured.

## Risks and rollback

- **Auth lockout:** explicit bootstrap mode and health endpoints; production refuses unsafe mode but local tests stay deterministic.
- **Resume duplication:** every command and stage transition is idempotent and version-checked before a resume worker is enabled.
- **Provider outage:** production fails safely; demo remains available only under explicit profile.
- **GitHub preview drift:** adapters isolate API/version differences and tests mock documented contracts.
- **Ruleset misconfiguration:** verification tool is read-only by default; applying settings remains a deliberate admin action.
- **Rollback:** phases are additive and independently feature-flagged. Ledger history is not rewritten.

## Test targets

- Auth principal parsing, route-role matrix, team enforcement, workload token audience.
- Provider retry/failure/stub profile and synthetic delivery refusal.
- Artifact manifest hash equality at review and delivery.
- Decision command idempotency, expected-version conflict, duplicate finalize.
- Durable checkpoint resume and lease contention.
- Review-loop workflow/API/OpenAPI contract, dispatch replay, exact head SHA.
- SSE second-instance creation and backoff.
- Review-loop identity/status projection.
- GitHub governance verification report.
- Full orchestrator, ledger-core, MCP, pipeline-doctor, scripts, and UI suites; TypeScript/build; strict OpenSpec; browser QA.
