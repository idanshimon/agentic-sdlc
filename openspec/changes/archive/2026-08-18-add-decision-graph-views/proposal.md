# Add Decision Graph Views

## Why

The Decision Ledger surfaces every governed agent decision, but the existing
`/decisions` surface presents them only as a flat, dense table + a plain-language
activity feed. Both are excellent for "read the record" but cannot answer three
structural questions a dev-leader or compliance reviewer asks about the ledger as
a whole:

1. **How does it all connect?** Which standards rule is doing the most work
   (cited by the most decisions), and is a given flag isolated or systemic?
2. **Is the system actually learning?** The single most important relationship in
   a governed agentic SDLC — an autopilot decision auto-resolved from a human
   precedent (the `reuses` / learning-loop edge) — is invisible in a flat table.
3. **How did one run flow?** Which stage/ambiguity produced each decision, in
   pipeline order.

The ledger already carries the structure to answer all three (`precedent_refs`,
`references_entry_id`, `bundle_refs`, `run_id`, `ambiguity_class`,
`slot_value_hash`) — it is simply not visualized. This change adds three
read-only graph lenses over the SAME ledger read, additive to and non-destructive
of the existing table/feed.

## What Changes

- **ADDED** three read-only graph routes under the Ledger plane, each a thin
  renderer over one shared, unit-tested graph-builder engine
  (`src/lib/graph/`):
  - `/decisions/graph` — **Decision Map**: cross-run governance network
    (bundles as hubs sized by citation count, decisions clustered by ambiguity
    class, learning-loop + teaching edges highlighted). Ships edge-family filter
    chips and a flag-focus control for scale legibility.
  - `/decisions/lineage` — **Precedent Lineage**: the learning loop as a
    left→right dagre DAG. Human precedents are roots on the left; each reuse hop
    moves right, so the human→agent teaching loop reads as a timeline.
  - `/decisions/runflow` — **Run Flow**: a single run's decisions laid out
    left→right under their pipeline stage (or ambiguity bucket).
- Every graph node MUST click through to its full audited record at
  `/decisions#decision-<id>` (the existing drill-down anchor contract).
- All three views read the existing `useDecisions` poll (auto-refresh) and
  perform NO writes. They are a reading layer, exactly like the AgentAssistant.
- The existing `/decisions` table and activity feed are UNCHANGED.

## Impact

- Affected specs: `decision-graph-views` (new capability).
- Affected code: `apps/ledger-insights-ui/src/lib/graph/*` (new, tested),
  `apps/ledger-insights-ui/src/app/decisions/{graph,lineage,runflow}/page.tsx`
  (new), sidebar nav (+3 entries). New deps: `@xyflow/react`, `@dagrejs/dagre`.
- No backend, ledger-schema, standards-bundle, or orchestrator change. No new
  write path. No PHI or customer-neutrality impact (sample data only).
