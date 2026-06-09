# Proposal: fix /decisions page empty on cold load (ledger.query team_id required)

> **Status:** SHIPPED 2026-06-09 · Container App revision `ca-ledger-mcp--0000002` healthy
> **Capability:** decision-ledger
> **Severity:** customer-blocking — `/decisions` rendered empty state for every cold-load operator visit
> **Related:** customer-engagement/hca-agentic-sdlc-demo skill (this fix shape is now standing preference)

## Why

The `/decisions` page on `ledger-insights-ui` rendered empty state ("No decisions logged yet") on every cold-load operator visit, even when ledger entries existed. Operators saw the page as *empty when it should have been populated*, and the dashboard's `useDecisions()` polled the proxy every 10s, producing a continuous loop of failed POSTs invisible to error trackers.

Three layers wired together produced the symptom:

1. **`apps/ledger-insights-ui/src/app/decisions/page.tsx:10`** — `useDecisions()` called with no filter:
   ```ts
   const { data, isLoading } = useDecisions();   // no args
   ```

2. **`apps/ledger-insights-ui/src/lib/hooks/use-runs.ts:64`** — hook forwards an empty filter to the proxy:
   ```ts
   queryFn: () => ledgerMcp.query({ limit: 50, ...filter }), // body = {limit:50}, no team_id
   ```

3. **`apps/decision-ledger-mcp/src/schema.ts:44-50`** — server zod schema rejected `team_id: undefined`:
   ```ts
   export const LedgerQueryInputSchema = z.object({
     team_id: z.string(),   // REQUIRED
     ...
   });
   ```

The 400 response was swallowed by TanStack Query, leaving `data?.entries ?? []` to fall through to `entries.length === 0` → empty state.

The redundancy was the bug: the bearer token in `LEDGER_MCP_TOKENS` already maps each token to exactly one `team_id` (per-tenant token model in `apps/decision-ledger-mcp/src/auth.ts`). Requiring the client to repeat what the token already implies served no security purpose and broke the dashboard's read path.

## What changes

**Schema layer** — `team_id` is now `optional`. Cross-team protection still happens at the handler, not the schema:

```diff
 export const LedgerQueryInputSchema = z.object({
-  team_id: z.string(),
+  team_id: z.string().optional(),
   limit: z.number().int().min(1).max(200).optional().default(25),
   ...
 });
```

**Handler layer** — `ledger.query` defaults `team_id` to the authed team when caller omits it. Cross-team check still rejects when caller passes an explicit mismatched team_id:

```ts
const team_id = args.team_id ?? authedTeamId;
if (team_id !== authedTeamId) {
  throw new Error(`Token scoped to '${authedTeamId}'; request targeted '${team_id}'`);
}
```

**`inputSchema.required`** — flipped from `["team_id"]` to `[]`. This is the regression-guard surface for tools that read MCP tool schemas (Copilot CLI, VS Code MCP).

**Tests** — 22/22 passing (5 new handler-level cases including a regression guard on `inputSchema.required`).

## Why this design (the alternatives considered)

**Cross-partition Cosmos query** — the original sketch. Would have made `queryEntries` accept `team_id?` and use `enableCrossPartitionQuery: true` when absent. **Rejected**: it's a security regression. The per-token tenancy model (`auth.ts:41`) is the boundary; cross-partition reads would let one team's token observe another team's ledger if the schema-level guard were ever bypassed. Default-to-authed-team preserves the boundary.

**Client-side fallback** — change `useDecisions()` to read a team_id from app config. **Rejected**: forces every dashboard caller to know the team, propagates the redundancy, doesn't fix the schema bug for OTHER MCP callers (Copilot CLI, VS Code, hook scripts) who would hit the same 400.

## Operational discovery surfaced by this fix

After the schema fix shipped, smoke against `/api/ledger/query` revealed a SECOND, hidden bug: Cosmos `cosmos-agentic-tj6c673gu6x5w` was `publicNetworkAccess: Disabled` with `ipRules: []` and `vnetRules: []` — every ledger query was being firewall-blocked at Cosmos. The original schema 400 was masking a Cosmos firewall 400. Tactical fix: added Container Apps egress IPs (`135.222.186.97`, `132.196.210.100`, `4.150.240.0/22`, `4.150.244.0/22`, `52.255.99.0/24`) to Cosmos `ipRules` and re-enabled `publicNetworkAccess`. Production-grade fix tracked separately as `add-cosmos-private-endpoint-v07`.

Lesson: when a schema rejection masks a real downstream bug, fixing it surfaces the next layer. Anytime a "fix" surfaces a second error layer, that's the diagnostic moment, not the resolution.

## Smoke evidence

```
$ curl -sS -w "HTTP %{http_code}\n" https://ca-ledger-ui.../api/ledger/query \
    -X POST -H 'content-type: application/json' -d '{}'
{"entries":[]}
HTTP 200

$ curl -sS -w "HTTP %{http_code}\n" https://ca-ledger-ui.../api/ledger/query \
    -X POST -H 'content-type: application/json' -d '{"team_id":"team-other"}'
{"error":"Token scoped to 'team-demo'; request targeted 'team-other'"}
HTTP 400
```

Browser verify: `/decisions` cold-load shows empty state cleanly, no console errors, no 400 polling loop.

## Out of scope

- Production-grade Cosmos network posture (VNET integration + private endpoint). Tracked as separate change `add-cosmos-private-endpoint-v07`.
- Same defaulting pattern for the other ledger tools (`find_precedent`, `write_runtime`). Those are write paths used by the orchestrator and hook scripts, not the dashboard, and they pass `team_id` explicitly. No customer-blocking symptom; lower priority.
