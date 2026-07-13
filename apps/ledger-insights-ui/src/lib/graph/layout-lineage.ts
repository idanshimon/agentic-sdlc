/**
 * Dagre layout for the precedent-lineage DAG (view C).
 *
 * Left→right (rankdir LR) so the learning loop reads as a timeline: human
 * precedents (roots) on the left, each reuse hop one rank to the right. Teaching
 * signals attach near the decision they act on. Deterministic — dagre gives the
 * same coordinates for the same input, so audit screenshots are reproducible.
 */
import dagre from "@dagrejs/dagre";
import type { GraphNode, GraphEdge } from "./build-graph";

export interface PositionedNode extends GraphNode {
  x: number;
  y: number;
}

const NODE_W = 234;
const NODE_H = 78;

export function layoutLineageDag(
  nodes: GraphNode[],
  edges: GraphEdge[],
): { positioned: PositionedNode[]; width: number; height: number } {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: "LR", nodesep: 64, ranksep: 220, marginx: 40, marginy: 40 });
  g.setDefaultEdgeLabel(() => ({}));

  for (const n of nodes) {
    // teaching nodes are smaller
    const isTeach = n.kind === "teaching";
    g.setNode(n.id, { width: isTeach ? 120 : NODE_W, height: isTeach ? 34 : NODE_H });
  }
  for (const e of edges) {
    if (g.hasNode(e.source) && g.hasNode(e.target)) g.setEdge(e.source, e.target);
  }

  dagre.layout(g);

  const positioned: PositionedNode[] = nodes.map((n) => {
    const p = g.node(n.id);
    // dagre returns centers; react-flow wants top-left
    return { ...n, x: (p?.x ?? 0) - (p?.width ?? NODE_W) / 2, y: (p?.y ?? 0) - (p?.height ?? NODE_H) / 2 };
  });

  const gr = g.graph();
  return { positioned, width: gr.width ?? 800, height: gr.height ?? 600 };
}

export interface LaneBand {
  rootId: string;
  y: number; // top of the band
  height: number;
}

/**
 * Lane-aware layout (5.6-sol "precedent story lanes"): each precedent root and
 * its descendants are laid out as an independent LR dagre subgraph, then the
 * lanes are stacked vertically into bands. Teaching nodes attach to their lane.
 * Produces positioned nodes plus band rects the page paints behind each lane.
 */
export function layoutLineageLanes(
  nodes: GraphNode[],
  edges: GraphEdge[],
  lanes: { rootId: string; nodeIds: string[] }[],
): { positioned: PositionedNode[]; bands: LaneBand[]; width: number; height: number } {
  const LANE_GAP = 40;
  const LANE_PAD = 24;
  const nodeById = new Map(nodes.map((n) => [n.id, n]));

  // teaching nodes belong to the lane of the decision they reference
  const teachTarget = new Map<string, string>();
  for (const e of edges) {
    if (e.kind === "teaches") teachTarget.set(e.source, e.target); // teach → decision
  }
  const laneForNode = new Map<string, string>();
  for (const lane of lanes) for (const id of lane.nodeIds) laneForNode.set(id, lane.rootId);
  for (const n of nodes) {
    if (n.kind === "teaching") {
      const tgt = teachTarget.get(n.id);
      if (tgt && laneForNode.has(tgt)) laneForNode.set(n.id, laneForNode.get(tgt)!);
    }
  }

  const positioned: PositionedNode[] = [];
  const bands: LaneBand[] = [];
  let cursorY = 0;
  let maxW = 0;

  for (const lane of lanes) {
    // Root is presented by the lane HEADER, not a duplicate card — exclude it
    // from the band's node layout (5.6-sol: header replaces the root card).
    // Teaching nodes are excluded from dagre ranking too (they'd push their
    // target card a rank right); we place them as satellites post-layout.
    const laneDecisionIds = nodes
      .filter((n) => laneForNode.get(n.id) === lane.rootId && n.id !== lane.rootId && n.kind !== "teaching")
      .map((n) => n.id);
    const laneTeachIds = nodes
      .filter((n) => laneForNode.get(n.id) === lane.rootId && n.kind === "teaching")
      .map((n) => n.id);
    const laneNodeSet = new Set(laneDecisionIds);
    const laneEdges = edges.filter((e) => laneNodeSet.has(e.source) && laneNodeSet.has(e.target));

    const g = new dagre.graphlib.Graph();
    g.setGraph({ rankdir: "LR", nodesep: 56, ranksep: 200, marginx: 12, marginy: 12 });
    g.setDefaultEdgeLabel(() => ({}));
    for (const id of laneDecisionIds) {
      g.setNode(id, { width: NODE_W, height: 104 });
    }
    for (const e of laneEdges) g.setEdge(e.source, e.target);
    dagre.layout(g);

    const gr = g.graph();
    const laneH = Math.max(gr.height ?? NODE_H, NODE_H);
    const placed = new Map<string, { x: number; y: number }>();
    for (const id of laneDecisionIds) {
      const n = nodeById.get(id)!;
      const p = g.node(id);
      const x = (p?.x ?? 0) - (p?.width ?? NODE_W) / 2 + LANE_PAD;
      const y = (p?.y ?? 0) - (p?.height ?? NODE_H) / 2 + cursorY + LANE_PAD;
      placed.set(id, { x, y });
      positioned.push({ ...n, x, y });
    }
    // teaching satellites: attach to the RIGHT of the decision they reference
    // (below-card placement collides with the next stacked card in the lane).
    for (const id of laneTeachIds) {
      const n = nodeById.get(id)!;
      const tgt = edges.find((e) => e.kind === "teaches" && e.source === id)?.target;
      const anchor = tgt ? placed.get(tgt) : undefined;
      positioned.push({
        ...n,
        x: (anchor?.x ?? LANE_PAD) + NODE_W + 12,
        y: (anchor?.y ?? cursorY + LANE_PAD) + 6,
      });
    }
    bands.push({ rootId: lane.rootId, y: cursorY, height: laneH + LANE_PAD * 2 });
    maxW = Math.max(maxW, (gr.width ?? 800) + LANE_PAD * 2 + 140);
    cursorY += laneH + LANE_PAD * 2 + LANE_GAP;
  }

  return { positioned, bands, width: maxW, height: cursorY };
}
