import { describe, it, expect } from "vitest";
import { buildRunOptions, filterRunOptions } from "./run-options";
import type { LedgerEntry } from "./types";

const NOW = Date.parse("2026-07-26T12:00:00Z");
const iso = (msAgo: number) => new Date(NOW - msAgo).toISOString();

function e(over: Partial<LedgerEntry>): LedgerEntry {
  return {
    id: Math.random().toString(36).slice(2),
    entry_type: "runtime",
    actor: { kind: "agent", id: "a" },
    decision: "",
    rationale: "",
    phi_class: "none",
    cost_usd: 0,
    model_used: "",
    bundle_refs: [],
    created_at: iso(60_000),
    ...over,
  } as LedgerEntry;
}

describe("buildRunOptions", () => {
  const entries = [
    e({ run_id: "aaaaaaaa-1111-2222-3333-444444444444", team_id: "team-cardiology", ambiguity_class: "phi-classification", created_at: iso(60_000) }),
    e({ run_id: "aaaaaaaa-1111-2222-3333-444444444444", team_id: "team-cardiology", ambiguity_class: "sla-binding", created_at: iso(120_000) }),
    e({ run_id: "bbbbbbbb-5555-6666-7777-888888888888", team_id: "team-oncology", ambiguity_class: "auth-policy", created_at: iso(3 * 86_400_000) }),
  ];

  it("produces one option per distinct run", () => {
    expect(buildRunOptions(entries, { now: NOW })).toHaveLength(2);
  });

  it("labels a run with time, team, size and subject — not just a UUID", () => {
    const [first] = buildRunOptions(entries, { now: NOW });
    expect(first.label).toContain("just now");
    expect(first.label).toContain("cardiology");
    expect(first.label).toContain("2 decisions");
    expect(first.label).toContain("phi-classification");
  });

  it("strips the team- prefix — operators say 'cardiology'", () => {
    const [first] = buildRunOptions(entries, { now: NOW });
    expect(first.label).not.toContain("team-cardiology");
  });

  it("still exposes a short id so the label stays anchored to the run", () => {
    const [first] = buildRunOptions(entries, { now: NOW });
    expect(first.shortId).toBe("aaaaaaaa");
    expect(first.label).toContain("aaaaaaaa");
  });

  it("orders newest-first", () => {
    const opts = buildRunOptions(entries, { now: NOW });
    expect(opts[0].runId.startsWith("aaaaaaaa")).toBe(true);
    expect(opts[1].runId.startsWith("bbbbbbbb")).toBe(true);
  });

  it("surfaces a flagged count when a decision was flagged", () => {
    const flagged = [
      ...entries,
      e({ run_id: "aaaaaaaa-1111-2222-3333-444444444444", runtime_kind: "decision_flagged" }),
    ];
    const [first] = buildRunOptions(flagged, { now: NOW });
    expect(first.flaggedCount).toBe(1);
    expect(first.label).toContain("1 flagged");
  });

  it("ignores entries with no run_id rather than inventing a bucket", () => {
    expect(buildRunOptions([...entries, e({ run_id: undefined })], { now: NOW })).toHaveLength(2);
  });
});

describe("filterRunOptions", () => {
  const opts = buildRunOptions(
    [
      e({ run_id: "aaaaaaaa-1111", team_id: "team-cardiology", ambiguity_class: "phi-classification" }),
      e({ run_id: "bbbbbbbb-5555", team_id: "team-oncology", ambiguity_class: "sla-binding" }),
    ],
    { now: NOW },
  );

  it("returns everything for an empty query", () => {
    expect(filterRunOptions(opts, "")).toHaveLength(2);
    expect(filterRunOptions(opts, "   ")).toHaveLength(2);
  });

  it("matches on team name", () => {
    const r = filterRunOptions(opts, "oncology");
    expect(r).toHaveLength(1);
    expect(r[0].runId).toContain("bbbbbbbb");
  });

  it("matches on ambiguity class", () => {
    expect(filterRunOptions(opts, "phi")).toHaveLength(1);
  });

  it("still matches a pasted full UUID — machines paste ids", () => {
    expect(filterRunOptions(opts, "aaaaaaaa-1111")).toHaveLength(1);
  });

  it("ANDs multiple terms so more words narrow the result", () => {
    expect(filterRunOptions(opts, "cardiology phi")).toHaveLength(1);
    expect(filterRunOptions(opts, "cardiology sla")).toHaveLength(0);
  });

  it("is case-insensitive", () => {
    expect(filterRunOptions(opts, "ONCOLOGY")).toHaveLength(1);
  });
});
