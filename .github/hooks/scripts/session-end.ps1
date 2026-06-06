#!/usr/bin/env pwsh
$ErrorActionPreference = "Continue"
$payload = $input | Out-String
if (-not ($env:LEDGER_MCP_URL -and $env:LEDGER_MCP_TOKEN)) { "{}"; exit 0 }
try {
    $obj = $payload | ConvertFrom-Json
    $body = @{
        team_id = (if ($env:LEDGER_TEAM_ID) { $env:LEDGER_TEAM_ID } else { "team-demo" })
        agent_session_id = $obj.session_id
        runtime_kind = "ide_session_summary"
        actor = @{ kind = "agent"; id = "github-copilot-ide" }
        decision = "session ended: $($obj.reason) in $($obj.cwd)"
        bundle_refs = @()
    } | ConvertTo-Json
    Invoke-RestMethod -Method Post -Uri "$($env:LEDGER_MCP_URL)/tools/ledger.write_runtime" `
        -Headers @{ "Authorization" = "Bearer $($env:LEDGER_MCP_TOKEN)" } `
        -ContentType "application/json" -Body $body -TimeoutSec 3 | Out-Null
} catch { }
"{}"
exit 0
