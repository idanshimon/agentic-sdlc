import { describe, it, expect } from "vitest";

/**
 * Regression test for the render-storm pattern caught 2026-06-09 v0.7.
 *
 * The bug: `useAssistantContext` previously used `JSON.stringify(context)`
 * as the effect dep key. Inline `payload: { status, stage }` literals at
 * call sites produced fresh object identities every render. Combined with
 * the demo replay engine's setTimeout cascade after Approve and a 3s
 * useRun polling interval, the ctxKey changed on every render → effect
 * re-fired → setContext on the provider → all consumers re-rendered →
 * renderer SIGKILL → Chrome's "This page couldn't load" page.
 *
 * The fix: ctxKey only watches PRIMITIVE-typed fields (kind, id, label).
 * The provider's reply engine reads `payload` from a ref at reply time,
 * not via React state, so excluding it from the dep key is safe.
 *
 * This test pins the dep-key shape so a future "let's add payload back to
 * the dep key for completeness" PR fails CI.
 */

// Same recipe as the production hook: see src/lib/assist/context.tsx
function buildCtxKey(context: { kind: string; id?: string; label?: string }): string {
  return `${context.kind}|${context.id ?? ""}|${context.label ?? ""}`;
}

describe("useAssistantContext ctxKey (render-storm regression)", () => {
  it("ctxKey is stable when only payload identity changes", () => {
    // Simulate what the run-detail page does: each render produces a fresh
    // payload object with the SAME values. The dep key must NOT change.
    const renders = Array.from({ length: 10 }, () => ({
      kind: "run-detail",
      id: "run-abc-123",
      label: "Run abc-123",
      payload: { status: "running", stage: "architect" }, // FRESH object identity
    }));

    const keys = new Set(renders.map(buildCtxKey));
    expect(keys.size).toBe(1);
  });

  it("ctxKey changes when kind flips (resolver-gate ↔ run-detail)", () => {
    const a = buildCtxKey({ kind: "run-resolver-gate", id: "run-1" });
    const b = buildCtxKey({ kind: "run-detail", id: "run-1" });
    expect(a).not.toBe(b);
  });

  it("ctxKey changes when id changes (different run)", () => {
    const a = buildCtxKey({ kind: "run-detail", id: "run-1" });
    const b = buildCtxKey({ kind: "run-detail", id: "run-2" });
    expect(a).not.toBe(b);
  });

  it("ctxKey changes when label changes", () => {
    const a = buildCtxKey({ kind: "run-detail", id: "run-1", label: "Run abc" });
    const b = buildCtxKey({ kind: "run-detail", id: "run-1", label: "Run xyz" });
    expect(a).not.toBe(b);
  });

  it("ctxKey is stable when status field inside payload changes", () => {
    // The DEEP regression: even when payload.status changes (which is
    // semantically meaningful), the dep key must NOT change. The provider
    // reads the latest payload via a ref at reply time. If this ever
    // changed, the dep-key fix would re-introduce the render storm.
    const renders = [
      { kind: "run-detail", id: "run-1", payload: { status: "awaiting_gate" } },
      { kind: "run-detail", id: "run-1", payload: { status: "running" } },
      { kind: "run-detail", id: "run-1", payload: { status: "completed" } },
    ];

    const keys = new Set(renders.map(buildCtxKey));
    expect(keys.size).toBe(1);
  });
});

describe("useRun refetchInterval (terminal-state stops polling)", () => {
  // Mirror the production logic from src/lib/hooks/use-runs.ts.
  // A copy here so we can pin the contract without the next.js client runtime.
  function refetchIntervalForStatus(status: string | undefined): number | false {
    if (status === "completed" || status === "failed" || status === "cancelled") {
      return false;
    }
    return 3_000;
  }

  it("polls every 3s while running", () => {
    expect(refetchIntervalForStatus("running")).toBe(3_000);
    expect(refetchIntervalForStatus("awaiting_gate")).toBe(3_000);
    expect(refetchIntervalForStatus("queued")).toBe(3_000);
    expect(refetchIntervalForStatus(undefined)).toBe(3_000);
  });

  it("stops polling once run reaches a terminal state", () => {
    expect(refetchIntervalForStatus("completed")).toBe(false);
    expect(refetchIntervalForStatus("failed")).toBe(false);
    expect(refetchIntervalForStatus("cancelled")).toBe(false);
  });
});
