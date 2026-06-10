/**
 * Tests for the economics aggregator. Pure-function tests; no React.
 *
 * Anti-temptation note (per AGENTS.md "behavior contracts over snapshots"):
 * Tests assert RELATIONSHIPS between fields, not literal numbers. If we add
 * a new entry kind tomorrow that bumps total_decisions, we don't want every
 * test to fail.
 */
import { describe, it, expect } from "vitest";
import { summarize, summarizeByTeam, trendByDay, FRESH_LLM_FALLBACK_USD } from "./index";
import type { LedgerEntry } from "@/lib/types";

const baseEntry = (over: Partial<LedgerEntry> & { team_id?: string; created_at?: string } = {}): LedgerEntry => ({
  id: "test-id",
  entry_type: "runtime",
  actor: { kind: "agent", id: "orchestrator" },
  decision: "test",
  rationale: "",
  cost_usd: 0,
  model_used: "",
  bundle_refs: [],
  precedent_refs: [],
  phi_class: "none",
  created_at: "2026-06-10T00:00:00Z",
  ...over,
} as LedgerEntry);

describe("economics.summarize", () => {
  it("empty input returns all-zero summary", () => {
    const r = summarize([]);
    expect(r.total_decisions).toBe(0);
    expect(r.estimated_savings_usd).toBe(0);
    expect(r.novel_cost_is_estimate).toBe(false);
  });

  it("single novel decision: no precedent, no savings", () => {
    const r = summarize([baseEntry({ cost_usd: 0.30 })]);
    expect(r.total_decisions).toBe(1);
    expect(r.precedent_hits).toBe(0);
    expect(r.novel_decisions).toBe(1);
    expect(r.precedent_hit_rate).toBe(0);
    expect(r.estimated_savings_usd).toBe(0);
    expect(r.avg_novel_cost_usd).toBeCloseTo(0.30);
  });

  it("precedent hits priced against measured novel avg", () => {
    const entries = [
      baseEntry({ cost_usd: 0.40 }), // novel
      baseEntry({ cost_usd: 0.20 }), // novel
      baseEntry({ cost_usd: 0.005, precedent_refs: ["x"] }), // precedent
      baseEntry({ cost_usd: 0.005, precedent_refs: ["y"] }), // precedent
    ];
    const r = summarize(entries);
    expect(r.total_decisions).toBe(4);
    expect(r.precedent_hits).toBe(2);
    expect(r.novel_decisions).toBe(2);
    expect(r.avg_novel_cost_usd).toBeCloseTo(0.30); // (0.40 + 0.20) / 2
    // Counterfactual: 2 precedent hits * $0.30 each = $0.60.
    // Actual precedent cost: $0.005 + $0.005 = $0.01.
    // Saved: $0.59.
    expect(r.estimated_savings_usd).toBeCloseTo(0.59);
    expect(r.novel_cost_is_estimate).toBe(false);
  });

  it("all-precedent: novel cost is fallback, savings flagged as estimate", () => {
    const entries = [
      baseEntry({ cost_usd: 0.005, precedent_refs: ["x"] }),
      baseEntry({ cost_usd: 0.005, precedent_refs: ["y"] }),
    ];
    const r = summarize(entries);
    expect(r.novel_decisions).toBe(0);
    expect(r.novel_cost_is_estimate).toBe(true);
    expect(r.avg_novel_cost_usd).toBe(FRESH_LLM_FALLBACK_USD);
    // Savings still computable: 2 * $0.30 - $0.01 = $0.59
    expect(r.estimated_savings_usd).toBeCloseTo(0.59);
  });

  it("autonomy: human actor counts as gated", () => {
    const entries = [
      baseEntry({ actor: { kind: "agent", id: "orchestrator" } }),
      baseEntry({ actor: { kind: "agent", id: "orchestrator" } }),
      baseEntry({ actor: { kind: "human", id: "kapil@hca.com" } }),
    ];
    const r = summarize(entries);
    expect(r.agent_driven).toBe(2);
    expect(r.human_gated).toBe(1);
    expect(r.autonomy_ratio).toBeCloseTo(2 / 3);
  });

  it("autonomy: plan_proposed counts as human-gated even with agent actor", () => {
    const entries = [
      baseEntry({ runtime_kind: "stage_decision" }),
      baseEntry({ runtime_kind: "plan_proposed" }),
    ];
    const r = summarize(entries);
    expect(r.agent_driven).toBe(1);
    expect(r.human_gated).toBe(1);
  });

  it("savings never negative even when precedent cost > counterfactual", () => {
    // Pathological: precedent costs MORE than novel avg. Should clamp at 0.
    const entries = [
      baseEntry({ cost_usd: 0.01 }), // novel cheap
      baseEntry({ cost_usd: 0.50, precedent_refs: ["x"] }), // expensive precedent
    ];
    const r = summarize(entries);
    expect(r.estimated_savings_usd).toBe(0);
  });
});

describe("economics.summarizeByTeam", () => {
  it("groups by team_id, sorted by volume desc", () => {
    const entries = [
      baseEntry({ team_id: "cardiology" }),
      baseEntry({ team_id: "cardiology" }),
      baseEntry({ team_id: "pharmacy" }),
      baseEntry({ team_id: "cardiology" }),
    ];
    const r = summarizeByTeam(entries);
    expect(r.length).toBe(2);
    expect(r[0].team_id).toBe("cardiology");
    expect(r[0].total_decisions).toBe(3);
    expect(r[1].team_id).toBe("pharmacy");
    expect(r[1].total_decisions).toBe(1);
  });

  it("missing team_id falls back to 'unknown'", () => {
    const r = summarizeByTeam([baseEntry()]);
    expect(r[0].team_id).toBe("unknown");
  });
});

describe("economics.trendByDay", () => {
  it("buckets by date prefix", () => {
    const entries = [
      baseEntry({ created_at: "2026-06-10T08:00:00Z", cost_usd: 0.10 }),
      baseEntry({ created_at: "2026-06-10T16:00:00Z", cost_usd: 0.20, precedent_refs: ["x"] }),
      baseEntry({ created_at: "2026-06-11T09:00:00Z", cost_usd: 0.05 }),
    ];
    const t = trendByDay(entries);
    expect(t.length).toBe(2);
    expect(t[0].bucket).toBe("2026-06-10");
    expect(t[0].decisions).toBe(2);
    expect(t[0].precedent_hits).toBe(1);
    expect(t[0].cost_usd).toBeCloseTo(0.30);
    expect(t[1].bucket).toBe("2026-06-11");
    expect(t[1].decisions).toBe(1);
  });

  it("entries without created_at are dropped", () => {
    const entries = [
      baseEntry({ created_at: undefined as unknown as string }),
      baseEntry({ created_at: "2026-06-10T08:00:00Z" }),
    ];
    const t = trendByDay(entries);
    expect(t.length).toBe(1);
  });
});
