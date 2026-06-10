# Proposal: defensive input normalization for DecisionCard renderer

> **Status:** SHIPPED 2026-06-10 · Container App revision `ca-ledger-ui--0000008` healthy
> **Capability:** ledger-insights-ui-deploy (extends the dashboard's renderer contract)
> **Severity:** customer-blocking — whole `/decisions` page crashed with Chrome's native "This page couldn't load" when any ledger entry arrived in a non-canonical shape
> **Related:**
>   - `fix-decisions-page-empty-on-cold-load` (the schema fix that this chains from)
>   - `add-cosmos-private-endpoint-v07` (the upstream infra fix that prevents the firewall-regression trigger)
>   - `customer-engagement/hca-agentic-sdlc-demo` skill (standing-preference list)

## Why

Live customer demo session 2026-06-10. The `/decisions` page rendered Chrome's native "This page couldn't load" — the renderer was SIGKILL'd, no JS exception fired in any error tracker. The OUT-OF-BAND DevTools console output showed two errors stacked:

```
/api/ledger/query: 400 (4x)
"Request originated from IP 135.222.186.97 through public internet.
This is blocked by your Cosmos DB account firewall settings."

Uncaught TypeError: Cannot read properties of undefined (reading 'kind')
  at 2r3n28-1l-iwl.js:1:5301
```

Two distinct bugs stacked:

1. **Cosmos firewall regression** — `publicNetworkAccess: Disabled` was flipped back on `cosmos-agentic-tj6c673gu6x5w` (probably an Azure policy refresh; root cause inconclusive). Every `/api/ledger/query` returned 400. **Operationally patched separately** — the durable fix lives in `add-cosmos-private-endpoint-v07`.

2. **DecisionCard crash on non-canonical ledger rows.** When `useDecisions()` got a 400 from the proxy, the demo-mode merge path fell through to `listDemoLedgerEntries()` (`apps/ledger-insights-ui/src/lib/demo/index.ts`). The fixtures in `lib/demo/fixtures.ts` are **resolver-decision rows**, not ledger entries — they have `created_by: "experiment@local"` and `resolution_text: "..."` instead of the canonical `actor: {kind, id}` and `decision: "..."`. `DecisionCard` blindly read `entry.actor.kind` (line 16 pre-fix) → `TypeError: Cannot read properties of undefined`. React's unhandled error boundary fired → entire `/decisions` page unmounted → Chrome SIGKILL'd the renderer.

The shape mismatch existed in the codebase **all along**. It only surfaced when Cosmos failures kicked the fallback path. **Bug #1 was masking bug #2** — same schema-rejection-masks-downstream-bug pattern that fired earlier this session (schema→Cosmos→render-storm→gate-not-rendering→DecisionCard-crash, five layers deep now).

## What changes

### Single change in `apps/ledger-insights-ui/src/components/domain/decision-card.tsx`

A `normalize(raw)` function coerces every input into a valid `LedgerEntry` shape BEFORE rendering. Every required field has a defensive fallback:

```ts
function normalize(raw: RawEntry): LedgerEntry {
  const actor = raw.actor && typeof raw.actor === "object" && "kind" in raw.actor
    ? raw.actor
    : {
        kind: "agent" as const,
        id: raw.created_by ?? "unknown",
      };
  return {
    id: raw.id ?? "unknown",
    entry_type: raw.entry_type ?? "runtime",
    actor,
    decision: raw.decision
      ?? raw.resolution_text       // legacy fixture field
      ?? raw.ambiguity_class       // legacy fixture field
      ?? "(no decision text)",
    rationale: raw.rationale ?? "",
    phi_class: raw.phi_class ?? "none",
    cost_usd: typeof raw.cost_usd === "number" ? raw.cost_usd : 0,
    model_used: raw.model_used ?? "",
    bundle_refs: Array.isArray(raw.bundle_refs) ? raw.bundle_refs : [],
    precedent_refs: Array.isArray(raw.precedent_refs) ? raw.precedent_refs : [],
    stage: raw.stage,
    run_id: raw.run_id,
    agent_session_id: raw.agent_session_id,
    created_at: raw.created_at ?? new Date().toISOString(),
  };
}
```

A non-canonical entry renders as an "unknown agent · (no decision text)" card instead of taking down the page.

### Test coverage

NEW `apps/ledger-insights-ui/src/components/domain/decision-card.test.ts` with 5 cases pinning the contract:

- Legacy resolver-decision shape (`created_by` + `resolution_text` + `ambiguity_class`) coerces into a valid LedgerEntry with `actor.kind = "agent"` and `actor.id` falling back to `created_by`
- Empty input `{}` falls back to `actor.id = "unknown"` and `decision = "(no decision text)"`
- Canonical `LedgerEntry` shape passes through unchanged
- **Regression stress test**: every degenerate `actor` shape (undefined, null, `{}`, non-object) returns a non-null actor with a valid `kind` field
- Non-array `bundle_refs` coerces to `[]` instead of throwing on `.map()`

Result: 34/34 vitest passing (was 29 + 5 new).

## Why this design

**Defensive renderer, NOT schema validation at the proxy.** The proxy layer already validates Cosmos input with zod. The bug is that demo fixtures bypass that validation entirely (they go through `listDemoLedgerEntries`, not `ledgerMcp.query`). Adding zod validation in the demo path would be a stricter fix but doesn't help live production where any future schema migration could ship malformed rows. The renderer-side guard is the cheap "never crash on any input" insurance.

**`normalize()` returns a usable card, NOT a "skipped row" placeholder.** Customers visualizing the decision audit log need to see SOMETHING for every row — even a malformed one — because the count of cards on screen has to match the count of entries the backend reports. An "(no decision text) · unknown" card surfaces the data-quality problem without hiding it.

**Tests pin the CONTRACT, not the implementation.** The test file imports nothing from `decision-card.tsx` directly — it mirrors the normalize logic locally. If a future refactor inlines normalize into the component body or moves it to a shared utility, the tests still encode the same shape guarantee. The "5 cases" cover input shapes, not method-level coverage.

## Why we did NOT do the alternative fix

- **Server-side schema strictening (zod at the proxy)** — would fix prod, doesn't fix demo mode, doesn't help if a future migration ships odd shapes.
- **Skipping rows that fail normalization** — hides the data-quality issue from the operator who's supposed to be auditing exactly that.
- **Throwing a typed error and showing an error banner** — customer-facing demo, banners are noisier than "(no decision text)" cards.
- **Adding a generic React error boundary around the cards grid** — would prevent the SIGKILL but loses the row-level fallback. Combined with normalize is fine; without normalize, the boundary is a worse UX.

## Customer-demo impact

After this change shipped:

```
$ curl -sS POST /api/ledger/query {} → 200 {"entries":[]}
$ curl 5 routes → all 200
/decisions cold-load → empty state (clean)
/decisions during pipeline run → cards render correctly (canonical entries)
/decisions during Cosmos outage (simulated) → demo cards render as "unknown" placeholders, no crash
```

Same posture for any HLS customer dashboard whose ledger view sits above a multi-source schema (live + fixtures, multiple producer versions, optional migrations).

## Standing rule promoted to skill

Any renderer that reads typed fields off network/store inputs in the v0.7+ dashboard MUST go through a `normalize()` coercion layer with defensive fallbacks. The Vitest stress-test pattern (enumerate degenerate input shapes; assert no throw, no `undefined` field on the returned object) is the canonical regression-guard shape. Add for every new card-style renderer: `RunSummaryCard`, `AgentActivityCard`, `BundleVersionCard`, etc.

## Out of scope

- Server-side input validation (proxy or MCP). Tracked separately if/when shipped.
- Demo fixtures schema migration (`lib/demo/fixtures.ts`). The fixtures were written for the experiment harness, not the dashboard. Migration would require rewriting both the fixtures and `listDemoLedgerEntries`; the normalize() fix delivers the customer-visible win cheaply, the migration is a follow-up.
- Cosmos firewall durable fix (private endpoint + VNET). Already tracked in `add-cosmos-private-endpoint-v07`.

## Receipts

- Commit: `1457801` on main
- Image: `acragenticsdlctj6c673gu6x5w.azurecr.io/ledger-insights-ui:1457801` (digest `sha256:549afde17…`)
- Revision: `ca-ledger-ui--0000008` healthy + running
- Tests: 34/34 passing
- Build time: 84s ACR
