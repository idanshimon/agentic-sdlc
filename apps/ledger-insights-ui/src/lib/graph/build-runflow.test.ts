import { describe, it, expect } from "vitest";
import { buildRunFlow, runIdsFrom } from "./build-runflow";
import type { LedgerEntry } from "@/lib/types";

function entry(over: Partial<LedgerEntry>): LedgerEntry {
  return {
    id: over.id ?? "e-" + Math.random().toString(36).slice(2, 8),
    entry_type: "runtime",
    actor: over.actor ?? { kind: "agent", id: "a" },
    decision: over.decision ?? "d",
    rationale: "",
    phi_class: over.phi_class ?? "none",
    cost_usd: 0,
    model_used: "",
    bundle_refs: [],
    created_at: "2026-07-12T00:00:00Z",
    ...over,
  } as LedgerEntry;
}

describe("buildRunFlow", () => {
  it("scopes to one run and buckets decisions by ambiguity_class when stage is null", () => {
    const g = buildRunFlow(
      [
        entry({ id: "d1", run_id: "r1", ambiguity_class: "phi-classification" }),
        entry({ id: "d2", run_id: "r1", ambiguity_class: "auth-policy" }),
        entry({ id: "other", run_id: "r2", ambiguity_class: "phi-classification" }),
      ],
      "r1",
    );
    expect(g.runId).toBe("r1");
    expect(g.stats.decisions).toBe(2); // r2 excluded
    // two class-bucket spine nodes
    expect(g.nodes.filter((n) => n.kind === "class")).toHaveLength(2);
    // each decision leaf attached to its bucket
    expect(g.edges.filter((e) => e.kind === "in_run")).toHaveLength(2);
  });

  it("orders real pipeline stages by canonical rank (assessor before codegen)", () => {
    const g = buildRunFlow(
      [
        entry({ id: "c", run_id: "r1", stage: "codegen" }),
        entry({ id: "a", run_id: "r1", stage: "assessor" }),
      ],
      "r1",
    );
    const spine = g.nodes.filter((n) => n.kind === "class").map((n) => n.label);
    expect(spine.indexOf("assessor")).toBeLessThan(spine.indexOf("codegen"));
    // spine connected in order
    expect(g.edges.filter((e) => e.kind === "of_class")).toHaveLength(1);
  });

  it("marks a flagged decision in the run", () => {
    const g = buildRunFlow(
      [
        entry({ id: "bad", run_id: "r1", ambiguity_class: "data-retention" }),
        entry({ id: "flag", runtime_kind: "decision_flagged", references_entry_id: "bad", run_id: "teach", actor: { kind: "human", id: "x" } }),
      ],
      "r1",
    );
    expect(g.nodes.find((n) => n.id === "bad")!.flagged).toBe(true);
    expect(g.stats.flagged).toBe(1);
  });

  it("runIdsFrom returns distinct decision run ids, teaching runs excluded", () => {
    const ids = runIdsFrom([
      entry({ run_id: "meridian-run-0001", ambiguity_class: "x" }),
      entry({ run_id: "meridian-run-0002", ambiguity_class: "y" }),
      entry({ run_id: "meridian-run-0001", ambiguity_class: "z" }),
      entry({ run_id: "meridian-teaching", runtime_kind: "feedback_thumbs", feedback_kind: "thumbs_up", references_entry_id: "x" }),
    ]);
    expect(ids).toEqual(["meridian-run-0002", "meridian-run-0001"]);
  });
});
