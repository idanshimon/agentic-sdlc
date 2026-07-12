import { describe, expect, it } from "vitest";
import { projectArtifactsFromEvents } from "./artifacts";
import type { StageEvent } from "./types";

function ev(stage: string, status: StageEvent["status"], payload: Record<string, unknown>): StageEvent {
  return { stage: stage as StageEvent["stage"], status, payload };
}

describe("projectArtifactsFromEvents", () => {
  it("projects every live pipeline artifact from producer payloads", () => {
    const projected = projectArtifactsFromEvents([
      ev("architect", "completed", { architecture: "# Architecture" }),
      ev("test_plan", "completed", { test_plan: "# Test plan" }),
      ev("codegen", "completed", { app_code: "APP", test_code: "PYTEST", code: "LEGACY" }),
      ev("deliver", "completed", {
        decisions_md: "# Decisions",
        decisions_md_url: "https://github.com/o/r/blob/x/decisions.md",
        pr_url: "https://github.com/o/r/pull/1",
        delivery_status: "delivered",
        artifact_files: ["src/main.py", "tests/test_main.py"],
      }),
    ]);

    expect(projected.architecture).toBe("# Architecture");
    expect(projected.testPlan).toBe("# Test plan");
    expect(projected.implementation).toBe("APP");
    expect(projected.tests).toBe("PYTEST");
    expect(projected.decisionsMd).toBe("# Decisions");
    expect(projected.decisionsMdUrl).toContain("decisions.md");
    expect(projected.prUrl).toContain("/pull/1");
    expect(projected.deliveryStatus).toBe("delivered");
    expect(projected.artifactFiles).toEqual(["src/main.py", "tests/test_main.py"]);
  });

  it("uses the newest non-empty artifact and falls back to legacy code", () => {
    const projected = projectArtifactsFromEvents([
      ev("architect", "completed", { architecture: "v1" }),
      ev("architect", "completed", { architecture: "" }),
      ev("architect", "completed", { architecture: "v2" }),
      ev("codegen", "completed", { code: "LEGACY" }),
    ]);

    expect(projected.architecture).toBe("v2");
    expect(projected.implementation).toBe("LEGACY");
    expect(projected.tests).toBe("");
  });

  it("returns an empty projection for no events", () => {
    expect(projectArtifactsFromEvents([])).toEqual({
      architecture: "",
      testPlan: "",
      implementation: "",
      tests: "",
      decisionsMd: "",
      decisionsMdUrl: "",
      prUrl: "",
      deliveryStatus: "",
      deliveryReason: "",
      artifactFiles: [],
    });
  });
});
