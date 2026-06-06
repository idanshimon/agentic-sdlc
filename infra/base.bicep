// agentic-sdlc v0.7 — base infrastructure (no container apps)
// Resource group: rg-agentic-sdlc-v07-eastus2
// Subscription: dev (b3a032cf-f672-4071-b7c8-2bcbe087bbd0)
//
// This Bicep deploys EVERYTHING except the Container Apps + Container Job.
// Reason: Container Apps reference ACR images that must exist before
// provisioning. Two-phase deploy:
//   1. base.bicep      → ACR + Cosmos + Storage + LAW + AppI + MI + RBAC + CAE
//   2. az acr build    → push 3 images
//   3. apps.bicep      → Container Apps + Container Job (referencing base outputs)
//
// Companion: apps.bicep

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
    disableLocalAuth: true
  }
}

resource cosmosDb 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-05-15' = {
  parent: cosmosAccount
  name: 'agentic-sdlc'
  properties: { resource: { id: 'agentic-sdlc' } }
}

resource ledgerContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: cosmosDb
  name: 'decision-ledger'
  properties: {
    resource: {
      id: 'decision-ledger'
      partitionKey: { paths: [ '/team_id' ], kind: 'Hash' }
      indexingPolicy: {
        automatic: true
        indexingMode: 'consistent'
        includedPaths: [ { path: '/*' } ]
        excludedPaths: [ { path: '/"_etag"/?' } ]
        compositeIndexes: [
          [ { path: '/team_id', order: 'ascending' }, { path: '/created_at', order: 'descending' } ]
          [ { path: '/entry_type', order: 'ascending' }, { path: '/created_at', order: 'descending' } ]
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
      partitionKey: { paths: [ '/run_id' ], kind: 'Hash' }
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
  name: '00000000-0000-0000-0000-000000000002'
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

// ---------- Storage Blob Data Contributor ----------
resource storageBlobContrib 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storage
  name: guid(storage.id, workloadMi.id, 'StorageBlobDataContributor')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalId: workloadMi.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// ---------- ACR Pull ----------
resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: acr
  name: guid(acr.id, workloadMi.id, 'AcrPull')
  properties: {
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

// ---------- Outputs (consumed by apps.bicep) ----------
output acrName string = acr.name
output acrLoginServer string = acr.properties.loginServer
output cosmosEndpoint string = cosmosAccount.properties.documentEndpoint
output storageAccountName string = storage.name
output workloadMiId string = workloadMi.id
output workloadMiClientId string = workloadMi.properties.clientId
output workloadMiPrincipalId string = workloadMi.properties.principalId
output caeId string = cae.id
output caeName string = cae.name
output appInsightsConnectionString string = appInsights.properties.ConnectionString
output lawCustomerId string = law.properties.customerId
