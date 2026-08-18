# Proposal: wire real LLM providers

> **Status:** SHIPPED (retroactive) — v0.7, orchestrator `ca-orchestrator-vnet--0000040`
> **Capabilities:** pipeline, deployment
> **Commits:** e291d6b, 1869783, 7581829

## Why

The v0.7 deployment had no real model provider wired in, so the pipeline
fail-closed to synthetic stub output and could never reach real delivery. To make
the reference design demonstrate real governed code generation, a real LLM must
drive the stages — using production-correct auth (keyless Managed Identity), and
without weakening the demo's auth posture.

## KEEP / SWAP / ADD / OUT

### KEEP
- The provider abstraction and per-stage provider selection.
- The delivery guard that blocks synthetic output from reaching a PR.
- `AUTH_MODE=disabled` for the demo (production auth lockdown stays separate).

### SWAP
- No provider / synthetic-only → a real Azure OpenAI account in the v07 RG.
- API-key auth → keyless Managed Identity (`DefaultAzureCredential` +
  bearer-token provider scoped to Cognitive Services).

### ADD
- `REQUIRE_LIVE_PROVIDERS` flag that forces fail-closed on provider errors WITHOUT
  requiring `EXECUTION_PROFILE=production` (which would also lock down auth and
  break the demo).
- Raised ledger query cap (200 → 2000) so graph/decision views read the full set.
- A one-shot team backfill endpoint gated behind `ENABLE_TEAM_BACKFILL`.

### OUT
- Databricks-Claude routing for architect/codegen (documented as a follow-on).
- Multi-region / failover model routing.

## Verification

- Live: real GPT-4.1 (`gpt-4-1` deployment, keyless MI) drove full runs producing
  multi-kilobyte real code at real token cost (~$0.13–0.26/run), generalizing
  across eligibility, vitals-streaming, and payer-contract (Neo4j) PRDs.
- The `REQUIRE_LIVE_PROVIDERS` flag verified to fail-closed on provider error
  while `AUTH_MODE=disabled` still permitted the demo principal.
