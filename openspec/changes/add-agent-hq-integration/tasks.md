# Tasks — add Agent HQ integration

## Decision Ledger MCP server

- [ ] `apps/decision-ledger-mcp/package.json` — Node 20, `@modelcontextprotocol/sdk` pinned, `@azure/cosmos`, `zod`, `vitest`
- [ ] `apps/decision-ledger-mcp/tsconfig.json` strict mode
- [ ] `apps/decision-ledger-mcp/src/server.ts` — MCP server entrypoint, stdio transport
- [ ] `apps/decision-ledger-mcp/src/tools/query.ts`
- [ ] `apps/decision-ledger-mcp/src/tools/write-runtime.ts`
- [ ] `apps/decision-ledger-mcp/src/tools/find-precedent.ts`
- [ ] `apps/decision-ledger-mcp/src/tools/get-bundle.ts`
- [ ] `apps/decision-ledger-mcp/src/tools/classify-phi.ts`
- [ ] `apps/decision-ledger-mcp/src/auth.ts` — bearer token validation
- [ ] `apps/decision-ledger-mcp/src/cosmos-client.ts` — DefaultAzureCredential, MI auth
- [ ] `apps/decision-ledger-mcp/src/copilot-sdk-client.ts` — thin SDK wrapper for future Mission Control integration
- [ ] `apps/decision-ledger-mcp/Dockerfile` — node 20-alpine, multi-stage build
- [ ] `apps/decision-ledger-mcp/README.md`
- [ ] `apps/decision-ledger-mcp/tests/` — 15 cases minimum

## Hook bundle

- [ ] `.github/hooks/session-start.json`
- [ ] `.github/hooks/scripts/session-start.sh`
- [ ] `.github/hooks/scripts/session-start.ps1`
- [ ] `.github/hooks/user-prompt-submit.json`
- [ ] `.github/hooks/scripts/user-prompt-submit.sh`
- [ ] `.github/hooks/scripts/user-prompt-submit.ps1`
- [ ] `.github/hooks/pre-tool-use.json`
- [ ] `.github/hooks/scripts/pre-tool-use.sh` — PHI classifier via MCP, BLOCK on raw PHI
- [ ] `.github/hooks/scripts/pre-tool-use.ps1`
- [ ] `.github/hooks/post-tool-use.json`
- [ ] `.github/hooks/scripts/post-tool-use.sh` — write ledger entry
- [ ] `.github/hooks/scripts/post-tool-use.ps1`
- [ ] `.github/hooks/session-end.json`
- [ ] `.github/hooks/scripts/session-end.sh`
- [ ] `.github/hooks/scripts/session-end.ps1`
- [ ] `.github/hooks/README.md` — install instructions, env vars, troubleshooting
- [ ] `scripts/validate-hook-bundle.sh` — checks all 10 scripts are present and executable

## Custom agents

- [ ] `.github/agents/assessor.agent.md`
- [ ] `.github/agents/architect.agent.md`
- [ ] `.github/agents/codegen.agent.md`
- [ ] `.github/agents/review-scan.agent.md`
- [ ] `.github/agents/pipeline-doctor.agent.md` (referenced earlier; here we author it)
- [ ] `.github/agents/standards-change.agent.md` (referenced earlier; here we author it)

## A365 registration

- [ ] `deploy/scripts/register-a365-agents.sh` — bootstrap script that registers each `.github/agents/*.agent.md` as an A365 tenant agent identity
- [ ] `deploy/scripts/sync-a365-from-ledger.py` — fan-out worker (Container Job, every 5 min)
- [ ] `docs/A365-INTEGRATION.md` — attribution mechanism, fan-out worker, troubleshooting

## Tests

- [ ] `apps/decision-ledger-mcp/tests/server.test.ts::test_stdio_transport_initializes`
- [ ] `apps/decision-ledger-mcp/tests/tools/query.test.ts::test_filters_by_team_id`
- [ ] `apps/decision-ledger-mcp/tests/tools/query.test.ts::test_filters_by_bundle_ref`
- [ ] `apps/decision-ledger-mcp/tests/tools/write-runtime.test.ts::test_validates_runtime_schema`
- [ ] `apps/decision-ledger-mcp/tests/tools/write-runtime.test.ts::test_rejects_meta_entry_via_runtime_tool`
- [ ] `apps/decision-ledger-mcp/tests/tools/find-precedent.test.ts::test_orders_by_recency_and_similarity`
- [ ] `apps/decision-ledger-mcp/tests/tools/classify-phi.test.ts::test_blocks_raw_mrn`
- [ ] `apps/decision-ledger-mcp/tests/tools/classify-phi.test.ts::test_passes_redacted_id`
- [ ] `apps/decision-ledger-mcp/tests/auth.test.ts::test_rejects_missing_token`
- [ ] `apps/decision-ledger-mcp/tests/auth.test.ts::test_rejects_team_mismatch`
- [ ] `tests/test_hooks_pre_tool_use.sh::test_blocks_raw_mrn_in_log_statement`
- [ ] `tests/test_hooks_pre_tool_use.sh::test_passes_redacted`
- [ ] `tests/test_hooks_pre_tool_use.sh::test_fail_open_on_mcp_unavailable`
- [ ] `tests/test_hooks_post_tool_use.sh::test_writes_ledger_entry_with_correct_attribution`

## Verification (definition of done)

- [ ] All MCP server tests passing
- [ ] All hook script tests passing (run via bats or shellcheck-driven cases)
- [ ] MCP server deployed to dev RG, reachable via private endpoint, returns valid MCP responses
- [ ] Hook bundle validated by `scripts/validate-hook-bundle.sh`
- [ ] Live test: synthetic VS Code session writes one entry to ledger via post-tool-use hook
- [ ] A365 registration script registers all 6 agents successfully against tenant
