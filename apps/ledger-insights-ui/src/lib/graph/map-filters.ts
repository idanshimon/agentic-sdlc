/**
 * Map view-model filters (view B scale-survival). Pure, testable transforms the
 * map page applies before layout so the "everything" graph answers a question
 * instead of rendering a starfield. Per the second-opinion critique:
 *  - default structural edges OFF (of_class / in_run), learning-loop + teaching ON
 *  - filter-by-flag: keep only flagged decisions + their 1-hop neighborhood
 *  - filter-by-bundle: scope to one rule and what cites it
 *  - node budget: cap rendered decision nodes, keep hubs/classes/flagged
 */
import type { DecisionGraph, GraphNode, GraphEdge, GraphEdgeKind } from "./build-graph";

export interface MapFilters {
  edgeKinds: Set<GraphEdgeKind>; // which edge types to render
  onlyFlagged: boolean; // focus on flagged + neighborhood
  bundleId?: string; // scope to one bundle node id (e.g. "bundle:security/v0.1.0/PHI-001")
  nodeBudget?: number; // hard cap on rendered nodes (hubs/flagged always kept)
}

export const DEFAULT_EDGE_KINDS: GraphEdgeKind[] = ["reuses", "teaches", "grounded_in", "same_slot"];

export function defaultMapFilters(): MapFilters {
  return { edgeKinds: new Set(DEFAULT_EDGE_KINDS), onlyFlagged: false, nodeBudget: 150 };
}

/** Neighbors of a node id across the given edges (both directions). */
function neighbors(id: string, edges: GraphEdge[]): Set<string> {
  const out = new Set<string>();
  for (const e of edges) {
    if (e.source === id) out.add(e.target);
    if (e.target === id) out.add(e.source);
  }
  return out;
}

export function applyMapFilters(graph: DecisionGraph, f: MapFilters): DecisionGraph {
  let edges = graph.edges.filter((e) => f.edgeKinds.has(e.kind));
  let keep = new Set(graph.nodes.map((n) => n.id));

  // Bundle scope: keep the bundle + everything grounded_in it (1 hop) + their edges.
  if (f.bundleId) {
    const nb = neighbors(f.bundleId, graph.edges);
    keep = new Set<string>([f.bundleId, ...nb]);
  }

  // Flag focus: keep flagged decisions + 1-hop neighborhood.
  if (f.onlyFlagged) {
    const flagged = graph.nodes.filter((n) => n.flagged).map((n) => n.id);
    const focus = new Set<string>(flagged);
    for (const id of flagged) for (const n of neighbors(id, graph.edges)) focus.add(n);
    keep = new Set([...keep].filter((id) => focus.has(id)));
  }

  // Node budget: if over cap, drop the lowest-degree plain decision nodes first.
  // Always keep hubs (bundle/class), runs, teaching, and flagged decisions.
  if (f.nodeBudget && keep.size > f.nodeBudget) {
    const protectedKinds = new Set<GraphNode["kind"]>(["bundle", "class", "run", "teaching"]);
    const candidates = graph.nodes
      .filter((n) => keep.has(n.id) && !protectedKinds.has(n.kind) && !n.flagged)
      .sort((a, b) => (a.degree ?? 0) - (b.degree ?? 0));
    const mustKeep = keep.size - candidates.length;
    const room = Math.max(0, f.nodeBudget - mustKeep);
    const keptCandidates = new Set(candidates.slice(candidates.length - room).map((n) => n.id));
    keep = new Set(
      [...keep].filter((id) => {
        const n = graph.nodes.find((x) => x.id === id)!;
        return protectedKinds.has(n.kind) || n.flagged || keptCandidates.has(id);
      }),
    );
  }

  const nodes = graph.nodes.filter((n) => keep.has(n.id));
  edges = edges.filter((e) => keep.has(e.source) && keep.has(e.target));

  return { nodes, edges, stats: graph.stats };
}
