## ADDED Requirements

### Requirement: Dockerfile threads NEXT_PUBLIC_* as build args

The `apps/ledger-insights-ui/Dockerfile` MUST declare `ARG` directives for every `NEXT_PUBLIC_*` variable required at build time and SHALL set them as `ENV` BEFORE the `RUN pnpm build` invocation. Setting them only as Container App runtime env vars MUST be considered a build error.

#### Scenario: build with NEXT_PUBLIC_DEMO_MODE=1
- **WHEN** `az acr build` runs with `--build-arg NEXT_PUBLIC_DEMO_MODE=1`
- **THEN** the resulting image's `.next/static/chunks/*.js` MUST contain the literal string `"NEXT_PUBLIC_DEMO_MODE":"1"` or equivalent inlined value

#### Scenario: missing build arg
- **WHEN** `az acr build` runs without passing `NEXT_PUBLIC_DEMO_MODE`
- **THEN** the build SHALL succeed but the resulting Demo Mode pill MUST NOT render in the deployed UI

### Requirement: Build context is monorepo root

The build context for `az acr build` MUST be the monorepo root, not `apps/ledger-insights-ui/`. The Dockerfile MUST `COPY openspec/ ./openspec/` so the `/changes` route can read OpenSpec proposals at request time. The `.dockerignore` at monorepo root MUST exclude every path except `apps/ledger-insights-ui/**`, `openspec/**`, `pnpm-lock.yaml`, `package.json`, and `pnpm-workspace.yaml`.

#### Scenario: /changes reads from filesystem
- **WHEN** the deployed container receives a request to `/changes`
- **THEN** the route MUST list all proposals present at `/openspec/changes/` inside the container, NOT a fixture

#### Scenario: openspec/ missing from image
- **WHEN** an image is built without `COPY openspec/`
- **THEN** the smoke test for `/changes` MUST fail because the response body is missing the literal string `OpenSpec`

### Requirement: Container App ingress and scale

The `ca-ledger-insights-ui` Container App MUST run in the existing `cae-agentic-sdlc` managed environment with `external = true` ingress on port 3005, scale `minReplicas = 1` to `maxReplicas = 3`, and resource allocation 0.5 vCPU + 1 GiB memory.

#### Scenario: cold-hit response
- **WHEN** the deployed URL is hit after >5 minutes of inactivity
- **THEN** the first response MUST return HTTP 200 in under 3 seconds (no scale-from-zero penalty)

#### Scenario: external resolution
- **WHEN** an outside-corp-VPN client resolves the FQDN
- **THEN** the DNS lookup MUST resolve to a public IP and return HTTP 200 on `/`

### Requirement: App Insights server-side only, PHI-safe defaults

The Container App MUST wire `APPLICATIONINSIGHTS_CONNECTION_STRING` from the existing `ai-agentic-sdlc` resource (no new secrets). Telemetry SHALL capture only path, method, status code, and duration. Request bodies, query strings (beyond redacted form), and user-typed input MUST NOT be captured.

#### Scenario: telemetry never carries body
- **WHEN** a Kusto query against the App Insights resource runs `requests | take 1000 | where isnotempty(customDimensions.body)`
- **THEN** the query MUST return zero rows

#### Scenario: telemetry captures route metrics
- **WHEN** a user navigates `/reports`
- **THEN** App Insights MUST record a `requests` row with `name = "/reports"`, `resultCode = "200"`, and a populated `duration`

### Requirement: Smoke test gates archive

Before this change is archive-able, `scripts/smoke-ledger-insights-ui.sh <fqdn>` MUST pass: every one of `/`, `/runs`, `/decisions`, `/reports`, `/changes` returns HTTP 200 with `Content-Length > 1024`. Additionally, `/changes` MUST contain the literal string `OpenSpec` in its response body.

#### Scenario: smoke pass on healthy deploy
- **WHEN** smoke runs against a freshly-deployed working URL
- **THEN** all 5 assertions MUST pass and the script SHALL exit 0

#### Scenario: filesystem read regression
- **WHEN** `/changes` returns 200 but the body lacks `OpenSpec`
- **THEN** the smoke script MUST exit non-zero with `"openspec read regression"`

#### Scenario: route returns empty fallback
- **WHEN** any route returns 200 but `Content-Length < 1024`
- **THEN** the smoke script MUST exit non-zero with the offending route name

### Requirement: Public ingress for Demo Mode only

Public ingress without Entra authentication is permitted ONLY while `NEXT_PUBLIC_DEMO_MODE=1` is baked into the deployed image. The deployment manifest (Bicep + build script) MUST refuse to build a Demo-Mode-disabled image with public-only ingress.

#### Scenario: Demo Mode build with public ingress
- **WHEN** the build runs with `NEXT_PUBLIC_DEMO_MODE=1` and Bicep declares `external = true`
- **THEN** the deploy MUST succeed

#### Scenario: Demo Mode disabled with public ingress
- **WHEN** a build is requested with `NEXT_PUBLIC_DEMO_MODE=0` and Bicep still declares `external = true` without EasyAuth
- **THEN** the build script MUST refuse to push and emit `"public ingress requires Demo Mode or EasyAuth"`

### Requirement: Reproducible build via single script

A single command `bash scripts/build-ledger-insights-ui.sh` MUST produce a tagged image in `cragenticsdlc.azurecr.io/ledger-insights-ui:<sha>` and `:latest`, where `<sha>` is `git rev-parse --short HEAD`. The script MUST print the resulting image digest at completion.

#### Scenario: clean tree build
- **WHEN** the build script runs against a clean working tree
- **THEN** the resulting image tag SHALL be `<sha>` matching `git rev-parse --short HEAD` AND the digest MUST be printed

#### Scenario: build with overrides
- **WHEN** the build script runs with `NEXT_PUBLIC_ORCHESTRATOR_URL=https://override.example.com`
- **THEN** that URL MUST be inlined into the resulting bundle

### Requirement: Bicep adds module without disturbing existing apps

`infra/apps.bicep` MUST add the ledger-insights-ui module call after the `ledger-ui` module. A `what-if` deployment against `rg-agentic-sdlc-eastus2` MUST show ONLY the creation of the new Container App; no modifications to `ca-orchestrator`, `ca-ledger-mcp`, or `ca-ledger-ui` are permitted.

#### Scenario: what-if shows only additive change
- **WHEN** `az deployment group what-if -g rg-agentic-sdlc-eastus2 -f infra/apps.bicep` runs
- **THEN** the diff MUST show one Create operation (`Microsoft.App/containerApps/ca-ledger-insights-ui`) and zero Modify operations on existing apps

### Requirement: Future Entra gate before Demo Mode rip-out

When `NEXT_PUBLIC_DEMO_MODE=0` ships (Demo Mode rip-out), the deployment MUST gate access via Azure EasyAuth with tenant restriction to the Microsoft tenant before the new image is pushed to ACR. A pre-push CI step SHALL refuse the rip-out push without an active EasyAuth configuration on the Container App.

#### Scenario: rip-out without EasyAuth
- **WHEN** a build is requested with `NEXT_PUBLIC_DEMO_MODE=0` and the target Container App has no `Microsoft.App/containerApps/<name>/authConfigs/current` resource
- **THEN** the build script MUST refuse to push with `"Demo Mode rip-out requires EasyAuth"`

#### Scenario: rip-out with EasyAuth configured
- **WHEN** EasyAuth is configured AND `NEXT_PUBLIC_DEMO_MODE=0`
- **THEN** the build and deploy MUST succeed
