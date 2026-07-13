# Decision Ledger Graph Redesign

## Five real compliance workflows

### 1. “This agent decision looks wrong—where did it come from?”

**Trigger:** I notice an autopilot decision that appears inconsistent with policy.

**Interaction:** I click the agent decision card. The graph centers it, opens the right-side detail panel, and enters **Focus mode: Upstream lineage**. Its precedent chain, cited rule, pipeline run, and teaching signals remain at full opacity; unrelated nodes dim to 12%. The reused-from edge animates upstream toward the originating human ruling. Filters auto-apply as removable chips: `Neighborhood: selected`, `Direction: upstream`, `Relations: reuses + cites rule + in run`.

The panel shows the complete decision text, actor, timestamp/run stage, ambiguity class, PHI class, cited rule excerpt, and a chronological provenance chain. Each reuse step explains: **“Reused because…”**, agent confidence, and whether the precedent had been endorsed or later flagged.

**New affordance:** A segmented **Upstream / Both / Downstream** control above the panel, plus a persistent provenance breadcrumb: `Agent decision → Human precedent → Rule`.

---

### 2. “How widely was this human ruling reused?”

**Trigger:** I want to assess the influence and consistency of a human precedent.

**Interaction:** I click a human precedent root and choose **Show downstream impact** from its card action menu. The graph switches to a compact fan-out tree with the ruling pinned left and reuse generations flowing right. Auto-filters become `Direction: downstream` and `Relation: reuses`; rule and run nodes are hidden unless explicitly enabled.

The root card displays `8 direct · 14 total reuses`. Descendants are grouped by ambiguity class, then run. Any flagged reuse stays danger-red and is never dimmed. The panel summarizes direct/indirect reuse, affected runs, agents, endorsement rate, flagged count, and divergence in resulting PHI classifications.

**New affordance:** Reuse-count badges on every precedent root and a **Group by: Class / Run / Agent / None** selector.

---

### 3. “Show me everything touching PHI classification.”

**Trigger:** I am preparing a PHI-classification review.

**Interaction:** I select `Class: PHI classification` in the filter bar. Matching decisions remain visible alongside their directly cited rules, runs, and teaching signals; unrelated classes disappear rather than dim. Within the result, human precedents form vertical anchors and their agent reuses form compact horizontal branches.

I can then select `Actor: Agent` and `Teaching: Flagged or endorsed`. Filters combine as AND across categories and OR within a category. The panel becomes an aggregate summary until a node is selected: decision count, human/agent split, reuse rate, rules cited, PHI-class distribution, flagged decisions, and runs affected.

**New affordance:** A **Review summary** panel for filtered sets and a **Save view** action that preserves filters and layout in the URL.

---

### 4. “A decision was flagged—what downstream reuse is unsafe?”

**Trigger:** A human marks a precedent as prohibited from future reuse.

**Interaction:** Clicking the flagged card’s **Assess blast radius** action enters a dedicated downstream mode. All transitive reuse descendants are revealed, even if other filters would normally hide them. Edges from the flagged source become danger-red; descendant cards receive an **At risk** warning stripe. Nodes already superseded or independently re-reviewed receive amber rather than red.

Auto-filters show `Blast radius: DEC-142`, `Direction: downstream`, `Relation: reuses`, with an explicit banner: **“12 decisions across 5 runs may rely on a prohibited precedent.”** The panel lists affected decisions by severity and generation, with evidence for why each is included. Actions include **Open run**, **Mark reviewed**, and **Create remediation task**.

**New affordance:** First-class **Blast radius** mode, risk-state badges, and a sortable affected-decisions list synchronized with graph selection.

---

### 5. “Which human precedents should become standards?”

**Trigger:** I want to codify repeated human judgment into governed policy.

**Interaction:** I choose **Insights → Precedent leverage**. The graph collapses to human precedent roots ranked vertically by total downstream reuse. Each root shows direct reuse, transitive reuse, run coverage, agent coverage, endorsement rate, flagged descendants, and age. Node width remains fixed; a green leverage bar encodes reuse volume without distorting card size.

Selecting a root opens its lineage and panel. The panel provides a **Codification score** based on reuse volume, cross-run reach, consistency, endorsement, and absence of flags—not an opaque AI score. The underlying factors are visible.

**New affordance:** A ranked **Precedent leverage** view with sortable metrics and **Draft standard from precedent** as a governed workflow entry point.

---

# Implementable visual specification

## Card and node design

Use `#0B0F14` canvas with a subtle 24px dot grid at `#243042` and 18% opacity. Remove full-width grey lanes.

### Decision card

- **Size:** 264×116px; focused card 280×124px.
- **Surface:** `#161D26`; 1px border `#243042`; 10px radius.
- **Elevation:** `0 8px 24px rgba(0,0,0,.34), 0 1px 0 rgba(255,255,255,.04)`.
- **Structure:**
  1. 4px left actor accent: human `#22C55E`, agent `#0EA5E9`.
  2. Header: actor avatar, actor name, Human/Agent badge, timestamp.
  3. Two-line decision text in `#E6EDF3`, 14px/20px, medium weight.
  4. Footer: ambiguity-class chip, rule ID, reuse count or teaching signal.
- Use violet `#A78BFA` for class chips, blue for pipeline/run metadata, and green for endorsed state.

**States:**

| State | Treatment |
|---|---|
| Default | Elevated surface and actor accent |
| Hover | Border `#0EA5E9`; translateY(-2px); reveal quick actions |
| Focused | 2px `#0EA5E9` ring plus blue outer glow |
| Dimmed | 12% opacity; labels and pointer events disabled |
| Flagged | Border and top-right flag `#EF4444`; subtle red surface tint |
| Precedent root | Green top rail, “Human precedent” badge, reuse-count badge |

Rule, run, and teaching nodes must have distinct silhouettes: rule as compact violet document (200×72), run as blue pill-ended container header, teaching signal as 32px circular icon. Never represent every entity as identical white boxes.

### Precedent Lineage

Replace empty bands with **content-sized lineage groups**. Each group has a 40px header rail containing precedent title, class, reuse totals, and collapse control. Its bounding surface is `#11161D`, border `#243042`, 16px internal padding, and grows only around contained nodes. Roots align left; reuse generations flow right. Shared downstream routes use trunked edges before branching.

## Focus interaction

Single click selects and centers a node within 250ms; do not unexpectedly zoom beyond 110%. The 384px right panel slides in without covering graph controls. Related nodes stay fully opaque, second-degree neighbors use 55%, and everything else uses 12%.

Press `Enter` to open focus, arrow keys to traverse connected nodes, `[` upstream, `]` downstream, and `Esc` to clear focus. Clicking canvas also exits focus. Preserve the user’s prior filters and viewport so exiting returns exactly to the previous state. Every decision row in `/decisions` gets **Open in map**, linking to `/decision-map?focus=<id>&relations=all`.

## Filter bar

Sticky, single-line bar with expandable overflow:

- **Ambiguity class:** multi-select
- **Actor:** Human / Agent, multi-select
- **Teaching:** Endorsed / Flagged / None, multi-select
- **Rule:** searchable multi-select
- **Relation:** Learning loop / Teaching / Cites rule / In run / Same bucket / Of class
- **Run:** searchable multi-select
- **Only flagged + neighbors:** toggle

OR within each filter; AND across filters. Show active filters as removable chips and always provide **Clear all**. If nothing matches, keep the selected focus visible when applicable and explain which filter excluded its neighbors; offer **Clear conflicting filters**, never a blank canvas.

## Scaling to 200+ nodes

Default to a summarized graph, not “show all.” Use three semantic zoom levels:

1. **Overview:** precedent roots and grouped class/run clusters with counts.
2. **Structure:** expanded lineage branches and bundled relation trunks.
3. **Detail:** full cards, labels, rules, and teaching signals.

Collapse reuse branches after the second generation; show `+17 descendants`. Bundle parallel edges by relation type and expand them on hover or focus. Keep lineage deterministic and layered; reserve force layout only for exploratory Decision Map mode. Virtualize offscreen nodes and hide labels below 55% zoom.

## North-star products

- **GitHub commit graph:** steal deterministic lineage, familiar directional ancestry, and compact branch divergence.
- **Datadog Service Map:** steal click-to-focus, neighborhood dimming, synchronized details, and filterable topology.
- **Linear:** steal crisp dark-theme hierarchy, keyboard-first navigation, restrained color, and fast side-panel transitions.

# Highest-impact first change

**Replace the Precedent Lineage bands with content-sized, left-to-right lineage groups and make every decision click enter neighborhood focus.** This simultaneously fixes the unfinished visual appearance and makes the human-to-agent learning loop immediately understandable.



Changes    +0 -0
AI Credits 18.3 (42s)
Tokens     ↑ 19.2k (19.2k written) • ↓ 2.1k (47 reasoning)
Resume     copilot --resume=49d4ef04-2646-4259-9cb9-f50d47acc1ef
