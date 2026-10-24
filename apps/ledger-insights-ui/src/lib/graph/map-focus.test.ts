import { describe, it, expect } from "vitest";
import { resolveMapFocus } from "./map-focus";
import type { LedgerEntry } from "@/lib/types";

const e = (p: Partial<LedgerEntry> & { id: string }): LedgerEntry =>
  ({ run_id: "r1", created_at: "2026-10-24T10:00:00Z", actor: { kind: "agent", id: "a" }, ...p }) as LedgerEntry;

describe("resolveMapFocus", () => {
  const entries = [
    e({ id: "a1" }),
    e({ id: "a2", confidence_source: "autopilot" }),
    e({ id: "h-old", card_id: "c1", confidence_source: "human", created_at: "2026-10-24T09:00:00Z" }),
    e({ id: "h-new", card_id: "c1", confidence_source: "human", created_at: "2026-10-24T11:00:00Z", precedent_id: "x" }),
    e({ id: "later", run_id: "r2", precedent_id: "h-new" }),
  ];

  it("picks the latest human decision for the card and counts its connections", () => {
    const f = resolveMapFocus(entries, "r1", "c1");
    expect(f).toMatchObject({ status: "found", entryId: "h-new", agentInRun: 2, humanInRun: 1, reusedBy: 1, reuses: 1 });
  });

  it("is pending when the ledger has not caught up with the run yet", () => {
    expect(resolveMapFocus(entries, "r9", "c1").status).toBe("pending");
  });

  it("is run-only when the run exists but no human decision for the card has landed", () => {
    expect(resolveMapFocus(entries, "r1", "c-missing")).toMatchObject({ status: "run-only", agentInRun: 2 });
  });

  it("does not treat an agent decision on the card as the operator's", () => {
    const f = resolveMapFocus([e({ id: "ag", card_id: "c2" })], "r1", "c2");
    expect(f.status).toBe("run-only");
  });
});
