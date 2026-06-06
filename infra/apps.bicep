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
      ingress: {
        external: true
        targetPort: 8000
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
      ingress: {
        external: true
        targetPort: 3001
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
