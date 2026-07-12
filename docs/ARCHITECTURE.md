# Production architecture

Agentic SDLC is an enterprise governance and evidence plane over GitHub-native execution.

## Product boundary

GitHub remains authoritative for repositories, branches, pull requests, checks, reviews, Actions, runners, merge queue, coding-agent sessions, setup environments, and repository rulesets.

Agentic SDLC owns:

- typed decisions and hard human gates
- standards bundles and deterministic policy evidence
- autonomy envelopes and escalation floors
- cross-runtime identity, lineage, cost, and precedent
- durable run checkpoints and artifact integrity
- enterprise decision lifecycle projections

It does not rebuild Agent HQ, generic session management, Actions, pull requests, runners, or model marketplaces.

## Runtime planes

1. Standards: versioned department bundles, instructions, prompts, agents, hooks.
2. Pipeline: PRD through assessment, decisions, architecture, tests, code generation, assurance, and GitHub delivery.
3. Ledger and Doctor: append-only decision evidence, run checkpoints, drift detection, bounded remediation.
4. GitHub Agent runtime: coding agents and repository-native enforcement connected through authenticated dispatch and ledger evidence.

## Decision lifecycle

The append-only ledger remains authoritative history. Operator views derive:

```text
proposed → required → resolved → applied → verified → learned
```

Raw events are supporting evidence, not the primary operator abstraction.

## Trust and execution

All mutations resolve an authoritative server-side principal. Production uses validated trusted headers behind an identity-aware ingress. Provider failures fail closed. Demo/test synthetic output is labeled and cannot cross the GitHub delivery boundary.

Raw PRD input is stored in Blob with SHA-256. Runs persist cursor, gate, command, lease, and artifact-manifest state in Cosmos. Recovery is bounded at-least-once execution from safe stage boundaries. Commands use idempotency records and Cosmos ETag conditional replacement.

## Review and delivery

Review records SHA-256 hashes for the complete delivery file set. Deliver refuses changed bytes. Autonomous review identity is repository + PR + exact head SHA. Outcomes publish an exact-SHA GitHub check and idempotent PR comment. Tier-B human merge requires a passing loop and revalidates the SHA immediately before merge.

## Enforcement boundary

Checked-in workflows are advisory until GitHub rulesets or branch protection require them. `scripts/verify_github_governance.py` reports enforced, advisory, and unknown posture separately.

## Deployment topology

- Azure Container Apps: orchestrator, UI, Decision Ledger MCP, Pipeline Doctor
- Cosmos DB: decision ledger and pipeline runs
- Blob Storage: raw run inputs and generated artifacts
- Managed identity: Azure data-plane access
- Validating ingress: human/workload authentication headers
- GitHub credential/App installation token: scoped PR/check/comment/merge operations

See `SECURITY.md`, `docs/AUTHENTICATION.md`, `docs/RUN-RECOVERY.md`, and `docs/GITHUB-ENFORCEMENT.md`.
