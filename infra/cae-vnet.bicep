// agentic-sdlc v0.7 — Phase 4 of add-cosmos-private-endpoint-v07
// New VNET-integrated Container Apps environment
//
// CAE envs CANNOT be VNET-integrated in place (Azure API rejects update on
// infrastructureSubnetId). So we create a NEW env and migrate apps in a
// follow-up step (deploy/scripts/06-migrate-apps-to-vnet.sh).
//
// Apps' ingress FQDNs change — different default-domain hash for the new env.
// Skill `customer-engagement/hca-agentic-sdlc-demo` "Live URLs" section needs
// patching as part of the migration.
//
// Depends on: infra/network.bicep deployed.

@description('Location for all resources')
param location string = resourceGroup().location

@description('Name suffix (matches base.bicep)')
param suffix string = 'tj6c673gu6x5w'

@description('VNET name')
param vnetName string = 'vnet-agentic-v07'

@description('CAE subnet name (Microsoft.App/environments delegated)')
param caeSubnetName string = 'snet-cae'

@description('New CAE env name (does NOT replace the existing cae-agentic-{suffix})')
param newCaeName string = 'cae-agentic-v07-vnet'

// References to existing resources
resource law 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: 'law-agentic-${suffix}'
}

resource vnet 'Microsoft.Network/virtualNetworks@2024-01-01' existing = {
  name: vnetName
}

resource caeSubnet 'Microsoft.Network/virtualNetworks/subnets@2024-01-01' existing = {
  parent: vnet
  name: caeSubnetName
}

// ---------- New VNET-integrated Container Apps environment ----------
resource cae 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: newCaeName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: law.properties.customerId
        sharedKey: law.listKeys().primarySharedKey
      }
    }
    vnetConfiguration: {
      infrastructureSubnetId: caeSubnet.id
      internal: false                  // public ingress (FQDNs reachable from internet)
    }
    zoneRedundant: false
  }
}

output caeId string = cae.id
output caeName string = cae.name
output caeDefaultDomain string = cae.properties.defaultDomain
output caeStaticIp string = cae.properties.staticIp
