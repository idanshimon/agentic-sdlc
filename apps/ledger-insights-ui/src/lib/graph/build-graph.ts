/**
 * Decision-graph builders — the shared engine behind the three graph views.
 *
 * All three pages (run-flow / governance-map / precedent-lineage) are the SAME
 * ledger read (`useDecisions` → LedgerEntry[]) passed through a different pure
 * builder here. Nodes always carry the source entry id so every node can click
 * through to `/decisions#decision-<id>` — the same drill-down contract the
 * activity feed uses. These functions are DOM-free and unit-tested; the React
 * page is a thin renderer over them.
 *
 * This module NEVER mutates the ledger and NEVER invents an edge that isn't
 * grounded in a real field (precedent_refs / references_entry_id / slot_value_hash
 * / bundle_refs / run_id). No edge = no line.
 */
import type { LedgerEntry } from "@/lib/types";

export type GraphNodeKind =
  | "decision" // a stage_decision ledger entry
  | "teaching" // a Track B signal (thumbs / flag / pause / replay)
  | "bundle" // a standards rule referenced by decisions (hub)
  | "run" // a pipeline run (groups its decisions)
  | "class"; // an ambiguity class (clusters decisions of the same kind)

export interface GraphNode {
  id: string; // unique node id (entry id, or synthetic `bundle:<ref>` etc.)
  kind: GraphNodeKind;
  label: string; // human-readable, already plain-language
  entryId?: string; // ledger entry id for click-through (decision/teaching nodes)
  actorKind?: "human" | "agent";
  ambiguityClass?: string;
  flagged?: boolean; // this decision was flagged as wrong (glow red)
  phiHigh?: boolean; // phi_class === "high" (compliance emphasis)
  degree?: number; // filled in by the builder — how many edges touch it (hub sizing)
  meta?: Record<string, unknown>;
}

export type GraphEdgeKind =
  | "in_run" // decision → run (belongs to)
  | "grounded_in" // decision → bundle (cites this rule)
  | "of_class" // decision → class (clustering)
  | "teaches" // teaching signal → decision it acts on
  | "reuses" // decision → precedent decision it was resolved from (the learning loop)
  | "same_slot"; // decision ↔ decision sharing a slot_value_hash (teaching cluster)

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  kind: GraphEdgeKind;
  label?: string;
}

export interface DecisionGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  stats: {
    decisions: number;
    teachingSignals: number;
    bundles: number;
    runs: number;
    reuseEdges: number; // learning-loop lines — the money metric
    flagged: number;
  };
}

const TEACHING_KINDS = new Set([
  "feedback_thumbs",
  "decision_flagged",
  "replay_requested",
  "class_paused",
]);

function isTeaching(e: LedgerEntry): boolean {
  return !!e.runtime_kind && TEACHING_KINDS.has(e.runtime_kind);
}

/** Coerce a possibly-null decision string into a readable label. */
function decisionLabel(e: LedgerEntry): string {
  const d = (e.decision ?? "").trim();
  if (d) return d.length > 60 ? d.slice(0, 57) + "…" : d;
  if (e.ambiguity_class) return `(${e.ambiguity_class})`;
  return "(no decision text)";
}

/** Plain-English label for a teaching signal (mirrors teachingSignalSummary). */
function teachingLabel(e: LedgerEntry): string {
  switch (e.runtime_kind) {
    case "feedback_thumbs":
      return e.feedback_kind === "thumbs_down" ? "👎 not helpful" : "👍 helpful";
    case "decision_flagged":
      return "🚩 flagged wrong";
    case "replay_requested":
      return "↻ replay requested";
    case "class_paused":
      return `⏸ paused '${e.paused_class ?? "class"}'`;
    default:
      return "teaching signal";
  }
}

/**
 * B — Governance / knowledge map. The force-directed "map": every decision, the
 * rules it's grounded in, the ambiguity classes that cluster it, and the
 * teaching signals + reuse edges that draw the human→agent learning loop.
 *
 * This is the one that answers "how does it all connect" for a dev-leader /
 * compliance reader. Bundles become hubs; flagged decisions glow; reuse edges
 * are the learning loop made visible.
 */
export function buildGovernanceNetwork(entries: LedgerEntry[]): DecisionGraph {
  const nodes = new Map<string, GraphNode>();
  const edges: GraphEdge[] = [];
  const degree = new Map<string, number>();

  const bump = (id: string) => degree.set(id, (degree.get(id) ?? 0) + 1);
  const addEdge = (e: GraphEdge) => {
    edges.push(e);
    bump(e.source);
    bump(e.target);
  };

  // Which entry ids were flagged — so we can glow the flagged decision.
  const flaggedIds = new Set(
    entries
      .filter((e) => e.runtime_kind === "decision_flagged" && e.references_entry_id)
      .map((e) => e.references_entry_id as string),
  );

  const decisionEntries = entries.filter((e) => !isTeaching(e));
  const decisionIds = new Set(decisionEntries.map((e) => e.id));

  // Decision nodes + their structural edges (run / class / bundle).
  for (const e of decisionEntries) {
    nodes.set(e.id, {
      id: e.id,
      kind: "decision",
      label: decisionLabel(e),
      entryId: e.id,
      actorKind: e.actor?.kind,
      ambiguityClass: e.ambiguity_class,
      flagged: flaggedIds.has(e.id),
      phiHigh: e.phi_class === "high",
      meta: { runId: e.run_id, model: e.model_used, cost: e.cost_usd },
    });

    if (e.run_id) {
      const rid = `run:${e.run_id}`;
      if (!nodes.has(rid))
        nodes.set(rid, { id: rid, kind: "run", label: `run ${e.run_id.slice(0, 8)}` });
      addEdge({ id: `${e.id}->${rid}`, source: e.id, target: rid, kind: "in_run" });
    }

    if (e.ambiguity_class) {
      const cid = `class:${e.ambiguity_class}`;
      if (!nodes.has(cid))
        nodes.set(cid, { id: cid, kind: "class", label: e.ambiguity_class });
      addEdge({ id: `${e.id}->${cid}`, source: e.id, target: cid, kind: "of_class" });
    }

    for (const ref of e.bundle_refs ?? []) {
      const bid = `bundle:${ref}`;
      if (!nodes.has(bid))
        nodes.set(bid, { id: bid, kind: "bundle", label: ref });
      addEdge({ id: `${e.id}->${bid}`, source: e.id, target: bid, kind: "grounded_in" });
    }
  }

  // Reuse edges — the learning loop. A decision auto-resolved from a precedent.
  let reuseEdges = 0;
  for (const e of decisionEntries) {
    const refs = new Set<string>();
    if (e.precedent_id) refs.add(e.precedent_id);
    for (const r of e.precedent_refs ?? []) refs.add(r);
    for (const target of refs) {
      if (decisionIds.has(target) && target !== e.id) {
        addEdge({
          id: `${e.id}~reuses~${target}`,
          source: e.id,
          target,
          kind: "reuses",
          label: "reused",
        });
        reuseEdges++;
      }
    }
  }

  // Teaching-signal nodes + edges to the decision they act on.
  const teachingEntries = entries.filter(isTeaching);
  for (const e of teachingEntries) {
    nodes.set(e.id, {
      id: e.id,
      kind: "teaching",
      label: teachingLabel(e),
      entryId: e.id,
      actorKind: e.actor?.kind,
      meta: { rationale: e.rationale },
    });
    if (e.references_entry_id && nodes.has(e.references_entry_id)) {
      addEdge({
        id: `${e.id}->teaches->${e.references_entry_id}`,
        source: e.id,
        target: e.references_entry_id,
        kind: "teaches",
      });
    }
  }

  // Same-slot clustering edges (teaching bucket): connect decisions that share a
  // slot_value_hash so the map visually groups one ambiguity bucket. Chain them
  // (sorted by created_at) rather than fully-connect to avoid O(n^2) hairball.
  const bySlot = new Map<string, LedgerEntry[]>();
  for (const e of decisionEntries) {
    if (!e.slot_value_hash) continue;
    const arr = bySlot.get(e.slot_value_hash) ?? [];
    arr.push(e);
    bySlot.set(e.slot_value_hash, arr);
  }
  for (const [hash, arr] of bySlot) {
    if (arr.length < 2) continue;
    const sorted = [...arr].sort((a, b) => (a.created_at ?? "").localeCompare(b.created_at ?? ""));
    for (let i = 1; i < sorted.length; i++) {
      addEdge({
        id: `slot:${hash}:${i}`,
        source: sorted[i - 1].id,
        target: sorted[i].id,
        kind: "same_slot",
      });
    }
  }

  // Fold degree back onto nodes (hub sizing).
  for (const n of nodes.values()) n.degree = degree.get(n.id) ?? 0;

  const all = Array.from(nodes.values());
  return {
    nodes: all,
    edges,
    stats: {
      decisions: decisionEntries.length,
      teachingSignals: teachingEntries.length,
      bundles: all.filter((n) => n.kind === "bundle").length,
      runs: all.filter((n) => n.kind === "run").length,
      reuseEdges,
      flagged: flaggedIds.size,
    },
  };
}
