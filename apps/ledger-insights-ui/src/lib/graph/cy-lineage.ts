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
  position?: { x: number; y: number };
}

/** Trim a decision sentence to a node-sized title (full text lives in the panel). */
function shortLabel(s: string, max = 34): string {
  const clean = s.replace(/\s+/g, " ").trim();
  if (clean.length <= max) return clean;
  // cut on a word boundary before max
  const cut = clean.slice(0, max);
  const lastSpace = cut.lastIndexOf(" ");
  return (lastSpace > 16 ? cut.slice(0, lastSpace) : cut).trimEnd() + "…";
}

/** Map a lineage graph to Cytoscape elements — a clean left→right DAG.
 *  No compound lane containers (they forced quadrant spread + overlap when a
 *  decision reused two precedents). Dagre lays precedents on the left, reuse
 *  decisions flowing right; multi-precedent reuse is handled by the DAG engine.
 *  Precedent-vs-agent is conveyed by node shape/color, not containers. */
export function lineageToCyElements(g: LineageGraph): CyElement[] {
  const els: CyElement[] = [];

  const rootSet = new Set(g.roots);
  const laneMeta = new Map(g.lanes.map((l) => [l.rootId, l]));

  // decision nodes only (teaching excluded — folded into the modal)
  for (const n of g.nodes) {
    if (n.kind === "teaching") continue;
    const isRoot = rootSet.has(n.id);
    const kindClass = isRoot ? "precedent" : "agent";
    const lane = laneMeta.get(n.id);
    els.push({
      group: "nodes",
      classes: [kindClass, n.flagged ? "flagged" : "", n.phiHigh ? "phi" : ""].filter(Boolean).join(" "),
      data: {
        id: n.id,
        label: shortLabel(n.label),
        full: n.label,
        actorKind: n.actorKind ?? "agent",
        ambiguityClass: n.ambiguityClass ?? "",
        rule: (n.meta as { rule?: string } | undefined)?.rule ?? "",
        role: (n.meta as { role?: string } | undefined)?.role ?? "",
        flagged: n.flagged ? 1 : 0,
        phiHigh: n.phiHigh ? 1 : 0,
        isRoot: isRoot ? 1 : 0,
        applied: lane?.applied ?? 0,
        endorsed: lane?.endorsed ?? 0,
        entryId: n.entryId ?? n.id,
        kind: n.kind,
      },
    });
  }

  // reuse edges only (teaching edges excluded with their nodes)
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
