#!/usr/bin/env pwsh
$ErrorActionPreference = "Continue"
$payload = $input | Out-String
$obj = $payload | ConvertFrom-Json
$toolInput = ($obj.tool_input -as [string])
if (-not $toolInput) { '{"allow": true}'; exit 0 }
if ($toolInput.Length -gt 8000) { $toolInput = $toolInput.Substring(0, 8000) }

if ($toolInput -match '(MRN|patient_id|SSN|DOB[\s_-]*[0-9]{4})') {
    $bundleRef = "security/v0.1.0/PHI-001"
    $detail = "raw PHI pattern detected in tool input"
    if ($env:LEDGER_MCP_URL -and $env:LEDGER_MCP_TOKEN) {
        try {
            $body = @{
                team_id = (if ($env:LEDGER_TEAM_ID) { $env:LEDGER_TEAM_ID } else { "team-demo" })
                agent_session_id = $obj.session_id
                runtime_kind = "phi_block"
                actor = @{ kind = "agent"; id = "github-copilot-ide" }
                decision = "blocked: $detail (tool=$($obj.tool_name))"
                phi_class = "high"
                bundle_refs = @($bundleRef)
            } | ConvertTo-Json
            Invoke-RestMethod -Method Post -Uri "$($env:LEDGER_MCP_URL)/tools/ledger.write_runtime" `
                -Headers @{ "Authorization" = "Bearer $($env:LEDGER_MCP_TOKEN)" } `
                -ContentType "application/json" -Body $body -TimeoutSec 3 | Out-Null
        } catch { }
    }
    @{ allow = $false; reason = "$detail (cited: $bundleRef). Use redacted_id() helper." } | ConvertTo-Json -Compress
    exit 0
}
'{"allow": true}'
exit 0
