# Proposal: production-grade Cosmos network posture for v0.7+ — VNET integration + private endpoint

> **Status:** DRAFT — surfaces from incident 2026-06-09
> **Capability:** infrastructure
> **Severity:** P1 — every ledger query is currently traversing public internet against an IP-allowlisted Cosmos account. Posture is acceptable for the demo period but NOT acceptable for any customer-facing production engagement.
> **Related:** `fix-decisions-page-empty-on-cold-load` (this change is the durable follow-up to that fix's tactical patch)

## Why

The v0.6 (HCA Nashville) deployment ran on `vnet-agentic-sdlc 10.40.0.0/16` with private endpoints on Cosmos and Storage and `publicNetworkAccess: Disabled` everywhere. That posture matched the customer's compliance bar.

The v0.7 deployment in `rg-agentic-sdlc-v07-eastus2` regressed:

- Container Apps env `cae-agentic-tj6c673gu6x5w` has `vnet: null` (no VNET integration)
- Cosmos `cosmos-agentic-tj6c673gu6x5w` shipped with `publicNetworkAccess: Disabled` + `ipRules: []` + `vnetRules: []` — meaning **nothing could reach it**
- Storage account, ACR, Container Apps env environment ingress are all on public network
- The schema bug in `decision-ledger-mcp` (see `fix-decisions-page-empty-on-cold-load`) was masking this — when the schema rejected requests at the orchestrator boundary, no Cosmos call was made

Once the schema fix shipped 2026-06-09, every ledger query started failing with:

```
Request originated from IP 135.222.186.97 through public internet.
This is blocked by your Cosmos DB account firewall settings.
```

The tactical fix (added Container Apps egress IPs to Cosmos `ipRules` + flipped `publicNetworkAccess: Enabled`) restored function but moved us to a posture where:

1. Every ledger read traverses the public internet → Container Apps env shared NAT → Cosmos public endpoint
2. The IP allowlist is brittle — Container Apps SHARED NAT IPs can rotate, and `132.196.210.100` is the env's INBOUND staticIp not its outbound, so the allowlist depends on hard-coded Azure-region NAT prefixes (`4.150.240.0/22`, `4.150.244.0/22`, `52.255.99.0/24`)
3. We violate the customer-facing principle in `AGENTS.md`: "Never commit account keys, connection strings with embedded keys, or service-principal secrets. Managed Identity only for data-plane auth." — the spirit of this rule is "data plane never traverses public internet"; we're using MI but the data path is public

This change restores the v0.6 posture in the v0.7+ environment.

## What changes

### Infrastructure additions (`infra/network.bicep`, NEW)

A new bicep module deploys:

1. **Virtual network** `vnet-agentic-v07 10.50.0.0/16`:
   - subnet `snet-cae` (10.50.0.0/23, /23 required by Container Apps workload profile envs)
   - subnet `snet-pe` (10.50.2.0/24, private endpoints — Cosmos + ACR + Storage + KV)
   - subnet `snet-mgmt` (10.50.3.0/24, future jump-box / build-runner)
2. **NSGs** on each subnet (deny inbound by default, allow CAE-managed flows per docs)
3. **Private DNS zones** linked to the VNET: `privatelink.documents.azure.com`, `privatelink.azurecr.io`, `privatelink.blob.core.windows.net`, `privatelink.vaultcore.azure.net`

### Migrations to existing resources

1. **Container Apps env** — recreate `cae-agentic-tj6c673gu6x5w` with `vnetConfiguration.infrastructureSubnetId` pointing at `snet-cae`. Container Apps envs cannot be VNET-integrated in-place; we deploy a NEW env (`cae-agentic-v07-vnet`) and migrate the 3 apps, then delete the old env. Apps' FQDNs change; UI bookmarks need refresh once.
2. **Cosmos** — add a private endpoint into `snet-pe` for the SQL API on `cosmos-agentic-tj6c673gu6x5w`, then flip `publicNetworkAccess: Disabled` and clear `ipRules`. Verify the private endpoint resolves through the linked DNS zone before flipping public access.
3. **ACR** — add a private endpoint into `snet-pe`. ACR registration data plane (image pull) shifts to private. The Premium-tier requirement bumps cost from Basic ~$0.17/day to Premium ~$1.67/day.
4. **Storage** (decision-ledger blobs) — add a private endpoint into `snet-pe`, flip `publicNetworkAccess: Disabled`.
5. **Key Vault** (when added; currently Container App secrets are inline) — same treatment.

### Code changes

None for the runtime apps. The orchestrator, ledger-mcp, and pipeline-doctor already use Managed Identity + endpoint URLs, which work transparently against private endpoints once DNS resolves to the private IP.

The only code change is `apps/decision-ledger-mcp/Dockerfile` — currently uses `node:20-alpine` from Docker Hub via the Container Apps env's egress; once env is VNET-integrated, base image pulls go through private ACR. We retag `node:20-alpine` into the registry as `private-base/node:20-alpine` and use `FROM acragenticsdlctj6c673gu6x5w.azurecr.io/private-base/node:20-alpine`.

### CI/CD

1. `deploy/scripts/01-deploy-base.sh` — add network module to the bicep entry
2. `deploy/scripts/02-build-and-push-images.sh` — image pulls during `az acr build` are server-side, no change
3. `deploy/scripts/03-deploy-apps.sh` — point at the new VNET-integrated CAE env; FQDN outputs flow downstream
4. New `deploy/scripts/06-rotate-network.sh` — one-shot migration runbook documenting the env rebuild + DNS settle wait + cutover

## Why this design

**Two-subnet split (snet-cae + snet-pe), not one shared subnet.** Container Apps requires a delegated subnet `Microsoft.App/environments`; private endpoints can't share it. Separating them also lets us apply different NSG postures to each.

**`/23` for snet-cae.** Required by Container Apps workload-profile envs even though we're well under the IP budget. A `/24` works for Consumption-only envs but locks us out of moving to workload profiles (dedicated compute for the orchestrator's long-running runs).

**Private endpoint, not Service Endpoint.** Service Endpoints are cheaper but don't carry across regions, don't have audit visibility for the customer's compliance team, and Cosmos's private DNS story is cleaner with PEs. Service Endpoints are the wrong choice for any HLS customer.

**Recreate CAE env, don't try to VNET-integrate in place.** Azure ContainerApps explicitly does not support adding VNET to an existing env (`Cannot update infrastructureSubnetId on an existing environment` per the API). The migration cost is one-time; ingress FQDNs change but that's a known Container Apps quirk.

**Premium ACR.** Required for private endpoints. Cost delta is ~$1.50/day; well below noise on customer demos. Audit log retention bumps to 90 days as a side effect.

**Don't move to AKS.** The standing posture (per `~/.hermes/agent-os/10-work/_moc.md` and skill notes) is "Container Apps for any v0.7+ HLS demo work, not AKS or VMs." Container Apps + VNET satisfies the compliance bar without AKS's operational tax. Re-litigate ONLY if a customer has an existing AKS investment and asks for it.

## Operational risks

1. **FQDN cutover.** `ca-ledger-ui.whitewater-f74a5db8.eastus2.azurecontainerapps.io` becomes a NEW domain on the new env (different default-domain hash). Demo URLs in skills, runbooks, scripts ALL need refresh in one commit. The skill's "Live URLs" section is the canonical source for these — patch in the same change.
2. **DNS propagation.** Private DNS zones can take 5-15 min to fully settle. The cutover script has a `dig +short` poll loop with a 20-min timeout.
3. **IP space collision with v0.6.** v0.6 used `10.40.0.0/16`; v0.7 will use `10.50.0.0/16`. If we ever VNET-peer the two for cross-version testing, no conflict.
4. **Customer self-deploy reproducibility.** The PRIVATE-ENDPOINT-DEPLOY.md doc from v0.6 is the template. Port verbatim into v0.7 docs as `docs/PRIVATE-ENDPOINT-DEPLOY-v07.md`.

## Why not Azure Front Door / API Management front-end?

Out of scope for this change — that's the gateway pattern. Customers like HCA who have an existing APIM treat that as their gateway; this change is about the data-plane between the orchestrator/ledger-mcp and Cosmos/Storage/ACR. APIM can sit in front of the public ingress separately without changing the data-plane posture.

## Validation plan

1. `bash deploy/scripts/04-smoke-test.sh` against the new VNET-integrated env — every stage of the orchestrator pipeline runs, every PHI classification call succeeds, ledger reads + writes succeed.
2. `dig +short cosmos-agentic-tj6c673gu6x5w.documents.azure.com` from the orchestrator container resolves to a `10.50.2.x` private IP, NOT a public IP.
3. From outside the VNET, `curl https://cosmos-agentic-tj6c673gu6x5w.documents.azure.com` MUST fail (publicNetworkAccess: Disabled enforced).
4. Cosmos `ipRules` and `virtualNetworkRules` MUST both be empty (private endpoint is the only ingress).
5. Audit log: every Cosmos data-plane call MUST have `clientIpAddress` in the `10.50.x.x` range.

## Estimated work

- Bicep authoring: 4-6 hours
- CAE recreate + migrate (3 apps): 2-3 hours including DNS settle waits
- Validation + smoke: 2 hours
- Doc + runbook updates: 1 hour

Single-day timebox. Schedule alongside any v0.7 demo prep window where temporary URL rotation is acceptable.
