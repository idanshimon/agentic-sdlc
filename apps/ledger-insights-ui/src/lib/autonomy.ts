/**
 * autonomy.ts — per-ambiguity-class autonomy model, derived from the flat
 * ledger + the live hard-gate floor.
 *
 * The teaching loop (see lineage.ts) proves the SYSTEM is learning. This module
 * answers the operator's three questions PER CLASS:
 *
 *   1. How does the agent improve?  → human decisions in a class become
 *      precedent; later hybrid runs reuse them (reuse count climbs).
 *   2. Where do I see it?           → each class sits on an autonomy rung:
 *      Floor (never auto) → Learning (has precedent, low reuse) →
 *      Trusted (reuse rate high) → Autonomous.
 *   3. How do I control it?         → the envelope: which classes MAY earn
 *      autonomy at all, and the immovable PHI/auth floor.
 *
 * Pure functions. No React, no I/O.
 */
import type { LedgerEntry } from "@/lib/types";
import {
  isStageDecision,
  isHumanSwap,
  isAutopilot,
} from "@/lib/lineage";

export type AutonomyRung = "floor" | "learning" | "trusted" | "autonomous";

export interface ClassAutonomy {
  ambiguityClass: string;
  /** Total stage decisions seen in this class. */
  total: number;
  /** Human decisions (operator owned this call). */
  humanCount: number;
  /** Agent (autopilot) decisions — the loop closing. */
  agentCount: number;
  /** Human swaps that became precedent. */
  taughtCount: number;
  /** Distinct ambiguity buckets that carry a human-taught precedent. */
  precedentBuckets: number;
  /** % of this class's decisions made autonomously. */
  autonomyPct: number;
  /** Is this class pinned to the floor (PHI/auth) — never auto-resolvable? */
  isFloor: boolean;
  /** Which rung the class currently sits on. */
  rung: AutonomyRung;
}

const RUNG_ORDER: Record<AutonomyRung, number> = {
  floor: 0,
  learning: 1,
  trusted: 2,
  autonomous: 3,
};

export function rungLabel(r: AutonomyRung): string {
  switch (r) {
    case "floor":
      return "Human-only floor";
    case "learning":
      return "Learning";
    case "trusted":
      return "Trusted";
    case "autonomous":
      return "Autonomous";
  }
}

export function rungTone(r: AutonomyRung): string {
  switch (r) {
    case "floor":
      return "var(--danger, #ef4444)";
    case "learning":
      return "var(--warning, #f59e0b)";
    case "trusted":
      return "var(--plane-ledger, #22c55e)";
    case "autonomous":
      return "var(--success, #10b981)";
  }
}

/**
 * Compute per-class autonomy from ledger entries + the live floor set.
 *
 * @param entries  Full ledger entries (stage decisions + teaching signals).
 * @param floor    Ambiguity classes that can NEVER auto-resolve (from the
 *                 /api/config/hard-gate-classes endpoint). PHI/auth by default.
 */
export function computeClassAutonomy(
  entries: LedgerEntry[],
  floor: Set<string>,
): ClassAutonomy[] {
  const stage = entries.filter(isStageDecision);
  const byClass = new Map<string, LedgerEntry[]>();
  for (const e of stage) {
    const c = e.ambiguity_class ?? "other";
    const arr = byClass.get(c) ?? [];
    arr.push(e);
    byClass.set(c, arr);
  }

  const out: ClassAutonomy[] = [];
  for (const [ambiguityClass, list] of byClass) {
    const total = list.length;
    const agentCount = list.filter(isAutopilot).length;
    const humanCount = total - agentCount;
    const taughtCount = list.filter(isHumanSwap).length;

    // distinct buckets that carry a human swap
    const taughtBuckets = new Set<string>();
    for (const e of list) {
      if (isHumanSwap(e) && e.slot_value_hash) taughtBuckets.add(e.slot_value_hash);
    }

    const isFloor = floor.has(ambiguityClass);
    const autonomyPct = total ? Math.round((agentCount / total) * 100) : 0;

    let rung: AutonomyRung;
    if (isFloor) {
      rung = "floor";
    } else if (taughtBuckets.size === 0 && agentCount === 0) {
      rung = "learning";
    } else if (autonomyPct >= 60) {
      rung = "autonomous";
    } else if (autonomyPct > 0 || taughtBuckets.size > 0) {
      rung = "trusted";
    } else {
      rung = "learning";
    }

    out.push({
      ambiguityClass,
      total,
      humanCount,
      agentCount,
      taughtCount,
      precedentBuckets: taughtBuckets.size,
      autonomyPct,
      isFloor,
      rung,
    });
  }

  // Floor classes first (they're the control story), then by autonomy desc.
  out.sort((a, b) => {
    if (a.isFloor !== b.isFloor) return a.isFloor ? -1 : 1;
    if (a.rung !== b.rung) return RUNG_ORDER[b.rung] - RUNG_ORDER[a.rung];
    return b.total - a.total;
  });
  return out;
}

/** Human-readable class label (kebab -> Title Case). */
export function classLabel(c: string): string {
  return c
    .split(/[-_]/)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}
