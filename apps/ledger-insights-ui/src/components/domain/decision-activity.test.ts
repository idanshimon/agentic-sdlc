import { describe, expect, it } from "vitest";
import { classify, sentence } from "./decision-activity";
import type { LedgerEntry } from "@/lib/types";

const base: LedgerEntry = {
  id: "d-1",
  entry_type: "runtime",
  actor: { kind: "agent", id: "architect-agent" },
  decision: "Store consent as a boolean with a timestamp",
  rationale: "",
  phi_class: "none",
  cost_usd: 0,
  model_used: "gpt-x",
  bundle_refs: [],
  precedent_refs: [],
  created_at: "2026-07-12T00:00:00Z",
  stage: "resolver",
} as LedgerEntry;

describe("decision-activity classify", () => {
  it("classifies an agent stage decision", () => {
    expect(classify(base)).toBe("agent_decision");
  });

  it("classifies a human decision", () => {
    expect(classify({ ...base, actor: { kind: "human", id: "idan" } })).toBe("human_decision");
  });

  it("classifies autopilot reuse from confidence_source", () => {
    expect(classify({ ...base, confidence_source: "autopilot" })).toBe("reused");
  });

  it("classifies teaching signals", () => {
    expect(classify({ ...base, runtime_kind: "feedback_thumbs" })).toBe("taught");
    expect(classify({ ...base, runtime_kind: "decision_flagged" })).toBe("flagged");
    expect(classify({ ...base, runtime_kind: "class_paused" })).toBe("paused");
  });

  it("classifies delivery and convergence", () => {
    expect(classify({ ...base, runtime_kind: "delivered" })).toBe("delivered");
    expect(classify({ ...base, runtime_kind: "loop_converged" })).toBe("converged");
  });
});

describe("decision-activity sentence", () => {
  it("names the decision for an agent call and marks it autonomous", () => {
    const s = sentence(base, "agent_decision");
    expect(s).toContain("The agent resolved");
    expect(s).toContain("Store consent as a boolean");
    expect(s).toContain("on its own");
  });

  it("credits the human actor by id", () => {
    const s = sentence({ ...base, actor: { kind: "human", id: "idan" } }, "human_decision");
    expect(s).toContain("idan");
    expect(s).toContain("resolved");
  });

  it("explains autopilot reuse as a learned human decision", () => {
    const s = sentence({ ...base, confidence_source: "autopilot" }, "reused");
    expect(s.toLowerCase()).toContain("reusing a decision a human made");
  });

  it("never emits a raw undefined when decision text is missing", () => {
    const s = sentence({ ...base, decision: undefined, ambiguity_class: undefined } as unknown as LedgerEntry, "agent_decision");
    expect(s).not.toContain("undefined");
    expect(s).toContain("a pipeline decision");
  });
});
