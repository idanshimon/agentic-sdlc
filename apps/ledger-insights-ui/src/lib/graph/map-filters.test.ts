import { describe, it, expect } from "vitest";
import { applyMapFilters, defaultMapFilters } from "./map-filters";
import { buildGovernanceNetwork } from "./build-graph";
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
    bundle_refs: over.bundle_refs ?? [],
    created_at: "2026-07-12T00:00:00Z",
    ...over,
  } as LedgerEntry;
}

describe("applyMapFilters", () => {
  it("default filters drop structural of_class/in_run edges, keep grounded_in + reuses", () => {
    const g = buildGovernanceNetwork([
      entry({ id: "d1", run_id: "r1", ambiguity_class: "phi-classification", bundle_refs: ["security/v0.1.0/PHI-001"] }),
      entry({ id: "d2", run_id: "r1", precedent_refs: ["d1"] }),
    ]);
    const f = applyMapFilters(g, defaultMapFilters());
    expect(f.edges.some((e) => e.kind === "in_run")).toBe(false);
    expect(f.edges.some((e) => e.kind === "of_class")).toBe(false);
    expect(f.edges.some((e) => e.kind === "grounded_in")).toBe(true);
    expect(f.edges.some((e) => e.kind === "reuses")).toBe(true);
  });

  it("onlyFlagged keeps flagged decision + its neighborhood, drops the rest", () => {
    const g = buildGovernanceNetwork([
      entry({ id: "bad", decision: "wrong call", bundle_refs: ["privacy/v0.1.0/RETAIN-004"] }),
      entry({ id: "unrelated", decision: "fine", bundle_refs: ["architect/v0.1.0/NAMING-001"] }),
      entry({ id: "flag", runtime_kind: "decision_flagged", references_entry_id: "bad", actor: { kind: "human", id: "idan" } }),
    ]);
    const f = applyMapFilters(g, { ...defaultMapFilters(), onlyFlagged: true, edgeKinds: new Set(["grounded_in", "teaches"]) });
    const ids = f.nodes.map((n) => n.id);
    expect(ids).toContain("bad");
    expect(ids).not.toContain("unrelated");
  });

  it("bundle scope keeps only the bundle and what cites it", () => {
    const g = buildGovernanceNetwork([
      entry({ id: "d1", bundle_refs: ["security/v0.1.0/PHI-001"] }),
      entry({ id: "d2", bundle_refs: ["architect/v0.1.0/NAMING-001"] }),
    ]);
    const f = applyMapFilters(g, { ...defaultMapFilters(), bundleId: "bundle:security/v0.1.0/PHI-001" });
    const ids = f.nodes.map((n) => n.id).sort();
    expect(ids).toContain("bundle:security/v0.1.0/PHI-001");
    expect(ids).toContain("d1");
    expect(ids).not.toContain("d2");
  });

  it("node budget caps rendered nodes but always keeps hubs and flagged", () => {
    const many: LedgerEntry[] = [];
    for (let i = 0; i < 40; i++) many.push(entry({ id: `d${i}`, bundle_refs: ["security/v0.1.0/PHI-001"], run_id: "r1" }));
    many.push(entry({ id: "flagged", bundle_refs: ["security/v0.1.0/PHI-001"], run_id: "r1" }));
    many.push(entry({ id: "flag", runtime_kind: "decision_flagged", references_entry_id: "flagged", actor: { kind: "human", id: "x" } }));
    const g = buildGovernanceNetwork(many);
    const f = applyMapFilters(g, { ...defaultMapFilters(), nodeBudget: 20 });
    expect(f.nodes.length).toBeLessThanOrEqual(20);
    // hub (bundle) + flagged decision survive the cull
    expect(f.nodes.some((n) => n.kind === "bundle")).toBe(true);
    expect(f.nodes.some((n) => n.id === "flagged")).toBe(true);
  });
});
