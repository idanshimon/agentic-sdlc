# Tasks: production-grade Cosmos network posture for v0.7+

## 1. Network bicep module
- [ ] 1.1 Create `infra/network.bicep` — VNET `vnet-agentic-v07 10.50.0.0/16`
- [ ] 1.2 Subnet `snet-cae` (10.50.0.0/23) with `Microsoft.App/environments` delegation
- [ ] 1.3 Subnet `snet-pe` (10.50.2.0/24) for private endpoints (no delegation)
- [ ] 1.4 Subnet `snet-mgmt` (10.50.3.0/24) reserved for future use
- [ ] 1.5 NSG per subnet with default deny + Container Apps required allows
- [ ] 1.6 Private DNS zones: `privatelink.documents.azure.com`, `privatelink.azurecr.io`, `privatelink.blob.core.windows.net`, `privatelink.vaultcore.azure.net`
- [ ] 1.7 Link all 4 zones to the VNET

## 2. Cosmos private endpoint
- [ ] 2.1 PE on `cosmos-agentic-tj6c673gu6x5w` SQL API into `snet-pe`
- [ ] 2.2 DNS A record in `privatelink.documents.azure.com` pointing at the PE
- [ ] 2.3 Verify private DNS resolves to a `10.50.2.x` IP from a VNET-resident probe
- [ ] 2.4 Flip `publicNetworkAccess: Disabled`, clear `ipRules`
- [ ] 2.5 Verify external `curl` fails (closed loop)

## 3. ACR private endpoint (Premium tier)
- [ ] 3.1 Upgrade `acragenticsdlctj6c673gu6x5w` from Basic to Premium
- [ ] 3.2 PE on the registry into `snet-pe`
- [ ] 3.3 DNS records in `privatelink.azurecr.io` for the registry + data endpoints
- [ ] 3.4 Disable public access on the registry (after image pulls verified through private endpoint)

## 4. Storage private endpoint (decision-ledger blobs)
- [ ] 4.1 PE on the storage account's blob endpoint
- [ ] 4.2 DNS records in `privatelink.blob.core.windows.net`
- [ ] 4.3 Disable public access

## 5. Container Apps env recreate (REPLACES `cae-agentic-tj6c673gu6x5w`)
- [ ] 5.1 New env `cae-agentic-v07-vnet` with `vnetConfiguration.infrastructureSubnetId` = `snet-cae`
- [ ] 5.2 Workload profile `Consumption` (preserve current cost shape)
- [ ] 5.3 Recreate the 3 apps (ca-orchestrator, ca-ledger-mcp, ca-ledger-ui) on the new env
- [ ] 5.4 Verify ingress FQDNs and update skill `customer-engagement/hca-agentic-sdlc-demo` "Live URLs" section
- [ ] 5.5 Delete the old env after 24h soak (rollback window)

## 6. Code adjustments
- [ ] 6.1 Retag `node:20-alpine` into ACR as `private-base/node:20-alpine`
- [ ] 6.2 Update `apps/decision-ledger-mcp/Dockerfile` to pull from private ACR base
- [ ] 6.3 Same for `apps/orchestrator` (Python 3.11 base)
- [ ] 6.4 Same for `apps/pipeline-doctor` and `apps/ledger-insights-ui`
- [ ] 6.5 Verify `az acr build` still succeeds with the new base image refs

## 7. CI/CD scripts
- [ ] 7.1 Update `deploy/scripts/01-deploy-base.sh` to deploy `network.bicep` first
- [ ] 7.2 Add `deploy/scripts/06-rotate-network.sh` — one-shot migration recipe
- [ ] 7.3 Update `scripts/build-ledger-insights-ui.sh` defaults for new ACR + RG (the existing comment in `references/demo-store-renderer-oom-pattern.md` notes these defaults rotted; durable fix here)

## 8. Documentation
- [ ] 8.1 New `docs/PRIVATE-ENDPOINT-DEPLOY-v07.md` ported from v0.6
- [ ] 8.2 Update `docs/ARCHITECTURE.md` with the new network topology
- [ ] 8.3 Update `AGENTS.md` if any rule changes (probably not — the principle was already there)

## 9. Validation
- [ ] 9.1 `dig +short` from inside the VNET: cosmos endpoint resolves to `10.50.2.x`
- [ ] 9.2 External curl to Cosmos endpoint: must fail
- [ ] 9.3 Cosmos `ipRules: []` and `virtualNetworkRules: []` after migration
- [ ] 9.4 Full pipeline smoke (`deploy/scripts/04-smoke-test.sh`) — all stages succeed
- [ ] 9.5 Audit log spot check: at least one Cosmos data-plane call has `clientIpAddress` in `10.50.x.x`
- [ ] 9.6 ACR pull works from the new env

## 10. Cleanup
- [ ] 10.1 Remove the temporary IP allowlist on Cosmos (left over from `fix-decisions-page-empty-on-cold-load`)
- [ ] 10.2 Delete the old non-VNET CAE env after 24h
- [ ] 10.3 Update skill "Live URLs" section with final FQDNs
- [ ] 10.4 Archive this change to `openspec/changes/archive/`
