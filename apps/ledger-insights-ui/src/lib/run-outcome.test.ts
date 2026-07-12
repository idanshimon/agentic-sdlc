import { describe, expect, it } from "vitest";
import { classifyRunOutcome } from "./run-outcome";
import type { RunState, StageEvent } from "./types";

function run(status: RunState["status"], events: StageEvent[]): RunState {
  return {
    run_id: "r1",
    team_id: "team-demo",
    mode: "guided",
    status,
    current_stage: "review_scan",
    created_at: "2026-07-11T00:00:00Z",
    updated_at: "2026-07-11T00:01:00Z",
    events,
  };
}

describe("classifyRunOutcome", () => {
  it("uses the latest failed event and surfaces policy blocker evidence", () => {
    const outcome = classifyRunOutcome(run("failed", [{
      stage: "review_scan",
      status: "failed",
      message: "Policy gate FAILED",
      payload: { blockers: [{ rule: "security/v1/SEC-1", detail: "secret found" }] },
    }]));

    expect(outcome?.kind).toBe("failed");
    expect(outcome?.stage).toBe("review_scan");
    expect(outcome?.reason).toBe("Policy gate FAILED");
    expect(outcome?.action).toBe("Inspect blockers and remediate");
    expect(outcome?.evidence).toEqual(["security/v1/SEC-1: secret found"]);
  });

  it("does not invent details when a failed run has no failed event", () => {
    const outcome = classifyRunOutcome(run("failed", []));
    expect(outcome?.stage).toBeUndefined();
    expect(outcome?.reason).toBe("Failure details are unavailable.");
  });

  it("classifies undelivered artifacts as action required rather than success", () => {
    const outcome = classifyRunOutcome(run("completed", [{
      stage: "deliver",
      status: "completed",
      message: "Artifacts ready",
      payload: { delivery_status: "not_delivered", delivery_reason: "token missing" },
    }]));
    expect(outcome?.kind).toBe("action_required");
    expect(outcome?.reason).toContain("token missing");
    expect(outcome?.action).toBe("Configure delivery and retry");
  });
});
