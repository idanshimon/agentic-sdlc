/* Tests for the demo store cache, LRU eviction, and clearDemoRuns.
 *
 * These cover the renderer-OOM regression caught on 2026-06-08:
 * - localStorage parse was called on every gatherContext() (every render),
 *   causing O(N) JSON.parse work that eventually killed the tab.
 * - Demo runs accumulated unboundedly because there was no eviction.
 * - clearDemoRuns dispatched an unused custom event but did not invalidate
 *   any in-process cache.
 *
 * Spec reference: openspec/changes/fix-demo-store-renderer-oom/specs/demo-store/spec.md
 */
import { describe, it, expect, beforeEach, vi } from "vitest";
import {
  listDemoRuns,
  getDemoRun,
  listDemoLedgerEntries,
  clearDemoRuns,
  startDemoRun,
} from "./index";

const STORAGE_KEY = "agentic-sdlc.demo.runs";

function seedStore(store: Record<string, unknown>) {
  globalThis.localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
}

beforeEach(() => {
  globalThis.localStorage.clear();
});

describe("REQ-1: loadStore is memoized by raw-string identity", () => {
  it("re-parses only when the stored string changes", () => {
    seedStore({
      "demo-a": {
        scenario_id: "vitals",
        run_id: "demo-a",
        team_id: "cardiology",
        status: "running",
        current_stage: "ingest",
        events: [],
        created_at: "2026-06-08T00:00:00Z",
        updated_at: "2026-06-08T00:00:00Z",
        cost_usd: 0,
        decisions_count: 0,
        ledger_entries: [],
      },
    });
    const parseSpy = vi.spyOn(JSON, "parse");

    // Three reads back-to-back — only the first should parse.
    listDemoRuns();
    listDemoRuns();
    listDemoRuns();
    const callsAfterReads = parseSpy.mock.calls.length;

    // Mutate underlying storage; next read MUST re-parse.
    seedStore({
      "demo-b": {
        scenario_id: "vitals",
        run_id: "demo-b",
        team_id: "cardiology",
        status: "running",
        current_stage: "ingest",
        events: [],
        created_at: "2026-06-08T00:01:00Z",
        updated_at: "2026-06-08T00:01:00Z",
        cost_usd: 0,
        decisions_count: 0,
        ledger_entries: [],
      },
    });
    const before = parseSpy.mock.calls.length;
    listDemoRuns();
    listDemoRuns();
    const after = parseSpy.mock.calls.length;

    expect(callsAfterReads).toBeLessThanOrEqual(1);
    expect(after - before).toBeLessThanOrEqual(1);
    parseSpy.mockRestore();
  });

  it("survives corrupted JSON without throwing", () => {
    globalThis.localStorage.setItem(STORAGE_KEY, "{not json");
    expect(() => listDemoRuns()).not.toThrow();
    expect(listDemoRuns()).toEqual([]);
  });
});

describe("REQ-2: store is capped at MAX_DEMO_RUNS via LRU eviction", () => {
  it("never exceeds 10 stored runs after consecutive starts", () => {
    // Start 15 runs back to back. Each start writes via saveStore which
    // applies the cap. The newest 10 must survive.
    const ids: string[] = [];
    for (let i = 0; i < 15; i++) {
      const id = startDemoRun("vitals");
      ids.push(id);
    }
    const runs = listDemoRuns();
    expect(runs.length).toBeLessThanOrEqual(10);
    // Newest 10 created should be present.
    const survivingIds = new Set(runs.map((r) => r.run_id));
    for (const recent of ids.slice(-10)) {
      expect(survivingIds.has(recent)).toBe(true);
    }
  });
});

describe("REQ-3: clearDemoRuns wipes both localStorage and the in-process cache", () => {
  it("returns empty after clear, even if a stale parse was cached", () => {
    seedStore({
      "demo-stale": {
        scenario_id: "vitals",
        run_id: "demo-stale",
        team_id: "cardiology",
        status: "running",
        current_stage: "ingest",
        events: [],
        created_at: "2026-06-08T00:00:00Z",
        updated_at: "2026-06-08T00:00:00Z",
        cost_usd: 0,
        decisions_count: 0,
        ledger_entries: [],
      },
    });
    // Prime the cache.
    expect(listDemoRuns().length).toBe(1);
    expect(getDemoRun("demo-stale")).toBeDefined();

    clearDemoRuns();

    // Both reads MUST see the empty post-clear state immediately.
    expect(listDemoRuns()).toEqual([]);
    expect(getDemoRun("demo-stale")).toBeUndefined();
    expect(listDemoLedgerEntries()).toEqual([]);
  });
});
