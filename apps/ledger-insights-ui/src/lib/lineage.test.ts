/**
 * Tests for lineage.ts — the teaching-loop relationship graph reconstruction.
 *
 * Pins the core promise: a human swap + the later autopilot reuses of that
 * ambiguity bucket are correctly classified as taught / reused, and the
 * autonomy-earned metric reflects the loop closing.
 */
import { describe, it, expect } from "vitest";
import { buildLineageIndex, isHumanSwap, isAutopilot, lineageBadge, buildAutonomyBuckets } from "./lineage";
import type { LedgerEntry } from "@/lib/types";

function entry(over: Partial<LedgerEntry> & { id: string }): LedgerEntry {
  return {
    entry_type: "runtime",
    actor: { kind: "agent", id: "orchestrator" },
    decision: "x",
    rationale: "",
    phi_class: "none",
    cost_usd: 0,
    model_used: "",
    bundle_refs: [],
    created_at: "2026-06-21T00:00:00Z",
    ...over,
  };
}

describe("buildLineageIndex — teaching loop", () => {
  it("classifies a human swap as 'taught' and counts later autopilot reuses", () => {
    const entries: LedgerEntry[] = [
      entry({
        id: "swap1",
        slot_value_hash: "H",
        decision_kind: "swap",
        confidence_source: "human",
        actor: { kind: "human", id: "operator@dashboard" },
      }),
      entry({ id: "auto1", slot_value_hash: "H", confidence_source: "autopilot" }),
      entry({ id: "auto2", slot_value_hash: "H", confidence_source: "autopilot" }),
    ];
    const idx = buildLineageIndex(entries);
    expect(idx.byId.get("swap1")!.role).toBe("taught");
    expect(idx.byId.get("swap1")!.reusedByCount).toBe(2);
    expect(idx.byId.get("auto1")!.role).toBe("reused");
    expect(idx.byId.get("auto2")!.role).toBe("reused");
  });

  it("reports autonomy-earned metrics for the KPI strip", () => {
    const entries: LedgerEntry[] = [
      entry({ id: "swap1", slot_value_hash: "H", decision_kind: "swap", confidence_source: "human", actor: { kind: "human", id: "op" } }),
      entry({ id: "auto1", slot_value_hash: "H", confidence_source: "autopilot" }),
      entry({ id: "auto2", slot_value_hash: "H", confidence_source: "autopilot" }),
      entry({ id: "plain1", slot_value_hash: "OTHER", confidence_source: "human", actor: { kind: "human", id: "op" } }),
    ];
    const { metrics } = buildLineageIndex(entries);
    expect(metrics.taughtCount).toBe(1);
    expect(metrics.reusedCount).toBe(2);
    expect(metrics.bucketsTaught).toBe(1);
    // 2 reused of 4 stage decisions = 50%
    expect(metrics.autonomyEarnedPct).toBe(50);
  });

  it("an autopilot decision in a bucket with NO human swap is 'plain', not 'reused'", () => {
    const entries: LedgerEntry[] = [
      entry({ id: "auto1", slot_value_hash: "H", confidence_source: "autopilot" }),
      entry({ id: "auto2", slot_value_hash: "H", confidence_source: "autopilot" }),
    ];
    const idx = buildLineageIndex(entries);
    expect(idx.byId.get("auto1")!.role).toBe("plain");
    expect(idx.metrics.reusedCount).toBe(0);
  });

  it("classifies flagged decisions (teaching signal points at them)", () => {
    const entries: LedgerEntry[] = [
      entry({ id: "dec1", slot_value_hash: "H" }),
      entry({ id: "flag1", runtime_kind: "decision_flagged", references_entry_id: "dec1", actor: { kind: "human", id: "op" } }),
    ];
    const idx = buildLineageIndex(entries);
    expect(idx.byId.get("dec1")!.role).toBe("flagged");
    expect(idx.byId.get("dec1")!.signalCount).toBe(1);
  });

  it("ties a heal chain via heal_id", () => {
    const entries: LedgerEntry[] = [
      entry({ id: "h1", heal_id: "HEAL", runtime_kind: "stage_decision" }),
      entry({ id: "h2", heal_id: "HEAL", runtime_kind: "stage_decision" }),
      entry({ id: "h3", heal_id: "HEAL", runtime_kind: "stage_decision" }),
    ];
    const idx = buildLineageIndex(entries);
    expect(idx.byId.get("h1")!.role).toBe("heal");
    expect(idx.byId.get("h1")!.healChainIds.sort()).toEqual(["h2", "h3"]);
    expect(idx.metrics.healChains).toBe(1);
  });

  it("empty list → zeroed metrics, no throw", () => {
    const idx = buildLineageIndex([]);
    expect(idx.metrics.autonomyEarnedPct).toBe(0);
    expect(idx.byId.size).toBe(0);
  });
});

describe("predicates", () => {
  it("isHumanSwap requires swap + human", () => {
    expect(isHumanSwap(entry({ id: "a", decision_kind: "swap", confidence_source: "human" }))).toBe(true);
    expect(isHumanSwap(entry({ id: "b", decision_kind: "accept", confidence_source: "human" }))).toBe(false);
    expect(isHumanSwap(entry({ id: "c", decision_kind: "swap", confidence_source: "autopilot" }))).toBe(false);
  });

  it("isAutopilot requires autopilot confidence", () => {
    expect(isAutopilot(entry({ id: "a", confidence_source: "autopilot" }))).toBe(true);
    expect(isAutopilot(entry({ id: "b", confidence_source: "human" }))).toBe(false);
  });
});

describe("lineageBadge", () => {
  it("taught + reused shows the reuse count", () => {
    const idx = buildLineageIndex([
      entry({ id: "swap1", slot_value_hash: "H", decision_kind: "swap", confidence_source: "human", actor: { kind: "human", id: "op" } }),
      entry({ id: "auto1", slot_value_hash: "H", confidence_source: "autopilot" }),
    ]);
    const badge = lineageBadge(idx.byId.get("swap1")!);
    expect(badge?.label).toContain("reused 1");
    expect(badge?.tone).toBe("success");
  });

  it("plain entries get no badge", () => {
    const idx = buildLineageIndex([entry({ id: "p1" })]);
    expect(lineageBadge(idx.byId.get("p1")!)).toBeNull();
  });
});

describe("buildAutonomyBuckets — per-bucket teaching detail", () => {
  it("surfaces the taught bucket with class, teacher, resolution, and reuse count", () => {
    const buckets = buildAutonomyBuckets([
      entry({
        id: "swap1", slot_value_hash: "H", ambiguity_class: "sla-binding",
        decision_kind: "swap", confidence_source: "human",
        actor: { kind: "human", id: "chen@stonybrook" },
        decision: "SLA must be 4h not 24h", created_at: "2026-06-20T10:00:00Z",
      }),
      entry({ id: "auto1", slot_value_hash: "H", ambiguity_class: "sla-binding", confidence_source: "autopilot", created_at: "2026-06-21T10:00:00Z" }),
      entry({ id: "auto2", slot_value_hash: "H", ambiguity_class: "sla-binding", confidence_source: "autopilot", created_at: "2026-06-22T10:00:00Z" }),
    ]);
    expect(buckets).toHaveLength(1);
    const b = buckets[0];
    expect(b.ambiguityClass).toBe("sla-binding");
    expect(b.taughtBy).toBe("chen@stonybrook");
    expect(b.resolutionText).toBe("SLA must be 4h not 24h");
    expect(b.reuseCount).toBe(2);
    expect(b.slotKey).toBe("H");
    expect(b.status).toBe("active"); // taught + reused, no flag
  });

  it("marks a bucket 'dormant' when taught but never reused", () => {
    const buckets = buildAutonomyBuckets([
      entry({ id: "swap1", slot_value_hash: "H", ambiguity_class: "naming-convention", decision_kind: "swap", confidence_source: "human", actor: { kind: "human", id: "op" } }),
    ]);
    expect(buckets[0].reuseCount).toBe(0);
    expect(buckets[0].status).toBe("dormant");
  });

  it("sorts most-reused buckets first", () => {
    const buckets = buildAutonomyBuckets([
      entry({ id: "s1", slot_value_hash: "A", ambiguity_class: "sla-binding", decision_kind: "swap", confidence_source: "human", actor: { kind: "human", id: "op" } }),
      entry({ id: "s2", slot_value_hash: "B", ambiguity_class: "scope-resolution", decision_kind: "swap", confidence_source: "human", actor: { kind: "human", id: "op" } }),
      entry({ id: "a1", slot_value_hash: "B", confidence_source: "autopilot" }),
      entry({ id: "a2", slot_value_hash: "B", confidence_source: "autopilot" }),
      entry({ id: "a3", slot_value_hash: "A", confidence_source: "autopilot" }),
    ]);
    expect(buckets[0].slotKey).toBe("B"); // 2 reuses
    expect(buckets[1].slotKey).toBe("A"); // 1 reuse
  });

  it("returns empty when nothing has been taught", () => {
    expect(buildAutonomyBuckets([entry({ id: "p1", confidence_source: "autopilot" })])).toEqual([]);
  });
});
