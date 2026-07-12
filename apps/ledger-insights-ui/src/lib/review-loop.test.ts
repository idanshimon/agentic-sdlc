import { describe, expect, it } from "vitest";
import { projectReviewLoops } from "./review-loop";
import type { LedgerEntry } from "./types";

const base: LedgerEntry = {
  id: "base",
  entry_type: "runtime",
  actor: { kind: "agent", id: "review-loop" },
  created_at: "2026-01-01",
  decision: "",
  rationale: "",
  phi_class: "none",
  cost_usd: 0,
  model_used: "",
  bundle_refs: [],
};

describe("review loop projection", () => {
  it("keeps two PRs in one repo separate by loop_id", () => {
    const entries: LedgerEntry[] = [
      { ...base, id: "1", loop_id: "loop-1", repo: "o/r", pr_number: 1, head_sha: "a", runtime_kind: "loop_converged", disposition: "PASSED_AWAITING_MERGE" },
      { ...base, id: "2", loop_id: "loop-2", repo: "o/r", pr_number: 2, head_sha: "b", runtime_kind: "loop_converged", disposition: "MERGED" },
    ];
    const loops = projectReviewLoops(entries);
    expect(loops).toHaveLength(2);
    expect(loops.map((l) => l.loopId)).toEqual(["loop-1", "loop-2"]);
  });

  it("does not render Tier-B convergence as merged", () => {
    const entry: LedgerEntry = { ...base, id: "1", loop_id: "loop-1", repo: "o/r", pr_number: 1, head_sha: "a", runtime_kind: "loop_converged", disposition: "PASSED_AWAITING_MERGE" };
    const loops = projectReviewLoops([entry]);
    expect(loops[0].terminal).toBe("passed_awaiting_merge");
  });
});
