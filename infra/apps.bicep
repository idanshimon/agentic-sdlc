// agentic-sdlc v0.7 — Container Apps + Container Job
// Companion to base.bicep. Run AFTER images are built in ACR.
//
// Inputs come from base.bicep outputs (run via the deploy script which
// passes them in via az deployment group create --parameters).

@description('Location (defaults to RG location)')
param location string = resourceGroup().location

@description('ACR login server (e.g. myacr.azurecr.io)')
param acrLoginServer string

@description('Cosmos document endpoint URL')
param cosmosEndpoint string

@description('Storage account name')
param storageAccountName string

@description('User-assigned MI resource id')
param workloadMiId string

@description('User-assigned MI client id (for env var injection)')
param workloadMiClientId string

@description('Container Apps Environment id')
param caeId string

@description('Application Insights connection string')
param appInsightsConnectionString string

@description('Image tags')
param orchestratorImageTag string = '0.7.0-rc1'
param ledgerMcpImageTag string = '0.7.0-rc1'
param pipelineDoctorImageTag string = '0.7.0-rc1'
param ledgerUiImageTag string = '0.7.0-rc1'

@description('Bearer token for the demo team. Mapped to team-demo in LEDGER_MCP_TOKENS. Generated at deploy time.')
@secure()
param ledgerMcpDemoToken string

// JSON map consumed by apps/decision-ledger-mcp/src/auth.ts at startup.
// Maps bearer tokens → team_id. v0.7-rc1 ships with one demo team; production
// adds per-team tokens or replaces with Entra App auth (see auth.ts header).
var ledgerMcpTokensJson = '{"${ledgerMcpDemoToken}":"team-demo"}'

// ---------- Container App: orchestrator ----------
resource caOrchestrator 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-orchestrator'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${workloadMiId}': {} }
  }
  properties: {
    managedEnvironmentId: caeId
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
            { name: 'LEDGER_MCP_URL',           value: 'http://ca-ledger-mcp/' }
            { name: 'LEDGER_MCP_TOKEN',         secretRef: 'ledger-mcp-token' }
          ]
        }
      ]
      scale: { minReplicas: 1, maxReplicas: 3 }
    }
  }
}

// ---------- Container App: decision-ledger-mcp (HTTP) ----------
resource caLedgerMcp 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-ledger-mcp'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${workloadMiId}': {} }
  }
  properties: {
    managedEnvironmentId: caeId
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

// ---------- Container App: ledger-insights-ui (Next.js dashboard) ----------
resource caLedgerUi 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-ledger-ui'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${workloadMiId}': {} }
  }
  properties: {
    managedEnvironmentId: caeId
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
            // Browser uses the NEXT_PUBLIC_* for /healthz + /tools (CORS-allowed,
            // unauthenticated). All authenticated MCP calls go through same-origin
            // Next.js API routes; those read LEDGER_MCP_TOKEN server-side only.
            { name: 'NEXT_PUBLIC_ORCHESTRATOR_URL', value: 'https://${caOrchestrator.properties.configuration.ingress.fqdn}' }
            { name: 'NEXT_PUBLIC_LEDGER_MCP_URL',   value: 'https://${caLedgerMcp.properties.configuration.ingress.fqdn}' }
            { name: 'ORCHESTRATOR_URL',             value: 'https://${caOrchestrator.properties.configuration.ingress.fqdn}' }
            { name: 'LEDGER_MCP_URL',               value: 'https://${caLedgerMcp.properties.configuration.ingress.fqdn}' }
            { name: 'LEDGER_MCP_TOKEN',             secretRef: 'ledger-mcp-token' }
          ]
        }
      ]
      scale: { minReplicas: 1, maxReplicas: 3 }
    }
  }
}

// ---------- Container Job: pipeline-doctor (cron every 1h) ----------
resource cjDoctor 'Microsoft.App/jobs@2024-03-01' = {
  name: 'cj-pipeline-doctor'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${workloadMiId}': {} }
  }
  properties: {
    environmentId: caeId
    configuration: {
      triggerType: 'Schedule'
      replicaTimeout: 600
      replicaRetryLimit: 1
      secrets: [
        { name: 'ledger-mcp-token', value: ledgerMcpDemoToken }
      ]
      scheduleTriggerConfig: {
        cronExpression: '0 * * * *'
        parallelism: 1
        replicaCompletionCount: 1
      }
      registries: [
        { server: acrLoginServer, identity: workloadMiId }
      ]
    }
    template: {
      containers: [
        {
          name: 'pipeline-doctor'
          image: '${acrLoginServer}/pipeline-doctor:${pipelineDoctorImageTag}'
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: [
            { name: 'COSMOS_ENDPOINT',          value: cosmosEndpoint }
            { name: 'COSMOS_DB',                value: 'agentic-sdlc' }
            { name: 'AZURE_CLIENT_ID',          value: workloadMiClientId }
            { name: 'STANDARDS_BUNDLES_ROOT',   value: '/app/standards-bundles' }
            { name: 'DOCTOR_MODE',              value: 'dry-run' }
            { name: 'LEDGER_TEAM_ID',           value: 'team-demo' }
            { name: 'LEDGER_MCP_URL',           value: 'http://ca-ledger-mcp/' }
            { name: 'LEDGER_MCP_TOKEN',         secretRef: 'ledger-mcp-token' }
          ]
          args: [
            '--mode', 'dry-run', '--team-id', 'team-demo'
          ]
        }
      ]
    }
  }
}

// ---------- Outputs ----------
output orchestratorFqdn string = caOrchestrator.properties.configuration.ingress.fqdn
output ledgerMcpFqdn string = caLedgerMcp.properties.configuration.ingress.fqdn
output ledgerUiFqdn string = caLedgerUi.properties.configuration.ingress.fqdn
