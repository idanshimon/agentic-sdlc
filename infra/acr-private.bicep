// agentic-sdlc v0.7 — Phase 2 of add-cosmos-private-endpoint-v07
// ACR Basic → Premium upgrade + private endpoint
//
// Premium tier is REQUIRED for private endpoints (Basic + Standard don't support PE).
// Cost delta: Basic ~$0.17/day → Premium ~$1.67/day (~$45/month delta).
// Side benefit: audit log retention bumps from 7d to 90d.
//
// publicNetworkAccess remains ENABLED in this phase — we keep public access for the
// existing `az acr build` and `az containerapp create --image` flows to keep working.
// Public access flips Disabled only AFTER:
//   - Phase 3 (app images rebuilt successfully through any path)
//   - Phase 4 (new VNET-integrated CAE env pulls images via PE successfully)
//
// Depends on: infra/network.bicep deployed first.

@description('Location for all resources')
param location string = resourceGroup().location

@description('Name suffix (matches base.bicep)')
param suffix string = 'tj6c673gu6x5w'

@description('ACR name')
param acrName string = 'acragenticsdlc${suffix}'

@description('VNET name (from network.bicep)')
param vnetName string = 'vnet-agentic-v07'

@description('PE subnet name (from network.bicep)')
param peSubnetName string = 'snet-pe'

// References to existing resources
resource acr 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' existing = {
  name: acrName
}

resource vnet 'Microsoft.Network/virtualNetworks@2024-01-01' existing = {
  name: vnetName
}

resource peSubnet 'Microsoft.Network/virtualNetworks/subnets@2024-01-01' existing = {
  parent: vnet
  name: peSubnetName
}

resource dnsAcr 'Microsoft.Network/privateDnsZones@2020-06-01' existing = {
  name: 'privatelink.azurecr.io'
}

// ---------- Upgrade ACR to Premium (in-place) ----------
// Bicep applies sku changes via PUT on the registry resource.
resource acrPremium 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: acrName
  location: location
  sku: { name: 'Premium' }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled' // KEEP enabled; we flip in a later phase after cutover
    networkRuleBypassOptions: 'AzureServices'
    zoneRedundancy: 'Disabled'
  }
}

// ---------- Private endpoint for ACR ----------
resource acrPe 'Microsoft.Network/privateEndpoints@2024-01-01' = {
  name: 'pe-${acrName}'
  location: location
  properties: {
    subnet: { id: peSubnet.id }
    privateLinkServiceConnections: [
      {
        name: 'plsc-${acrName}'
        properties: {
          privateLinkServiceId: acr.id
          groupIds: [ 'registry' ]
        }
      }
    ]
  }
  dependsOn: [ acrPremium ]
}

// ---------- DNS zone group: wires PE into private DNS automatically ----------
resource acrPeDnsGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-01-01' = {
  parent: acrPe
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'privatelink-azurecr-io'
        properties: { privateDnsZoneId: dnsAcr.id }
      }
    ]
  }
}

// ---------- Outputs ----------
output acrId string = acrPremium.id
output acrLoginServer string = acrPremium.properties.loginServer
output acrSku string = acrPremium.sku.name
output acrPeId string = acrPe.id
output acrPeName string = acrPe.name
