import { describe, it, expect } from "vitest";
import {
  ringOf, runStage, stageOccupancy, agentActivity, orbitLayout, normalizeStage,
} from "./mission";
import type { RunState, LedgerEntry } from "./types";

const NOW = Date.parse("2026-07-26T12:00:00Z");
const iso = (msAgo: number) => new Date(NOW - msAgo).toISOString();

const run = (over: Partial<RunState>): RunState =>
  ({
    run_id: "run-1", team_id: "team-x", mode: "auto", status: "running",
    created_at: iso(1000), updated_at: iso(1000), events: [], ...over,
  }) as RunState;

const entry = (over: Partial<LedgerEntry>): LedgerEntry =>
  ({
    id: "e1", entry_type: "runtime", actor: { kind: "agent", id: "a" },
    decision: "d", rationale: "", phi_class: "none", cost_usd: 0.01,
    model_used: "gpt-4.1", bundle_refs: [], created_at: iso(1000),
    runtime_kind: "stage_decision", ...over,
  }) as LedgerEntry;

describe("mission projection", () => {
  it("rings by consequence", () => {
    expect(ringOf(run({ status: "awaiting_gate" }))).toBe("blocked");
    expect(ringOf(run({ status: "failed" }))).toBe("failed");
    expect(ringOf(run({ status: "running" }))).toBe("active");
    expect(ringOf(run({ status: "completed" }))).toBe("done");
  });

  it("places a blocked run at its gate stage", () => {
    expect(runStage(run({ status: "awaiting_gate", pending_gate: { stage: "resolver" } }))).toBe("resolver");
    expect(runStage(run({ status: "completed" }))).toBe("deliver");
    expect(normalizeStage("review-scan")).toBe("review_scan");
  });

  it("counts occupancy per stage", () => {
    const occ = stageOccupancy([
      run({ run_id: "a", current_stage: "codegen" }),
      run({ run_id: "b", current_stage: "codegen", status: "failed" }),
    ]);
    const cg = occ.find((o) => o.id === "codegen")!;
    expect(cg.total).toBe(2);
    expect(cg.byRing.failed).toBe(1);
  });

  it("never credits unattributable entries to an agent", () => {
    const res = agentActivity(
      [
        entry({ id: "1", stage: "assessor" }),
        entry({ id: "2", stage: undefined, ambiguity_class: "phi" }),
        entry({ id: "3", stage: "codegen", actor: { kind: "human", id: "h" } }),
        entry({ id: "f", runtime_kind: "decision_flagged", references_entry_id: "1" }),
      ],
      ["assessor", "codegen", "review-scan"],
      { now: NOW },
    );
    expect(res.unattributed).toBe(1);
    expect(res.agents.assessor.decisions).toBe(1);
    expect(res.agents.assessor.flagged).toBe(1);
    expect(res.agents.codegen.human).toBe(1);
    expect(res.agents["review-scan"].decisions).toBe(0);
    expect(res.agents.assessor.spark).toHaveLength(12);
    expect(res.agents.assessor.spark.at(-1)).toBe(1);
  });

  it("attributes from the stage the prompt resolver recorded", () => {
    const live = entry({
      id: "L", stage: undefined, cost_usd: undefined as unknown as number, confidence_source: "autopilot",
      actor: { kind: "human", id: "x" },
      prompt_resolution_path: [{ scope: "team", matched: false, reason: "no published team prompt for team=t stage=assessor" }],
    });
    const res = agentActivity([live], ["assessor"], { now: NOW });
    expect(res.agents.assessor.decisions).toBe(1);
    expect(res.agents.assessor.autonomous).toBe(1);
    expect(res.agents.assessor.costed).toBe(0);
    expect(res.unattributed).toBe(0);
  });

  it("orbit layout is deterministic and puts blocked innermost", () => {
    const radii = { blocked: 120, failed: 180, active: 240, done: 300 };
    const runs = [run({ run_id: "z", status: "awaiting_gate" }), run({ run_id: "y", status: "completed" })];
    const a = orbitLayout(runs, radii);
    const b = orbitLayout([...runs].reverse(), radii);
    const byId = (xs: typeof a) => [...xs].sort((p, q) => p.runId.localeCompare(q.runId));
    expect(byId(a)).toEqual(byId(b));
    expect(a.find((p) => p.runId === "z")!.radius).toBe(120);
  });

  it("stacks a crowded sector into lanes so dots do not overlap", () => {
    const runs = Array.from({ length: 30 }, (_, i) =>
      run({ run_id: `r${String(i).padStart(2, "0")}`, status: "failed", current_stage: "codegen" }));
    const pts = orbitLayout(runs, { blocked: 120, failed: 180, active: 240, done: 300 });
    const xy = pts.map((p) => [p.radius * Math.sin(p.angle), p.radius * Math.cos(p.angle)]);
    let minD = Infinity;
    for (let i = 0; i < xy.length; i++) for (let j = i + 1; j < xy.length; j++)
      minD = Math.min(minD, Math.hypot(xy[i][0] - xy[j][0], xy[i][1] - xy[j][1]));
    expect(new Set(pts.map((p) => p.radius)).size).toBeGreaterThan(1);
    expect(minD).toBeGreaterThan(8);
  });
});
