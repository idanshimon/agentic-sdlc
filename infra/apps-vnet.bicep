// agentic-sdlc v0.7 — Phase 4b of add-cosmos-private-endpoint-v07
// Deploy the 3 apps onto the new VNET-integrated CAE env with -vnet suffixed names.
// Old apps (ca-orchestrator, ca-ledger-mcp, ca-ledger-ui) stay running for rollback window.
//
// After verification:
//   - Skill `customer-engagement/hca-agentic-sdlc-demo` Live URLs updated to -vnet FQDNs
//   - 24h soak
//   - Delete old apps + old CAE env

@description('Location')
param location string = resourceGroup().location

@description('Name suffix (matches base.bicep)')
param suffix string = 'tj6c673gu6x5w'

@description('ACR login server')
param acrLoginServer string = 'acragenticsdlc${suffix}.azurecr.io'

@description('New VNET-integrated CAE env name')
param caeName string = 'cae-agentic-v07-vnet'

@description('Image tags — match current production')
param orchestratorImageTag string = '0.7.0-rc1'
param ledgerMcpImageTag string = '0.7.0-fix-decisions-team-id'
param ledgerUiImageTag string = '1457801'

@description('Bearer token mapped to team-demo. Pass from current ca-ledger-mcp secret.')
@secure()
param ledgerMcpDemoToken string

// References
resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' existing = {
  name: 'cosmos-agentic-${suffix}'
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: 'appi-agentic-${suffix}'
}

resource workloadMi 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: 'mi-agentic-workload'
}

resource cae 'Microsoft.App/managedEnvironments@2024-03-01' existing = {
  name: caeName
}

var cosmosEndpoint = cosmosAccount.properties.documentEndpoint
var workloadMiId = workloadMi.id
var workloadMiClientId = workloadMi.properties.clientId
var appInsightsConnectionString = appInsights.properties.ConnectionString
var storageAccountName = 'stagentic${suffix}'
var ledgerMcpTokensJson = '{"${ledgerMcpDemoToken}":"team-demo"}'

// ---------- Container App: orchestrator-vnet ----------
resource caOrchestratorVnet 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-orchestrator-vnet'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${workloadMiId}': {} }
  }
  properties: {
    managedEnvironmentId: cae.id
    configuration: {
      activeRevisionsMode: 'Single'
      secrets: [
        { name: 'ledger-mcp-token', value: ledgerMcpDemoToken }
      ]
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
        corsPolicy: {
          allowedOrigins: ['*']
          allowedMethods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
          allowedHeaders: ['*']
          allowCredentials: false
          maxAge: 3600
        }
      }
      registries: [
        { server: acrLoginServer, identity: workloadMiId }
      ]
    }
    template: {
      containers: [
        {
          name: 'orchestrator'
          image: '${acrLoginServer}/orchestrator:${orchestratorImageTag}'
          resources: { cpu: 1, memory: '2Gi' }
          env: [
            { name: 'COSMOS_ENDPOINT',          value: cosmosEndpoint }
            { name: 'COSMOS_DB',                value: 'agentic-sdlc' }
            { name: 'COSMOS_LEDGER_CONTAINER',  value: 'decision-ledger' }
            { name: 'COSMOS_RUNS_CONTAINER',    value: 'pipeline-runs' }
            { name: 'STORAGE_ACCOUNT_NAME',     value: storageAccountName }
            { name: 'AZURE_CLIENT_ID',          value: workloadMiClientId }
            { name: 'APPINSIGHTS_CONNECTION_STRING', value: appInsightsConnectionString }
            { name: 'DELIVER_PROVIDER',         value: 'github' }
            { name: 'LEDGER_MCP_URL',           value: 'http://ca-ledger-mcp-vnet/' }
            { name: 'LEDGER_MCP_TOKEN',         secretRef: 'ledger-mcp-token' }
          ]
        }
      ]
      scale: { minReplicas: 1, maxReplicas: 3 }
    }
  }
}

// ---------- Container App: ledger-mcp-vnet ----------
resource caLedgerMcpVnet 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-ledger-mcp-vnet'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${workloadMiId}': {} }
  }
  properties: {
    managedEnvironmentId: cae.id
    configuration: {
      activeRevisionsMode: 'Single'
      secrets: [
        { name: 'ledger-mcp-tokens', value: ledgerMcpTokensJson }
      ]
      ingress: {
        external: true
        targetPort: 3001
        transport: 'auto'
        allowInsecure: false
        corsPolicy: {
          allowedOrigins: ['*']
          allowedMethods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
          allowedHeaders: ['*']
          allowCredentials: false
          maxAge: 3600
        }
      }
      registries: [
        { server: acrLoginServer, identity: workloadMiId }
      ]
    }
    template: {
      containers: [
        {
          name: 'ledger-mcp'
          image: '${acrLoginServer}/decision-ledger-mcp:${ledgerMcpImageTag}'
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: [
            { name: 'COSMOS_ENDPOINT',          value: cosmosEndpoint }
            { name: 'COSMOS_DB',                value: 'agentic-sdlc' }
            { name: 'COSMOS_LEDGER_CONTAINER',  value: 'decision-ledger' }
            { name: 'AZURE_CLIENT_ID',          value: workloadMiClientId }
            { name: 'MCP_TRANSPORT',            value: 'http' }
            { name: 'MCP_PORT',                 value: '3001' }
            { name: 'STANDARDS_BUNDLES_ROOT',   value: '/app/standards-bundles' }
            { name: 'LEDGER_MCP_TOKENS',        secretRef: 'ledger-mcp-tokens' }
          ]
        }
      ]
      scale: { minReplicas: 1, maxReplicas: 3 }
    }
  }
}

// ---------- Container App: ledger-ui-vnet ----------
resource caLedgerUiVnet 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-ledger-ui-vnet'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${workloadMiId}': {} }
  }
  properties: {
    managedEnvironmentId: cae.id
    configuration: {
      activeRevisionsMode: 'Single'
      secrets: [
        { name: 'ledger-mcp-token', value: ledgerMcpDemoToken }
      ]
      ingress: {
        external: true
        targetPort: 3000
        transport: 'auto'
        allowInsecure: false
      }
      registries: [
        { server: acrLoginServer, identity: workloadMiId }
      ]
    }
    template: {
      containers: [
        {
          name: 'ledger-ui'
          image: '${acrLoginServer}/ledger-insights-ui:${ledgerUiImageTag}'
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: [
            { name: 'NEXT_PUBLIC_DEMO_MODE',        value: '1' }
            { name: 'NEXT_PUBLIC_ORCHESTRATOR_URL', value: 'https://${caOrchestratorVnet.properties.configuration.ingress.fqdn}' }
            { name: 'NEXT_PUBLIC_LEDGER_MCP_URL',   value: 'https://${caLedgerMcpVnet.properties.configuration.ingress.fqdn}' }
            { name: 'ORCHESTRATOR_URL',             value: 'https://${caOrchestratorVnet.properties.configuration.ingress.fqdn}' }
            { name: 'LEDGER_MCP_URL',               value: 'https://${caLedgerMcpVnet.properties.configuration.ingress.fqdn}' }
            { name: 'LEDGER_MCP_TOKEN',             secretRef: 'ledger-mcp-token' }
            { name: 'APPINSIGHTS_CONNECTION_STRING', value: appInsightsConnectionString }
          ]
        }
      ]
      scale: { minReplicas: 1, maxReplicas: 3 }
    }
  }
}

output orchestratorFqdn string = caOrchestratorVnet.properties.configuration.ingress.fqdn
output ledgerMcpFqdn string = caLedgerMcpVnet.properties.configuration.ingress.fqdn
output ledgerUiFqdn string = caLedgerUiVnet.properties.configuration.ingress.fqdn
