import { describe, it, expect } from "vitest";
import { parseAutonomyRef, projectAutonomy } from "./autonomy-governance";
import type { LedgerEntry } from "./types";

function e(over: Partial<LedgerEntry>): LedgerEntry {
  return {
    id: "x",
    entry_type: "runtime",
    actor: { kind: "agent", id: "a" },
    decision: "",
    rationale: "",
    phi_class: "none",
    cost_usd: 0,
    model_used: "",
    bundle_refs: [],
    created_at: "2026-07-20T10:00:00Z",
    ...over,
  } as LedgerEntry;
}

describe("parseAutonomyRef", () => {
  it("parses a mode/autopilot ref into its parts", () => {
    const r = parseAutonomyRef("autonomy/mode/bootstrap/scope-resolution/autopilot:autopilot-mode");
    expect(r).toMatchObject({
      family: "mode",
      scope: "bootstrap",
      ambiguityClass: "scope-resolution",
      outcome: "autopilot",
      ruleId: "autopilot-mode",
    });
  });

  it("parses an invariant/gate ref (class sits one level higher)", () => {
    const r = parseAutonomyRef("autonomy/invariant/phi-classification/gate:phi-auth-hard-lock");
    expect(r).toMatchObject({
      family: "invariant",
      ambiguityClass: "phi-classification",
      outcome: "gate",
      ruleId: "phi-auth-hard-lock",
    });
  });

  it("degrades gracefully on an unknown shape instead of throwing", () => {
    const r = parseAutonomyRef("something/else/entirely");
    expect(r?.family).toBe("other");
    expect(r?.outcome).toBe("other");
  });

  it("returns null for empty input", () => {
    expect(parseAutonomyRef(undefined)).toBeNull();
    expect(parseAutonomyRef("")).toBeNull();
  });
});

describe("projectAutonomy", () => {
  const entries = [
    ...Array.from({ length: 3 }, (_, i) =>
      e({
        id: `auto-${i}`,
        run_id: `run-${i}`,
        confidence_source: "autopilot",
        autonomy_ref: "autonomy/mode/bootstrap/scope-resolution/autopilot:autopilot-mode",
      }),
    ),
    ...Array.from({ length: 2 }, (_, i) =>
      e({
        id: `inv-${i}`,
        run_id: `run-${i}`,
        confidence_source: "human",
        autonomy_ref: "autonomy/invariant/phi-classification/gate:phi-auth-hard-lock",
      }),
    ),
    e({ id: "ungoverned", autonomy_ref: undefined }),
  ];

  it("groups decisions by the rule that governed them", () => {
    const s = projectAutonomy(entries);
    expect(s.rules).toHaveLength(2);
    expect(s.totalGoverned).toBe(5);
  });

  it("ignores entries with no autonomy_ref rather than bucketing them as unknown", () => {
    const s = projectAutonomy(entries);
    expect(s.rules.every((r) => r.ref)).toBe(true);
    expect(s.totalGoverned).toBe(5);
  });

  it("puts invariants first — hard constraints lead", () => {
    expect(projectAutonomy(entries).rules[0].family).toBe("invariant");
  });

  it("computes autonomy share from autopilot vs gated decisions", () => {
    const s = projectAutonomy(entries);
    expect(s.autopilotCount).toBe(3);
    expect(s.gatedCount).toBe(2);
    expect(s.autonomyPct).toBe(60);
  });

  it("explains a hard lock in plain language, not rule syntax", () => {
    const inv = projectAutonomy(entries).rules.find((r) => r.family === "invariant")!;
    expect(inv.explanation).toContain("Hard lock");
    expect(inv.explanation).toContain("phi-classification");
    expect(inv.explanation).not.toContain("autonomy/");
  });

  it("explains autopilot with the real count of agent decisions", () => {
    const auto = projectAutonomy(entries).rules.find((r) => r.outcome === "autopilot")!;
    expect(auto.explanation).toContain("trusted");
    expect(auto.explanation).toContain("3 times");
  });

  it("counts distinct runs, not raw decisions", () => {
    const auto = projectAutonomy(entries).rules.find((r) => r.outcome === "autopilot")!;
    expect(auto.decisionCount).toBe(3);
    expect(auto.runCount).toBe(3);
  });

  it("returns an empty, non-throwing summary for no data", () => {
    const s = projectAutonomy([]);
    expect(s.rules).toEqual([]);
    expect(s.autonomyPct).toBe(0);
  });
});
