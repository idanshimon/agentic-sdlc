## ADDED Requirements

### Requirement: Container Apps env MUST be VNET-integrated

The Container Apps env hosting the orchestrator, decision-ledger-mcp, pipeline-doctor, and ledger-insights-ui MUST have `vnetConfiguration.infrastructureSubnetId` set to a delegated `Microsoft.App/environments` subnet. The env's outbound traffic MUST egress through the VNET, not through Container Apps' shared public NAT.

#### Scenario: env has VNET integration

- **WHEN** `az containerapp env show` is invoked on the production env
- **THEN** `properties.vnetConfiguration.infrastructureSubnetId` MUST be non-null
- **AND** the referenced subnet MUST have `Microsoft.App/environments` delegation

#### Scenario: outbound traffic uses VNET egress

- **WHEN** any Container App in the env opens an outbound connection to a private endpoint within the same VNET
- **THEN** the destination MUST resolve to a private IP within the VNET's address space
- **AND** the source IP visible to the destination MUST NOT be a public Container Apps NAT IP

### Requirement: Cosmos data plane MUST be private-endpoint only

The Cosmos account backing the decision ledger MUST have `publicNetworkAccess: Disabled`, `ipRules: []`, and `virtualNetworkRules: []`. The only ingress path MUST be a private endpoint resolved via private DNS within the same VNET as the Container Apps env.

#### Scenario: Cosmos rejects public-internet calls

- **WHEN** a client outside the VNET attempts to connect to the Cosmos data-plane endpoint
- **THEN** the connection MUST fail (publicNetworkAccess: Disabled enforced)

#### Scenario: Cosmos allows private-endpoint calls from the VNET

- **WHEN** a client inside the VNET resolves the Cosmos endpoint via DNS
- **THEN** the resolved IP MUST be a private address within the VNET
- **AND** the connection MUST succeed without any IP allowlist entry

#### Scenario: Cosmos firewall rules are empty

- **WHEN** `az cosmosdb show` is invoked
- **THEN** `properties.ipRules` MUST be empty
- **AND** `properties.virtualNetworkRules` MUST be empty
- **AND** `properties.publicNetworkAccess` MUST equal `"Disabled"`

### Requirement: ACR data plane MUST be private-endpoint only (Premium SKU)

The ACR backing the v0.7+ deployment MUST be Premium tier with a private endpoint into the VNET's PE subnet. Image pulls from Container Apps in the same VNET MUST resolve to private IPs. Public access MUST be disabled.

#### Scenario: ACR is Premium and private-endpoint enabled

- **WHEN** `az acr show` is invoked
- **THEN** `sku.name` MUST equal `"Premium"`
- **AND** `properties.publicNetworkAccess` MUST equal `"Disabled"`

### Requirement: Storage data plane MUST be private-endpoint only

The Storage account backing decision-ledger blob writes MUST have `publicNetworkAccess: Disabled` and a blob-endpoint private endpoint in the same VNET as the Container Apps env.

#### Scenario: Storage rejects public access

- **WHEN** an external client attempts to access the blob endpoint
- **THEN** the request MUST fail (publicNetworkAccess: Disabled)

### Requirement: Private DNS zones MUST be linked to the VNET

The four canonical Azure private DNS zones — `privatelink.documents.azure.com`, `privatelink.azurecr.io`, `privatelink.blob.core.windows.net`, `privatelink.vaultcore.azure.net` — MUST exist in the deployment's resource group and MUST be linked to the orchestrator VNET. Without these links, private endpoints exist but DNS resolves to public IPs and the data-plane calls still traverse the internet.

#### Scenario: all four canonical zones exist and are linked

- **WHEN** the network bicep module deploys
- **THEN** all four private DNS zones MUST be created
- **AND** each MUST have a virtual network link to the orchestrator VNET
