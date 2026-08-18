# Operator UI — Graph Surface Redesign Findings

**Date:** 2026-08-18
**Repo:** `agentic-sdlc` · app `apps/ledger-insights-ui`
**Branch at time of audit:** `chore/recover-stranded-pr-work` (clean)
**Status of this document:** analysis + recommendation. **No code has been changed.**

**Purpose.** The operator's decision-graph surfaces were reported as unclear —
"not very clear what is going on, what belongs to what." This document records
what was actually found in the codebase, what two external reference designs
teach, and a ranked recommendation. It is written to be evaluated
independently, so every claim is traceable to a file or an observed artifact.

---

## 1. Evidence base

| Source | How it was inspected | Confidence |
|---|---|---|
| `apps/ledger-insights-ui` | Read directly: `globals.css`, `ui/card.tsx`, `ui/badge.tsx`, all 20 `page.tsx`, all 14 files in `src/lib/graph/` | High — read from disk |
| Reference design A ("knowledge-graph city") | Live public web app; fetched and read its `graph.js`, `config.js`, `styles.css`, import map | High — read its actual source |
| Reference design B (third-party QA-agent prototype) | `~/projects/research/qa-agent/DESIGN-TEARDOWN.md` + screenshots | Medium — teardown of a static prototype |

Reference design B is a **third-party artifact** containing another vendor's
internal service names, an internal framework codename, and real engineer
names. Nothing from it is reproduced here verbatim. Only abstracted UX
patterns are carried forward. **No part of it may be pasted into this repo.**

---

## 2. What exists today

Four graph routes, all under `/decisions`, all fed by one hook (`useDecisions`
→ `LedgerEntry[]`) through pure builders in `src/lib/graph/`.

| Route | Library | Layout | Node kinds | Edge kinds | Detail interaction | In nav? |
|---|---|---|---|---|---|---|
| `/decisions/graph` (Decision Map) | Cytoscape + fcose | organic force | decision, teaching, bundle, class | reuses, teaches, grounded_in, same_slot, of_class, in_run | modal | yes |
| `/decisions/lineage` | **@xyflow/react** | custom `layoutLineageLanes` swimlanes | precedent decisions + teaching | reuses, teaches | **router push (navigates away)** | yes |
| `/decisions/lineage-v2` | Cytoscape + dagre | dagre DAG | same as lineage | same as lineage | **side panel** | **no — orphaned** |
| `/decisions/runflow` | Cytoscape + dagre | dagre spine | stage-spine + decisions | canonical stage order + attach | modal | yes |

Supporting modules: `build-graph.ts`, `build-lineage.ts`, `build-runflow.ts`
(pure builders, all unit-tested), `cy-map.ts`, `cy-lineage.ts`,
`cy-runflow.ts`, `layout-lineage.ts`, `layout.ts`, `map-filters.ts`,
`canvas-theme.ts`. ~2,985 LOC across builders + the four pages.

The design-token layer in `globals.css` is real and complete: surfaces
(`--bg` `--surface` `--elevated` `--overlay`), borders, a three-step text
ramp, semantic colors, and four plane colors (`--plane-standards`
`--plane-pipeline` `--plane-ledger` `--plane-agenthq`). House primitives
`Card` and `Badge` are token-driven. **The token layer is not the problem.**

---

## 3. Defects found

Ranked by contribution to the reported confusion.

### D1 — Three of four views ship without a legend
Four node kinds and six edge kinds are encoded in color alone. The only view
carrying a legend is `lineage-v2`, which is **not linked from the nav**
(`decision-views.tsx` links only Map, Lineage, Run flow) and therefore
unreachable in normal use. The decoder ring exists but was never put on
screen. This is the direct cause of "what belongs to what."

### D2 — Two libraries doing one job
`@xyflow/react` powers `lineage`; Cytoscape powers the other three. The
migration was started and abandoned. The two stacks theme through **different
paths** — react-flow reads CSS variables via `.react-flow` overrides,
Cytoscape draws to canvas and cannot read CSS variables, so it needs the
`canvas-theme.ts` JS bridge. The panes therefore drift visually *by
construction*, not by neglect.

### D3 — Duplicate lineage views, neither resolved
`lineage` (shipped, in nav, react-flow) and `lineage-v2` (orphaned, Cytoscape,
self-labelled "spike, feature-flagged, additive"). The orphan is the better
implementation — it is the one with the legend, and it disables node dragging
(correct for an audit view). Stranded generation: neither promoted nor deleted.

### D4 — The Decision Map is a hairball
Described as such in its own source comment. Six edge kinds with no grouping
and no spatial organisation; the default filter hides structural edges, which
makes the remaining picture readable but semantically incomplete — and
undecodable without the legend it lacks (D1).

### D5 — Three different detail interactions
Clicking a node opens a modal (`graph`, `runflow`), a side panel
(`lineage-v2`), or navigates away entirely (`lineage`). Nothing feels like one
product. Navigating away is the worst of the three: it destroys the user's
spatial context in a view whose entire value is spatial.

### D6 — `runflow` stage-spine has two meanings (correctness, not cosmetics)
The spine is built from the stage field, falling back to `ambiguity_class`
when stage is null — which the code notes "often is." The same axis therefore
silently represents two different things depending on the row. This is a real
defect, not a design preference, and should be fixed regardless of any
redesign.

---

## 4. What reference design A teaches

Stack: **three.js (3D view) + d3-force (2D graph)**, hand-rolled, one
`<canvas>`, no React, no graph library. Three views over one dataset.

Its clarity comes from four decisions, all portable to a graph library:

**A1 — Weak district anchoring.** Every node is pulled toward its district
centroid at strength `0.028` (`forceX`/`forceY`). Weak enough to be a
tendency, not a cage. Visible neighborhoods emerge **without drawing a single
box or lane rectangle**. This is the structural answer to "what belongs to
what," and it is strictly better than our current band/lane rectangles.

**A2 — Dual-channel node encoding, never mixed.**
- core color = lifecycle/health
- ring color = district membership
- radius = `4.4 + sqrt(degree) * 2.35` — importance, sublinear so hubs do not
  dominate the canvas

Two independent questions answered in one glance.

**A3 — Typed edges own both a color and a physics.** Each relation type has a
distinct color, *and* link distance/strength differ by kind: authored edges
pull tight (distance 58, strength 0.16), inferred edges hang slack
(distance 84, strength 0.05). Provenance becomes visible in the **shape** of
the graph, not just its palette.

**A4 — Focus dims, never hides.** Hover/select raises the neighborhood to
alpha 1.0 and drops everything else to 0.1; filtered-out nodes go to 0.05.
Labels appear only within focus. Nothing ever disappears, so spatial bearings
survive every interaction.

**A5 — Provenance honesty as a data field.** Their config carries
`TELEMETRY_SOURCE.measured: true|false`, with the comment that *"nobody has
read this" and "nobody is counting" arrive as the same zero, so the label is
the only thing that separates them.* This is our seeded-vs-live discipline
expressed in the data model rather than in narration. Worth copying directly.

---

## 5. What reference design B teaches

Abstracted patterns only; all vendor-specific content excluded.

**B1 — Typeface encodes authorship.** Monospace for every machine-generated
token (IDs, hashes, durations, cost); sans for anything a human wrote. Applied
without exception. This is the highest-leverage single rule available to us,
because our ledger is *entirely* about human-versus-agent attribution and we
currently apply `.mono` only to rule/ID chips.

**B2 — Hold-to-confirm with friction proportional to consequence.** A
sustained ~900–1100ms gesture on irreversible actions. We already carry
`blast_radius_cost_usd` on gating cards, and our bulk "approve all
recommended" is currently a single click — the mapping is direct.

**B3 — Shape-coded gates.** Gate nodes are a different *shape*, not just a
different color, so they survive grayscale and color-blindness.

**B4 — Self-doubt as a shipped surface.** A "possible gaps" card in which the
agent argues against its own green result, at equal visual weight to the
verdict. This is our honest-narration discipline as a component.

**B5 — Plain-English stage bodies.** Every stage carries a human sentence, not
a state-machine tuple. Consistent with our existing operator-legibility rule.

**Explicitly not worth taking:** no token layer (every hex inline across
~100KB); not responsive (fixed px, dies below laptop width); unconditional
motion with no `prefers-reduced-motion`, and text contrast at or below WCAG AA.

---

## 6. Recommendation

### 6.1 Cut first
**Delete `/decisions/lineage` (@xyflow/react) and promote `lineage-v2` in its
place.** This removes an entire graph library, ~333 lines, the dual theming
path (D2), and the duplicate-view ambiguity (D3) in one move — and the
surviving view is the one that already has a legend. Standardise on
**Cytoscape**.

Noted for the evaluator: the react-flow lineage view was built in an earlier
session of this same workstream. This recommendation cuts prior in-flight work
rather than defending it.

### 6.2 Steal the grammar, not the implementation
Adopt reference design A's **visual grammar** (A1–A4) inside Cytoscape.
Do **not** rewrite as a hand-rolled d3 + canvas renderer: that is ~24KB of
bespoke render loop we would own permanently, and it forfeits Cytoscape's
built-in `neighborhood()` traversal, stylesheet theming, and layout ecosystem.

Concretely: one shared `graph-grammar.ts` imported by all three surviving
views, defining node shape by kind, core/ring dual-channel color, radius by
reuse-degree, and edge color + physics by relation type. Consistency then
comes from a shared module rather than from discipline.

### 6.3 One legend, one detail pattern
- A single mandatory `<GraphLegend>` component rendered on **every** graph
  view. (Fixes D1.)
- A single detail pattern everywhere: **centered quick-view modal over a
  dimmed backdrop**. Not a side panel, not navigation. (Fixes D5.)

### 6.4 Unify the shell
Present Map / Lineage / Run flow as three **lenses on one dataset** behind a
view-switcher, rather than four unrelated pages. Four disconnected routes are
a meaningful share of the "what belongs to what" problem.

### 6.5 Field mapping — we already have the data
| Reference design A concept | Our existing ledger field |
|---|---|
| district anchor | `ambiguity_class` / team / bundle |
| lifecycle core color | decision state (endorsed / flagged / auto-deferred / gating) |
| ring color | `bundle_refs` (governing bundle) |
| radius = degree | reuse count / blast radius |
| typed edges | `precedent_refs`, `references_entry_id`, `slot_value_hash` |
| `measured: false` | seeded-vs-live provenance |

No new backend fields are required for the visual redesign. The ledger is
already a latent graph; it has been rendered as a flat diagram.

### 6.6 Fix independently of the redesign
D6 (`runflow` stage-spine dual meaning) is a correctness bug and should be
fixed on its own merits, not bundled into a visual change.

---

## 7. Sequencing

1. OpenSpec change proposal (repo rule: >3 files touched requires one).
2. Fix D6 as a standalone correctness change.
3. Delete `lineage`, promote `lineage-v2`, single library.
4. Extract `graph-grammar.ts` + `<GraphLegend>`; apply to all three views.
5. Unify shell + single modal detail pattern.
6. Design pass over **real ledger data**: 2–3 styled variants, screenshot,
   choose, implement the winner.
7. Deploy `ca-ledger-ui-vnet` only — this is a pure-UI change reading existing
   fields, so no orchestrator rebuild is required. Verify the new revision is
   sole-active at 100% traffic before evaluating screenshots.

---

## 8. Open questions for the evaluator

1. **Library choice.** Cytoscape (recommended) versus a d3-force + canvas
   renderer matching reference design A more literally. The tradeoff is
   fidelity and beauty against permanently owning a bespoke render loop.
2. **Shell.** Unified view-switcher (recommended) versus keeping distinct
   routes.
3. **Scope of B1.** Applying "mono = machine-generated" consistently touches
   far more than the graph views — it reaches every surface that renders an
   ID, hash, duration, or cost. Should that be in scope here, or its own
   change?
4. **Cut confirmation.** Does the evaluator agree that deleting the shipped
   react-flow `lineage` view in favour of the orphaned `lineage-v2` is the
   right call?

---

## 9. Explicit non-claims

- No code has been written or changed.
- No deployment has been performed or re-verified as part of this analysis.
  The live UI returned HTTP 200 at audit time; nothing further was checked.
- Reference design B is a third-party prototype with hardcoded fiction. Its
  patterns are abstracted here; its content is not a source of truth and its
  identifiers must not enter this repo.
- Claims about reference design A are read from its shipped client source, not
  from documentation about it.
