import { describe, expect, it } from "vitest";
import { ApiError, operatorErrorMessage } from "./orchestrator";

describe("operator conflict messages", () => {
  it("turns stale gate conflict into a refresh instruction", () => {
    const message = operatorErrorMessage(new ApiError(409, "conflict", "stale_gate_version"));
    expect(message).toBe("This gate changed in another session. Refresh before deciding again.");
  });

  it("turns idempotency conflict into a safe retry instruction", () => {
    const message = operatorErrorMessage(new ApiError(409, "conflict", "idempotency_conflict"));
    expect(message).toContain("Refresh and retry");
  });
});
