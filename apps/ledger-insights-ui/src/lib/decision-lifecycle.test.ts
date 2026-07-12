import { describe, expect, it } from "vitest";
import { projectDecisionLifecycle } from "./decision-lifecycle";
import type { LedgerEntry } from "./types";

const base: LedgerEntry = {
  id: "d1", entry_type: "runtime", actor: { kind: "human", id: "u" },
  decision: "x", rationale: "r", phi_class: "none", cost_usd: 0,
  model_used: "", bundle_refs: [], created_at: "2026-01-01",
};

it("does not invent missing lifecycle evidence", () => {
  const rows = projectDecisionLifecycle([{ ...base, decision_kind: "accept" }]);
  expect(rows[0].state).toBe("resolved");
  expect(rows[0].missing).toEqual(["proposed", "required"]);
  expect(rows[0].evidence.applied).toBeUndefined();
});

describe("terminal lifecycle evidence", () => {
  it("projects verified only from converged evidence", () => {
    const rows = projectDecisionLifecycle([
      { ...base, decision_kind: "accept" },
      { ...base, id: "v1", references_entry_id: "d1", runtime_kind: "loop_converged", created_at: "2026-01-02" },
    ]);
    expect(rows[0].state).toBe("verified");
    expect(rows[0].missing).toContain("applied");
  });
});
