/**
 * Run-flow builder (graph view A). Answers "how did THIS run flow, stage by
 * stage, and where did each decision land?" for an engineer debugging a run.
 *
 * Unlike the map (cross-run network) and lineage (precedent DAG), this is
 * scoped to a single run and ordered by the pipeline's canonical stage
 * sequence. Decisions attach under their stage; the stages form the L→R spine.
 */
import type { LedgerEntry } from "@/lib/types";
import type { GraphNode, GraphEdge } from "./build-graph";

// Canonical pipeline stage order (mirrors the orchestrator's Stage enum).
export const STAGE_ORDER = [
  "ingest",
  "assessor",
  "resolver",
  "architect",
  "testplan",
  "codegen",
  "review",
  "deliver",
];

export interface RunFlowGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  runId: string | null;
  stats: { stages: number; decisions: number; flagged: number };
}

function stageRank(stage: string | null | undefined): number {
  if (!stage) return STAGE_ORDER.length; // unknown → far right
  const i = STAGE_ORDER.indexOf(stage);
  return i === -1 ? STAGE_ORDER.length : i;
}

function label(e: LedgerEntry): string {
  const d = (e.decision ?? "").trim();
  if (d) return d.length > 48 ? d.slice(0, 45) + "…" : d;
  return e.ambiguity_class ? `(${e.ambiguity_class})` : "(decision)";
}

/** Spine bucket for decisions carrying no stage. Not a stage — labelled as such. */
export const UNSTAGED_KEY = "unstaged";

/**
 * Build the run-flow graph for a single run. Stages present in the run become
 * spine nodes connected in canonical order; each decision hangs under its stage.
 *
 * Decisions with no `stage` (resolver decisions carry `ambiguity_class`, not
 * stage) collect under ONE terminal `unstaged` bucket. They are deliberately
 * NOT bucketed by `ambiguity_class`: doing so made the spine axis mean two
 * different things — pipeline stage for some rows, ambiguity class for others —
 * so an operator could not tell whether spine position encoded *when* a
 * decision happened or *what kind* it was. The axis now means exactly one
 * thing: pipeline stage. Ambiguity class remains available on each node as
 * `ambiguityClass` for color/filter encoding.
 */
export function buildRunFlow(entries: LedgerEntry[], runId: string): RunFlowGraph {
  const runEntries = entries.filter((e) => e.run_id === runId && (!e.runtime_kind || e.runtime_kind === "stage_decision"));

  const flaggedIds = new Set(
    entries
      .filter((e) => e.runtime_kind === "decision_flagged" && e.references_entry_id)
      .map((e) => e.references_entry_id as string),
  );

  // Group by stage only. Stage-less decisions go to one honest `unstaged`
  // bucket rather than masquerading as stages (see fn doc).
  const groupKey = (e: LedgerEntry) => e.stage ?? UNSTAGED_KEY;
  const groups = new Map<string, LedgerEntry[]>();
  for (const e of runEntries) {
    const k = groupKey(e);
    const arr = groups.get(k) ?? [];
    arr.push(e);
    groups.set(k, arr);
  }

  // Order groups: real stages by canonical rank, `unstaged` always terminal.
  const orderedKeys = [...groups.keys()].sort((a, b) => {
    const ra = a === UNSTAGED_KEY ? STAGE_ORDER.length + 1 : stageRank(a);
    const rb = b === UNSTAGED_KEY ? STAGE_ORDER.length + 1 : stageRank(b);
    return ra - rb || a.localeCompare(b);
  });

  const nodes: GraphNode[] = [];
  const edges: GraphEdge[] = [];

  // Stage spine.
  orderedKeys.forEach((k, i) => {
    const spineId = `stage:${k}`;
    const isUnstaged = k === UNSTAGED_KEY;
    // The unstaged bucket is labelled as what it is, so nobody reads it as a
    // ninth pipeline stage.
    const pretty = isUnstaged ? "unstaged" : k;
    nodes.push({ id: spineId, kind: "class", label: pretty, degree: groups.get(k)!.length });
    if (i > 0) {
      const prev = `stage:${orderedKeys[i - 1]}`;
      edges.push({ id: `spine-${i}`, source: prev, target: spineId, kind: "of_class" });
    }
    // Decision leaves under this stage.
    for (const e of groups.get(k)!) {
      nodes.push({
        id: e.id,
        kind: "decision",
        label: label(e),
        entryId: e.id,
        actorKind: e.actor?.kind,
        ambiguityClass: e.ambiguity_class ?? undefined,
        flagged: flaggedIds.has(e.id),
        phiHigh: e.phi_class === "high",
      });
      edges.push({ id: `leaf-${e.id}`, source: spineId, target: e.id, kind: "in_run" });
    }
  });

  return {
    nodes,
    edges,
    runId,
    stats: {
      stages: orderedKeys.length,
      decisions: runEntries.length,
      flagged: runEntries.filter((e) => flaggedIds.has(e.id)).length,
    },
  };
}

/** Distinct run ids present in the ledger (newest-ish first by string sort desc). */
export function runIdsFrom(entries: LedgerEntry[]): string[] {
  const ids = new Set<string>();
  for (const e of entries) if (e.run_id && (!e.runtime_kind || e.runtime_kind === "stage_decision")) ids.add(e.run_id);
  return [...ids].sort().reverse();
}
