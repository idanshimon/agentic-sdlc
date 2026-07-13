# Decision: Adopt Cytoscape.js

Use **Cytoscape.js** as the graph engine for the Decision Ledger. Its compound nodes directly replace manual precedent bands, while selectors and built-in traversal eliminate the hand-written grouping, BFS, neighborhood-focus, and blast-radius logic currently surrounding React Flow. Cytoscape’s deterministic and compound-aware layout ecosystem also fits reproducible audit views and exploratory maps without maintaining separate layout machinery.

The decisive tradeoff is rich HTML nodes versus graph semantics. React Flow excels when every node is an interactive React card, but this surface is fundamentally a **compliance lineage graph**, where deterministic structure, trustworthy traversal, grouping, and visual state are more important than embedding full records inside nodes. Cytoscape’s canvas rendering wins: show compact, strongly differentiated nodes in the graph and move complete decision content into the existing detail side-panel.

## Rendering and interaction design

### Rich nodes

Use **native Cytoscape canvas nodes**, not `cytoscape-node-html-label`, for the primary implementation. HTML labels introduce DOM synchronization, zoom alignment, clipping, export, and performance risks—the same class of layout complexity the migration is intended to remove.

Encode entities through a Cytoscape stylesheet:

- Human precedent: shield or hexagonal silhouette, high-contrast cyan border.
- Agent decision: rounded rectangle or diamond, violet accent.
- Rule: document-shaped rectangle, amber accent.
- Run: pill or barrel, neutral blue.
- Teaching signal: small star/triangle satellite, green or red by outcome.
- PHI and flagged states: badges expressed through border, overlay icon, color, and line style rather than long text.

Keep graph labels concise: actor name, ambiguity class, and a truncated decision title. Selection opens the React side-panel containing the complete decision text, cited rule, teaching signals, PHI metadata, and audit actions. Use **Popper/Tippy overlays only for short hover previews**; never as the authoritative detail view.

### Precedent lanes

Represent each human precedent as a Cytoscape **compound parent node**. Every agent decision that reuses it receives `parent: precedentGroupId`; Cytoscape automatically computes and resizes the container around its children. Style parents with padding, translucent backgrounds, labeled borders, and ambiguity-class accents.

The human precedent itself remains a visible child with a dedicated type, avoiding duplicate semantic and container nodes in traversal. Rules, runs, and teaching signals remain outside the compound unless they are genuinely owned by that precedent group.

### Focus and blast radius

On selection, construct the focus collection from typed edge relations:

```ts
const focused = selected
  .union(selected.predecessors())
  .union(selected.successors())
  .union(selected.neighborhood());
```

Restrict traversal by edge type where semantics require it:

- Upstream lineage: `predecessors('edge[relation = "reuses"]')`
- Downstream reuse blast radius: `successors('edge[relation = "reuses"]')`
- Context attachments: adjacent `cites`, `occurred_in`, and `teaches` edges

Add a `focused` class to the resulting collection and `dimmed` to its complement. A flagged-node blast radius is the selected decision plus all transitive `reuses` successors. Keep traversal functions in a small typed domain adapter so UI components do not embed graph semantics.

### Filtering and layouts

Map filters to Cytoscape data fields and selectors, for example:

```ts
node[ambiguityClass = "auth-policy"]
node[actorType = "human"]
node[flagged]
node[ruleId = "RULE-42"]
```

For audit stability, **dim non-matches by default** so positions do not shift. Offer explicit “hide unmatched” behavior that reruns layout only when requested.

Use:

- **`cytoscape-dagre`** for the default lineage view, with fixed rank direction, spacing, ordering inputs, and animation disabled.
- **`cytoscape-fcose`** for the exploratory Decision Map because it supports compound structures and organic positioning.

Persist normalized element ordering and layout options to make screenshots reproducible.

## Migration plan

| Phase | Work | Effort |
|---|---|---:|
| 1. Real-data spike | Build a client-only Cytoscape component using the current 16-node dataset. Prove five silhouettes, compound precedent groups, dagre layout, selection, side-panel integration, focus traversal, filtering, and PNG export. | 2–3 days |
| 2. Domain adapter | Convert existing decision data into typed Cytoscape elements. Centralize stable IDs, edge relations, parent assignment, selector-safe fields, traversal helpers, and deterministic ordering. | 2–3 days |
| 3. Parallel production route | Place Cytoscape behind a feature flag or `/decisions/graph-v2`. Keep the current React Flow graph available and leave the existing `/decisions` table and its data contract untouched. Both graphs consume the same normalized decision model. | 2 days |
| 4. Product completion | Add filters, keyboard selection/navigation, focus reset, blast radius, hover previews, responsive side-panel behavior, empty states, telemetry, and dagre/fCoSE switching. | 4–6 days |
| 5. Verification and cutover | Add traversal unit tests, adapter tests, interaction tests, and fixed-viewport screenshots for baseline, focused, filtered, flagged, and 200-node fixtures. Compare exports for deterministic placement, then make Cytoscape the default. | 3–4 days |
| 6. Removal | Remove React Flow, dagre orchestration, manual band nodes, width calculations, and satellite hacks after one release of fallback coverage. | 1–2 days |

## Top risks

1. **Loss of rich inline cards:** Canvas nodes cannot reproduce arbitrary React markup. Mitigate by designing compact semantic glyphs, retaining the full React side-panel, and limiting Popper overlays to previews.
2. **Accessibility and keyboard behavior:** Canvas content has weaker native semantics than DOM nodes. Mitigate with a synchronized off-screen accessible node list, explicit focus state, arrow-key traversal, Enter-to-select, Escape-to-reset, and side-panel announcements.
3. **Extension compatibility and layout drift:** Cytoscape extensions may lag core releases, and compound dagre behavior must be validated. Pin compatible versions, wrap layouts behind an internal adapter, snapshot the real and 200-node fixtures, and retain fCoSE as the compound-aware fallback.

**Verdict: switch to Cytoscape.js; the first commit should add a feature-flagged client-only spike proving native styled nodes, compound precedent groups, and click-to-focus on the real 16-node dataset.**



Changes    +0 -0
AI Credits 17.1 (34s)
Tokens     ↑ 19.4k (19.4k written) • ↓ 1.6k (262 reasoning)
Resume     copilot --resume=f1cfa9ed-b001-4bd2-a9d6-ca946ae82701
