// agentic-sdlc v0.7 — Phase 1 of add-cosmos-private-endpoint-v07
// Resource group: rg-agentic-sdlc-v07-eastus2
//
// NON-DESTRUCTIVE: deploys VNET + subnets + NSGs + private DNS zones.
// No private endpoints, no flips to existing resources.
// Existing apps continue to work via public ingress.
//
// Next phases (separate bicep / scripts):
//   - Phase 2: ACR upgrade Basic→Premium + private endpoint
//   - Phase 3: Rebuild app images on private ACR base
//   - Phase 4: New VNET-integrated CAE env + migrate apps
//   - Phase 5: Cosmos private endpoint + flip public access Disabled
//   - Phase 6: Storage private endpoint + flip public access Disabled
//
// Source: openspec/changes/add-cosmos-private-endpoint-v07/

@description('Location for all resources')
param location string = resourceGroup().location

@description('VNET name')
param vnetName string = 'vnet-agentic-v07'

@description('VNET address space')
param vnetAddressPrefix string = '10.50.0.0/16'

@description('Container Apps environment subnet (delegated, /23 required by workload profiles)')
param caeSubnetPrefix string = '10.50.0.0/23'

@description('Private endpoints subnet')
param peSubnetPrefix string = '10.50.2.0/24'

@description('Management / future jump-box subnet')
param mgmtSubnetPrefix string = '10.50.3.0/24'

// ---------- NSGs ----------
// Container Apps managed env subnet — required-allows per
// https://learn.microsoft.com/azure/container-apps/networking#nsg-allow-rules
resource nsgCae 'Microsoft.Network/networkSecurityGroups@2024-01-01' = {
  name: 'nsg-${vnetName}-cae'
  location: location
  properties: {
    securityRules: [
      {
        name: 'AllowCorpNetPublic-AzureCloud-Out'
        properties: {
          access: 'Allow'
          direction: 'Outbound'
          priority: 100
          protocol: '*'
          sourceAddressPrefix: '*'
          sourcePortRange: '*'
          destinationAddressPrefix: 'AzureCloud'
          destinationPortRange: '*'
        }
      }
      {
        name: 'AllowMcrPull'
        properties: {
          access: 'Allow'
          direction: 'Outbound'
          priority: 110
          protocol: 'Tcp'
          sourceAddressPrefix: '*'
          sourcePortRange: '*'
          destinationAddressPrefix: 'MicrosoftContainerRegistry'
          destinationPortRange: '443'
        }
      }
      {
        name: 'AllowHttpsInternet'
        properties: {
          access: 'Allow'
          direction: 'Outbound'
          priority: 120
          protocol: 'Tcp'
          sourceAddressPrefix: '*'
          sourcePortRange: '*'
          destinationAddressPrefix: 'Internet'
          destinationPortRange: '443'
        }
      }
      {
        name: 'AllowVnetInbound'
        properties: {
          access: 'Allow'
          direction: 'Inbound'
          priority: 100
          protocol: '*'
          sourceAddressPrefix: 'VirtualNetwork'
          sourcePortRange: '*'
          destinationAddressPrefix: 'VirtualNetwork'
          destinationPortRange: '*'
        }
      }
    ]
  }
}

resource nsgPe 'Microsoft.Network/networkSecurityGroups@2024-01-01' = {
  name: 'nsg-${vnetName}-pe'
  location: location
  properties: {
    securityRules: [
      {
        name: 'AllowVnetInbound'
        properties: {
          access: 'Allow'
          direction: 'Inbound'
          priority: 100
          protocol: '*'
          sourceAddressPrefix: 'VirtualNetwork'
          sourcePortRange: '*'
          destinationAddressPrefix: 'VirtualNetwork'
          destinationPortRange: '*'
        }
      }
    ]
  }
}

resource nsgMgmt 'Microsoft.Network/networkSecurityGroups@2024-01-01' = {
  name: 'nsg-${vnetName}-mgmt'
  location: location
  properties: {
    securityRules: [
      {
        name: 'AllowVnetInbound'
        properties: {
          access: 'Allow'
          direction: 'Inbound'
          priority: 100
          protocol: '*'
          sourceAddressPrefix: 'VirtualNetwork'
          sourcePortRange: '*'
          destinationAddressPrefix: 'VirtualNetwork'
          destinationPortRange: '*'
        }
      }
    ]
  }
}

// ---------- Virtual network ----------
resource vnet 'Microsoft.Network/virtualNetworks@2024-01-01' = {
  name: vnetName
  location: location
  properties: {
    addressSpace: { addressPrefixes: [ vnetAddressPrefix ] }
    subnets: [
      {
        name: 'snet-cae'
        properties: {
          addressPrefix: caeSubnetPrefix
          networkSecurityGroup: { id: nsgCae.id }
          delegations: [
            {
              name: 'Microsoft.App.environments'
              properties: { serviceName: 'Microsoft.App/environments' }
            }
          ]
          // CAE env requires the subnet to NOT have a service endpoint policy
        }
      }
      {
        name: 'snet-pe'
        properties: {
          addressPrefix: peSubnetPrefix
          networkSecurityGroup: { id: nsgPe.id }
          privateEndpointNetworkPolicies: 'Disabled'
        }
      }
      {
        name: 'snet-mgmt'
        properties: {
          addressPrefix: mgmtSubnetPrefix
          networkSecurityGroup: { id: nsgMgmt.id }
        }
      }
    ]
  }
}

// ---------- Private DNS zones ----------
// These are linked to the VNET so private-endpoint DNS resolves automatically
// for any workload running in the VNET (including the future VNET-integrated CAE env).

resource dnsCosmos 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: 'privatelink.documents.azure.com'
  location: 'global'
}

resource dnsAcr 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: 'privatelink.azurecr.io'
  location: 'global'
}

resource dnsBlob 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: 'privatelink.blob.core.windows.net'
  location: 'global'
}

resource dnsKv 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: 'privatelink.vaultcore.azure.net'
  location: 'global'
}

resource dnsLinkCosmos 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: dnsCosmos
  name: 'link-${vnetName}'
  location: 'global'
  properties: {
    virtualNetwork: { id: vnet.id }
    registrationEnabled: false
  }
}

resource dnsLinkAcr 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: dnsAcr
  name: 'link-${vnetName}'
  location: 'global'
  properties: {
    virtualNetwork: { id: vnet.id }
    registrationEnabled: false
  }
}

resource dnsLinkBlob 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: dnsBlob
  name: 'link-${vnetName}'
  location: 'global'
  properties: {
    virtualNetwork: { id: vnet.id }
    registrationEnabled: false
  }
}

resource dnsLinkKv 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: dnsKv
  name: 'link-${vnetName}'
  location: 'global'
  properties: {
    virtualNetwork: { id: vnet.id }
    registrationEnabled: false
  }
}

// ---------- Outputs ----------
output vnetId string = vnet.id
output vnetName string = vnet.name
output caeSubnetId string = '${vnet.id}/subnets/snet-cae'
output peSubnetId string = '${vnet.id}/subnets/snet-pe'
output mgmtSubnetId string = '${vnet.id}/subnets/snet-mgmt'
output dnsCosmosId string = dnsCosmos.id
output dnsAcrId string = dnsAcr.id
output dnsBlobId string = dnsBlob.id
output dnsKvId string = dnsKv.id
