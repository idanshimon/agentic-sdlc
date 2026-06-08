/* Tests for the context-aware AgentAssistant reply engine.
 *
 * Grounded in spec:
 *   openspec/changes/add-context-aware-agent-assistant/specs/agent-assistant/spec.md
 *
 * Each test names the REQ-N it covers. Tests seed localStorage directly under
 * the demo store key so we don't depend on startDemoRun's animation timing.
 */
import { describe, it, expect, beforeEach } from "vitest";
import {
  gatherContext,
  pickReply,
  getSuggestions,
  type GatheredContext,
} from "@/lib/assist/replies";
import type { AssistContext } from "@/lib/assist/context";

const STORAGE_KEY = "agentic-sdlc.demo.runs";

interface SeedRun {
  run_id: string;
  status: string;
  current_stage?: string | null;
  events?: Array<{ stage: string; status: string; timestamp: string; message?: string }>;
  ledger_entries?: Array<Record<string, unknown>>;
}

function seedDemoStore(runs: SeedRun[]) {
  const store: Record<string, unknown> = {};
  for (const r of runs) {
    store[r.run_id] = {
      scenario_id: "vitals",
      run_id: r.run_id,
      team_id: "team-demo",
      status: r.status,
      current_stage: r.current_stage ?? null,
      events: r.events ?? [],
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      cost_usd: 0,
      decisions_count: r.ledger_entries?.length ?? 0,
      ledger_entries: r.ledger_entries ?? [],
    };
  }
  globalThis.localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
}

beforeEach(() => {
  globalThis.localStorage.clear();
});

/* ─────────────── REQ-2: fresh gather every turn, no caching ─────────────── */

describe("REQ-2: gatherContext runs fresh every turn", () => {
  it("reflects awaiting_gate=true then awaiting_gate=false across two calls", () => {
    seedDemoStore([
      {
        run_id: "run-flip",
        status: "awaiting_gate",
        current_stage: "resolver",
        events: [
          { stage: "ingest", status: "completed", timestamp: "2026-06-08T00:00:00Z" },
          { stage: "assessor", status: "completed", timestamp: "2026-06-08T00:00:01Z" },
          { stage: "resolver", status: "awaiting_gate", timestamp: "2026-06-08T00:00:02Z" },
        ],
      },
    ]);

    const ctx: AssistContext = { kind: "run-detail", id: "run-flip" };
    const first = gatherContext(ctx);
    expect(first.run?.awaiting_gate).toBe(true);

    seedDemoStore([
      {
        run_id: "run-flip",
        status: "in_progress",
        current_stage: "architect",
        events: [
          { stage: "ingest", status: "completed", timestamp: "2026-06-08T00:00:00Z" },
          { stage: "assessor", status: "completed", timestamp: "2026-06-08T00:00:01Z" },
          { stage: "resolver", status: "completed", timestamp: "2026-06-08T00:00:02Z" },
          { stage: "architect", status: "in_progress", timestamp: "2026-06-08T00:00:03Z" },
        ],
      },
    ]);

    const second = gatherContext(ctx);
    expect(second.run?.awaiting_gate).toBe(false);
    expect(second.run?.completed_stages).toContain("resolver");
  });

  it("two identical (context, prompt) calls re-gather and reflect mutated store", () => {
    seedDemoStore([{ run_id: "run-mut", status: "awaiting_gate", current_stage: "resolver" }]);
    const ctx: AssistContext = { kind: "run-detail", id: "run-mut" };
    const replyA = pickReply(ctx, "what do you recommend");
    expect(replyA.text.toLowerCase()).toMatch(/awaiting/);

    seedDemoStore([{ run_id: "run-mut", status: "completed", current_stage: null }]);
    const replyB = pickReply(ctx, "what do you recommend");
    expect(replyB.text.toLowerCase()).not.toMatch(/awaiting human gate/);
  });
});

/* ─────────────── REQ-3: run-focused gathered fields ─────────────── */

describe("REQ-3: run-focused context fields", () => {
  it("populates {id, status, stage, awaiting_gate, completed_stages, has_artifacts} for run-detail", () => {
    seedDemoStore([
      {
        run_id: "run-shape",
        status: "in_progress",
        current_stage: "codegen",
        events: [
          { stage: "ingest", status: "completed", timestamp: "2026-06-08T00:00:00Z" },
          { stage: "assessor", status: "completed", timestamp: "2026-06-08T00:00:01Z" },
          { stage: "resolver", status: "completed", timestamp: "2026-06-08T00:00:02Z" },
          { stage: "architect", status: "completed", timestamp: "2026-06-08T00:00:03Z" },
          { stage: "codegen", status: "in_progress", timestamp: "2026-06-08T00:00:04Z" },
        ],
      },
    ]);
    const g = gatherContext({ kind: "run-detail", id: "run-shape" });
    expect(g.run).toBeDefined();
    expect(g.run!.id).toBe("run-shape");
    expect(g.run!.status).toBe("in_progress");
    expect(g.run!.stage).toBe("codegen");
    expect(g.run!.awaiting_gate).toBe(false);
    expect(g.run!.completed_stages).toEqual(
      expect.arrayContaining(["ingest", "assessor", "resolver", "architect"]),
    );
    expect(g.run!.completed_stages).not.toContain("codegen");
    // has_artifacts can be true or false depending on demo fixture wiring; just
    // assert the field is defined (boolean).
    expect(typeof g.run!.has_artifacts).toBe("boolean");
  });

  it("returns run=undefined when run is not in the demo store", () => {
    seedDemoStore([]);
    const g = gatherContext({ kind: "run-detail", id: "run-does-not-exist" });
    expect(g.run).toBeUndefined();
  });

  it("run-resolver-gate uses the same shape as run-detail", () => {
    seedDemoStore([{ run_id: "run-gate", status: "awaiting_gate", current_stage: "resolver" }]);
    const a = gatherContext({ kind: "run-detail", id: "run-gate" });
    const b = gatherContext({ kind: "run-resolver-gate", id: "run-gate" });
    expect(b.run).toEqual(a.run);
  });
});

/* ─────────────── REQ-4: portfolio gathered fields ─────────────── */

describe("REQ-4: portfolio aggregation fields", () => {
  it("computes total_runs, by_status, awaiting_gate_count for dashboard kind", () => {
    seedDemoStore([
      { run_id: "r1", status: "awaiting_gate" },
      { run_id: "r2", status: "awaiting_gate" },
      { run_id: "r3", status: "in_progress" },
      { run_id: "r4", status: "completed" },
    ]);
    const g = gatherContext({ kind: "dashboard" });
    expect(g.portfolio).toBeDefined();
    expect(g.portfolio!.total_runs).toBe(4);
    expect(g.portfolio!.awaiting_gate_count).toBe(2);
    expect(g.portfolio!.by_status).toMatchObject({
      awaiting_gate: 2,
      in_progress: 1,
      completed: 1,
    });
  });

  it("returns zeroed portfolio against an empty store", () => {
    seedDemoStore([]);
    const g = gatherContext({ kind: "runs-list" });
    expect(g.portfolio).toMatchObject({
      total_runs: 0,
      by_status: {},
      awaiting_gate_count: 0,
      total_cost_usd: 0,
      total_decisions: 0,
      bundle_citation_density: 0,
    });
  });

  it("computes bundle_citation_density from ledger entries", () => {
    // 3 runtime entries: 2 cite at least one bundle_ref, 1 has empty bundle_refs.
    seedDemoStore([
      {
        run_id: "r-cite",
        status: "completed",
        ledger_entries: [
          { id: "e1", entry_type: "runtime", bundle_refs: ["security/v0.1.0/PHI-001"] },
          { id: "e2", entry_type: "runtime", bundle_refs: ["privacy/v0.1.0/PHI-REDACT-001"] },
          { id: "e3", entry_type: "runtime", bundle_refs: [] },
        ],
      },
    ]);
    const g = gatherContext({ kind: "telemetry" });
    expect(g.portfolio!.total_decisions).toBe(3);
    // 2 of 3 are cited.
    expect(g.portfolio!.bundle_citation_density).toBeCloseTo(2 / 3, 2);
  });
});

/* ─────────────── REQ-5: citations cite real bundle_refs ─────────────── */

describe("REQ-5: citations come from real ledger entries", () => {
  it("only emits citation refs that exist in the run's ledger entries", () => {
    seedDemoStore([
      {
        run_id: "run-cite",
        status: "awaiting_gate",
        current_stage: "resolver",
        ledger_entries: [
          {
            id: "d1",
            entry_type: "runtime",
            run_id: "run-cite",
            decision: "Vendor auth = mTLS+OAuth client_credentials",
            stage: "resolver",
            phi_class: "high",
            cost_usd: 0.01,
            model_used: "sonnet-4-6",
            rationale: "Required by HIPAA §164.312(d)",
            bundle_refs: ["security/v0.1.0/AUTH-001"],
          },
          {
            id: "d2",
            entry_type: "runtime",
            run_id: "run-cite",
            decision: "Egress redaction = Safe Harbor 18-identifier",
            stage: "resolver",
            phi_class: "high",
            cost_usd: 0.012,
            model_used: "sonnet-4-6",
            rationale: "HIPAA §164.514(b)",
            bundle_refs: ["privacy/v0.1.0/PHI-REDACT-001"],
          },
        ],
      },
    ]);
    const reply = pickReply(
      { kind: "run-resolver-gate", id: "run-cite" },
      "what do you recommend",
    );
    const refs = (reply.citations ?? []).map((c) => c.ref);
    // Every emitted ref MUST be in the seeded ledger.
    const seededRefs = new Set(["security/v0.1.0/AUTH-001", "privacy/v0.1.0/PHI-REDACT-001"]);
    for (const ref of refs) {
      expect(seededRefs.has(ref)).toBe(true);
    }
    // And we expect at least one ref since the ledger has two cited entries.
    expect(refs.length).toBeGreaterThan(0);
  });

  it("emits no citations when ledger has no bundle_refs", () => {
    seedDemoStore([
      {
        run_id: "run-bare",
        status: "awaiting_gate",
        current_stage: "resolver",
        ledger_entries: [
          {
            id: "d-empty",
            entry_type: "runtime",
            run_id: "run-bare",
            decision: "no-citation decision",
            stage: "resolver",
            phi_class: "low",
            cost_usd: 0,
            model_used: "haiku-4-5",
            bundle_refs: [],
          },
        ],
      },
    ]);
    const reply = pickReply(
      { kind: "run-resolver-gate", id: "run-bare" },
      "what do you recommend",
    );
    expect(reply.citations ?? []).toHaveLength(0);
  });
});

/* ─────────────── REQ-6: suggestions react to state ─────────────── */

describe("REQ-6: suggestion chips react to gathered state", () => {
  it("run with awaiting_gate=true produces a chip mentioning 'gate' or 'awaiting'", () => {
    seedDemoStore([{ run_id: "run-aw", status: "awaiting_gate", current_stage: "resolver" }]);
    const chips = getSuggestions({ kind: "run-detail", id: "run-aw" });
    expect(chips.some((s) => /gate|awaiting|recommend/i.test(s))).toBe(true);
  });

  it("dashboard with N awaiting-gate runs surfaces N in a chip", () => {
    seedDemoStore([
      { run_id: "a", status: "awaiting_gate" },
      { run_id: "b", status: "awaiting_gate" },
      { run_id: "c", status: "awaiting_gate" },
      { run_id: "d", status: "awaiting_gate" },
      { run_id: "e", status: "in_progress" },
    ]);
    const chips = getSuggestions({ kind: "dashboard" });
    // At least one chip must include the literal "4".
    expect(chips.some((s) => s.includes("4"))).toBe(true);
  });

  it("run with no awaiting_gate produces a non-gate chip set", () => {
    seedDemoStore([{ run_id: "run-clean", status: "completed", current_stage: null }]);
    const chips = getSuggestions({ kind: "run-detail", id: "run-clean" });
    // None of the chips should literally say "awaiting" since the run is done.
    expect(chips.some((s) => /awaiting human gate/i.test(s))).toBe(false);
    // And we still get a non-empty chip set.
    expect(chips.length).toBeGreaterThan(0);
  });

  it("empty portfolio on dashboard suggests starting a run", () => {
    seedDemoStore([]);
    const chips = getSuggestions({ kind: "dashboard" });
    expect(chips.some((s) => /start|demo flow|how do i/i.test(s))).toBe(true);
  });
});

/* ─────────────── REQ-2 reinforced: text reflects state ─────────────── */

describe("REQ-2 reinforced: replies quote real run id and counts", () => {
  it("recommend reply on awaiting_gate quotes the run id and decision count", () => {
    seedDemoStore([
      {
        run_id: "run-quote",
        status: "awaiting_gate",
        current_stage: "resolver",
        ledger_entries: [
          {
            id: "d1",
            entry_type: "runtime",
            run_id: "run-quote",
            decision: "decision-one",
            stage: "resolver",
            phi_class: "high",
            cost_usd: 0,
            model_used: "sonnet-4-6",
            bundle_refs: ["security/v0.1.0/AUTH-001"],
          },
          {
            id: "d2",
            entry_type: "runtime",
            run_id: "run-quote",
            decision: "decision-two",
            stage: "resolver",
            phi_class: "high",
            cost_usd: 0,
            model_used: "sonnet-4-6",
            bundle_refs: ["privacy/v0.1.0/PHI-REDACT-001"],
          },
        ],
      },
    ]);
    const reply = pickReply({ kind: "run-resolver-gate", id: "run-quote" }, "what do you recommend");
    expect(reply.text).toContain("run-quote");
    // The reply mentions "2" (decision count) somewhere.
    expect(reply.text).toMatch(/\b2\b/);
    // And mentions at least one of the seeded decisions verbatim.
    expect(reply.text.includes("decision-one") || reply.text.includes("decision-two")).toBe(true);
  });
});
