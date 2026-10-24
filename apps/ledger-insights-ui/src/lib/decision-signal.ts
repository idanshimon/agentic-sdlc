/* Decision signal projections — pure, framework-free.
 *
 * One place that answers "who actually decided this?" and the time/class
 * rollups the Decisions command deck draws. Live Cosmos rows have no actor
 * object; the UI normalizer fills one with a default kind, so actor.kind
 * cannot be trusted on its own. `confidence_source` is the producer's explicit
 * record of who made the call and wins whenever present.
 */
import type { LedgerEntry } from "@/lib/types";

export const TEACHING_KINDS = new Set([
  "feedback_thumbs", "decision_flagged", "replay_requested", "class_paused",
]);

export type DecidedBy = "human" | "agent";

export function decidedBy(e: LedgerEntry): DecidedBy {
  if (e.confidence_source === "autopilot") return "agent";
  if (e.confidence_source === "human") return "human";
  const raw = e as unknown as { actor_kind?: string };
  if (raw.actor_kind === "human" || raw.actor_kind === "agent") return raw.actor_kind;
  return e.actor?.kind === "human" ? "human" : "agent";
}

/** Pipeline decisions only — operator teaching signals are not decisions. */
export function stageDecisions(entries: LedgerEntry[]): LedgerEntry[] {
  return entries.filter((e) => !e.runtime_kind || !TEACHING_KINDS.has(e.runtime_kind));
}

export interface DayBucket {
  day: string; // YYYY-MM-DD (UTC)
  human: number;
  agent: number;
  signals: number;
}

/** Daily human/agent counts over the span the data actually covers.
 *  Days with no activity inside the span are present as zeros (so the chart
 *  shows real gaps) but the span never extends past the data. */
export function dailyTimeline(entries: LedgerEntry[], maxDays = 60): DayBucket[] {
  const map = new Map<string, DayBucket>();
  let min = Infinity;
  let max = -Infinity;
  for (const e of entries) {
    const t = Date.parse(e.created_at);
    if (Number.isNaN(t)) continue;
    const day = new Date(t).toISOString().slice(0, 10);
    const b = map.get(day) ?? { day, human: 0, agent: 0, signals: 0 };
    if (e.runtime_kind && TEACHING_KINDS.has(e.runtime_kind)) b.signals += 1;
    else b[decidedBy(e)] += 1;
    map.set(day, b);
    min = Math.min(min, t);
    max = Math.max(max, t);
  }
  if (!map.size) return [];
  const DAY = 86_400_000;
  const end = Date.parse(new Date(max).toISOString().slice(0, 10));
  const start = Math.max(Date.parse(new Date(min).toISOString().slice(0, 10)), end - (maxDays - 1) * DAY);
  const out: DayBucket[] = [];
  for (let t = start; t <= end; t += DAY) {
    const day = new Date(t).toISOString().slice(0, 10);
    out.push(map.get(day) ?? { day, human: 0, agent: 0, signals: 0 });
  }
  return out;
}

export interface ClassRow {
  klass: string;
  total: number;
  agent: number;
  human: number;
  /** agent share, 0..1 */
  autonomy: number;
}

export function classBreakdown(entries: LedgerEntry[]): { rows: ClassRow[]; unclassified: number } {
  const map = new Map<string, ClassRow>();
  let unclassified = 0;
  for (const e of stageDecisions(entries)) {
    if (!e.ambiguity_class) {
      unclassified += 1;
      continue;
    }
    const r = map.get(e.ambiguity_class) ?? { klass: e.ambiguity_class, total: 0, agent: 0, human: 0, autonomy: 0 };
    r.total += 1;
    r[decidedBy(e)] += 1;
    map.set(e.ambiguity_class, r);
  }
  const rows = [...map.values()]
    .map((r) => ({ ...r, autonomy: r.total ? r.agent / r.total : 0 }))
    .sort((a, b) => b.total - a.total || a.klass.localeCompare(b.klass));
  return { rows, unclassified };
}
