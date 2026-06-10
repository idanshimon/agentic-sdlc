// agentic-sdlc v0.7 — Phase 5 of add-cosmos-private-endpoint-v07
// Cosmos private endpoint + flip publicNetworkAccess Disabled
//
// IMPORTANT: this bicep is deployed AFTER the new VNET-integrated CAE env is live
// AND apps are migrated AND DNS resolves through the PE. Premature deploy will
// lock the existing apps out of Cosmos.
//
// Order:
//   1. Phase 4 ships: new CAE env + apps migrated, FQDNs updated, soak 10 min
//   2. Verify from a VNET-resident probe that dig +short resolves to 10.50.2.x
//   3. Deploy this bicep
//   4. Verify ledger queries still 200
//   5. Verify external curl to cosmos endpoint fails (closed loop)
//
// Depends on: infra/network.bicep deployed.

@description('Location for all resources')
param location string = resourceGroup().location

@description('Name suffix (matches base.bicep)')
param suffix string = 'tj6c673gu6x5w'

@description('Cosmos account name')
param cosmosAccountName string = 'cosmos-agentic-${suffix}'

@description('VNET name')
param vnetName string = 'vnet-agentic-v07'

@description('PE subnet name')
param peSubnetName string = 'snet-pe'

@description('Flip publicNetworkAccess to Disabled. Set true only after VNET-integrated CAE + apps are verified reaching Cosmos via PE.')
param disablePublicAccess bool = false

// References to existing resources
resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' existing = {
  name: cosmosAccountName
}

resource vnet 'Microsoft.Network/virtualNetworks@2024-01-01' existing = {
  name: vnetName
}

resource peSubnet 'Microsoft.Network/virtualNetworks/subnets@2024-01-01' existing = {
  parent: vnet
  name: peSubnetName
}

resource dnsCosmos 'Microsoft.Network/privateDnsZones@2020-06-01' existing = {
  name: 'privatelink.documents.azure.com'
}

// ---------- Private endpoint for Cosmos SQL API ----------
resource cosmosPe 'Microsoft.Network/privateEndpoints@2024-01-01' = {
  name: 'pe-${cosmosAccountName}'
  location: location
  properties: {
    subnet: { id: peSubnet.id }
    privateLinkServiceConnections: [
      {
        name: 'plsc-${cosmosAccountName}'
        properties: {
          privateLinkServiceId: cosmosAccount.id
          groupIds: [ 'Sql' ]
        }
      }
    ]
  }
}

// ---------- DNS zone group ----------
resource cosmosPeDnsGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-01-01' = {
  parent: cosmosPe
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'privatelink-documents-azure-com'
        properties: { privateDnsZoneId: dnsCosmos.id }
      }
    ]
  }
}

// ---------- Optionally flip publicNetworkAccess ----------
// This is a separate deployment step gated by the disablePublicAccess param so
// the rollback story is: redeploy with disablePublicAccess=false to restore.
resource cosmosLock 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' = if (disablePublicAccess) {
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
    publicNetworkAccess: 'Disabled'
    disableLocalAuth: true
    ipRules: []
    virtualNetworkRules: []
  }
  dependsOn: [ cosmosPeDnsGroup ]
}

// ---------- Outputs ----------
output cosmosPeId string = cosmosPe.id
output cosmosPeName string = cosmosPe.name
output publicAccessFlipped bool = disablePublicAccess
