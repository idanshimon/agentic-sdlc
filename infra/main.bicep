// agentic-sdlc v0.7 — main infrastructure
// Resource group: rg-agentic-sdlc-v07-eastus
// Subscription: dev (b3a032cf-f672-4071-b7c8-2bcbe087bbd0)
//
// Deploys:
//   - Log Analytics workspace + Application Insights
//   - Azure Container Registry (basic SKU)
//   - Cosmos DB (NoSQL, serverless) with two containers:
//       decision-ledger (PK /team_id) + pipeline-runs (PK /run_id)
//   - Storage account (decisions blob)
//   - Container Apps environment (Consumption only — no VNET in v0.7-rc1)
//   - Three Container Apps:
//       ca-orchestrator     (FastAPI, public ingress)
//       ca-ledger-mcp       (HTTP MCP server, internal ingress)
//       ca-ledger-insights  (Next.js UI, public ingress)
//   - One Container Job:
//       cj-pipeline-doctor  (cron every 1h)
//   - User-assigned Managed Identity for all four workloads with:
//       Cosmos Built-in Data Contributor + Storage Blob Data Contributor
//
// v0.7-rc1 deliberately ships without VNET / private endpoints. The v0.6 RG
// (rg-agentic-sdlc-demo-eastus) keeps the VNET pattern proven; v0.7 demo
// optimizes for fast spin-up and easy customer fork. Production deploy guide
// in docs/PRIVATE-ENDPOINT-DEPLOY.md.

@description('Location for all resources')
param location string = resourceGroup().location

@description('Name suffix for all resources (defaults to short uniqueness hash)')
param suffix string = uniqueString(resourceGroup().id)

@description('ACR name (must be globally unique)')
param acrName string = 'acragenticsdlc${suffix}'

@description('Cosmos account name (must be globally unique)')
param cosmosAccountName string = 'cosmos-agentic-${suffix}'

@description('Storage account name (must be globally unique, lowercase only)')
param storageAccountName string = 'stagentic${suffix}'

@description('Image tags for the four images')
param orchestratorImageTag string = '0.7.0-rc1'
param ledgerMcpImageTag string = '0.7.0-rc1'
param ledgerInsightsImageTag string = '0.7.0-rc1'
param pipelineDoctorImageTag string = '0.7.0-rc1'

// ---------- Log Analytics + App Insights ----------
resource law 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'law-agentic-${suffix}'
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-agentic-${suffix}'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: law.id
  }
}

// ---------- ACR ----------
resource acr 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: acrName
  location: location
  sku: { name: 'Basic' }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

// ---------- Storage ----------
resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    accessTier: 'Hot'
  }
}

resource storageBlobSvc 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
  properties: {
    deleteRetentionPolicy: { enabled: true, days: 7 }
  }
}

resource decisionsBlob 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: storageBlobSvc
  name: 'decisions'
  properties: { publicAccess: 'None' }
}

// ---------- Cosmos ----------
resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' = {
  name: cosmosAccountName
  location: location
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    enableAutomaticFailover: false
    consistencyPolicy: { defaultConsistencyLevel: 'Session' }
    capabilities: [
      { name: 'EnableServerless' }
    ]
    locations: [
      { locationName: location, failoverPriority: 0, isZoneRedundant: false }
    ]
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: true  // MI-only data plane
  }
}

resource cosmosDb 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-05-15' = {
  parent: cosmosAccount
  name: 'agentic-sdlc'
  properties: {
    resource: { id: 'agentic-sdlc' }
  }
}

resource ledgerContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: cosmosDb
  name: 'decision-ledger'
  properties: {
    resource: {
      id: 'decision-ledger'
      partitionKey: {
        paths: [ '/team_id' ]
        kind: 'Hash'
      }
      indexingPolicy: {
        automatic: true
        indexingMode: 'consistent'
        includedPaths: [
          { path: '/*' }
        ]
        excludedPaths: [
          { path: '/"_etag"/?' }
        ]
        compositeIndexes: [
          [
            { path: '/team_id', order: 'ascending' }
            { path: '/created_at', order: 'descending' }
          ]
          [
            { path: '/entry_type', order: 'ascending' }
            { path: '/created_at', order: 'descending' }
          ]
        ]
      }
    }
  }
}

resource runsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: cosmosDb
  name: 'pipeline-runs'
  properties: {
    resource: {
      id: 'pipeline-runs'
      partitionKey: {
        paths: [ '/run_id' ]
        kind: 'Hash'
      }
    }
  }
}

// ---------- User-assigned Managed Identity ----------
resource workloadMi 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'mi-agentic-workload'
  location: location
}

// ---------- Cosmos data-plane RBAC: Built-in Data Contributor ----------
resource cosmosBuiltInDataContributor 'Microsoft.DocumentDB/databaseAccounts/sqlRoleDefinitions@2024-05-15' existing = {
  parent: cosmosAccount
  name: '00000000-0000-0000-0000-000000000002'  // built-in Data Contributor
}

resource cosmosRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, workloadMi.id, cosmosBuiltInDataContributor.id)
  properties: {
    roleDefinitionId: cosmosBuiltInDataContributor.id
    principalId: workloadMi.properties.principalId
    scope: cosmosAccount.id
  }
}

// ---------- Storage Blob Data Contributor for the MI ----------
resource storageBlobContrib 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storage
  name: guid(storage.id, workloadMi.id, 'StorageBlobDataContributor')
  properties: {
    // Storage Blob Data Contributor
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalId: workloadMi.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// ---------- ACR Pull for the MI ----------
resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: acr
  name: guid(acr.id, workloadMi.id, 'AcrPull')
  properties: {
    // AcrPull
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalId: workloadMi.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// ---------- Container Apps environment ----------
resource cae 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'cae-agentic-${suffix}'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: law.properties.customerId
        sharedKey: law.listKeys().primarySharedKey
      }
    }
  }
}

// ---------- Container App: orchestrator ----------
resource caOrchestrator 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-orchestrator'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${workloadMi.id}': {} }
  }
  properties: {
    managedEnvironmentId: cae.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
      }
      registries: [
        {
          server: '${acr.name}.azurecr.io'
          identity: workloadMi.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'orchestrator'
          image: '${acr.name}.azurecr.io/orchestrator:${orchestratorImageTag}'
          resources: { cpu: 1, memory: '2Gi' }
          env: [
            { name: 'COSMOS_ENDPOINT',          value: cosmosAccount.properties.documentEndpoint }
            { name: 'COSMOS_DB',                value: 'agentic-sdlc' }
            { name: 'COSMOS_LEDGER_CONTAINER',  value: 'decision-ledger' }
            { name: 'COSMOS_RUNS_CONTAINER',    value: 'pipeline-runs' }
            { name: 'STORAGE_ACCOUNT_NAME',     value: storage.name }
            { name: 'AZURE_CLIENT_ID',          value: workloadMi.properties.clientId }
            { name: 'APPINSIGHTS_CONNECTION_STRING', value: appInsights.properties.ConnectionString }
            { name: 'DELIVER_PROVIDER',         value: 'github' }
          ]
        }
      ]
      scale: { minReplicas: 1, maxReplicas: 3 }
    }
  }
}

// ---------- Container App: ledger-insights-ui ----------
resource caLedgerUi 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-ledger-insights'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${workloadMi.id}': {} }
  }
  properties: {
    managedEnvironmentId: cae.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 3000
        transport: 'auto'
        allowInsecure: false
      }
      registries: [
        {
          server: '${acr.name}.azurecr.io'
          identity: workloadMi.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'ledger-insights-ui'
          image: '${acr.name}.azurecr.io/ledger-insights-ui:${ledgerInsightsImageTag}'
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: [
            { name: 'NEXT_PUBLIC_ORCHESTRATOR_URL', value: 'https://${caOrchestrator.properties.configuration.ingress.fqdn}' }
            { name: 'APPINSIGHTS_CONNECTION_STRING', value: appInsights.properties.ConnectionString }
          ]
        }
      ]
      scale: { minReplicas: 1, maxReplicas: 2 }
    }
  }
}

// ---------- Container App: decision-ledger-mcp (HTTP) ----------
resource caLedgerMcp 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-ledger-mcp'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${workloadMi.id}': {} }
  }
  properties: {
    managedEnvironmentId: cae.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true   // public for hooks; in production, internal + private DNS
        targetPort: 3001
        transport: 'auto'
        allowInsecure: false
      }
      registries: [
        {
          server: '${acr.name}.azurecr.io'
          identity: workloadMi.id
        }
      ]
      secrets: [
        // LEDGER_MCP_TOKENS is set via az containerapp update --set-env-vars at deploy time
      ]
    }
    template: {
      containers: [
        {
          name: 'ledger-mcp'
          image: '${acr.name}.azurecr.io/decision-ledger-mcp:${ledgerMcpImageTag}'
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: [
            { name: 'COSMOS_ENDPOINT',          value: cosmosAccount.properties.documentEndpoint }
            { name: 'COSMOS_DB',                value: 'agentic-sdlc' }
            { name: 'COSMOS_LEDGER_CONTAINER',  value: 'decision-ledger' }
            { name: 'AZURE_CLIENT_ID',          value: workloadMi.properties.clientId }
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
    userAssignedIdentities: { '${workloadMi.id}': {} }
  }
  properties: {
    environmentId: cae.id
    configuration: {
      triggerType: 'Schedule'
      replicaTimeout: 600
      replicaRetryLimit: 1
      scheduleTriggerConfig: {
        cronExpression: '0 * * * *'  // every hour at :00
        parallelism: 1
        replicaCompletionCount: 1
      }
      registries: [
        {
          server: '${acr.name}.azurecr.io'
          identity: workloadMi.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'pipeline-doctor'
          image: '${acr.name}.azurecr.io/pipeline-doctor:${pipelineDoctorImageTag}'
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: [
            { name: 'COSMOS_ENDPOINT',          value: cosmosAccount.properties.documentEndpoint }
            { name: 'COSMOS_DB',                value: 'agentic-sdlc' }
            { name: 'AZURE_CLIENT_ID',          value: workloadMi.properties.clientId }
            { name: 'STANDARDS_BUNDLES_ROOT',   value: '/app/standards-bundles' }
            { name: 'DOCTOR_MODE',              value: 'dry-run' }  // start safe
            { name: 'LEDGER_TEAM_ID',           value: 'team-demo' }
          ]
          args: [
            '--mode'
            'dry-run'
            '--team-id'
            'team-demo'
          ]
        }
      ]
    }
  }
}

// ---------- Outputs ----------
output orchestratorFqdn string = caOrchestrator.properties.configuration.ingress.fqdn
output ledgerUiFqdn string = caLedgerUi.properties.configuration.ingress.fqdn
output ledgerMcpFqdn string = caLedgerMcp.properties.configuration.ingress.fqdn
output cosmosEndpoint string = cosmosAccount.properties.documentEndpoint
output acrLoginServer string = acr.properties.loginServer
output workloadMiClientId string = workloadMi.properties.clientId
output appInsightsConnectionString string = appInsights.properties.ConnectionString
