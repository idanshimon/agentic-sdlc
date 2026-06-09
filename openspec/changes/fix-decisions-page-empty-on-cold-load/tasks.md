# Tasks: fix /decisions page empty on cold load

## 1. Schema layer
- [x] 1.1 Make `team_id` optional in `LedgerQueryInputSchema` (`apps/decision-ledger-mcp/src/schema.ts`)
- [x] 1.2 Document the handler-layer defaulting in a comment above the schema
- [x] 1.3 Update `tests/schema.test.ts` — replace "requires team_id" with "allows omitting team_id" + "accepts explicit team_id"

## 2. Handler layer
- [x] 2.1 `ledger.query` handler defaults `team_id` to `authedTeamId` when caller omits it (`apps/decision-ledger-mcp/src/tools.ts`)
- [x] 2.2 Cross-team check still rejects when explicit `team_id !== authedTeamId`
- [x] 2.3 Flip `inputSchema.required` from `["team_id"]` to `[]`
- [x] 2.4 Update tool description to note the defaulting behavior

## 3. Test coverage
- [x] 3.1 NEW `tests/tools.test.ts` — 5 handler-level cases:
  - defaults team_id to authed team when caller omits
  - accepts explicit team_id when it matches authed
  - rejects cross-team requests
  - forwards optional filters (entry_type, agent_session_id, bundle_ref_prefix)
  - regression guard on `inputSchema.required` being `[]`
- [x] 3.2 All 22 tests passing (was 17 → +5)
- [x] 3.3 `tsc --noEmit` clean

## 4. Build + deploy
- [x] 4.1 ACR build: `acragenticsdlctj6c673gu6x5w.azurecr.io/decision-ledger-mcp:0.7.0-fix-decisions-team-id` (digest sha256:93c634…)
- [x] 4.2 Container App update: `ca-ledger-mcp` → revision `--0000002`, healthy + running
- [x] 4.3 Cosmos firewall opened to Container Apps egress (tactical; permanent fix in separate change)

## 5. Smoke
- [x] 5.1 `POST /api/ledger/query` body `{}` → 200 `{"entries":[]}` (was 400)
- [x] 5.2 `POST /api/ledger/query` body `{"team_id":"team-cardiology"}` → 400 cross-team rejection (regression check)
- [x] 5.3 `POST /api/ledger/query` body `{"limit":5}` → 200 `{"entries":[]}`
- [x] 5.4 Browser cold-load `/decisions` — empty state, zero console errors, no 400 loop

## 6. Standing preferences captured
- [x] 6.1 Update `customer-engagement/hca-agentic-sdlc-demo` skill with the schema-masks-downstream lesson
- [ ] 6.2 Audit other read endpoints in `decision-ledger-mcp` for the same pattern (`find_precedent` is a write-path read; defer)

## 7. Archive
- [ ] 7.1 Move to `openspec/changes/archive/fix-decisions-page-empty-on-cold-load/` after merge to main
