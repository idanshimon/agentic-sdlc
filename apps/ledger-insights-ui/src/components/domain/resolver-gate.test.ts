/**
 * Unit tests for the resolver-gate tier-2 + teaching-loop logic.
 *
 * Component-render tests aren't used here (the codebase has no
 * @testing-library/react setup — existing tests are logic-only). Instead we
 * test the pure helpers that the approve handlers delegate to: the hard-gate
 * bulk-skip filter and the PHI soft-warn. These are the load-bearing governance
 * decisions; the handlers just call them.
 */
import { describe, it, expect } from "vitest";
import { phiSoftWarn, bulkApprovableCards, gateProgress } from "./resolver-gate";

describe("phiSoftWarn", () => {
  it("returns false for empty / undefined / policy-level text", () => {
    expect(phiSoftWarn(undefined)).toBe(false);
    expect(phiSoftWarn("")).toBe(false);
    expect(phiSoftWarn("Retain logs 7 years per HIPAA §164.530(j).")).toBe(false);
  });

  it("warns on an SSN pattern", () => {
    expect(phiSoftWarn("patient ssn 123-45-6789 must be redacted")).toBe(true);
  });

  it("warns on an MRN pattern", () => {
    expect(phiSoftWarn("see MRN: 0099123 for details")).toBe(true);
    expect(phiSoftWarn("MRN#4521")).toBe(true);
  });

  it("warns on a DOB pattern", () => {
    expect(phiSoftWarn("DOB 03/14/1981 on file")).toBe(true);
  });
});

describe("bulkApprovableCards (tier-2 hard-gate filter)", () => {
  const mk = (card_id: string, is_hard_gated = false) => ({ card_id, is_hard_gated });

  it("excludes hard-gated cards from bulk approve", () => {
    const gating = [mk("a"), mk("phi", true), mk("b")];
    const result = bulkApprovableCards(gating, {});
    expect(result.map((c) => c.card_id)).toEqual(["a", "b"]);
  });

  it("excludes already-decided cards", () => {
    const gating = [mk("a"), mk("b"), mk("c")];
    const result = bulkApprovableCards(gating, { b: { label: "x", custom: false } });
    expect(result.map((c) => c.card_id)).toEqual(["a", "c"]);
  });

  it("excludes both hard-gated AND decided", () => {
    const gating = [mk("a"), mk("phi", true), mk("c")];
    const result = bulkApprovableCards(gating, { a: {} });
    expect(result.map((c) => c.card_id)).toEqual(["c"]);
  });

  it("returns empty when every card is hard-gated", () => {
    const gating = [mk("phi1", true), mk("auth", true)];
    expect(bulkApprovableCards(gating, {})).toEqual([]);
  });

  it("skips cards with no card_id (cannot be approved)", () => {
    const gating: Array<{ card_id?: string; is_hard_gated?: boolean }> = [
      { is_hard_gated: false },
      mk("b"),
    ];
    const result = bulkApprovableCards(gating, {});
    expect(result.map((c) => c.card_id)).toEqual(["b"]);
  });
});

describe("gateProgress (primary-button label + next-action state)", () => {
  const mk = (card_id: string, is_hard_gated = false) => ({ card_id, is_hard_gated });

  it("no cards decided, none hard-gated -> Approve all recommended, partial-off", () => {
    const p = gateProgress([mk("a"), mk("b")], {});
    expect(p.primaryLabel).toBe("Approve all recommended");
    expect(p.primaryDisabled).toBe(false);
    expect(p.allDecided).toBe(false);
    expect(p.phase).toBe("none");
  });

  it("some decided but not all -> still Approve all recommended, phase=partial", () => {
    const p = gateProgress([mk("a"), mk("b"), mk("c")], { a: { label: "x" } });
    expect(p.decidedCount).toBe(1);
    expect(p.primaryLabel).toBe("Approve all recommended");
    expect(p.phase).toBe("partial");
    expect(p.allDecided).toBe(false);
  });

  it("ALL cards decided -> Finalize & advance (the fix), phase=all-decided", () => {
    const p = gateProgress([mk("a"), mk("b")], { a: {}, b: {} });
    expect(p.primaryLabel).toBe("Finalize & advance");
    expect(p.primaryDisabled).toBe(false);
    expect(p.allDecided).toBe(true);
    expect(p.phase).toBe("all-decided");
  });

  it("hard-gated card decided individually + rest recommended-ready still shows Finalize once all decided", () => {
    // The exact reported scenario: PHI card decided, other 4 also decided.
    const cards = [mk("phi", true), mk("a"), mk("b"), mk("c"), mk("d")];
    const p = gateProgress(cards, { phi: {}, a: {}, b: {}, c: {}, d: {} });
    expect(p.allDecided).toBe(true);
    expect(p.primaryLabel).toBe("Finalize & advance");
  });

  it("only a hard-gated card remains undecided -> button locked with guidance", () => {
    const cards = [mk("phi", true), mk("a"), mk("b")];
    const p = gateProgress(cards, { a: {}, b: {} });
    expect(p.onlyHardGatedRemain).toBe(true);
    expect(p.undecidedHardGatedCount).toBe(1);
    expect(p.primaryLabel).toBe("Decide the locked card to continue");
    expect(p.primaryDisabled).toBe(true);
    expect(p.phase).toBe("hard-gated");
  });

  it("undecided mix of hard-gated + normal -> NOT locked (normal ones bulk-approvable)", () => {
    const cards = [mk("phi", true), mk("a"), mk("b")];
    const p = gateProgress(cards, {}); // nothing decided
    expect(p.onlyHardGatedRemain).toBe(false);
    expect(p.primaryLabel).toBe("Approve all recommended");
    expect(p.primaryDisabled).toBe(false);
  });

  it("empty gating set is not 'allDecided' (guards a vacuous finalize)", () => {
    const p = gateProgress([], {});
    expect(p.allDecided).toBe(false);
    expect(p.phase).toBe("none");
  });
});
