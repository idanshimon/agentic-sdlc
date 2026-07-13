# Precedent Lineage — Production Visual Language

## Design thesis

This is not a generic dependency graph. It is an **evidence map of institutional learning**: a human ruling established a precedent, agents reused it, and governance either endorsed or revoked that reuse. Every visual decision should answer:

> **What did the human teach, where did the agents apply it, and is that teaching still safe?**

The shipped design has the correct topology and hierarchy, but it is still too card-heavy and graph-like. It communicates records before it communicates governance outcomes.

## 1. Fix the node, edge, and layout hierarchy

### Nodes

At `234px`, cards are too narrow for decision language and too dense for three metadata systems: actor, rule, and ambiguity class. Increase expanded cards to **272×132px**. Use:

- Surface: `#111827`
- Border: `#334155`
- Primary text: `#F8FAFC`, 13px/18px, semibold
- Secondary text: `#94A3B8`, 11px/16px
- Human accent: `#34D399`
- Agent accent: `#60A5FA`
- Flagged accent: `#FB7185`
- Focus ring: 2px `#A7F3D0`, 3px offset

Remove the full-height colored left bar. It overstates actor type and competes with flagged status. Instead, use a **4px top status rail**: green for active precedent, blue for valid reuse, red for blocked reuse. Actor remains a compact pill.

Rewrite card hierarchy:

1. **Outcome sentence** — the decision itself.
2. **Relationship label** — “Reused Idan’s precedent” or “Established precedent.”
3. **Evidence footer** — `PHI classification · security/PHI-001`.

Hide bundle version by default; reveal it in the detail panel or tooltip. `security/v0.1.0/PHI-001` reads like plumbing, not an operator outcome.

Teaching signals should attach to the card’s upper-right edge as recognizable icons with labels on hover—not amber pills inside content. Use `👍 Endorsed` in `#FBBF24`; `⚑ Do not reuse` in `#FB7185`.

### Edges

Every reuse edge currently being bold, glowing, dashed, and animated creates equal emphasis everywhere. At five edges it looks energetic; at fifty it becomes surveillance-map noise.

Default reuse edge:

- 2px solid `#34D399`
- 70% opacity
- 8px arrowhead
- No glow
- Bézier radius equivalent: 18px

Animate only the **currently focused lineage**, using a 6/8 dash pattern moving left-to-right over **900ms linear**. Flagged reuse edges become `#FB7185`, 2px, with a short terminal crossbar before the blocked node. Structural edges should be `#475569`, 1px, 30% opacity, with no arrowhead.

Increase `ranksep` to **256px** and reduce `nodesep` to **48px**. Group descendants into stable horizontal lanes by precedent root; do not let dagre interleave chains.

## 2. Highest-impact upgrade: precedent story lanes

Replace the undifferentiated canvas with **one horizontal story lane per human precedent**. Each lane begins with a compact governance header:

> **Human precedent: Treat appointment notes as PHI**  
> Applied automatically 3 times · 2 endorsed · 0 blocked

The human root sits immediately below it; all reuse descendants remain within that lane. Use a faint lane surface `#0B1220`, 1px separator `#1E293B`, and a persistent left label column of **280px**.

This makes the human-to-agent learning loop obvious before the reader parses a single edge. It also turns compliance review into three scannable claims rather than a topology puzzle. The summary banner should become a single-line page assertion, while lane headers carry the evidence.

## 3. Scale without wire spaghetti

Use three semantic zoom levels:

- **Below 45%:** precedent lanes only—root title, reuse count, endorsement count, blocked count. No individual nodes or edges.
- **45–75%:** compact nodes at `168×56px`, showing outcome fragment and status. Descendants beyond the first six collapse into a **“+14 more applications”** pill.
- **Above 75%:** full evidence cards and individual signals.

For roots reused more than six times, use **fan-out trunking**: one 3px green trunk leaves the root, then branches near descendants. Show a count badge on the trunk: `20 applications`. This preserves causality without drawing twenty full-length parallel wires.

At 200 nodes, default to collapsed lanes and expand only one lane at a time. Preserve viewport and selection when expanding. Provide search and filters for ambiguity class, actor, rule, and governance status; filtered-out nodes should disappear rather than remain as ghost clutter.

## 4. Micro-interactions

On node hover, highlight its ancestors and descendants in **120ms ease-out**; dim unrelated lanes to 18% opacity. Show a plain-language edge label: “This agent reused the ruling from 14 May.”

Click opens the full record in a right-side drawer, **420px** wide, without destroying graph position. Double-click centers and fits the selected lineage over **240ms cubic-bezier(0.2, 0, 0, 1)**.

Keyboard behavior must match the visual topology: arrow keys move between parent, child, and sibling nodes; `Enter` opens the record; `Esc` closes the drawer or clears focus; `F` fits the selected lineage. Every node needs an accessible label containing actor, decision, precedent relationship, and governance status.

Respect `prefers-reduced-motion`: disable edge flow and use immediate viewport changes.

## 5. Cut this noise

**Cut continuous animated edge dashes.** Motion should indicate active investigation, not decorate settled governance evidence.

## North stars

Steal **lane-based causal scanning from Honeycomb traces**, **progressive disclosure and neighbor dimming from Datadog Service Map**, and **plain-language status summaries from GitHub Actions’ workflow graph**. Do not copy their infrastructure vocabulary; copy how they reveal causality, isolate context, and foreground outcomes.

## Verdict

The shipped design is good enough for a product-team demo, but not yet definitive for an executive or compliance audience. The **one must-fix** is precedent story lanes: make each human ruling and its governed downstream applications readable as a single claim within three seconds.



