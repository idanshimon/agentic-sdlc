import { describe, it, expect } from "vitest";
import { buildGovernanceNetwork } from "./build-graph";
import type { LedgerEntry } from "@/lib/types";

// Minimal factory — only the fields the graph builder reads.
function entry(over: Partial<LedgerEntry>): LedgerEntry {
  return {
    id: over.id ?? "e-" + Math.random().toString(36).slice(2, 8),
    entry_type: "runtime",
    actor: over.actor ?? { kind: "agent", id: "agent-1" },
    decision: over.decision ?? "",
    rationale: "",
    phi_class: over.phi_class ?? "none",
    cost_usd: 0,
    model_used: "",
    bundle_refs: over.bundle_refs ?? [],
    created_at: over.created_at ?? "2026-07-12T00:00:00Z",
    ...over,
  } as LedgerEntry;
}

describe("buildGovernanceNetwork", () => {
  it("creates a decision node with a readable label and click-through entryId", () => {
    const g = buildGovernanceNetwork([
      entry({ id: "d1", decision: "Use FHIR R4 for the alert payload", run_id: "run-abc123ef" }),
    ]);
    const d = g.nodes.find((n) => n.id === "d1")!;
    expect(d.kind).toBe("decision");
    expect(d.label).toContain("FHIR R4");
    expect(d.entryId).toBe("d1"); // drill-down contract
  });

  it("falls back to ambiguity_class then a phrase, never emits empty label", () => {
    const g1 = buildGovernanceNetwork([entry({ id: "d1", decision: "", ambiguity_class: "phi-classification" })]);
    expect(g1.nodes[0].label).toBe("(phi-classification)");
    const g2 = buildGovernanceNetwork([entry({ id: "d2", decision: "", ambiguity_class: undefined })]);
    expect(g2.nodes[0].label).toBe("(no decision text)");
  });

  it("links a decision to its run, class, and each bundle ref (hubs)", () => {
    const g = buildGovernanceNetwork([
      entry({ id: "d1", run_id: "r1", ambiguity_class: "auth-policy", bundle_refs: ["security/v0.1.0/PHI-001", "security/v0.1.0/AUTH-002"] }),
    ]);
    expect(g.edges.filter((e) => e.kind === "in_run")).toHaveLength(1);
    expect(g.edges.filter((e) => e.kind === "of_class")).toHaveLength(1);
    expect(g.edges.filter((e) => e.kind === "grounded_in")).toHaveLength(2);
    // bundle is a hub: two decisions citing the same rule share one bundle node
    const g2 = buildGovernanceNetwork([
      entry({ id: "d1", bundle_refs: ["security/v0.1.0/PHI-001"] }),
      entry({ id: "d2", bundle_refs: ["security/v0.1.0/PHI-001"] }),
    ]);
    expect(g2.nodes.filter((n) => n.kind === "bundle")).toHaveLength(1);
    expect(g2.nodes.find((n) => n.kind === "bundle")!.degree).toBe(2);
  });

  it("draws a reuse edge (the learning loop) from precedent_refs and precedent_id", () => {
    const g = buildGovernanceNetwork([
      entry({ id: "human-swap", decision: "human wrote this", actor: { kind: "human", id: "idan" } }),
      entry({ id: "auto-1", decision: "autopilot reused it", precedent_refs: ["human-swap"] }),
      entry({ id: "auto-2", decision: "autopilot reused it again", precedent_id: "human-swap" }),
    ]);
    const reuse = g.edges.filter((e) => e.kind === "reuses");
    expect(reuse).toHaveLength(2);
    expect(reuse.every((e) => e.target === "human-swap")).toBe(true);
    expect(g.stats.reuseEdges).toBe(2);
  });

  it("ignores a reuse edge whose precedent target isn't in the loaded window", () => {
    const g = buildGovernanceNetwork([entry({ id: "auto-1", precedent_id: "not-loaded" })]);
    expect(g.edges.filter((e) => e.kind === "reuses")).toHaveLength(0);
  });

  it("renders a teaching signal as a plain node and links it to the decision it acts on; flags glow", () => {
    const g = buildGovernanceNetwork([
      entry({ id: "d1", decision: "auto-resolved identifier format" }),
      entry({ id: "t1", runtime_kind: "decision_flagged", references_entry_id: "d1", actor: { kind: "human", id: "idan" } }),
    ]);
    const t = g.nodes.find((n) => n.id === "t1")!;
    expect(t.kind).toBe("teaching");
    expect(t.label).toContain("flagged");
    expect(g.edges.filter((e) => e.kind === "teaches")).toHaveLength(1);
    // the flagged decision glows
    expect(g.nodes.find((n) => n.id === "d1")!.flagged).toBe(true);
    expect(g.stats.flagged).toBe(1);
  });

  it("chains same-slot decisions into a cluster (not a full mesh)", () => {
    const g = buildGovernanceNetwork([
      entry({ id: "s1", slot_value_hash: "abc", created_at: "2026-07-12T01:00:00Z" }),
      entry({ id: "s2", slot_value_hash: "abc", created_at: "2026-07-12T02:00:00Z" }),
      entry({ id: "s3", slot_value_hash: "abc", created_at: "2026-07-12T03:00:00Z" }),
    ]);
    // 3 nodes in a slot → 2 chain edges, not 3 (mesh would be 3)
    expect(g.edges.filter((e) => e.kind === "same_slot")).toHaveLength(2);
  });

  it("counts teaching signals separately from decisions in stats", () => {
    const g = buildGovernanceNetwork([
      entry({ id: "d1", decision: "x" }),
      entry({ id: "d2", decision: "y" }),
      entry({ id: "t1", runtime_kind: "feedback_thumbs", feedback_kind: "thumbs_up", references_entry_id: "d1" }),
    ]);
    expect(g.stats.decisions).toBe(2);
    expect(g.stats.teachingSignals).toBe(1);
  });
});
