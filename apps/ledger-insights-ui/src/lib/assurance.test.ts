import { describe, expect, it } from "vitest";
import { deriveAssurance } from "./assurance";

describe("assurance dimensions", () => {
  it("does not call partial verification fully verified", () => {
    const assurance = deriveAssurance({ deterministic_policy: "pass" });
    expect(assurance.deterministicPolicy).toBe("pass");
    expect(assurance.buildTests).toBe("unknown");
    expect(assurance.fullyVerified).toBe(false);
  });

  it("requires every dimension to pass", () => {
    const assurance = deriveAssurance({
      deterministic_policy: "pass",
      build_tests: "pass",
      dependency_security: "pass",
      semantic_review: "pass",
      mandatory_human: "pass",
    });
    expect(assurance.fullyVerified).toBe(true);
  });
});
