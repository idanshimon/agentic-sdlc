# Tasks: wire-real-llm-providers

> **Status: 100% shipped in v0.7** (orchestrator `--0000040`). All sections complete.

## 1 — Keyless AOAI provider

- [x] 1.1 Keyless Managed Identity auth path in `providers/aoai.py` *(commit e291d6b)*
- [x] 1.2 `REQUIRE_LIVE_PROVIDERS` flag — fail-closed decoupled from production profile *(commit e291d6b)*
- [x] 1.3 Provision AOAI account + `gpt-4-1`/`gpt-4-1-mini` deployments in the v07 RG; grant orchestrator MI the Cognitive Services OpenAI User role *(infra — verified live)*

## 2 — Supporting changes

- [x] 2.1 Raise ledger query cap 200 → 2000; graph views fetch 1000 + honest cap notice *(commit 7581829)*
- [x] 2.2 Gate one-shot team backfill behind `ENABLE_TEAM_BACKFILL` *(commit 1869783)*

## Delta from original plan

Retroactive. Wiring a real provider was a prerequisite discovered mid-session —
without it the pipeline could only emit synthetic stubs. The keyless-MI posture
was chosen over API keys as the production-correct default. Databricks-Claude
routing for architect/codegen remains a documented follow-on, not shipped here.
