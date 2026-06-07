# Tasks: add-ledger-insights-ui-deploy

## 1. Dockerfile + .dockerignore

- [ ] 1.1 Author `apps/ledger-insights-ui/Dockerfile` as multi-stage (deps → build → runtime) with build context = monorepo root.
- [ ] 1.2 Declare ARG/ENV pairs for `NEXT_PUBLIC_DEMO_MODE`, `NEXT_PUBLIC_ORCHESTRATOR_URL`, `NEXT_PUBLIC_LEDGER_MCP_URL` BEFORE `RUN pnpm build`.
- [ ] 1.3 `COPY openspec/ ./openspec/` so the `/changes` route can read at request time inside the container.
- [ ] 1.4 Author `.dockerignore` at monorepo root that excludes everything except `apps/ledger-insights-ui/**`, `openspec/**`, `pnpm-lock.yaml`, `package.json`, `pnpm-workspace.yaml`.
- [ ] 1.5 Validate: local `docker build` from repo root, then `docker run -e PORT=3005 -p 3005:3005` and curl `/`, `/changes` — both 200, `/changes` body >1 KB.

## 2. Bicep module

- [ ] 2.1 Author `infra/modules/ledger-insights-ui.bicep` declaring a Container App resource named `ca-ledger-insights-ui` in the existing `cae-agentic-sdlc` managed environment.
- [ ] 2.2 Set ingress: `external = true`, `targetPort = 3005`, `transport = "auto"`.
- [ ] 2.3 Set scale: `minReplicas = 1`, `maxReplicas = 3`. CPU 0.5, memory 1Gi.
- [ ] 2.4 Wire App Insights connection string from existing `ai-agentic-sdlc` resource using `existing` reference (no new secrets).
- [ ] 2.5 Wire env vars `APPLICATIONINSIGHTS_CONNECTION_STRING`, `NEXT_PUBLIC_DEMO_MODE=1`, `PORT=3005` (the last as a defense-in-depth match for the Dockerfile).
- [ ] 2.6 Add `infra/apps.bicep` module call for `ledger-insights-ui` after `ledger-ui`.
- [ ] 2.7 Validate: `az bicep build infra/apps.bicep` clean; `az deployment group what-if` against the existing RG shows only the new resource.

## 3. ACR build script

- [ ] 3.1 Author `scripts/build-ledger-insights-ui.sh` that runs `az acr build` with: registry `cragenticsdlc`, image `ledger-insights-ui:<sha>` (sha from `git rev-parse --short HEAD`), build context `.` (monorepo root), file `apps/ledger-insights-ui/Dockerfile`, and explicit `--build-arg` for each `NEXT_PUBLIC_*`.
- [ ] 3.2 Default values for build args: `NEXT_PUBLIC_DEMO_MODE=1`, `NEXT_PUBLIC_ORCHESTRATOR_URL=https://ca-orchestrator.<env>.eastus2.azurecontainerapps.io`, `NEXT_PUBLIC_LEDGER_MCP_URL=https://ca-ledger-mcp.<env>.eastus2.azurecontainerapps.io`. Override via env vars.
- [ ] 3.3 Tag both `<sha>` and `latest`. Print resulting image digest at end.
- [ ] 3.4 Validate: dry-run with `--build-arg NEXT_PUBLIC_DEMO_MODE=1` succeeds; built image has `NEXT_PUBLIC_DEMO_MODE=1` baked into the bundle (verifiable via `grep` on extracted `.next/static/chunks/*.js`).

## 4. Smoke test

- [ ] 4.1 Author `scripts/smoke-ledger-insights-ui.sh` that takes a base URL arg and curls `/`, `/runs`, `/decisions`, `/reports`, `/changes`.
- [ ] 4.2 For each route, assert HTTP 200 and `Content-Length > 1024` (catches the empty-body / fallback-page failure mode).
- [ ] 4.3 For `/changes`, additionally assert the response body contains the literal string `OpenSpec` (catches filesystem-read regression).
- [ ] 4.4 Exit non-zero on any failure with route-specific error message.
- [ ] 4.5 Validate: smoke test passes against local Demo Mode container; test fails (as expected) when run against `https://example.com`.

## 5. Documentation

- [ ] 5.1 Update root `README.md` topology section to list `ca-ledger-insights-ui` alongside the three existing apps with a one-line description and demo URL placeholder.
- [ ] 5.2 Update `apps/ledger-insights-ui/DEMO_MODE.md` to document the deploy path: build script, Bicep module, smoke test, and rip-out instructions.
- [ ] 5.3 Add a "Demo URL" row to root `README.md`'s topology table referencing the public FQDN once deployed.

## 6. Deploy to eastus2

- [ ] 6.1 Run `bash scripts/build-ledger-insights-ui.sh` from repo root; verify ACR shows new image tag.
- [ ] 6.2 Deploy Bicep: `az deployment group create -g rg-agentic-sdlc-eastus2 -f infra/apps.bicep`.
- [ ] 6.3 Capture the resulting public FQDN; record in README and DEMO_MODE.md.
- [ ] 6.4 Run `bash scripts/smoke-ledger-insights-ui.sh https://<fqdn>/` — assert all 5 routes pass.
- [ ] 6.5 Manually click through Demo Mode end-to-end: home → /runs/new → vitals fixture → approve gate → /runs/[id] artifacts → /decisions → /reports → /changes. Confirm no errors in browser console.
- [ ] 6.6 Open the universal assistant via ⌘K on `/agents`; type "tighten phi"; click Apply; confirm new version lands in History tab. Smoke-test for the assistant subsystem.

## 7. Validation + safety

- [ ] 7.1 Run `openspec validate add-ledger-insights-ui-deploy --strict` — must pass.
- [ ] 7.2 Confirm App Insights does NOT capture request bodies or query strings (verifyable via Kusto query on the resource: `requests | take 100 | extend has_body = isnotempty(customDimensions.body)` — must return zero rows with body).
- [ ] 7.3 Confirm public ingress works from outside the corp VPN.
- [ ] 7.4 File a follow-up tracking issue: "Enable EasyAuth + Entra tenant restriction when `NEXT_PUBLIC_DEMO_MODE=0` ships" (gates spec REQ-9).
- [ ] 7.5 `git add -A && git commit -S -m "feat(deploy): ledger-insights-ui on Azure Container Apps"` and push.
