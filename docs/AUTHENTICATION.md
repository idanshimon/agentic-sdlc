# Orchestrator authentication

The orchestrator has an explicit trust boundary for every mutating `/api/*` request.

## Modes

- `AUTH_MODE=disabled`: local development and tests only. The server creates a development admin principal. `EXECUTION_PROFILE=production` refuses to start in this mode.
- `AUTH_MODE=trusted_headers`: production mode behind an identity-validating ingress such as Azure Container Apps EasyAuth or another trusted reverse proxy.
- `AUTH_MODE=entra`: reserved for direct JWT validation. It currently refuses startup rather than decoding unverified tokens.

## Trusted identity headers

The validating ingress must remove client-supplied versions and inject:

- `X-Auth-Subject`: stable human/workload identifier
- `X-Auth-Kind`: `human` or `workload`
- `X-Auth-Roles`: comma-separated roles
- `X-Auth-Teams`: comma-separated authorized team IDs

Roles are `operator`, `persona_owner`, `standards_reviewer`, `release_manager`, `admin`, and `github_workload`.

The server derives ledger actor identity from `X-Auth-Subject`; body fields such as `actor` and `approver_id` are compatibility inputs and are not authoritative when authentication is active.

## Deployment requirement

The checked-in production Bicep sets:

```text
EXECUTION_PROFILE=production
AUTH_MODE=trusted_headers
```

This deliberately makes an unconfigured production deployment fail closed. Before rollout, configure the ingress identity provider/header adapter. Do not expose the container directly while trusting arbitrary client headers.

## Local development

Leave both variables unset, or set:

```text
EXECUTION_PROFILE=development
AUTH_MODE=disabled
```

This mode must not be used for customer or production traffic.
