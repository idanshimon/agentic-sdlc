import { describe, it, expect } from "vitest";
import { bandFor, groupRuns, isStalled, isRecentFailure, BAND_ORDER } from "./runs-triage";
import type { RunState } from "@/lib/types";
import { STALL_THRESHOLD_MS, FAILURE_WINDOW_MS } from "@/lib/attention";

const NOW = Date.parse("2026-07-26T12:00:00Z");
const iso = (msAgo: number) => new Date(NOW - msAgo).toISOString();

function run(over: Partial<RunState>): RunState {
  return {
    run_id: "r1",
    team_id: "team-cardiology",
    mode: "auto",
    status: "running",
    created_at: iso(60_000),
    updated_at: iso(60_000),
    events: [],
    ...over,
  } as RunState;
}

describe("bandFor", () => {
  it("routes gate-blocked and paused runs to needs_you", () => {
    expect(bandFor(run({ status: "awaiting_gate" }), NOW)).toBe("needs_you");
    expect(bandFor(run({ status: "paused" }), NOW)).toBe("needs_you");
  });

  it("routes failed runs to failed regardless of age", () => {
    expect(bandFor(run({ status: "failed", updated_at: iso(9e8) }), NOW)).toBe("failed");
  });

  it("routes running and queued to in-flight", () => {
    expect(bandFor(run({ status: "running" }), NOW)).toBe("running");
    expect(bandFor(run({ status: "queued" }), NOW)).toBe("running");
  });

  it("routes completed and cancelled to done", () => {
    expect(bandFor(run({ status: "completed" }), NOW)).toBe("done");
    expect(bandFor(run({ status: "cancelled" }), NOW)).toBe("done");
  });
});

describe("groupRuns", () => {
  it("orders bands needs_you → failed → running → done", () => {
    const groups = groupRuns(
      [
        run({ run_id: "d", status: "completed" }),
        run({ run_id: "f", status: "failed" }),
        run({ run_id: "r", status: "running" }),
        run({ run_id: "n", status: "awaiting_gate" }),
      ],
      NOW,
    );
    expect(groups.map((g) => g.band)).toEqual(BAND_ORDER);
  });

  it("sorts newest-first inside a band", () => {
    const groups = groupRuns(
      [
        run({ run_id: "old", status: "failed", updated_at: iso(600_000) }),
        run({ run_id: "new", status: "failed", updated_at: iso(1_000) }),
      ],
      NOW,
    );
    expect(groups[0].runs.map((r) => r.run_id)).toEqual(["new", "old"]);
  });

  it("drops empty bands rather than rendering blank sections", () => {
    const groups = groupRuns([run({ status: "completed" })], NOW);
    expect(groups).toHaveLength(1);
    expect(groups[0].band).toBe("done");
  });

  it("surfaces the gate-blocked run FIRST even when failures dominate the list", () => {
    const many = Array.from({ length: 24 }, (_, i) =>
      run({ run_id: `f${i}`, status: "failed", updated_at: iso(1000 * i) }),
    );
    const groups = groupRuns([...many, run({ run_id: "gate", status: "awaiting_gate" })], NOW);
    expect(groups[0].band).toBe("needs_you");
    expect(groups[0].runs[0].run_id).toBe("gate");
  });

  it("handles an empty list without throwing", () => {
    expect(groupRuns([], NOW)).toEqual([]);
  });
});

describe("isStalled", () => {
  it("flags a running run past the stall threshold", () => {
    expect(isStalled(run({ status: "running", updated_at: iso(STALL_THRESHOLD_MS + 1000) }), NOW)).toBe(true);
  });
  it("leaves a healthy running run alone", () => {
    expect(isStalled(run({ status: "running", updated_at: iso(5_000) }), NOW)).toBe(false);
  });
  it("never flags a non-running run", () => {
    expect(isStalled(run({ status: "failed", updated_at: iso(9e8) }), NOW)).toBe(false);
  });
});

describe("isRecentFailure", () => {
  it("is true inside the alert window and false outside it", () => {
    expect(isRecentFailure(run({ status: "failed", updated_at: iso(1000) }), NOW)).toBe(true);
    expect(
      isRecentFailure(run({ status: "failed", updated_at: iso(FAILURE_WINDOW_MS + 1000) }), NOW),
    ).toBe(false);
  });
});
