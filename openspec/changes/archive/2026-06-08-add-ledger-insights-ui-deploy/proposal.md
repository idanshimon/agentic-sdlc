# Proposal: Deploy ledger-insights-ui to Azure Container Apps

> **Status:** DRAFT — for committee review
> **Authors:** Idan Shimon
> **Date:** 2026-06-06
> **Capabilities touched:** deployment, telemetry
> **Depends on:** master-v07-four-plane-architecture (v0.7 environment topology)

## Why

`apps/ledger-insights-ui/` is the new Next.js 14 governance dashboard for v0.7 — universal AgentAssistant, Reports (management posture + ROI), OpenSpec /changes surface, versioned editor for agents/prompts, click-to-replay Demo Mode. It currently runs only locally on `:3005` and large parts of it are uncommitted on `main`. To complete the v0.7 honest-demo goal (Master spec REQ-5), the dashboard MUST land in eastus2 with a documented public URL the customer can visit end-to-end.

The existing `ca-ledger-ui` Container App in `infra/apps.bicep` already deploys the `ledger-insights-ui:<tag>` image. This change does NOT create a new app; it HARDENS the existing build + deploy path so the Dashboard's two build-time traps and the Demo Mode contract don't ship broken:

1. **Next.js inlines `NEXT_PUBLIC_*` at `next build` time.** Setting `NEXT_PUBLIC_DEMO_MODE=1` as a Container App runtime env var alone ships a bundle with `undefined` and Demo Mode silently fails. Build args MUST thread through the Dockerfile.
2. **`/changes` reads `openspec/` at request time.** The Dockerfile MUST `COPY openspec/` from the monorepo root into the runtime image — `apps/ledger-insights-ui/` is not the build context root.

## What Changes

- `apps/ledger-insights-ui/Dockerfile` rewritten to (a) build context = monorepo root, (b) accept `NEXT_PUBLIC_*` build args set as ENV before `next build`, (c) `COPY openspec/` so `/changes` can read at request time.
- Root `.dockerignore` authored to exclude everything except `apps/ledger-insights-ui/**`, `openspec/**`, `pnpm-lock.yaml`, `package.json`, `pnpm-workspace.yaml`.
- `infra/apps.bicep` `ca-ledger-ui` resource updated: add `NEXT_PUBLIC_DEMO_MODE=1` env var, switch image name reference to `ledger-insights-ui` (already correct) + add ingress port confirmation (3000 matches Dockerfile EXPOSE).
- ACR build script `scripts/build-ledger-insights-ui.sh` invoking `az acr build` with build context = repo root and explicit `--build-arg` for all `NEXT_PUBLIC_*` keys.
- Smoke test `scripts/smoke-ledger-insights-ui.sh` that hits `/`, `/runs`, `/decisions`, `/reports`, `/changes` and asserts 200 + non-empty body + `/changes` body contains "OpenSpec".
- App Insights wiring already present in Bicep; this change adds the spec-level requirement that telemetry never captures bodies/query strings.

## Capabilities

### New Capabilities

- `ledger-insights-ui-deploy`: build, ship, and verify the Next.js dashboard on Azure Container Apps — the deployment surface for v0.7's governance UI.

### Modified Capabilities

- `deployment`: add the Bicep module + ACR build flow + smoke-test gates for the ledger-insights-ui Container App.

## Impact

- `apps/ledger-insights-ui/Dockerfile` — created (multi-stage: deps → build → runtime, build context = repo root).
- `infra/apps.bicep` — already +64 lines uncommitted; this change adds module wiring for ledger-insights-ui specifically.
- `infra/modules/ledger-insights-ui.bicep` — new file.
- `scripts/build-ledger-insights-ui.sh` — new.
- `scripts/smoke-ledger-insights-ui.sh` — new.
- `apps/ledger-insights-ui/DEMO_MODE.md` — already authored; cross-link from this change.
- ACR `cragenticsdlc.azurecr.io` — new image repository `ledger-insights-ui:<sha>`.
- One App Insights resource (shared with existing apps; no separate workspace).

## Safety Impact

- Demo Mode = no real PHI in the running environment. Public ingress is therefore defensible for v0.7.
- App Insights MUST NOT capture request bodies or query strings beyond path + status (PHI-safe-by-default).
- No Managed Identity required for v0.7 demo (no Cosmos/Storage reads from the UI directly; all data flows through `ca-orchestrator` / `ca-ledger-mcp` which already have MI).
- Future-state: when Demo Mode is rip-out via `NEXT_PUBLIC_DEMO_MODE=0` and real ledger reads land, Entra-gated ingress MUST be enabled — captured as a follow-up requirement in this change.

## Non-goals

- Not replacing `ca-ledger-ui`. Both run.
- Not setting up GitHub Actions for build automation. Manual `az acr build` for v0.7; CI is a follow-up change.
- Not custom-domain. `*.eastus2.azurecontainerapps.io` is the v0.7 demo URL.
- Not multi-region. Eastus2 only, matching v0.6 topology.
