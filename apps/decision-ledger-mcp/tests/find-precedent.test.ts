import { describe, it, expect, beforeEach, vi } from "vitest";

/**
 * Track B findPrecedent behavior tests.
 *
 * findPrecedent now does three things:
 *   1. Short-circuit to null if a class_paused entry exists for this
 *      (team_id, ambiguity_class).
 *   2. Pull top-5 candidate precedents (stage_decision-only).
 *   3. Exclude any candidate whose id appears in a decision_flagged entry.
 *
 * We mock @azure/cosmos / @azure/identity so the Cosmos SDK is never
 * instantiated. The mock's `query().fetchAll()` is dispatched per-call
 * (paused → candidates → flagged-ids) so we can assert each branch exactly.
 */

type FakeRow = Record<string, unknown>;

const fetchAllMock = vi.fn();

const queryMock = vi.fn(() => ({ fetchAll: fetchAllMock }));

vi.mock("@azure/cosmos", () => ({
  CosmosClient: vi.fn(() => ({
    database: vi.fn(() => ({
      container: vi.fn(() => ({
        items: {
          query: queryMock,
          upsert: vi.fn().mockResolvedValue(undefined),
        },
      })),
    })),
  })),
}));

vi.mock("@azure/identity", () => ({
  DefaultAzureCredential: vi.fn(),
}));

// COSMOS_ENDPOINT is required by getCosmos(); set it before module import.
process.env.COSMOS_ENDPOINT = "https://fake-cosmos.invalid";

const { findPrecedent } = await import("../src/cosmos-client.js");

const TEAM = "team-cardiology";
const CLASS = "auth-policy";
const HASH = "slot-hash-abc";

/**
 * Sequence the three internal Cosmos queries findPrecedent makes:
 *   1. paused-class probe         → paused
 *   2. candidate precedents       → candidates
 *   3. flagged-id projection      → flagged
 *
 * If a query is skipped (e.g. paused short-circuits before candidates run),
 * its slot is simply unused.
 */
function sequenceFetchAll(opts: {
  paused?: FakeRow[];
  candidates?: FakeRow[];
  flagged?: string[];
}) {
  fetchAllMock
    .mockResolvedValueOnce({ resources: opts.paused ?? [] })
    .mockResolvedValueOnce({ resources: opts.candidates ?? [] })
    .mockResolvedValueOnce({ resources: opts.flagged ?? [] });
}

beforeEach(() => {
  fetchAllMock.mockReset();
  queryMock.mockClear();
});

describe("findPrecedent — class_paused short-circuit", () => {
  it("returns null without querying candidates when class is paused", async () => {
    sequenceFetchAll({ paused: [{ id: "pause-evt-1" }] });

    const result = await findPrecedent({
      team_id: TEAM,
      ambiguity_class: CLASS,
      slot_value_hash: HASH,
    });

    expect(result).toBeNull();
    // Only the paused-probe query should have run; candidates + flagged
    // are skipped because the function returns early.
    expect(fetchAllMock).toHaveBeenCalledTimes(1);
    expect(queryMock).toHaveBeenCalledTimes(1);
    const firstQuery = queryMock.mock.calls[0]![0] as unknown as { query: string };
    expect(firstQuery.query).toContain("class_paused");
  });

  it("proceeds to candidate lookup when no class_paused entry exists", async () => {
    sequenceFetchAll({
      paused: [],
      candidates: [{ id: "decision-1", ambiguity_class: CLASS }],
      flagged: [],
    });

    const result = await findPrecedent({
      team_id: TEAM,
      ambiguity_class: CLASS,
      slot_value_hash: HASH,
    });

    expect(result).toMatchObject({ id: "decision-1" });
    expect(fetchAllMock).toHaveBeenCalledTimes(3);
  });
});

describe("findPrecedent — decision_flagged exclusion", () => {
  it("returns null when the only candidate has been flagged", async () => {
    sequenceFetchAll({
      paused: [],
      candidates: [{ id: "decision-bad", ambiguity_class: CLASS }],
      flagged: ["decision-bad"],
    });

    const result = await findPrecedent({
      team_id: TEAM,
      ambiguity_class: CLASS,
      slot_value_hash: HASH,
    });

    expect(result).toBeNull();
  });

  it("skips flagged candidates and returns the next-most-recent unflagged", async () => {
    sequenceFetchAll({
      paused: [],
      candidates: [
        { id: "decision-bad", ambiguity_class: CLASS, created_at: "2026-06-09T12:00:00Z" },
        { id: "decision-good", ambiguity_class: CLASS, created_at: "2026-06-08T12:00:00Z" },
      ],
      flagged: ["decision-bad"],
    });

    const result = await findPrecedent({
      team_id: TEAM,
      ambiguity_class: CLASS,
      slot_value_hash: HASH,
    });

    expect(result).toMatchObject({ id: "decision-good" });
  });

  it("returns the most recent candidate when none are flagged", async () => {
    sequenceFetchAll({
      paused: [],
      candidates: [
        { id: "decision-newest", ambiguity_class: CLASS },
        { id: "decision-older", ambiguity_class: CLASS },
      ],
      flagged: [],
    });

    const result = await findPrecedent({
      team_id: TEAM,
      ambiguity_class: CLASS,
      slot_value_hash: HASH,
    });

    expect(result).toMatchObject({ id: "decision-newest" });
  });

  it("returns null when no candidates exist (independent of flagged set)", async () => {
    sequenceFetchAll({ paused: [], candidates: [], flagged: ["decision-irrelevant"] });

    const result = await findPrecedent({
      team_id: TEAM,
      ambiguity_class: CLASS,
      slot_value_hash: HASH,
    });

    expect(result).toBeNull();
    // Optimization regression guard: when candidates is empty, the flagged-id
    // projection should NOT run — there's nothing to filter.
    expect(fetchAllMock).toHaveBeenCalledTimes(2);
  });
});

describe("findPrecedent — query shape regression guards", () => {
  it("candidate query excludes non-stage_decision runtime_kinds", async () => {
    // Without this filter, a flag/replay/pause entry could win the TOP 1
    // selection and be returned as a "precedent" — that would be a major
    // ledger-integrity bug. Lock the SQL filter in.
    sequenceFetchAll({
      paused: [],
      candidates: [{ id: "decision-1" }],
      flagged: [],
    });

    await findPrecedent({
      team_id: TEAM,
      ambiguity_class: CLASS,
      slot_value_hash: HASH,
    });

    const candidateQuery = queryMock.mock.calls[1]![0] as unknown as { query: string };
    expect(candidateQuery.query).toContain(
      "NOT IS_DEFINED(c.runtime_kind) OR c.runtime_kind='stage_decision'",
    );
  });

  it("flagged-id query is partition-scoped and projects references_entry_id only", async () => {
    sequenceFetchAll({
      paused: [],
      candidates: [{ id: "decision-1" }],
      flagged: [],
    });

    await findPrecedent({
      team_id: TEAM,
      ambiguity_class: CLASS,
      slot_value_hash: HASH,
    });

    const flaggedQuery = queryMock.mock.calls[2]![0] as unknown as { query: string };
    expect(flaggedQuery.query).toContain("SELECT VALUE c.references_entry_id");
    expect(flaggedQuery.query).toContain("c.runtime_kind='decision_flagged'");
  });
});
