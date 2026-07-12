# Production deployment configuration

## Required orchestrator settings

```text
EXECUTION_PROFILE=production
AUTH_MODE=trusted_headers
```

Production startup refuses disabled authentication. `trusted_headers` is safe only when the ingress validates identity and strips caller-supplied copies of identity headers.

Required Azure configuration:

- Cosmos endpoint, database, ledger container, and runs container
- Storage account URL and artifacts container
- Managed identity roles for Cosmos and Blob data-plane access
- Private networking/DNS where required by policy

Required GitHub configuration:

- Scoped GitHub App installation token or equivalent workload credential
- Orchestrator review-dispatch URL and secret/workload identity
- Repository ruleset or branch protection requiring deterministic checks
- Protected production/merge environments
- CODEOWNERS for governance-sensitive paths

## Identity proxy contract

The ingress supplies validated subject, kind, roles, and team scopes. The orchestrator ignores actor, approver, role, and team claims supplied in request bodies.

Direct Entra bearer-token mode remains fail-closed until cryptographic issuer/audience/signature validation is configured. Do not replace this with unsigned token parsing.

## Execution and recovery

Use one active execution replica until lease renewal and multi-replica operational proof are completed. Startup scans nonterminal runs, acquires Cosmos ETag leases, restores waiting gates, and resumes safe boundaries from Architect onward.

Do not enable production delivery when:

- provider configuration cannot be established
- the run contains synthetic output
- reviewed and delivered manifests differ
- input SHA-256 fails validation
- GitHub head SHA changed
- repository enforcement remains advisory for a workload requiring hard enforcement

## Verification

Before rollout:

```bash
openspec validate close-enterprise-production-gaps --strict
uv run --with-requirements apps/orchestrator/requirements.txt --with pytest pytest apps/orchestrator/tests -q
pnpm --dir apps/decision-ledger-mcp test
pnpm --dir apps/decision-ledger-mcp build
pnpm --dir apps/ledger-insights-ui vitest run
pnpm --dir apps/ledger-insights-ui build
python scripts/verify_github_governance.py owner/repo
```

After rollout, verify the active Container Apps revision/image, authenticated mutation rejection/acceptance, a durable run write/readback, Blob input hash readback, and required GitHub checks. Local tests are not deployment proof.

## Known limitations

- Direct Entra JWT validation is not implemented.
- Review-loop records share the `pipeline-runs` Cosmos container using `loop_id` as the partition key and ETag replacement for state transitions.
- Recovered execution supports safe continuation from Architect onward and renews its lease with ETag CAS during long stages. Ingest/Assessor recovery intentionally fails visible rather than replaying uncertain work.
- GitHub rulesets and branch protection are administrator-controlled; the reference repository's live posture was advisory when last verified.
- Synthetic demo/test providers are intentionally non-deliverable.
