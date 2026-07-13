import { describe, it, expect } from "vitest";
import { buildPrecedentLineage } from "./build-lineage";
import type { LedgerEntry } from "@/lib/types";

function entry(over: Partial<LedgerEntry>): LedgerEntry {
  return {
    id: over.id ?? "e-" + Math.random().toString(36).slice(2, 8),
    entry_type: "runtime",
    actor: over.actor ?? { kind: "agent", id: "a" },
    decision: over.decision ?? "",
    rationale: "",
    phi_class: over.phi_class ?? "none",
    cost_usd: 0,
    model_used: "",
    bundle_refs: [],
    created_at: over.created_at ?? "2026-07-12T00:00:00Z",
    ...over,
  } as LedgerEntry;
}

describe("buildPrecedentLineage", () => {
  it("keeps only lineage participants and identifies the human root", () => {
    const g = buildPrecedentLineage([
      entry({ id: "root", decision: "human set PHI-high", actor: { kind: "human", id: "idan" } }),
      entry({ id: "reuse1", decision: "autopilot reused it", precedent_refs: ["root"] }),
      entry({ id: "unrelated", decision: "no lineage here" }), // dropped
    ]);
    const ids = g.nodes.map((n) => n.id).sort();
    expect(ids).toEqual(["reuse1", "root"]);
    expect(g.roots).toEqual(["root"]);
    expect(g.stats.reuseEdges).toBe(1);
  });

  it("orients the reuse edge precedent→child (left to right)", () => {
    const g = buildPrecedentLineage([
      entry({ id: "root" }),
      entry({ id: "child", precedent_id: "root" }),
    ]);
    const e = g.edges.find((x) => x.kind === "reuses")!;
    expect(e.source).toBe("root"); // precedent on the left
    expect(e.target).toBe("child");
  });

  it("builds a multi-hop chain (root → r1 → r2)", () => {
    const g = buildPrecedentLineage([
      entry({ id: "root", actor: { kind: "human", id: "idan" } }),
      entry({ id: "r1", precedent_refs: ["root"] }),
      entry({ id: "r2", precedent_refs: ["r1"] }),
    ]);
    expect(g.stats.reuseEdges).toBe(2);
    expect(g.roots).toEqual(["root"]); // only the true origin is a root
  });

  it("attaches a flag teaching signal and glows the flagged precedent", () => {
    const g = buildPrecedentLineage([
      entry({ id: "root", actor: { kind: "human", id: "idan" } }),
      entry({ id: "child", precedent_refs: ["root"] }),
      entry({ id: "flag", runtime_kind: "decision_flagged", references_entry_id: "child", actor: { kind: "human", id: "idan" } }),
    ]);
    expect(g.nodes.find((n) => n.id === "flag")!.kind).toBe("teaching");
    expect(g.edges.filter((e) => e.kind === "teaches")).toHaveLength(1);
    expect(g.nodes.find((n) => n.id === "child")!.flagged).toBe(true);
    expect(g.stats.flagged).toBe(1);
  });

  it("ignores teaching signals that point outside the lineage", () => {
    const g = buildPrecedentLineage([
      entry({ id: "root" }),
      entry({ id: "child", precedent_id: "root" }),
      entry({ id: "t", runtime_kind: "feedback_thumbs", feedback_kind: "thumbs_up", references_entry_id: "not-in-lineage" }),
    ]);
    expect(g.nodes.find((n) => n.id === "t")).toBeUndefined();
  });

  it("drops a reuse edge whose precedent isn't loaded", () => {
    const g = buildPrecedentLineage([entry({ id: "child", precedent_id: "missing" })]);
    expect(g.nodes).toHaveLength(0);
    expect(g.stats.reuseEdges).toBe(0);
  });

  it("builds a story lane per root with applied/endorsed/blocked tallies", () => {
    const g = buildPrecedentLineage([
      entry({ id: "root", decision: "Classify PHI-high", ambiguity_class: "phi-classification" }),
      entry({ id: "c1", precedent_id: "root", decision: "Appt notes PHI" }),
      entry({ id: "c2", precedent_id: "root", decision: "Billing PHI" }),
      entry({ id: "t", runtime_kind: "feedback_thumbs", feedback_kind: "thumbs_up", references_entry_id: "root" }),
      entry({ id: "flag", runtime_kind: "decision_flagged", references_entry_id: "c2" }),
    ]);
    expect(g.lanes).toHaveLength(1);
    const lane = g.lanes[0];
    expect(lane.rootId).toBe("root");
    expect(lane.title).toBe("Classify PHI-high");
    expect(lane.applied).toBe(2); // c1 + c2
    expect(lane.endorsed).toBe(1); // 👍 on root
    expect(lane.blocked).toBe(1); // c2 flagged
    expect(lane.nodeIds.sort()).toEqual(["c1", "c2", "root"]);
  });
});
