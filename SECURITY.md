# Production security model

## Trust boundaries

- Browser/user → authenticated ingress → orchestrator.
- GitHub workflow → workload-authenticated dispatch endpoint.
- Orchestrator → Azure data plane through managed identity.
- Orchestrator → GitHub through a separately scoped delivery/review credential.
- Agents and models are untrusted reasoning components; deterministic gates and server policy are authoritative.

## Identity

Mutation actors are derived server-side from validated principal claims. Request-body actor fields are never authoritative. Team scope is checked after loading the target resource.

Roles: operator, persona owner, standards reviewer, release manager, administrator, GitHub workload.

## Fail-closed controls

Production refuses disabled authentication. Provider outages terminate the stage rather than producing deliverable stubs. Synthetic demo/test output is labeled and blocked from GitHub delivery. Reviewed artifact hashes must match delivered bytes.

## Data handling

Raw PRD input is stored in the artifacts container with SHA-256 verification. Decision Ledger entries contain decisions and evidence, not raw source documents. Raw PHI and secrets remain forbidden in prompts, logs, telemetry, and samples.

## GitHub

Repository workflow files are not enforcement until rulesets/branch protection require their checks. Use `scripts/verify_github_governance.py` to distinguish advisory from enforced posture.

## Known limits

- Direct Entra JWT verification is not implemented; production currently requires a validating trusted-header ingress.
- Review-loop records are not yet fully durable.
- Recovery is checkpoint-aware but the lease/startup worker is incomplete.
- Live rulesets and branch protection remain admin-controlled and unapplied in the reference repository.
