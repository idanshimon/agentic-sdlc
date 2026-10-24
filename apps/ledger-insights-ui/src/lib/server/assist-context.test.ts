import { describe, it, expect } from "vitest";
import { prepareContext, rank, type ContextSources, type RawLedgerEntry } from "./assist-context";

const entry = (o: Partial<RawLedgerEntry>): RawLedgerEntry => ({
  id: Math.random().toString(36).slice(2), confidence_source: "human", created_at: "2026-08-01T00:00:00Z", ...o,
});

function sources(over: Partial<ContextSources> = {}): ContextSources {
  return {
    ledger: async () => [
      entry({ id: "a", run_id: "R1", ambiguity_class: "sla-binding", resolution_text: "Set SLA to 99.9 uptime", bundle_refs: ["security/v0.1.0/PHI-002"] }),
      entry({ id: "b", run_id: "R2", ambiguity_class: "sla-binding", resolution_text: "Set SLA to 95% under 2s", confidence_source: "autopilot" }),
      entry({ id: "c", run_id: "R2", ambiguity_class: "phi-classification", resolution_text: "Classify MRN as PHI" }),
    ],
    runs: async () => [
      { run_id: "R1", status: "awaiting_gate", pending_gate: { stage: "resolver" } },
      { run_id: "R2", status: "failed", failure_kind: "policy_block", failure_reason: "PHI-001 block" },
    ],
    rules: async () => [{ id: "PHI-002", dept: "security", version: "v0.1.0", title: "PHI in transit must be TLS 1.2+", text: "tls" }],
    changes: async () => [],
    github: async () => [{ kind: "pr", ref: "#16", title: "autonomy blast radius", href: "https://github.com/x/y/pull/16" }],
    isHighPhi: async (t) => /MRN/.test(t),
    ...over,
  };
}

describe("assistant grounding", () => {
  it("scopes retrieval to the viewed run BEFORE ranking", async () => {
    const { grounding } = await prepareContext(sources(), { message: "sla", view: { kind: "run-detail", id: "R1" } });
    const ledgerRefs = grounding.sources.filter((s) => s.kind === "ledger").map((s) => s.ref);
    expect(ledgerRefs).toEqual(["a"]);
    expect(grounding.sources[0]).toMatchObject({ kind: "run", ref: "R1", matched: "pinned by view" });
  });

  it("pulls in the rule a selected decision cites", async () => {
    const { grounding } = await prepareContext(sources(), { message: "sla", view: { kind: "run-detail", id: "R1" } });
    expect(grounding.sources.some((s) => s.kind === "rule" && s.ref === "security/v0.1.0/PHI-002")).toBe(true);
  });

  it("withholds high-PHI excerpts from the prompt and says so", async () => {
    const { prompt, grounding } = await prepareContext(sources(), { message: "classify MRN phi", view: { kind: "decisions" } });
    expect(grounding.sources.some((s) => s.ref === "c")).toBe(false);
    expect(grounding.withheld).toEqual({ count: 1, rule: "security/v0.1.0/PHI-001" });
    expect(prompt).not.toMatch(/Classify MRN/);
  });

  it("fails closed when the PHI classifier errors", async () => {
    const { grounding } = await prepareContext(
      sources({ isHighPhi: async () => { throw new Error("down"); } }),
      { message: "sla", view: { kind: "decisions" } },
    );
    expect(grounding.sources.filter((s) => s.kind === "ledger")).toHaveLength(0);
    expect(grounding.withheld?.count).toBeGreaterThan(0);
  });

  it("degrades with a warning instead of inventing when a source is down", async () => {
    const { grounding } = await prepareContext(
      sources({ github: async () => { throw new Error("rate limited"); } }),
      { message: "sla", view: { kind: "decisions" } },
    );
    expect(grounding.degraded).toBe(true);
    expect(grounding.warnings.join(" ")).toMatch(/GitHub unavailable/);
    expect(grounding.sources.some((s) => s.kind === "github")).toBe(false);
  });

  it("computes derived facts from the record, labelled as such", async () => {
    const { prompt, grounding } = await prepareContext(sources(), { message: "status", view: { kind: "dashboard" } });
    expect(grounding.derived.join(" ")).toMatch(/1 waiting on a human gate, 1 failed \(1 blocked by policy\)/);
    expect(prompt).toMatch(/computed from the record/);
  });

  it("grounding off sends the message verbatim", async () => {
    const { prompt, grounding } = await prepareContext(sources(), { message: "hi", view: { kind: "dashboard" }, ground: false });
    expect(prompt).toBe("hi");
    expect(grounding.sources).toHaveLength(0);
  });

  it("rank ignores stopwords and prefers rarer terms", () => {
    const r = rank("why is the sla binding", ["sla binding", "the why is"], (s) => s, 5);
    expect(r[0].item).toBe("sla binding");
    expect(r).toHaveLength(1);
  });
});
