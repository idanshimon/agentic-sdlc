// agentic-sdlc v0.7 — Phase 6 of add-cosmos-private-endpoint-v07
// Storage private endpoint (blob) + flip publicNetworkAccess Disabled
//
// Same pattern as cosmos-private.bicep: PE first, soak, then flip public access.

@description('Location for all resources')
param location string = resourceGroup().location

@description('Name suffix (matches base.bicep)')
param suffix string = 'tj6c673gu6x5w'

@description('Storage account name')
param storageAccountName string = 'stagentic${suffix}'

@description('VNET name')
param vnetName string = 'vnet-agentic-v07'

@description('PE subnet name')
param peSubnetName string = 'snet-pe'

@description('Flip publicNetworkAccess to Disabled. Set true only after VNET-integrated CAE is verified reaching Storage via PE.')
param disablePublicAccess bool = false

// References to existing resources
resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}

resource vnet 'Microsoft.Network/virtualNetworks@2024-01-01' existing = {
  name: vnetName
}

resource peSubnet 'Microsoft.Network/virtualNetworks/subnets@2024-01-01' existing = {
  parent: vnet
  name: peSubnetName
}

resource dnsBlob 'Microsoft.Network/privateDnsZones@2020-06-01' existing = {
  name: 'privatelink.blob.core.windows.net'
}

// ---------- Private endpoint for blob ----------
resource blobPe 'Microsoft.Network/privateEndpoints@2024-01-01' = {
  name: 'pe-${storageAccountName}-blob'
  location: location
  properties: {
    subnet: { id: peSubnet.id }
    privateLinkServiceConnections: [
      {
        name: 'plsc-${storageAccountName}-blob'
        properties: {
          privateLinkServiceId: storage.id
          groupIds: [ 'blob' ]
        }
      }
    ]
  }
}

resource blobPeDnsGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-01-01' = {
  parent: blobPe
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'privatelink-blob-core-windows-net'
        properties: { privateDnsZoneId: dnsBlob.id }
      }
    ]
  }
}

// ---------- Optionally flip publicNetworkAccess ----------
resource storageLock 'Microsoft.Storage/storageAccounts@2023-05-01' = if (disablePublicAccess) {
  name: storageAccountName
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    accessTier: 'Hot'
    publicNetworkAccess: 'Disabled'
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Deny'
      ipRules: []
      virtualNetworkRules: []
    }
  }
  dependsOn: [ blobPeDnsGroup ]
}

output blobPeId string = blobPe.id
output blobPeName string = blobPe.name
output publicAccessFlipped bool = disablePublicAccess
