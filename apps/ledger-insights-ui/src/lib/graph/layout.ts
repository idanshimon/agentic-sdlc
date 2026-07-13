/**
 * Deterministic cluster layout for the governance map.
 *
 * We deliberately avoid a physics/force simulation: it's non-deterministic
 * (bad for screenshot verification), heavy, and famously produces hairballs.
 * Instead we place nodes by KIND into concentric bands and cluster decisions
 * around their ambiguity-class anchor. Bundles (the hubs) sit in the middle
 * band, classes ring them, decisions orbit their class, runs + teaching sit
 * on the outer band. This reads as a "map" (clusters + hubs) while staying
 * legible and stable at 200+ nodes.
 */
import type { DecisionGraph, GraphNode } from "./build-graph";

export interface PositionedNode extends GraphNode {
  x: number;
  y: number;
}

const R_BUNDLE = 0; // hubs in the center
const R_CLASS = 260;
const R_DECISION = 520;
const R_OUTER = 820; // runs + teaching

function ring(nodes: GraphNode[], radius: number, phase = 0): PositionedNode[] {
  const n = nodes.length || 1;
  return nodes.map((node, i) => {
    const a = phase + (2 * Math.PI * i) / n;
    return { ...node, x: Math.cos(a) * radius, y: Math.sin(a) * radius };
  });
}

export function layoutGovernanceMap(graph: DecisionGraph): PositionedNode[] {
  const byKind = (k: GraphNode["kind"]) => graph.nodes.filter((n) => n.kind === k);

  const bundles = byKind("bundle");
  const classes = byKind("class");
  const decisions = byKind("decision");
  const runs = byKind("run");
  const teaching = byKind("teaching");

  const positioned: PositionedNode[] = [];

  // Center hubs — bundles, packed in a small spiral so multiple don't overlap.
  bundles.forEach((b, i) => {
    const a = (2 * Math.PI * i) / (bundles.length || 1);
    const r = bundles.length <= 1 ? 0 : 70 + i * 6;
    positioned.push({ ...b, x: Math.cos(a) * r, y: Math.sin(a) * r });
  });

  // Class anchors on a ring; remember each class angle so its decisions cluster near it.
  const classAngle = new Map<string, number>();
  classes.forEach((c, i) => {
    const a = (2 * Math.PI * i) / (classes.length || 1);
    classAngle.set(c.id, a);
    positioned.push({ ...c, x: Math.cos(a) * R_CLASS, y: Math.sin(a) * R_CLASS });
  });

  // Decisions cluster around their class anchor (fan out in a small arc).
  const byClass = new Map<string, GraphNode[]>();
  for (const d of decisions) {
    const key = d.ambiguityClass ? `class:${d.ambiguityClass}` : "__none__";
    const arr = byClass.get(key) ?? [];
    arr.push(d);
    byClass.set(key, arr);
  }
  for (const [classId, arr] of byClass) {
    const base = classAngle.get(classId);
    if (base === undefined) {
      // classless decisions → their own outer arc
      ring(arr, R_DECISION).forEach((p) => positioned.push(p));
      continue;
    }
    const spread = Math.min(Math.PI / 3, 0.18 * arr.length);
    arr.forEach((d, i) => {
      const frac = arr.length === 1 ? 0 : i / (arr.length - 1) - 0.5;
      const a = base + frac * spread;
      const r = R_DECISION + (i % 2 === 0 ? 0 : 60); // stagger radius to reduce overlap
      positioned.push({ ...d, x: Math.cos(a) * r, y: Math.sin(a) * r });
    });
  }

  // Runs + teaching on the outer band.
  ring(runs, R_OUTER, 0.15).forEach((p) => positioned.push(p));
  ring(teaching, R_OUTER + 120, 0.4).forEach((p) => positioned.push(p));

  return positioned;
}
