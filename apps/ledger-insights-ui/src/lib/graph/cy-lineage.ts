/**
 * Cytoscape adapter for the precedent-lineage graph (spike / graph-v2).
 *
 * Converts the SAME buildPrecedentLineage() output the react-flow view uses into
 * Cytoscape elements — but leans on native compound nodes for precedent lanes
 * instead of the hand-rolled band rectangles + per-lane dagre in layout-lineage.ts.
 *
 * Each precedent root becomes a compound PARENT ("lane:<rootId>"); the root and
 * every agent decision that reuses it get parent:lane. Cytoscape auto-sizes the
 * container. Reuse/teaching edges carry a `relation` data field so click-to-focus
 * can traverse by edge type (predecessors('[relation="reuses"]') etc.).
 *
 * DOM-free and pure — unit-testable, no cytoscape import here.
 */
import type { LineageGraph } from "./build-lineage";

export interface CyElement {
  group: "nodes" | "edges";
  data: Record<string, unknown>;
  classes?: string;
}

/** Map a lineage graph to Cytoscape elements with compound precedent lanes. */
export function lineageToCyElements(g: LineageGraph): CyElement[] {
  const els: CyElement[] = [];

  // node id → its lane (root) id, so reuse children nest in the right parent
  const laneOf = new Map<string, string>();
  for (const lane of g.lanes) for (const id of lane.nodeIds) laneOf.set(id, lane.rootId);

  // 1) compound parent per precedent lane
  for (const lane of g.lanes) {
    els.push({
      group: "nodes",
      classes: "lane",
      data: {
        id: `lane:${lane.rootId}`,
        label: lane.title,
        actorKind: lane.actorKind ?? "human",
        applied: lane.applied,
        endorsed: lane.endorsed,
        blocked: lane.blocked,
        ambiguityClass: lane.ambiguityClass ?? "",
      },
    });
  }

  const rootSet = new Set(g.roots);

  // 2) decision nodes only, nested into their lane parent.
  //    Teaching signals are EXCLUDED from the graph (they floated loose outside
  //    lanes with awkward long edges); their endorsed/flagged state is folded
  //    onto the decision cards + surfaced in the side-panel instead.
  for (const n of g.nodes) {
    if (n.kind === "teaching") continue;
    const parent = laneOf.get(n.id);
    const isRoot = rootSet.has(n.id);
    const kindClass = isRoot ? "precedent" : "agent";
    els.push({
      group: "nodes",
      classes: [kindClass, n.flagged ? "flagged" : "", n.phiHigh ? "phi" : ""].filter(Boolean).join(" "),
      data: {
        id: n.id,
        label: n.label,
        parent: parent ? `lane:${parent}` : undefined,
        actorKind: n.actorKind ?? "agent",
        ambiguityClass: n.ambiguityClass ?? "",
        rule: (n.meta as { rule?: string } | undefined)?.rule ?? "",
        role: (n.meta as { role?: string } | undefined)?.role ?? "",
        flagged: n.flagged ? 1 : 0,
        phiHigh: n.phiHigh ? 1 : 0,
        isRoot: isRoot ? 1 : 0,
        entryId: n.entryId ?? n.id,
        kind: n.kind,
      },
    });
  }

  // 3) edges — reuse edges only (teaching edges excluded with their nodes)
  for (const e of g.edges) {
    if (e.kind === "teaches") continue;
    els.push({
      group: "edges",
      classes: e.kind,
      data: {
        id: e.id,
        source: e.source,
        target: e.target,
        relation: e.kind, // "reuses"
        label: e.kind === "reuses" ? "reuses" : "",
      },
    });
  }

  return els;
}
