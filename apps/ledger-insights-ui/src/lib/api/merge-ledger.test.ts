import { describe, it, expect } from "vitest";
import { mergeLedgerEntries } from "./merge-ledger";
import type { LedgerEntry } from "../types";

// Minimal ledger-entry factory — only the fields the merge touches.
function e(id: string, created_at: string): LedgerEntry {
  return { id, created_at } as unknown as LedgerEntry;
}

describe("mergeLedgerEntries", () => {
  it("a fresh live entry surfaces at the TOP, above older demo seeds (the bug)", () => {
    const demo = [e("d1", "2026-07-06T10:00:00Z"), e("d2", "2026-07-06T09:00:00Z")];
    const live = [e("live1", "2026-07-08T20:00:00Z")]; // just now
    const merged = mergeLedgerEntries(demo, live);
    expect(merged[0].id).toBe("live1"); // newest first, not appended below demo
  });

  it("sorts strictly newest-first by created_at across both sources", () => {
    const demo = [e("d1", "2026-07-01T00:00:00Z")];
    const live = [e("l1", "2026-07-05T00:00:00Z"), e("l2", "2026-07-03T00:00:00Z")];
    const merged = mergeLedgerEntries(demo, live);
    expect(merged.map((m) => m.id)).toEqual(["l1", "l2", "d1"]);
  });

  it("de-dupes by id with live winning over demo", () => {
    const demo = [e("shared", "2026-07-01T00:00:00Z")];
    const live = [e("shared", "2026-07-08T00:00:00Z")];
    const merged = mergeLedgerEntries(demo, live);
    expect(merged).toHaveLength(1);
    expect(merged[0].created_at).toBe("2026-07-08T00:00:00Z"); // live value kept
  });

  it("empty live -> returns sorted demo (offline fallback, no crash)", () => {
    const demo = [e("d2", "2026-07-06T09:00:00Z"), e("d1", "2026-07-06T10:00:00Z")];
    const merged = mergeLedgerEntries(demo, []);
    expect(merged.map((m) => m.id)).toEqual(["d1", "d2"]);
  });

  it("empty demo -> returns sorted live", () => {
    const live = [e("l1", "2026-07-08T00:00:00Z")];
    expect(mergeLedgerEntries([], live).map((m) => m.id)).toEqual(["l1"]);
  });

  it("keeps id-less entries instead of collapsing them into one", () => {
    const demo = [
      { created_at: "2026-07-01T00:00:00Z" } as unknown as LedgerEntry,
      { created_at: "2026-07-02T00:00:00Z" } as unknown as LedgerEntry,
    ];
    const merged = mergeLedgerEntries(demo, []);
    expect(merged).toHaveLength(2); // both retained, not de-duped away
  });
});
