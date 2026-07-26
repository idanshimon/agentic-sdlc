/* Autonomy governance projection.
 *
 * The autonomous PR review loop (msp durable store) is a SEPARATE mechanism
 * from per-decision autonomy governance, and on most tenants it has never run
 * — /api/review-loops returns zero items. That left this page empty even though
 * the ledger records, on every single decision, WHICH autonomy rule decided
 * whether an agent could act alone.
 *
 * That rule is stamped in `autonomy_ref`:
 *
 *   autonomy/mode/bootstrap/scope-resolution/autopilot:autopilot-mode
 *   autonomy/invariant/phi-classification/gate:phi-auth-hard-lock
 *   └─ family ─┘└ scope ┘└─ ambiguity class ─┘└ outcome ┘└── rule id ──┘
 *
 * Parsing it answers the question the page exists to answer: where is the
 * agent trusted to act alone, where is it stopped, and by which rule. This is
 * derived from data already in the ledger — nothing is invented.
 */
import type { LedgerEntry } from "./types";

export type AutonomyFamily = "invariant" | "mode" | "other";
export type AutonomyOutcome = "autopilot" | "gate" | "other";

export interface AutonomyRef {
  family: AutonomyFamily;
  scope?: string;
  ambiguityClass?: string;
  outcome: AutonomyOutcome;
  ruleId: string;
  raw: string;
}

export interface AutonomyRule {
  /** The raw autonomy_ref — stable identity for this rule. */
  ref: string;
  family: AutonomyFamily;
  outcome: AutonomyOutcome;
  ruleId: string;
  ambiguityClass: string;
  /** Decisions governed by this rule. */
  entries: LedgerEntry[];
  decisionCount: number;
  runCount: number;
  humanCount: number;
  agentCount: number;
  firstSeen: string;
  lastSeen: string;
  /** Plain-language explanation of what this rule did. */
  explanation: string;
}

export interface AutonomySummary {
  rules: AutonomyRule[];
  totalGoverned: number;
  autopilotCount: number;
  gatedCount: number;
  invariantCount: number;
  /** Share of governed decisions the agent was allowed to make alone. */
  autonomyPct: number;
}

/** Parse an autonomy_ref into its parts. Tolerant of unknown shapes. */
export function parseAutonomyRef(raw: string | undefined | null): AutonomyRef | null {
  if (!raw) return null;
  const [path, ruleId = ""] = raw.split(":");
  const parts = path.split("/").filter(Boolean);
  if (parts[0] !== "autonomy" || parts.length < 3) {
    return { family: "other", outcome: "other", ruleId: ruleId || raw, raw };
  }
  const familyRaw = parts[1];
  const family: AutonomyFamily =
    familyRaw === "invariant" ? "invariant" : familyRaw === "mode" ? "mode" : "other";
  const outcomeRaw = parts[parts.length - 1];
  const outcome: AutonomyOutcome =
    outcomeRaw === "autopilot" ? "autopilot" : outcomeRaw === "gate" ? "gate" : "other";
  // mode/<scope>/<class>/<outcome>  |  invariant/<class>/<outcome>
  const ambiguityClass = family === "mode" ? parts[3] : parts[2];
  const scope = family === "mode" ? parts[2] : undefined;
  return { family, scope, ambiguityClass, outcome, ruleId: ruleId || outcomeRaw, raw };
}

function explain(ref: AutonomyRef, agentCount: number, humanCount: number): string {
  const cls = ref.ambiguityClass ?? "this class";
  if (ref.family === "invariant" && ref.outcome === "gate") {
    return `Hard lock. "${cls}" can never be auto-resolved — a human must rule on it every time, no matter how much precedent exists. Enforced ${humanCount + agentCount} times.`;
  }
  if (ref.outcome === "autopilot") {
    return `The agent is trusted to resolve "${cls}" on its own. It did so ${agentCount} time${agentCount === 1 ? "" : "s"}.`;
  }
  if (ref.outcome === "gate") {
    return `"${cls}" stops for a human. ${humanCount} decision${humanCount === 1 ? "" : "s"} went to a person rather than being auto-resolved.`;
  }
  return `Governs "${cls}".`;
}

export function projectAutonomy(entries: LedgerEntry[]): AutonomySummary {
  const byRef = new Map<string, LedgerEntry[]>();
  for (const e of entries) {
    const raw = e.autonomy_ref;
    if (!raw) continue;
    byRef.set(raw, [...(byRef.get(raw) ?? []), e]);
  }

  const rules: AutonomyRule[] = [];
  for (const [ref, list] of byRef) {
    const parsed = parseAutonomyRef(ref);
    if (!parsed) continue;
    const sorted = [...list].sort((a, b) =>
      (a.created_at || "").localeCompare(b.created_at || ""),
    );
    const humanCount = sorted.filter(
      (e) => e.confidence_source === "human" || e.actor?.kind === "human",
    ).length;
    const agentCount = sorted.filter((e) => e.confidence_source === "autopilot").length;
    rules.push({
      ref,
      family: parsed.family,
      outcome: parsed.outcome,
      ruleId: parsed.ruleId,
      ambiguityClass: parsed.ambiguityClass ?? "unknown",
      entries: sorted,
      decisionCount: sorted.length,
      runCount: new Set(sorted.map((e) => e.run_id).filter(Boolean)).size,
      humanCount,
      agentCount,
      firstSeen: sorted[0]?.created_at ?? "",
      lastSeen: sorted[sorted.length - 1]?.created_at ?? "",
      explanation: explain(parsed, agentCount, humanCount),
    });
  }

  // Invariants first (they're the hard constraints), then by volume.
  rules.sort((a, b) => {
    if (a.family !== b.family) return a.family === "invariant" ? -1 : 1;
    return b.decisionCount - a.decisionCount;
  });

  const totalGoverned = rules.reduce((n, r) => n + r.decisionCount, 0);
  const autopilotCount = rules
    .filter((r) => r.outcome === "autopilot")
    .reduce((n, r) => n + r.decisionCount, 0);
  const gatedCount = rules
    .filter((r) => r.outcome === "gate")
    .reduce((n, r) => n + r.decisionCount, 0);
  const invariantCount = rules.filter((r) => r.family === "invariant").length;

  return {
    rules,
    totalGoverned,
    autopilotCount,
    gatedCount,
    invariantCount,
    autonomyPct: totalGoverned ? Math.round((autopilotCount / totalGoverned) * 100) : 0,
  };
}
