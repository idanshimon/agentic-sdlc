/**
 * Cytoscape adapter for the governance/decision map (graph-v2).
 *
 * Maps buildGovernanceNetwork() + applyMapFilters() output → Cytoscape elements.
 * The map is the cross-run "hairball" network, so it uses the fcose force layout
 * (organic) rather than dagre. Node kinds (bundle/class/decision/run/teaching)
 * get distinct silhouettes; edge families carry `relation` for styling + the
 * existing edge-family filter toolbar.
 *
 * DOM-free and pure.
 */
import type { DecisionGraph, GraphNodeKind } from "./build-graph";

export interface CyMapElement {
  group: "nodes" | "edges";
  data: Record<string, unknown>;
  classes?: string;
}

function shortLabel(s: string, max = 26): string {
  const clean = s.replace(/\s+/g, " ").trim();
  if (clean.length <= max) return clean;
  const cut = clean.slice(0, max);
  const sp = cut.lastIndexOf(" ");
  return (sp > 12 ? cut.slice(0, sp) : cut).trimEnd() + "…";
}

const KIND_CLASS: Record<GraphNodeKind, string> = {
  bundle: "bundle",
  class: "klass",
  decision: "decision",
  run: "run",
  teaching: "teaching",
};

/** Map a (filtered) governance graph to Cytoscape elements for the fcose map. */
export function mapToCyElements(g: DecisionGraph): CyMapElement[] {
  const els: CyMapElement[] = [];

  for (const n of g.nodes) {
    const kindClass = KIND_CLASS[n.kind] ?? "decision";
    els.push({
      group: "nodes",
      classes: [kindClass, n.flagged ? "flagged" : "", n.phiHigh ? "phi" : ""].filter(Boolean).join(" "),
      data: {
        id: n.id,
        label: shortLabel(n.label),
        full: n.label,
        kind: n.kind,
        actorKind: n.actorKind ?? "",
        degree: n.degree ?? 0,
        flagged: n.flagged ? 1 : 0,
        phiHigh: n.phiHigh ? 1 : 0,
        entryId: n.entryId ?? "",
      },
    });
  }

  for (const e of g.edges) {
    els.push({
      group: "edges",
      classes: e.kind,
      data: {
        id: e.id,
        source: e.source,
        target: e.target,
        relation: e.kind,
        label: e.kind === "reuses" ? "reused" : "",
      },
    });
  }

  return els;
}
