#!/usr/bin/env pwsh
# Hook: SessionStart (PowerShell variant)
$ErrorActionPreference = "Continue"
$payload = $input | Out-String
$repoDir = $env:GITHUB_REPOSITORY_DIR
if (-not $repoDir) { $repoDir = (Get-Location).Path }
$agentsMd = Join-Path $repoDir "AGENTS.md"

$agentsMdContent = ""
if (Test-Path $agentsMd) {
    $agentsMdContent = (Get-Content $agentsMd -Raw)
    if ($agentsMdContent.Length -gt 4000) {
        $agentsMdContent = $agentsMdContent.Substring(0, 4000)
    }
}

$ledgerRecent = ""
if ($env:LEDGER_MCP_URL -and $env:LEDGER_MCP_TOKEN) {
    $teamId = if ($env:LEDGER_TEAM_ID) { $env:LEDGER_TEAM_ID } else { "team-demo" }
    try {
        $resp = Invoke-RestMethod -Method Post -Uri "$($env:LEDGER_MCP_URL)/tools/ledger.query" `
            -Headers @{ "Authorization" = "Bearer $($env:LEDGER_MCP_TOKEN)" } `
            -ContentType "application/json" `
            -Body (@{ team_id = $teamId; limit = 5 } | ConvertTo-Json) `
            -TimeoutSec 4
        $ledgerRecent = $resp | ConvertTo-Json -Depth 4
    } catch {
        $ledgerRecent = ""
    }
}

$context = ""
if ($agentsMdContent) {
    $context += "## Repository agent guardrails (AGENTS.md)`n`n$agentsMdContent`n`n"
}
if ($ledgerRecent) {
    $context += "## Recent Decision Ledger entries`n`n``````json`n$ledgerRecent`n```````n"
}

if ($context) {
    @{ additionalContext = $context } | ConvertTo-Json -Compress
} else {
    "{}"
}
exit 0
