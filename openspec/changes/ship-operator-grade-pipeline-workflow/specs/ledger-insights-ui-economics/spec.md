# Spec delta: ship-operator-grade-pipeline-workflow / ledger-insights-ui-economics

## ADDED Requirements

### Requirement: Economics page MUST be backed by a real aggregation endpoint

The `/economics` page MUST be served by a Next.js API route at `/api/economics` that aggregates ledger entries fetched from the orchestrator's `/api/telemetry/decisions` endpoint via the pure functions in `lib/economics` (`summarize`, `summarizeByTeam`, `trendByDay`).

The route MUST return the exact shape `{summary, by_team, trend, sample_size, limit_applied}` consumed by `/economics/page.tsx`. The route MUST NOT directly query Cosmos — read-side authentication stays on the orchestrator.

#### Scenario: economics endpoint returns real aggregated data

- **GIVEN** a Cosmos ledger with N>0 decisions across one or more teams
- **WHEN** the `/api/economics?limit=200` endpoint is called
- **THEN** the response MUST be HTTP 200 with the full economics shape
- **AND** `summary.total_decisions` MUST equal the count of valid entries returned by the orchestrator
- **AND** `by_team` MUST contain one entry per distinct team_id in the ledger
- **AND** `trend` MUST contain at least one point per day decisions were written

### Requirement: Economics endpoint MUST degrade gracefully on upstream failure

When the orchestrator returns a 4xx/5xx response or the aggregation throws, the route MUST respond with the same shape but with an empty `summary` (all zeros) and an `error` field describing the failure. The page MUST NOT crash on a 404 from the orchestrator.

#### Scenario: orchestrator outage returns empty payload not 500 crash

- **GIVEN** the orchestrator's `/api/telemetry/decisions` endpoint returning 503 (unavailable)
- **WHEN** the `/api/economics` route is called
- **THEN** the response status MUST be 502 (not 500)
- **AND** the response body MUST include the standard shape with `summary.total_decisions === 0`
- **AND** the response body MUST include an `error` field containing the upstream status code
