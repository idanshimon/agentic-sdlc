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
  it("allows omitting team_id (defaults applied at handler layer)", () => {
    // Schema layer: team_id is optional. Handler layer defaults it to the
    // authed team — see tools.ts ledger.query handler + tools.test.ts.
    expect(() => LedgerQueryInputSchema.parse({})).not.toThrow();
    const r = LedgerQueryInputSchema.parse({});
    expect(r.team_id).toBeUndefined();
  });

  it("accepts explicit team_id", () => {
    const r = LedgerQueryInputSchema.parse({ team_id: "team-x" });
    expect(r.team_id).toBe("team-x");
  });

  it("defaults limit to 25", () => {
    const r = LedgerQueryInputSchema.parse({ team_id: "team-x" });
    expect(r.limit).toBe(25);
  });

  it("rejects limit > 200", () => {
    expect(() => LedgerQueryInputSchema.parse({ team_id: "team-x", limit: 500 })).toThrow();
  });
});

// -------- Track B: teaching-signal validation -------------------------------
describe("RuntimeEntrySchema teaching signals", () => {
  const base = {
    team_id: "team-x",
    actor: { kind: "human" as const, id: "ravi@hca.com" },
    decision: "flagging this",
    agent_session_id: "sess-1",
  };

  describe("feedback_thumbs", () => {
    it("requires references_entry_id AND feedback_kind", () => {
      // Missing both
      expect(() =>
        RuntimeEntrySchema.parse({ ...base, runtime_kind: "feedback_thumbs" })
      ).toThrow();
      // Missing feedback_kind
      expect(() =>
        RuntimeEntrySchema.parse({
          ...base,
          runtime_kind: "feedback_thumbs",
          references_entry_id: "ref-1",
        })
      ).toThrow();
      // Missing references_entry_id
      expect(() =>
        RuntimeEntrySchema.parse({
          ...base,
          runtime_kind: "feedback_thumbs",
          feedback_kind: "thumbs_up",
        })
      ).toThrow();
    });

    it("accepts thumbs_up with both refs", () => {
      const r = RuntimeEntrySchema.parse({
        ...base,
        runtime_kind: "feedback_thumbs",
        references_entry_id: "ref-1",
        feedback_kind: "thumbs_up",
      });
      expect(r.feedback_kind).toBe("thumbs_up");
    });

    it("rejects unknown feedback_kind", () => {
      expect(() =>
        RuntimeEntrySchema.parse({
          ...base,
          runtime_kind: "feedback_thumbs",
          references_entry_id: "ref-1",
          feedback_kind: "applause",
        })
      ).toThrow();
    });
  });

  describe("decision_flagged", () => {
    it("requires references_entry_id", () => {
      expect(() =>
        RuntimeEntrySchema.parse({ ...base, runtime_kind: "decision_flagged" })
      ).toThrow();
    });

    it("accepts with references_entry_id, no feedback_kind needed", () => {
      const r = RuntimeEntrySchema.parse({
        ...base,
        runtime_kind: "decision_flagged",
        references_entry_id: "bad-decision-id",
      });
      expect(r.runtime_kind).toBe("decision_flagged");
    });
  });

  describe("replay_requested", () => {
    it("requires references_entry_id", () => {
      expect(() =>
        RuntimeEntrySchema.parse({ ...base, runtime_kind: "replay_requested" })
      ).toThrow();
    });
  });

  describe("class_paused", () => {
    it("requires paused_class non-empty", () => {
      expect(() =>
        RuntimeEntrySchema.parse({ ...base, runtime_kind: "class_paused" })
      ).toThrow();
      expect(() =>
        RuntimeEntrySchema.parse({
          ...base,
          runtime_kind: "class_paused",
          paused_class: "",
        })
      ).toThrow();
    });

    it("accepts with paused_class set", () => {
      const r = RuntimeEntrySchema.parse({
        ...base,
        runtime_kind: "class_paused",
        paused_class: "auth-policy",
      });
      expect(r.paused_class).toBe("auth-policy");
    });
  });

  it("pre-Track-B entries (no teaching kinds) parse unchanged", () => {
    // Regression guard: existing entries continue to validate.
    const r = RuntimeEntrySchema.parse({
      team_id: "team-x",
      actor: { kind: "agent", id: "orchestrator" },
      decision: "approved auth model",
      run_id: "run-1",
      runtime_kind: "stage_decision",
    });
    expect(r.runtime_kind).toBe("stage_decision");
    expect(r.references_entry_id).toBeFalsy();
  });
});
