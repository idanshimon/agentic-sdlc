import { describe, it, expect } from "vitest";
import { composeLegacySettings } from "./settings-compose";

const fail = (error: string) => ({ ok: false as const, error });

describe("composeLegacySettings", () => {
  it("builds governance, pins and repo autonomy from the old endpoints", () => {
    const r = composeLegacySettings({
      hardGate: { ok: true, data: { hard_gate_classes: ["auth-policy"], floor: ["auth-policy"] } },
      pins: { ok: true, data: { defaults: { security: "v0.1.0" } } },
      repoAutonomy: { ok: true, data: { bootstrap: true, default_tier: "C", repos: [] } },
      integrations: fail("/api/integrations returned 404"),
    });
    const by = Object.fromEntries(r.sections.map((s) => [s.section, s]));
    expect(by.governance).toMatchObject({ status: "ok", hard_gate_classes: ["auth-policy"], editable: "governed_pr_only" });
    expect(by.standards_pins).toMatchObject({ status: "ok", activation: "activated" });
    expect(by.repo_autonomy).toMatchObject({ status: "ok", activation: "bootstrap" });
    expect(r.composed).toBe(true);
  });

  it("never reports an unavailable section as empty-but-ok", () => {
    const r = composeLegacySettings({
      hardGate: fail("x"), pins: fail("x"), repoAutonomy: fail("x"), integrations: fail("y"),
    });
    for (const s of r.sections) expect(s.status).toBe("error");
    expect(r.sections.find((s) => s.section === "organization")?.error).toMatch(/upgrade the orchestrator/);
  });
});
