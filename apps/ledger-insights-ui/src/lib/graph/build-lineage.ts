/**
 * Precedent-lineage DAG builder (graph view C — the learning-loop hero).
 *
 * The `reuses` edge (autopilot decision → the human precedent it was resolved
 * from) is a TRUE directed lineage: precedent flows one direction in time. The
 * second-opinion critique's headline: render it left-to-right as a "timeline of
 * inherited decisions" (Sugiyama/dagre layering), NOT scattered around a class
 * ring. This is where a compliance reader SEES the human→agent learning loop.
 *
 * We keep only decisions that participate in a lineage (are a precedent, or
 * reuse one) plus the teaching signals that act on them — everything else is
 * noise for this view. Roots (human precedents) sit on the left; each reuse
 * hop moves right. Flagged precedents glow; the flag's teaching node attaches.
 */
import type { LedgerEntry } from "@/lib/types";
import type { GraphNode, GraphEdge } from "./build-graph";

export interface LineageLane {
  rootId: string;
  title: string; // the human precedent's decision, plain language
  actorRole: string;
  actorKind?: "human" | "agent"; // root author kind — drives header label honesty
  ambiguityClass?: string;
  applied: number; // reuse count in this lane
  endorsed: number; // 👍 teaching signals in this lane
  blocked: number; // flagged nodes in this lane
  nodeIds: string[]; // all decision node ids in this lane (root + descendants)
}

export interface LineageGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  roots: string[]; // human-precedent entry ids (left edge of the DAG)
  lanes: LineageLane[]; // one story lane per precedent root (5.6-sol design)
  stats: { chains: number; reuseEdges: number; roots: number; flagged: number };
}

const TEACHING = new Set(["feedback_thumbs", "decision_flagged", "replay_requested", "class_paused"]);

function label(e: LedgerEntry): string {
  const d = (e.decision ?? "").trim();
  if (d) return d.length > 52 ? d.slice(0, 49) + "…" : d;
  return e.ambiguity_class ? `(${e.ambiguity_class})` : "(decision)";
}

/**
 * Build the precedent DAG. An entry X reuses Y when X.precedent_refs/precedent_id
 * contains Y.id. We surface every node reachable in a reuse chain, plus teaching
 * signals whose references_entry_id points at a lineage node.
 */
export function buildPrecedentLineage(entries: LedgerEntry[]): LineageGraph {
  const byId = new Map(entries.map((e) => [e.id, e]));
  const decisions = entries.filter((e) => !e.runtime_kind || !TEACHING.has(e.runtime_kind));

  // reuse edges (child → precedent)
  const reuse: Array<{ child: string; parent: string }> = [];
  for (const e of decisions) {
    const refs = new Set<string>();
    if (e.precedent_id) refs.add(e.precedent_id);
    for (const r of e.precedent_refs ?? []) refs.add(r);
    for (const p of refs) {
      if (byId.has(p) && p !== e.id) reuse.push({ child: e.id, parent: p });
    }
  }

  // nodes that participate in any lineage
  const inLineage = new Set<string>();
  for (const { child, parent } of reuse) {
    inLineage.add(child);
    inLineage.add(parent);
  }

  // children set → roots are lineage nodes that are never a child
  const children = new Set(reuse.map((r) => r.child));
  const roots = [...inLineage].filter((id) => !children.has(id));

  const flaggedIds = new Set(
    entries
      .filter((e) => e.runtime_kind === "decision_flagged" && e.references_entry_id)
      .map((e) => e.references_entry_id as string),
  );

  const nodes: GraphNode[] = [];
  for (const id of inLineage) {
    const e = byId.get(id)!;
    nodes.push({
      id,
      kind: "decision",
      label: label(e),
      entryId: id,
      actorKind: e.actor?.kind,
      ambiguityClass: e.ambiguity_class ?? undefined,
      flagged: flaggedIds.has(id),
      phiHigh: e.phi_class === "high",
      meta: {
        runId: e.run_id,
        isRoot: !children.has(id),
        role: (e.actor as { display_name?: string })?.display_name ?? (e.actor?.kind === "human" ? "Human" : "Agent"),
        rule: (e.bundle_refs ?? [])[0] ?? null,
        fullText: e.decision ?? "",
      },
    });
  }

  const edges: GraphEdge[] = reuse.map((r, i) => ({
    id: `reuse-${i}-${r.child}`,
    source: r.parent, // left→right: precedent → the decision that inherited it
    target: r.child,
    kind: "reuses",
    label: "reused by",
  }));

  // Attach teaching signals that act on a lineage node.
  for (const e of entries) {
    if (!e.runtime_kind || !TEACHING.has(e.runtime_kind)) continue;
    if (!e.references_entry_id || !inLineage.has(e.references_entry_id)) continue;
    nodes.push({
      id: e.id,
      kind: "teaching",
      label:
        e.runtime_kind === "decision_flagged"
          ? "🚩 flagged wrong"
          : e.runtime_kind === "feedback_thumbs"
            ? e.feedback_kind === "thumbs_down"
              ? "👎 not helpful"
              : "👍 endorsed"
            : e.runtime_kind === "replay_requested"
              ? "↻ replay"
              : "⏸ paused",
      entryId: e.id,
      actorKind: e.actor?.kind,
    });
    edges.push({
      id: `teach-${e.id}`,
      source: e.id,
      target: e.references_entry_id,
      kind: "teaches",
    });
  }

  // ── Story lanes: one per precedent root (5.6-sol "precedent story lanes") ──
  // Assign each lineage node to the lane of the root it descends from. A node
  // reached from multiple roots lands in its first root (stable by roots order).
  const childrenOf = new Map<string, string[]>();
  for (const { child, parent } of reuse) {
    const arr = childrenOf.get(parent) ?? [];
    arr.push(child);
    childrenOf.set(parent, arr);
  }
  const laneOf = new Map<string, string>(); // nodeId → rootId
  for (const root of roots) {
    const stack = [root];
    while (stack.length) {
      const id = stack.pop()!;
      if (laneOf.has(id)) continue;
      laneOf.set(id, root);
      for (const c of childrenOf.get(id) ?? []) stack.push(c);
    }
  }

  // 👍 endorsements and flags per node, for lane tallies.
  const endorsedNodes = new Set(
    entries
      .filter((e) => e.runtime_kind === "feedback_thumbs" && e.feedback_kind !== "thumbs_down" && e.references_entry_id)
      .map((e) => e.references_entry_id as string),
  );

  const lanes: LineageLane[] = roots.map((rootId) => {
    const e = byId.get(rootId)!;
    const nodeIds = [...laneOf.entries()].filter(([, r]) => r === rootId).map(([id]) => id);
    const descendants = nodeIds.filter((id) => id !== rootId);
    return {
      rootId,
      title: (e.decision ?? "").trim() || `(${e.ambiguity_class ?? "precedent"})`,
      actorRole: (e.actor as { display_name?: string })?.display_name ?? (e.actor?.kind === "human" ? "Human" : "Agent"),
      actorKind: e.actor?.kind,
      ambiguityClass: e.ambiguity_class ?? undefined,
      applied: descendants.length,
      endorsed: nodeIds.filter((id) => endorsedNodes.has(id)).length,
      blocked: nodeIds.filter((id) => flaggedIds.has(id)).length,
      nodeIds,
    };
  });

  return {
    nodes,
    edges,
    roots,
    lanes,
    stats: {
      chains: roots.length,
      reuseEdges: reuse.length,
      roots: roots.length,
      flagged: flaggedIds.size,
    },
  };
}
