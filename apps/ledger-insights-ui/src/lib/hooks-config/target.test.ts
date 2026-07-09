import { describe, it, expect } from "vitest";
import { deriveHookTarget, MODE_LABEL } from "./target";

describe("deriveHookTarget (what service a hook controls)", () => {
  it("PreToolUse is the enforcing PHI guard", () => {
    const t = deriveHookTarget("PreToolUse");
    expect(t.service).toMatch(/PHI/i);
    expect(t.mode).toBe("enforcing");
    expect(t.href).toBe("/phi");
  });

  it("PostToolUse / SessionEnd / UserPromptSubmit feed the Decision Ledger (observe only)", () => {
    for (const ev of ["PostToolUse", "SessionEnd", "UserPromptSubmit"] as const) {
      const t = deriveHookTarget(ev);
      expect(t.service).toMatch(/Ledger/i);
      expect(t.mode).toBe("observing");
      expect(t.href).toBe("/decisions");
    }
  });

  it("SessionStart injects bundles + AGENTS.md context", () => {
    const t = deriveHookTarget("SessionStart");
    expect(t.service).toMatch(/Bundles|AGENTS/i);
    expect(t.mode).toBe("injecting");
    expect(t.href).toBe("/bundles");
  });

  it("Notification notifies the operator and does not block", () => {
    const t = deriveHookTarget("Notification");
    expect(t.mode).toBe("notifying");
  });

  it("an explicit `controls` field overrides the derived service", () => {
    const t = deriveHookTarget("PostToolUse", { explicitControls: "Custom Sink X" });
    expect(t.service).toBe("Custom Sink X");
  });

  it("unknown events degrade safely to observing", () => {
    const t = deriveHookTarget("SomethingNew");
    expect(t.mode).toBe("observing");
    expect(t.service).toBe("Unknown surface");
  });

  it("every mode has a human label", () => {
    for (const m of ["enforcing", "observing", "injecting", "notifying"] as const) {
      expect(MODE_LABEL[m]).toBeTruthy();
    }
  });
});
