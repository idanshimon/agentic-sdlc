import { describe, it, expect, beforeEach, vi } from "vitest";

/**
 * Tools layer — handler-level tests.
 *
 * These tests cover the team_id-defaulting behavior added to the
 * `ledger.query` handler. Schema-level coverage lives in schema.test.ts.
 *
 * We mock cosmos-client so these run without an Azure dependency.
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

describe("ledger.query handler", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (cosmos.queryEntries as ReturnType<typeof vi.fn>).mockResolvedValue([]);
  });

  it("defaults team_id to authed team when caller omits it", async () => {
    const result = await tools["ledger.query"].handler({}, "team-cardiology");

    expect(cosmos.queryEntries).toHaveBeenCalledTimes(1);
    const call = (cosmos.queryEntries as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(call.team_id).toBe("team-cardiology");
    // The handler echoes the team it actually queried (KI-1: makes the
    // partition the dashboard read explicit instead of a silent empty result).
    expect(result).toEqual({ entries: [], team_id: "team-cardiology" });
  });

  it("accepts explicit team_id when it matches the authed team", async () => {
    await tools["ledger.query"].handler(
      { team_id: "team-cardiology", limit: 10 },
      "team-cardiology"
    );

    const call = (cosmos.queryEntries as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(call.team_id).toBe("team-cardiology");
    expect(call.limit).toBe(10);
  });

  it("rejects cross-team requests when explicit team_id != authed team", async () => {
    await expect(
      tools["ledger.query"].handler({ team_id: "team-radiology" }, "team-cardiology")
    ).rejects.toThrow(/Token scoped to 'team-cardiology'/);
    expect(cosmos.queryEntries).not.toHaveBeenCalled();
  });

  it("forwards optional filters (entry_type, agent_session_id, bundle_ref_prefix)", async () => {
    await tools["ledger.query"].handler(
      {
        entry_type: "runtime",
        agent_session_id: "sess-xyz",
        bundle_ref_prefix: "security/",
      },
      "team-cardiology"
    );

    const call = (cosmos.queryEntries as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(call).toEqual({
      team_id: "team-cardiology",
      limit: 25, // schema default
      entry_type: "runtime",
      agent_session_id: "sess-xyz",
      bundle_ref_prefix: "security/",
    });
  });

  it("declares team_id as NOT required in inputSchema (regression guard)", () => {
    // This guards against accidentally re-introducing required:["team_id"],
    // which would re-cause the dashboard 400 loop.
    expect(tools["ledger.query"].inputSchema.required).toEqual([]);
  });
});
