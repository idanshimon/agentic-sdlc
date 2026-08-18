# Proposal: Decision graph surfaces — one grammar, one legend, one library

> **Status:** DRAFT — open for review
> **Authors:** Idan Shimon
> **Date:** 2026-08-18
> **App touched:** `apps/ledger-insights-ui`
> **Capabilities touched:** ledger (operator UI surfaces only)
> **Grounded in:** `docs/UI-GRAPH-REDESIGN-FINDINGS.md`

## Why this exists

The operator's decision-graph surfaces were reported as unclear — *"not very
clear what is going on, what belongs to what."* An audit
(`docs/UI-GRAPH-REDESIGN-FINDINGS.md`) traced that report to six defects, of
which the top three are structural rather than cosmetic:

1. **No legend on the views people can reach.** Four node kinds and six edge
   kinds are encoded in color alone. The only view carrying a legend is
   `/decisions/lineage-v2`, which is not linked from the nav. Verified: `grep -ril legend src/`
   returns `lineage-v2/page.tsx` and two non-graph pages; `decision-views.tsx`
   links only Map, Lineage, Run flow. **The decoder ring exists and is unreachable.**
2. **Two graph libraries doing one job.** `@xyflow/react` powers `lineage`;
   Cytoscape powers the other three. They theme through different paths —
   react-flow reads CSS variables, Cytoscape draws to canvas and cannot, so it
   needs the `canvas-theme.ts` bridge. The panes drift visually *by
   construction*.
3. **Duplicate lineage views, neither resolved.** `lineage` (shipped, in nav)
   and `lineage-v2` (orphaned, self-labelled a spike). The orphan is the better
   implementation: it has the legend, it disables node dragging (correct for an
   audit view), and it already uses the centered quick-view modal.

Separately, `runflow` carries a **correctness** defect (D6): its stage spine is
built from `e.stage ?? ambiguity_class`, so one axis silently means two
different things depending on the row. Verified in `build-runflow.ts:60`.

## What changes

### 1. Cut a library and a duplicate view
Delete `/decisions/lineage` (react-flow, 333 LOC), promote `lineage-v2` into its
route, and remove `@xyflow/react` from `package.json`. Verified: the dependency
appears in exactly one source file, so this is a clean excision.

**Noted for the reviewer:** the react-flow lineage view was built in an earlier
session of this same workstream. This proposal cuts our own prior work rather
than defending it.

### 2. One shared visual grammar (`src/lib/graph/graph-grammar.ts`)
A single module all graph views import, encoding the four patterns that make the
reference design legible:

- **G1 — Weak class anchoring.** Nodes pull toward their `ambiguity_class`
  centroid weakly, so neighborhoods emerge without drawing lane rectangles.
- **G2 — Dual-channel node encoding, never mixed.** Core color = decision
  state (endorsed / flagged / gating / auto-deferred); border color = governing
  bundle; size = reuse degree, sublinear so hubs do not swamp the canvas.
- **G3 — Typed edges own a color *and* a weight.** Authored relations
  (`reuses`) draw tight and solid; inferred/structural relations draw slack and
  dashed. Provenance becomes visible in the *shape* of the graph.
- **G4 — Focus dims, never hides.** Selection raises a neighborhood and drops
  the rest to low alpha. Nothing disappears, so spatial bearings survive.

Grammar values resolve through the existing `useCanvasTheme()` bridge, so graphs
continue to track light/dark instead of pinning to dark.

### 3. One legend, mandatory (`<GraphLegend>`)
A single token-driven component rendered on **every** graph view, decoding node
kinds and edge kinds from the same grammar module that draws them. A legend
generated from the grammar cannot drift from what is on screen.

### 4. One detail pattern
Centered quick-view modal over a dimmed backdrop, everywhere. `lineage-v2`
already does this; `graph` and `runflow` use modals; the deleted `lineage` was
the only view that navigated away, destroying spatial context in a view whose
entire value is spatial.

### 5. Mono for machine-generated tokens — scoped
Apply "monospace = machine-generated, sans = human-authored" to IDs, hashes,
rule references, durations and costs **within the graph surfaces and their
legends/modals**. The repo-wide sweep is deliberately *out of scope* — see
Decisions.

### 6. D6 fixed as a standalone correctness change
The `runflow` spine must represent one thing. Where `stage` is absent the spine
renders an explicit `unstaged` bucket rather than silently substituting
`ambiguity_class` as if it were a stage.

## Decisions

**Cytoscape, not a hand-rolled d3+canvas renderer.** The reference design's
clarity comes from its *grammar*, not its renderer. Hand-rolling forfeits
Cytoscape's `neighborhood()` traversal, stylesheet theming and layout ecosystem
in exchange for a bespoke render loop we would own permanently.

**Mono sweep split out.** Applying B1 repo-wide touches every surface rendering
an ID, hash, duration or cost — roughly 20 `page.tsx` files. Bundled into this
change, a reviewer cannot distinguish a typography sweep from a graph rewrite in
one diff. Scope by diff-reviewability, not by rule purity: apply the rule fully
within the surfaces this change already touches, then extend it in its own
change.

**D6 lands first and separately.** It is a correctness bug and should be
reviewable on its own merits, not bundled into a visual change.

## Non-goals

- No backend or ledger schema changes. Every field the redesign needs already
  exists (`ambiguity_class`, `bundle_refs`, `precedent_refs`,
  `references_entry_id`, decision state).
- No orchestrator rebuild. This is a pure-UI change reading existing fields.
- No repo-wide typography sweep (its own change).
- No new graph view. This proposal deletes one and adds none.

## Verification

1. `pnpm test` — builders are pure and unit-tested; D6 gets a test asserting
   unstaged decisions do not enter the stage spine.
2. `pnpm build` clean.
3. Dev server on the app's configured port; all three surviving routes render
   under a headless browser with a legend present on each.
4. `grep` gate: zero references to `@xyflow/react` or the deleted route.

## Risks

- **Layout regression.** `lineage-v2` positions roots explicitly because the
  real precedent shape is many independent 1→1 pairs, which generic layouts
  flatten into one strip. That hand-tuned positioning must be preserved when the
  view is promoted, not replaced by a stock layout.
- **Grammar over-abstraction.** Three views with genuinely different topologies
  share one module; if the abstraction fights a view, prefer a per-view override
  in that view over bending the grammar for all three.
