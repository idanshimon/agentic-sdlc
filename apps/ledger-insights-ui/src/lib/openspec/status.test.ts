import { describe, it, expect } from "vitest";
import { deriveStatus } from "./status";

describe("deriveStatus (honest OpenSpec change status)", () => {
  it("archived on disk is always merged, regardless of tasks/text", () => {
    expect(deriveStatus("DRAFT", true, 0, 0)).toBe("merged");
    expect(deriveStatus("DRAFT", true, 10, 3)).toBe("merged");
  });

  it("100% tasks checked -> ready to merge (the key fix: not 'draft' forever)", () => {
    expect(deriveStatus("DRAFT", false, 33, 33)).toBe("ready");
    expect(deriveStatus("DRAFT (2026-07-08)", false, 18, 18)).toBe("ready");
  });

  it("some but not all tasks checked -> in-progress", () => {
    expect(deriveStatus("DRAFT", false, 36, 31)).toBe("in-progress");
    expect(deriveStatus("DRAFT", false, 43, 20)).toBe("in-progress");
  });

  it("no tasks started -> draft", () => {
    expect(deriveStatus("DRAFT", false, 60, 0)).toBe("draft");
    expect(deriveStatus("DRAFT", false, 0, 0)).toBe("draft");
  });

  it("author text 'merged' / 'shipped' -> merged even in active dir", () => {
    expect(deriveStatus("MERGED 2026-06-08", false, 48, 48)).toBe("merged");
    expect(deriveStatus("Shipped to main", false, 0, 0)).toBe("merged");
  });

  it("'partially shipped' text -> in-progress (never mislabeled merged)", () => {
    expect(deriveStatus("PARTIALLY SHIPPED (2026-06-23)", false, 0, 0)).toBe("in-progress");
    // partially wins even if 'shipped' substring is present
    expect(deriveStatus("PARTIALLY SHIPPED", false, 20, 20)).toBe("in-progress");
  });

  it("tolerates empty / undefined status text", () => {
    expect(deriveStatus("", false, 0, 0)).toBe("draft");
    // @ts-expect-error runtime guard for null
    expect(deriveStatus(undefined, false, 5, 5)).toBe("ready");
  });
});
