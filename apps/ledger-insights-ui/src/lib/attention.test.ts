import { describe, it, expect } from "vitest";
import {
  buildAttentionQueue,
  attentionFromRuns,
  attentionFromDecisions,
  attentionCounts,
  ago,
  STALL_THRESHOLD_MS,
  FAILURE_WINDOW_MS,
} from "./attention";
import type { RunState, LedgerEntry } from "./types";

const NOW = Date.parse("2026-07-26T12:00:00Z");
const iso = (msAgo: number) => new Date(NOW - msAgo).toISOString();

function run(over: Partial<RunState>): RunState {
  return {
    run_id: "run-abcdef123456",
    team_id: "team-cardiology",
    mode: "auto",
    status: "running",
    created_at: iso(60_000),
    updated_at: iso(60_000),
    events: [],
    ...over,
  } as RunState;
}

function entry(over: Partial<LedgerEntry>): LedgerEntry {
  return {
    id: "led-1",
    entry_type: "runtime",
    actor: { kind: "human", id: "a@b.com" },
    decision: "",
    rationale: "",
    phi_class: "none",
    cost_usd: 0,
    model_used: "",
    bundle_refs: [],
    created_at: iso(60_000),
    ...over,
  } as LedgerEntry;
}

describe("attentionFromRuns", () => {
  it("surfaces an awaiting_gate run as blocked, naming the gate stage", () => {
    const items = attentionFromRuns(
      [run({ status: "awaiting_gate", pending_gate: { stage: "resolver" } })],
      NOW,
    );
    expect(items).toHaveLength(1);
    expect(items[0].kind).toBe("blocked");
    expect(items[0].title).toContain("resolver");
    expect(items[0].href).toBe("/runs/run-abcdef123456");
  });

  it("treats paused the same as awaiting_gate — both stop progress", () => {
    const items = attentionFromRuns([run({ status: "paused" })], NOW);
    expect(items[0].kind).toBe("blocked");
  });

  it("surfaces a recent failure with its real recorded reason", () => {
    const items = attentionFromRuns(
      [
        run({
          status: "failed",
          updated_at: iso(60_000),
          events: [
            { stage: "codegen", status: "failed", message: "Delivery blocked — synthetic provider output" },
          ],
        }),
      ],
      NOW,
    );
    expect(items[0].kind).toBe("failed");
    expect(items[0].detail).toContain("synthetic provider output");
  });

  it("does NOT invent a failure reason when the run recorded none", () => {
    const items = attentionFromRuns(
      [run({ status: "failed", current_stage: "review_scan", events: [] })],
      NOW,
    );
    expect(items[0].detail).toContain("review_scan");
    expect(items[0].detail).not.toContain("undefined");
  });

  it("drops failures older than the 24h window — history is not an alert", () => {
    const stale = iso(FAILURE_WINDOW_MS + 60_000);
    const items = attentionFromRuns(
      [run({ status: "failed", updated_at: stale, created_at: stale })],
      NOW,
    );
    expect(items).toHaveLength(0);
  });

  it("flags a long-running run as stalled", () => {
    const items = attentionFromRuns(
      [run({ status: "running", updated_at: iso(STALL_THRESHOLD_MS + 60_000) })],
      NOW,
    );
    expect(items[0].kind).toBe("stalled");
  });

  it("leaves a healthy in-flight run alone", () => {
    const items = attentionFromRuns([run({ status: "running", updated_at: iso(5000) })], NOW);
    expect(items).toHaveLength(0);
  });

  it("leaves completed runs alone", () => {
    expect(attentionFromRuns([run({ status: "completed" })], NOW)).toHaveLength(0);
  });

  it("survives undefined input and rows with no run_id", () => {
    expect(attentionFromRuns(undefined, NOW)).toEqual([]);
    expect(attentionFromRuns([run({ run_id: "" })], NOW)).toEqual([]);
  });
});

describe("attentionFromDecisions", () => {
  it("surfaces a flagged decision and deep-links to the decision it references", () => {
    const items = attentionFromDecisions([
      entry({
        id: "signal-1",
        runtime_kind: "decision_flagged",
        decision: "Classify MRN as PHI",
        references_entry_id: "orig-99",
      }),
    ]);
    expect(items[0].kind).toBe("flagged");
    expect(items[0].title).toContain("Classify MRN as PHI");
    expect(items[0].href).toBe("/decisions#decision-orig-99");
  });

  it("surfaces a paused class and explains the consequence in plain language", () => {
    const items = attentionFromDecisions([
      entry({ id: "s2", runtime_kind: "class_paused", paused_class: "auth-policy" }),
    ]);
    expect(items[0].title).toContain("auth-policy");
    expect(items[0].detail).toContain("waits for a human");
  });

  it("never emits a literal undefined when decision and class are both missing", () => {
    const items = attentionFromDecisions([entry({ id: "s3", runtime_kind: "decision_flagged" })]);
    expect(items[0].title).not.toContain("undefined");
    expect(items[0].title).toContain("a decision");
  });

  it("ignores ordinary stage decisions — they are not attention items", () => {
    expect(
      attentionFromDecisions([entry({ id: "s4", runtime_kind: "stage_decision" })]),
    ).toHaveLength(0);
  });
});

describe("buildAttentionQueue", () => {
  it("ranks blocked above failed above flagged above stalled", () => {
    const items = buildAttentionQueue(
      [
        run({ run_id: "r-stall", status: "running", updated_at: iso(STALL_THRESHOLD_MS + 1000) }),
        run({ run_id: "r-fail", status: "failed" }),
        run({ run_id: "r-block", status: "awaiting_gate" }),
      ],
      [entry({ id: "s", runtime_kind: "decision_flagged", decision: "x" })],
      { now: NOW },
    );
    expect(items.map((i) => i.kind)).toEqual(["blocked", "failed", "flagged", "stalled"]);
  });

  it("orders newest-first within a bucket", () => {
    const items = buildAttentionQueue(
      [
        run({
          run_id: "r-old",
          status: "awaiting_gate",
          pending_gate: { stage: "design_review" },
          updated_at: iso(600_000),
        }),
        run({
          run_id: "r-new",
          status: "awaiting_gate",
          pending_gate: { stage: "resolver" },
          updated_at: iso(1_000),
        }),
      ],
      [],
      { now: NOW },
    );
    expect(items[0].id).toBe("blocked-r-new");
  });

  it("caps the fold at the requested limit", () => {
    // Distinct stages so nothing collapses — this test is about the cap.
    const stages = ["ingest", "assessor", "resolver", "architect", "codegen", "deliver"];
    const many = stages.map((stage, i) =>
      run({ run_id: `r-${i}`, status: "awaiting_gate", pending_gate: { stage } }),
    );
    expect(buildAttentionQueue(many, [], { limit: 4, now: NOW })).toHaveLength(4);
  });

  it("every item is actionable — non-empty href and action label", () => {
    const items = buildAttentionQueue([run({ status: "awaiting_gate" })], []);
    for (const item of items) {
      expect(item.href).toMatch(/^\//);
      expect(item.action.length).toBeGreaterThan(0);
    }
  });

  it("returns an empty queue when nothing needs a human", () => {
    expect(buildAttentionQueue([run({ status: "completed" })], [])).toEqual([]);
  });
});

describe("attentionCounts", () => {
  it("counts the FULL queue, not the capped or collapsed view", () => {
    const many = Array.from({ length: 9 }, (_, i) =>
      run({ run_id: `r-${i}`, status: "awaiting_gate" }),
    );
    expect(attentionCounts(many, [], NOW).blocked).toBe(9);
  });
});

describe("collapseDuplicates", () => {
  it("collapses N identical blocked runs into ONE counted row", () => {
    const many = Array.from({ length: 6 }, (_, i) =>
      run({
        run_id: `r-${i}`,
        status: "awaiting_gate",
        pending_gate: { stage: "resolver" },
        updated_at: iso(1000 * (i + 1)),
      }),
    );
    const items = buildAttentionQueue(many, [], { now: NOW });
    expect(items).toHaveLength(1);
    expect(items[0].count).toBe(6);
    expect(items[0].title).toBe("6 runs are waiting on your decision at resolver");
    expect(items[0].href).toBe("/runs?view=attention");
  });

  it("does NOT collapse runs blocked at different stages", () => {
    const items = buildAttentionQueue(
      [
        run({ run_id: "a", status: "awaiting_gate", pending_gate: { stage: "resolver" } }),
        run({ run_id: "b", status: "awaiting_gate", pending_gate: { stage: "design_review" } }),
      ],
      [],
      { now: NOW },
    );
    expect(items).toHaveLength(2);
  });

  it("leaves a lone item untouched — no count badge, original href", () => {
    const items = buildAttentionQueue(
      [run({ run_id: "solo", status: "awaiting_gate" })],
      [],
      { now: NOW },
    );
    expect(items[0].count).toBeUndefined();
    expect(items[0].href).toBe("/runs/solo");
  });

  it("reports the oldest member's age so the row is not falsely fresh", () => {
    const items = buildAttentionQueue(
      [
        run({ run_id: "new", status: "awaiting_gate", updated_at: iso(60_000) }),
        run({ run_id: "old", status: "awaiting_gate", updated_at: iso(3 * 86_400_000) }),
      ],
      [],
      { now: NOW },
    );
    expect(items[0].detail).toContain("oldest 3d ago");
  });
});

describe("ago", () => {
  it("renders coarse human durations", () => {
    expect(ago(iso(30_000), NOW)).toBe("just now");
    expect(ago(iso(5 * 60_000), NOW)).toBe("5m ago");
    expect(ago(iso(3 * 3_600_000), NOW)).toBe("3h ago");
    expect(ago(iso(2 * 86_400_000), NOW)).toBe("2d ago");
  });

  it("does not crash on missing or malformed timestamps", () => {
    expect(ago(undefined, NOW)).toBe("unknown");
    expect(ago("not-a-date", NOW)).toBe("unknown");
  });
});
