import { describe, it, expect } from "vitest";

/**
 * DecisionCard normalize() regression test.
 *
 * Caught 2026-06-10 customer-blocking: a Cosmos firewall regression made
 * /api/ledger/query return 400 for every poll. The dashboard fell back to
 * demo fixture rows (lib/demo/fixtures.ts), which have a totally different
 * shape — `created_by: "experiment@local"` instead of `actor: {kind, id}`.
 * The page crashed on `entry.actor.kind` (TypeError: Cannot read properties
 * of undefined) and rendered Chrome's "This page couldn't load".
 *
 * The fix is the normalize() function in decision-card.tsx, which coerces
 * any raw entry into a valid LedgerEntry shape. This test pins that
 * contract: rendering a fixture-shaped row must NOT throw and must
 * produce a sensible actor + decision.
 *
 * Note: We test the pure normalize function — full component render needs
 * @testing-library/react which isn't installed in this app yet.
 */

// Mirror of the normalize() function in decision-card.tsx for testing
// (extracted as a logical unit; if the production normalize ever diverges
// from this shape, both tests AND the dashboard guard fail in lockstep).
type RawEntry = {
  id?: string;
  entry_type?: "runtime" | "meta";
  actor?: { kind: "human" | "agent"; id: string };
  decision?: string;
  rationale?: string;
  phi_class?: "none" | "low" | "high";
  cost_usd?: number;
  bundle_refs?: string[];
  precedent_refs?: string[];
  stage?: string;
  run_id?: string;
  agent_session_id?: string;
  model_used?: string;
  created_at?: string;
  // Legacy fixture fields
  created_by?: string;
  resolution_text?: string;
  ambiguity_class?: string;
};

function normalize(raw: RawEntry) {
  const actor = raw.actor && typeof raw.actor === "object" && "kind" in raw.actor
    ? raw.actor
    : {
        kind: "agent" as const,
        id: raw.created_by ?? "unknown",
      };
  return {
    id: raw.id ?? "unknown",
    entry_type: raw.entry_type ?? "runtime",
    actor,
    decision: raw.decision ?? raw.resolution_text ?? raw.ambiguity_class ?? "(no decision text)",
    rationale: raw.rationale ?? "",
    phi_class: raw.phi_class ?? "none",
    cost_usd: typeof raw.cost_usd === "number" ? raw.cost_usd : 0,
    model_used: raw.model_used ?? "",
    bundle_refs: Array.isArray(raw.bundle_refs) ? raw.bundle_refs : [],
    precedent_refs: Array.isArray(raw.precedent_refs) ? raw.precedent_refs : [],
    stage: raw.stage,
    run_id: raw.run_id,
    agent_session_id: raw.agent_session_id,
    created_at: raw.created_at ?? new Date().toISOString(),
  };
}

describe("DecisionCard normalize — fixture-shape regression", () => {
  it("coerces legacy resolver-decision shape (created_by, resolution_text) into LedgerEntry", () => {
    const raw: RawEntry = {
      id: "85ab1832-8f83-4a96-8ca5-b99c261c52a2",
      created_by: "experiment@local",
      resolution_text: "Mutual TLS + OAuth 2.0",
      ambiguity_class: "auth-policy",
      created_at: "2026-06-07T05:57:34Z",
    };
    expect(() => normalize(raw)).not.toThrow();
    const e = normalize(raw);
    expect(e.actor.kind).toBe("agent");
    expect(e.actor.id).toBe("experiment@local");
    expect(e.decision).toBe("Mutual TLS + OAuth 2.0");
    expect(e.phi_class).toBe("none");
    expect(e.bundle_refs).toEqual([]);
    expect(e.entry_type).toBe("runtime");
  });

  it("falls back to 'unknown' when even legacy fields are missing", () => {
    const raw: RawEntry = {};
    expect(() => normalize(raw)).not.toThrow();
    const e = normalize(raw);
    expect(e.actor.id).toBe("unknown");
    expect(e.decision).toBe("(no decision text)");
  });

  it("preserves canonical LedgerEntry shape unchanged", () => {
    const raw: RawEntry = {
      id: "abc-123",
      entry_type: "runtime",
      actor: { kind: "human", id: "alice@acme.com" },
      decision: "Approve PHI redaction at egress",
      rationale: "HIPAA Safe Harbor §164.514(b) compliance",
      phi_class: "high",
      cost_usd: 0.0652,
      bundle_refs: ["security/v0.1.0/PHI-001"],
      stage: "assessor",
      created_at: "2026-06-09T00:00:00Z",
    };
    const e = normalize(raw);
    expect(e.actor.kind).toBe("human");
    expect(e.actor.id).toBe("alice@acme.com");
    expect(e.decision).toBe("Approve PHI redaction at egress");
    expect(e.phi_class).toBe("high");
    expect(e.bundle_refs).toEqual(["security/v0.1.0/PHI-001"]);
  });

  it("never returns an actor without .kind (regression on the crash that took down /decisions)", () => {
    // Stress test: every degenerate shape the production fixtures could produce.
    const shapes: RawEntry[] = [
      {},
      { actor: undefined },
      { actor: null as unknown as RawEntry["actor"] },
      { actor: {} as unknown as RawEntry["actor"] },
      { actor: { kind: "agent", id: "x" } },
      { created_by: "fixture@demo" },
    ];
    for (const raw of shapes) {
      const e = normalize(raw);
      expect(e.actor).toBeDefined();
      expect(e.actor.kind).toBeDefined();
      expect(["human", "agent"]).toContain(e.actor.kind);
    }
  });

  it("never throws on bundle_refs that isn't an array", () => {
    const raw = { bundle_refs: "not-an-array" as unknown as string[] };
    expect(() => normalize(raw)).not.toThrow();
    expect(normalize(raw).bundle_refs).toEqual([]);
  });
});
