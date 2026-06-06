# architect/v0.1.0

Architect bundle — allowed stacks, service patterns, deployment targets,
SLA defaults, provider routing, retry counts.

## Auto-fix envelope

Two rule fields may be auto-fixed by Pipeline Doctor (within bounds):
- `RETRY-COUNT-001.defaults.retry_count` (range [1, 5], max delta 1 per run)
- `PROVIDER-ROUTING-001.defaults.*` (switch between approved providers)

Both require the drift signal to have persisted for at least 7-14 days.

Auto-fix is FORBIDDEN on:
- ALLOWED-STACKS-001 (committee decision)
- SERVICE-AUTH-MI-001 (security-adjacent)

## Rule index

| ID | Title | PHI | Severity |
|---|---|---|---|
| ALLOWED-STACKS-001 | Approved language runtimes | false | WARN |
| ALLOWED-FRAMEWORKS-001 | Approved web frameworks | false | WARN |
| SERVICE-CONTAINERIZED-001 | All services containerized | false | BLOCK |
| SERVICE-AUTH-MI-001 | Azure data-plane auth = MI | false | BLOCK |
| SLA-DEFAULTS-001 | Service SLA defaults | false | WARN |
| PROVIDER-ROUTING-001 | Per-stage LLM provider routing | false | WARN |
| RETRY-COUNT-001 | Stage retry count | false | WARN |
