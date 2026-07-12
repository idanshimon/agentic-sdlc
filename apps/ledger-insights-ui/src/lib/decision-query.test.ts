import { describe, expect, it } from "vitest";
import { parseDecisionQuery, serializeDecisionQuery } from "./decision-query";

describe("decision query state", () => {
  it("parses supported URL filters and ignores empty values", () => {
    expect(parseDecisionQuery(new URLSearchParams("run=r-123&team=team-a&stage=review_scan&q=&unknown=x"))).toEqual({
      run: "r-123",
      team: "team-a",
      stage: "review_scan",
    });
  });

  it("serializes only defined supported filters", () => {
    expect(serializeDecisionQuery({ run: "r-123", phi: "high", q: "auth policy" }).toString())
      .toBe("run=r-123&phi=high&q=auth+policy");
  });
});
