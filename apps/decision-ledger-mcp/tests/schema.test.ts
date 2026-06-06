import { describe, it, expect } from "vitest";
import { RuntimeEntrySchema, LedgerQueryInputSchema } from "../src/schema.js";

describe("RuntimeEntrySchema", () => {
  it("accepts entry with run_id", () => {
    const r = RuntimeEntrySchema.parse({
      team_id: "team-x",
      actor: { kind: "agent", id: "orchestrator" },
      decision: "test",
      run_id: "run-1",
    });
    expect(r.run_id).toBe("run-1");
  });

  it("accepts entry with agent_session_id", () => {
    const r = RuntimeEntrySchema.parse({
      team_id: "team-x",
      actor: { kind: "agent", id: "github-copilot-ide" },
      decision: "test",
      agent_session_id: "sess-1",
    });
    expect(r.agent_session_id).toBe("sess-1");
  });

  it("rejects entry with neither", () => {
    expect(() =>
      RuntimeEntrySchema.parse({
        team_id: "team-x",
        actor: { kind: "agent", id: "x" },
        decision: "test",
      })
    ).toThrow();
  });
});

describe("LedgerQueryInputSchema", () => {
  it("requires team_id", () => {
    expect(() => LedgerQueryInputSchema.parse({})).toThrow();
  });

  it("defaults limit to 25", () => {
    const r = LedgerQueryInputSchema.parse({ team_id: "team-x" });
    expect(r.limit).toBe(25);
  });

  it("rejects limit > 200", () => {
    expect(() => LedgerQueryInputSchema.parse({ team_id: "team-x", limit: 500 })).toThrow();
  });
});
