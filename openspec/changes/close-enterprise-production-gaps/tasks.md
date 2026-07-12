# Tasks: close-enterprise-production-gaps

## 0. Specification and baseline
- [x] Reconcile identified gaps against current code and adjacent OpenSpec changes.
- [x] Author proposal, design, tasks, and spec deltas.
- [x] Strict OpenSpec validation.
- [x] Capture package test/build baselines.

## 1. Trust boundary
- [x] RED: principal parsing and auth-mode tests.
- [x] Implement typed principal and authentication dependencies.
- [x] RED: role/team authorization matrix for every mutating route.
- [x] Apply server-side authorization and derive actor/team from principal.
- [x] Configure production manifests to refuse disabled auth mode.
- [x] Document local bootstrap and production identity setup.

## 2. Fail-closed providers and artifact integrity
- [x] RED: production provider error terminates without stub.
- [x] RED: demo profile stamps synthetic output.
- [x] RED: delivery refuses synthetic runs.
- [x] Implement bounded error categorization and execution profiles (retry policy remains a later reliability enhancement).
- [x] RED: artifact manifest hashes reviewed bytes and delivery rejects drift.
- [x] Implement shared manifest from CodeGen through Review/Deliver.

## 3. Durable commands and resumability
- [x] RED: RunState checkpoint/version/gate fields round-trip through persistence.
- [x] Implement durable input/checkpoint and lease model.
- [x] RED: duplicate idempotency key returns original result; altered payload conflicts.
- [x] Implement durable command records in RunState with atomic Cosmos ETag CAS for pause/resume/finalize.
- [x] RED: stale expected gate version conflicts and duplicate finalize is safe.
- [x] Implement command guards and CAS finalize with explicit gate supersession.
- [x] RED: recovery worker leases an expired/no-lease run and plans the next stage.
- [x] Implement startup recovery scan, bounded stage-specific continuation for Architect onward, and ETag lease renewal.

## 4. Autonomous review loop
- [x] RED: workflow route/header contract matches OpenAPI.
- [x] RED: dispatch requires GitHub workload role and correct identity scope.
- [x] RED: repeated repo/PR/head SHA dispatch is idempotent.
- [x] Implement `POST /api/review-loops` and exact PR-head file retrieval.
- [x] Persist structured loop identity/hops/disposition durably in Cosmos using the pipeline-runs container and ETag replacement.
- [x] Publish GitHub check/comment evidence and preserve bounded merge rules.
- [x] Bind human merge to loop ID, Tier-B PASS disposition, and revalidated expected head SHA.
- [x] Fix workflow secret usage and failure reporting.

## 5. Runtime correctness
- [x] RED: SSE error creates a second EventSource after backoff.
- [x] Implement reconnect state machine and event-ID dedup.
- [x] RED: Tier-B renders PASSED_AWAITING_MERGE, not MERGED.
- [x] Update review-loop grouping/status by loop ID/PR/SHA.
- [x] Render independent assurance dimensions.
- [x] Surface 409 version/idempotency conflicts to operators.

## 6. GitHub-native enforcement package
- [x] Add CODEOWNERS aligned to owned config surfaces.
- [x] Add deterministic `copilot-setup-steps.yml` with fail-visible validation.
- [x] Pin third-party Actions to immutable SHAs.
- [x] Add read-only GitHub governance verifier and tests.
- [x] Document required ruleset/check/environment/scanning configuration.
- [x] Verify live GitHub posture; admin-only settings remain explicitly unapplied.

## 7. Documentation
- [x] Update architecture and API docs.
- [x] Add SECURITY.md threat/trust model.
- [x] Add operations/resume/recovery runbook.
- [x] Add GitHub enforcement setup and verification docs.
- [x] Update known limitations and deployment configuration.
- [x] Regenerate `docs/API.md`.

## 8. Verification and review
- [x] Targeted tests green after every slice.
- [x] Full orchestrator, ledger-core, MCP, pipeline-doctor, scripts, and UI tests.
- [x] TypeScript checks and production builds.
- [x] Strict OpenSpec validation.
- [x] Static security scan.
- [ ] Independent spec-compliance reviews per capability.
- [ ] Independent code-quality/security reviews per capability.
- [x] Browser QA: local production review-loop empty state and run-scoped Decisions degraded ledger state; auth/provider/recovery contracts verified through endpoint tests.
- [x] Live GitHub/Azure verification separated from local proof.
