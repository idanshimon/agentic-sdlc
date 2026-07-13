/**
 * Cytoscape adapter for the run-flow graph (graph-v2).
 *
 * Same buildRunFlow() output the react-flow view uses, mapped to Cytoscape
 * elements with a dagre left→right layout: a stage spine (blue stage nodes in
 * canonical order) with decision cards hanging under each stage. Distinct
 * silhouettes for stage vs human vs agent decision, matching lineage-v2.
 *
 * DOM-free and pure.
 */
import type { RunFlowGraph } from "./build-runflow";

export interface CyRunElement {
  group: "nodes" | "edges";
  data: Record<string, unknown>;
  classes?: string;
}

function shortLabel(s: string, max = 40): string {
  const clean = s.replace(/\s+/g, " ").trim();
  if (clean.length <= max) return clean;
  const cut = clean.slice(0, max);
  const sp = cut.lastIndexOf(" ");
  return (sp > 18 ? cut.slice(0, sp) : cut).trimEnd() + "…";
}

/** Map a run-flow graph to Cytoscape elements. */
export function runFlowToCyElements(g: RunFlowGraph): CyRunElement[] {
  const els: CyRunElement[] = [];

  for (const n of g.nodes) {
    if (n.kind === "class") {
      // stage / bucket spine node
      els.push({
        group: "nodes",
        classes: "stage",
        data: { id: n.id, label: n.label, full: n.label, kind: "stage", count: n.degree ?? 0 },
      });
    } else {
      // decision leaf
      const isHuman = n.actorKind === "human";
      els.push({
        group: "nodes",
        classes: ["decision", isHuman ? "human" : "agent", n.flagged ? "flagged" : "", n.phiHigh ? "phi" : ""].filter(Boolean).join(" "),
        data: {
          id: n.id,
          label: shortLabel(n.label),
          full: n.label,
          actorKind: n.actorKind ?? "agent",
          ambiguityClass: n.ambiguityClass ?? "",
          flagged: n.flagged ? 1 : 0,
          phiHigh: n.phiHigh ? 1 : 0,
          entryId: n.entryId ?? n.id,
          kind: "decision",
        },
      });
    }
  }

  for (const e of g.edges) {
    els.push({
      group: "edges",
      classes: e.kind, // "of_class" (spine) | "in_run" (leaf)
      data: { id: e.id, source: e.source, target: e.target, relation: e.kind },
    });
  }

  return els;
}
