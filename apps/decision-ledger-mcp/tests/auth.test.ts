import { describe, it, expect, beforeEach } from "vitest";
import { authenticate, loadTokenMap } from "../src/auth.js";

describe("auth", () => {
  beforeEach(() => {
    loadTokenMap({ LEDGER_MCP_TOKENS: JSON.stringify({ "tok-a": "team-x", "tok-b": "team-y" }) });
  });

  it("rejects missing Authorization header", () => {
    expect(() => authenticate(undefined)).toThrow(/Authorization/);
  });

  it("rejects malformed header", () => {
    expect(() => authenticate("Basic something")).toThrow(/Authorization/);
  });

  it("rejects unknown token", () => {
    expect(() => authenticate("Bearer unknown")).toThrow(/Invalid bearer token/);
  });

  it("accepts valid token + returns team_id", () => {
    expect(authenticate("Bearer tok-a")).toBe("team-x");
    expect(authenticate("Bearer tok-b")).toBe("team-y");
  });
});
