#!/usr/bin/env pwsh
$ErrorActionPreference = "Continue"
$payload = $input | Out-String
if (-not ($env:LEDGER_MCP_URL -and $env:LEDGER_MCP_TOKEN)) { "{}"; exit 0 }
try {
    $obj = $payload | ConvertFrom-Json
    $prompt = ($obj.user_prompt -as [string])
    if (-not $prompt) { "{}"; exit 0 }
    if ($prompt.Length -gt 200) { $prompt = $prompt.Substring(0, 200) }
    $teamId = if ($env:LEDGER_TEAM_ID) { $env:LEDGER_TEAM_ID } else { "team-demo" }
    $agentId = if ($env:COPILOT_AGENT_ID) { $env:COPILOT_AGENT_ID } else { "github-copilot-ide" }
    $body = @{
        team_id = $teamId
        agent_session_id = $obj.session_id
        runtime_kind = "ide_session_summary"
        actor = @{ kind = "human"; id = ($env:USER ?? "ide-user") }
        decision = "intent: $prompt"
        bundle_refs = @()
    } | ConvertTo-Json
    Invoke-RestMethod -Method Post -Uri "$($env:LEDGER_MCP_URL)/tools/ledger.write_runtime" `
        -Headers @{ "Authorization" = "Bearer $($env:LEDGER_MCP_TOKEN)" } `
        -ContentType "application/json" -Body $body -TimeoutSec 3 | Out-Null
} catch { }
"{}"
exit 0
