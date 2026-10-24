import { describe, it, expect } from "vitest";
import { decidedBy, dailyTimeline, classBreakdown } from "./decision-signal";
import type { LedgerEntry } from "./types";

const e = (over: Partial<LedgerEntry>): LedgerEntry =>
  ({
    id: Math.random().toString(36).slice(2), entry_type: "runtime",
    actor: { kind: "agent", id: "x" }, decision: "", rationale: "", phi_class: "none",
    cost_usd: 0, model_used: "", bundle_refs: [], created_at: "2026-08-01T10:00:00Z", ...over,
  }) as LedgerEntry;

describe("decision signal", () => {
  it("trusts confidence_source over a normalizer-defaulted actor.kind", () => {
    // live row shape: no actor object, the UI normalizer defaulted kind=agent
    expect(decidedBy(e({ confidence_source: "human", actor: { kind: "agent", id: "unknown" } }))).toBe("human");
    expect(decidedBy(e({ confidence_source: "autopilot" }))).toBe("agent");
    expect(decidedBy(e({ actor: { kind: "human", id: "h" } }))).toBe("human");
  });

  it("timeline spans only the data and keeps real gaps as zeros", () => {
    const t = dailyTimeline([
      e({ created_at: "2026-08-01T01:00:00Z", confidence_source: "human" }),
      e({ created_at: "2026-08-03T01:00:00Z", confidence_source: "autopilot" }),
      e({ created_at: "2026-08-03T02:00:00Z", runtime_kind: "feedback_thumbs" }),
    ]);
    expect(t.map((b) => b.day)).toEqual(["2026-08-01", "2026-08-02", "2026-08-03"]);
    expect(t[1]).toMatchObject({ human: 0, agent: 0 });
    expect(t[2]).toMatchObject({ agent: 1, signals: 1 });
  });

  it("class breakdown excludes teaching signals and counts unclassified", () => {
    const r = classBreakdown([
      e({ ambiguity_class: "phi", confidence_source: "autopilot" }),
      e({ ambiguity_class: "phi", confidence_source: "human" }),
      e({ ambiguity_class: undefined }),
      e({ runtime_kind: "feedback_thumbs" }),
    ]);
    expect(r.rows[0]).toMatchObject({ klass: "phi", total: 2, autonomy: 0.5 });
    expect(r.unclassified).toBe(1);
  });
});
