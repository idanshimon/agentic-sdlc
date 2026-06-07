# Design: ledger-insights-ui deploy

## Context

v0.7 ships a Next.js 14 governance dashboard (`apps/ledger-insights-ui/`) as the customer-facing surface for the Decision Ledger, Pipeline runs, OpenSpec /changes governance, and management Reports posture (92/100 + ROI math). It needs to land alongside the existing `ca-orchestrator` / `ca-ledger-mcp` / `ca-ledger-ui` apps in `rg-agentic-sdlc-eastus2`, behind public ingress, with Demo Mode enabled at build time so the customer can click-replay end-to-end without any backend dependency.

The legacy `ca-ledger-ui` (the v0.6 admin surface) remains running and unmodified. This is purely additive.

## Goals / Non-Goals

**Goals:**

- Customer can open `https://ca-ledger-insights-ui.<env>.eastus2.azurecontainerapps.io/` and walk a full Demo-Mode pipeline end-to-end (Vitals fixture → resolver gate → architect → deliver → /decisions → /reports → /changes) without backend.
- Build process is reproducible from a single `bash scripts/build-ledger-insights-ui.sh <sha>` and survives the `NEXT_PUBLIC_*` build-time-not-runtime trap.
- `/changes` reads the canonical `openspec/changes/` from disk inside the running container, so the OpenSpec governance surface is real (not a prerendered fixture).
- Smoke test gates the deploy: 5 routes return 200 with non-empty body before the change is considered shipped.

**Non-Goals:**

- Replacing `ca-ledger-ui` (v0.6 admin surface).
- Custom domains, multi-region, GitHub Actions CI, Managed Identity wiring (UI doesn't read Cosmos directly in v0.7).
- Disabling Demo Mode in production. v0.7 ships with Demo Mode default-on; rip-out is a future-state change.

## Decisions

### 1. Build context = monorepo root, not `apps/ledger-insights-ui/`

`/changes` reads `openspec/changes/` at request time. The Dockerfile must `COPY openspec/ ./openspec/` from the monorepo root. Setting build context to `apps/ledger-insights-ui/` would make `openspec/` un-COPY-able. Cost: the build sees the entire monorepo (~120 MB), but `.dockerignore` filters everything except `apps/ledger-insights-ui/**`, `openspec/**`, and `pnpm-lock.yaml` to keep the image small.

### 2. `NEXT_PUBLIC_*` threaded as build args, not runtime env

Verified pitfall (skill `nextjs-acr-build-public-env`): Next.js inlines `NEXT_PUBLIC_*` into the JS bundle during `next build`. Container App env vars are read at runtime — too late. Pattern:

```dockerfile
ARG NEXT_PUBLIC_DEMO_MODE
ARG NEXT_PUBLIC_ORCHESTRATOR_URL
ARG NEXT_PUBLIC_LEDGER_MCP_URL
ENV NEXT_PUBLIC_DEMO_MODE=$NEXT_PUBLIC_DEMO_MODE
ENV NEXT_PUBLIC_ORCHESTRATOR_URL=$NEXT_PUBLIC_ORCHESTRATOR_URL
ENV NEXT_PUBLIC_LEDGER_MCP_URL=$NEXT_PUBLIC_LEDGER_MCP_URL
RUN pnpm build
```

`scripts/build-ledger-insights-ui.sh` passes `--build-arg NEXT_PUBLIC_DEMO_MODE=1` etc. to `az acr build`.

### 3. Public ingress, no Entra gate (v0.7 only)

Demo Mode = no real PHI = public is defensible for v0.7. EasyAuth + tenant restriction is captured as a future-state requirement that fires the moment `NEXT_PUBLIC_DEMO_MODE=0` ships.

### 4. 1 replica, 0.5 vCPU / 1 GiB, scale-to-zero off

Demo URL is hit unpredictably during customer calls; cold-start from zero is a bad first impression. 1-replica minimum, max 3 (rare bursts during simultaneous customer demos). Cost ~$15/mo at idle — negligible.

### 5. App Insights server-side telemetry only, no user-event capture

Default Next.js + App Insights pairing captures route visits and response times. We explicitly disable user-event / query-string / request-body capture so a customer typing into the assistant input never produces a telemetry side-effect that could touch (real-future) PHI. Smoke-test asserts the App Insights config has these flags off.

### 6. Smoke test before declaring shipped

Five routes (`/`, `/runs`, `/decisions`, `/reports`, `/changes`) MUST return 200 with non-empty bodies (>1 KB) before the change is archive-able. Failure of any route = no archive. The smoke test runs from the deploying machine via curl, not from inside the container.

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| Build context = monorepo root inflates image | `.dockerignore` to filter all but `apps/ledger-insights-ui/**`, `openspec/**`, `pnpm-lock.yaml`, `package.json` |
| `NEXT_PUBLIC_*` build args leak into image layers | They're values like `1` and public URLs; nothing sensitive. Confirmed no secrets pass through build args |
| Public ingress + future PHI = silent exposure | Spec REQ-9 requires Entra gate before `NEXT_PUBLIC_DEMO_MODE=0` ships — guards the transition |
| `/changes` filesystem read fails in container | Smoke test for `/changes` returning >1 KB body catches this; also unit test confirms the route reads from `openspec/changes/` not a hardcoded fallback |
| Image size > 500 MB | Multi-stage build (deps → build → runtime); runtime stage = `node:20-alpine` + `.next/standalone`. Target <300 MB |

## Open Questions

- **Which orchestrator URL does the demo show when Demo Mode is OFF?** The internal Container App DNS (`ca-orchestrator.internal.<env>.eastus2.azurecontainerapps.io`) only resolves inside the env; the public FQDN goes through CA ingress. v0.7 demo runs Demo Mode ON, so this is deferred. When OFF: use the public FQDN since the UI calls from the browser, not server-side.
- **App Insights connection string source.** Reusing the existing `ai-agentic-sdlc` resource. Connection string lives in `Microsoft.App/managedEnvironments/cae-agentic-sdlc/properties/daprAIInstrumentationKey` already; module reads it via `existing` reference, not a fresh secret.
