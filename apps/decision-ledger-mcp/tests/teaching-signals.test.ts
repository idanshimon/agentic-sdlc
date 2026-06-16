import { describe, it, expect, beforeEach, vi } from "vitest";

/**
 * Track B teaching-signal handler tests.
 *
 * These cover the four operator-authored write paths added in Track B:
 *   ledger.add_feedback     — thumbs_up / thumbs_down sentiment
 *   ledger.flag_decision    — kill precedent reuse on a single decision
 *   ledger.request_replay   — request a re-run against current rules
 *   ledger.pause_class      — disable autopilot for an entire ambiguity class
 *
 * Schema-level coverage of the runtime_kind refines lives in schema.test.ts;
 * here we exercise the handler-shaped surface area: cross-team rejection,
 * runtime_kind correctness on the entry passed to writeRuntimeEntry, default
 * agent_session_id auto-generation, and rationale defaulting.
 *
 * cosmos-client is mocked so these run without an Azure dependency.
 */

vi.mock("../src/cosmos-client.js", () => ({
  queryEntries: vi.fn(),
  writeRuntimeEntry: vi.fn(),
  findPrecedent: vi.fn(),
}));

vi.mock("../src/bundle-loader.js", () => ({
  getBundle: vi.fn(),
}));

import { tools } from "../src/tools.js";
import * as cosmos from "../src/cosmos-client.js";

const mockedWrite = cosmos.writeRuntimeEntry as ReturnType<typeof vi.fn>;
const TEAM = "team-cardiology";
const HUMAN = { kind: "human" as const, id: "ravi@hca.com" };

beforeEach(() => {
  vi.clearAllMocks();
  mockedWrite.mockResolvedValue({ id: "entry-1" });
});

// ---------- ledger.add_feedback (thumbs) -----------------------------------
describe("ledger.add_feedback handler", () => {
  it("writes a feedback_thumbs entry with the correct runtime_kind + refs", async () => {
    await tools["ledger.add_feedback"].handler(
      {
        actor: HUMAN,
        references_entry_id: "decision-42",
        feedback_kind: "thumbs_up",
      },
      TEAM,
    );
    expect(mockedWrite).toHaveBeenCalledTimes(1);
    const written = mockedWrite.mock.calls[0][0];
    expect(written.runtime_kind).toBe("feedback_thumbs");
    expect(written.references_entry_id).toBe("decision-42");
    expect(written.feedback_kind).toBe("thumbs_up");
    expect(written.team_id).toBe(TEAM);
    expect(typeof written.agent_session_id).toBe("string");
    expect(written.agent_session_id).toMatch(/^feedback-/);
  });

  it("defaults team_id to the authed team when omitted", async () => {
    await tools["ledger.add_feedback"].handler(
      {
        actor: HUMAN,
        references_entry_id: "decision-42",
        feedback_kind: "thumbs_down",
      },
      TEAM,
    );
    expect(mockedWrite.mock.calls[0][0].team_id).toBe(TEAM);
  });

  it("rejects cross-team requests", async () => {
    await expect(
      tools["ledger.add_feedback"].handler(
        {
          team_id: "team-radiology",
          actor: HUMAN,
          references_entry_id: "decision-42",
          feedback_kind: "thumbs_up",
        },
        TEAM,
      ),
    ).rejects.toThrow(/Token scoped to 'team-cardiology'/);
    expect(mockedWrite).not.toHaveBeenCalled();
  });

  it("respects an explicit agent_session_id override", async () => {
    await tools["ledger.add_feedback"].handler(
      {
        actor: HUMAN,
        references_entry_id: "decision-42",
        feedback_kind: "thumbs_up",
        agent_session_id: "ide-session-abc",
      },
      TEAM,
    );
    expect(mockedWrite.mock.calls[0][0].agent_session_id).toBe("ide-session-abc");
  });

  it("rejects unknown feedback_kind via schema refine", async () => {
    await expect(
      tools["ledger.add_feedback"].handler(
        {
          actor: HUMAN,
          references_entry_id: "decision-42",
          feedback_kind: "applause",
        },
        TEAM,
      ),
    ).rejects.toThrow();
    expect(mockedWrite).not.toHaveBeenCalled();
  });
});

// ---------- ledger.flag_decision -------------------------------------------
describe("ledger.flag_decision handler", () => {
  it("writes a decision_flagged entry with rationale preserved", async () => {
    await tools["ledger.flag_decision"].handler(
      {
        actor: HUMAN,
        references_entry_id: "bad-decision-id",
        rationale: "Cited a stale PHI rule version",
      },
      TEAM,
    );
    const written = mockedWrite.mock.calls[0][0];
    expect(written.runtime_kind).toBe("decision_flagged");
    expect(written.references_entry_id).toBe("bad-decision-id");
    expect(written.rationale).toBe("Cited a stale PHI rule version");
    expect(written.agent_session_id).toMatch(/^flag-/);
  });

  it("rejects cross-team requests", async () => {
    await expect(
      tools["ledger.flag_decision"].handler(
        {
          team_id: "team-radiology",
          actor: HUMAN,
          references_entry_id: "bad-decision-id",
          rationale: "wrong",
        },
        TEAM,
      ),
    ).rejects.toThrow(/Token scoped to 'team-cardiology'/);
  });

  it("rejects when references_entry_id is missing (schema refine)", async () => {
    await expect(
      tools["ledger.flag_decision"].handler(
        { actor: HUMAN, rationale: "wrong" },
        TEAM,
      ),
    ).rejects.toThrow();
    expect(mockedWrite).not.toHaveBeenCalled();
  });
});

// ---------- ledger.request_replay ------------------------------------------
describe("ledger.request_replay handler", () => {
  it("writes a replay_requested entry; rationale defaults to empty", async () => {
    await tools["ledger.request_replay"].handler(
      { actor: HUMAN, references_entry_id: "decision-99" },
      TEAM,
    );
    const written = mockedWrite.mock.calls[0][0];
    expect(written.runtime_kind).toBe("replay_requested");
    expect(written.references_entry_id).toBe("decision-99");
    expect(written.rationale).toBe("");
    expect(written.agent_session_id).toMatch(/^replay-/);
  });

  it("rejects cross-team requests", async () => {
    await expect(
      tools["ledger.request_replay"].handler(
        {
          team_id: "team-radiology",
          actor: HUMAN,
          references_entry_id: "decision-99",
        },
        TEAM,
      ),
    ).rejects.toThrow(/Token scoped to 'team-cardiology'/);
  });
});

// ---------- ledger.pause_class ---------------------------------------------
describe("ledger.pause_class handler", () => {
  it("writes a class_paused entry mirroring paused_class into ambiguity_class", async () => {
    await tools["ledger.pause_class"].handler(
      {
        actor: HUMAN,
        paused_class: "auth-policy",
        rationale: "Need to re-teach the auth ladder before auto-deciding",
      },
      TEAM,
    );
    const written = mockedWrite.mock.calls[0][0];
    expect(written.runtime_kind).toBe("class_paused");
    expect(written.paused_class).toBe("auth-policy");
    // ambiguity_class is mirrored so the existing /decisions filters
    // (which key off ambiguity_class) surface paused-class entries
    // alongside the decisions they govern.
    expect(written.ambiguity_class).toBe("auth-policy");
    expect(written.agent_session_id).toMatch(/^pause-/);
  });

  it("rejects empty paused_class explicitly (defense-in-depth pre-schema)", async () => {
    await expect(
      tools["ledger.pause_class"].handler(
        { actor: HUMAN, paused_class: "", rationale: "x" },
        TEAM,
      ),
    ).rejects.toThrow();
    expect(mockedWrite).not.toHaveBeenCalled();
  });

  it("rejects cross-team requests", async () => {
    await expect(
      tools["ledger.pause_class"].handler(
        {
          team_id: "team-radiology",
          actor: HUMAN,
          paused_class: "auth-policy",
          rationale: "x",
        },
        TEAM,
      ),
    ).rejects.toThrow(/Token scoped to 'team-cardiology'/);
  });
});

// ---------- inputSchema regression guard -----------------------------------
describe("teaching-signal tool inputSchemas", () => {
  it("ledger.add_feedback declares actor + references_entry_id + feedback_kind required", () => {
    expect(tools["ledger.add_feedback"].inputSchema.required).toEqual([
      "actor",
      "references_entry_id",
      "feedback_kind",
    ]);
  });

  it("ledger.flag_decision declares actor + references_entry_id + rationale required", () => {
    expect(tools["ledger.flag_decision"].inputSchema.required).toEqual([
      "actor",
      "references_entry_id",
      "rationale",
    ]);
  });

  it("ledger.request_replay declares actor + references_entry_id required (rationale optional)", () => {
    expect(tools["ledger.request_replay"].inputSchema.required).toEqual([
      "actor",
      "references_entry_id",
    ]);
  });

  it("ledger.pause_class declares actor + paused_class + rationale required", () => {
    expect(tools["ledger.pause_class"].inputSchema.required).toEqual([
      "actor",
      "paused_class",
      "rationale",
    ]);
  });
});
