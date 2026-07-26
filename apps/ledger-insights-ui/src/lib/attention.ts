/* Attention engine — the "what needs me?" projection.
 *
 * Operator surfaces speak outcomes, not internal state. This module derives a
 * single ranked queue of things a human must look at, from run + decision
 * evidence that already exists. It is a PURE projection: no fetching, no React,
 * no side effects — so the ranking is unit-testable without a DOM.
 *
 * Ranking rationale (highest first):
 *   1. blocked   — a run is stopped waiting on a human. Nothing proceeds.
 *   2. failed    — work was lost; needs triage or retry.
 *   3. flagged   — a human marked a decision wrong; it must not become precedent.
 *   4. stalled   — running far longer than expected; probably wedged.
 * Within a bucket, newest first (freshest signal is most actionable).
 */
import type { RunState, LedgerEntry } from "@/lib/types";

export type AttentionKind = "blocked" | "failed" | "flagged" | "stalled";

export interface AttentionItem {
  /** Stable key for React + deep-link anchors. */
  id: string;
  kind: AttentionKind;
  /** Plain-language headline. Speaks the outcome, never the state machine. */
  title: string;
  /** One line of supporting evidence. Never invented — derived from the record. */
  detail: string;
  /** Where clicking takes the operator. Every item MUST be actionable. */
  href: string;
  /** Label for the primary action button. An immediate action, not a mechanism. */
  action: string;
  /** ISO timestamp used for within-bucket ordering. */
  at: string;
  /** Set when this row collapses several identical items. */
  count?: number;
}

const RANK: Record<AttentionKind, number> = {
  blocked: 0,
  failed: 1,
  flagged: 2,
  stalled: 3,
};

/** A run running longer than this is probably wedged, not working. */
export const STALL_THRESHOLD_MS = 30 * 60 * 1000;

/** Failures older than this are history, not an alert. */
export const FAILURE_WINDOW_MS = 24 * 60 * 60 * 1000;

function shortId(id: string | undefined | null): string {
  if (!id) return "unknown";
  return id.length > 8 ? id.slice(0, 8) : id;
}

function ts(value: string | undefined | null): number {
  if (!value) return 0;
  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? 0 : parsed;
}

/** Human-readable "how long ago", coarse on purpose — operators scan, not read. */
export function ago(at: string | undefined | null, now: number = Date.now()): string {
  const then = ts(at);
  if (!then) return "unknown";
  const delta = Math.max(0, now - then);
  const mins = Math.floor(delta / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

/** Which stage is a blocked run waiting at? Falls back gracefully. */
function gateStage(run: RunState): string {
  return (
    run.pending_gate?.stage ||
    (typeof run.current_stage === "string" ? run.current_stage : "") ||
    "a gate"
  );
}

/** Last failure message from the event stream, if the run recorded one. */
function failureReason(run: RunState): string {
  const events = run.events ?? [];
  for (let i = events.length - 1; i >= 0; i -= 1) {
    const ev = events[i];
    if (ev?.status === "failed" && ev.message) return ev.message;
  }
  const stage = typeof run.current_stage === "string" ? run.current_stage : "";
  return stage ? `Failed during ${stage}.` : "Failed with no recorded reason.";
}

export function attentionFromRuns(
  runs: RunState[] | undefined,
  now: number = Date.now(),
): AttentionItem[] {
  const items: AttentionItem[] = [];
  for (const run of runs ?? []) {
    if (!run?.run_id) continue;
    const at = run.updated_at || run.created_at || "";

    if (run.status === "awaiting_gate" || run.status === "paused") {
      items.push({
        id: `blocked-${run.run_id}`,
        kind: "blocked",
        title: `A run is waiting on your decision at ${gateStage(run)}`,
        detail: `Run ${shortId(run.run_id)} · ${run.team_id || "unknown team"} · nothing proceeds until this is answered.`,
        href: `/runs/${run.run_id}`,
        action: "Open gate",
        at,
      });
      continue;
    }

    if (run.status === "failed" && now - ts(at) <= FAILURE_WINDOW_MS) {
      items.push({
        id: `failed-${run.run_id}`,
        kind: "failed",
        title: `A run failed and produced no delivery`,
        detail: `Run ${shortId(run.run_id)} · ${failureReason(run)}`,
        href: `/runs/${run.run_id}`,
        action: "Triage",
        at,
      });
      continue;
    }

    if (run.status === "running" && ts(at) > 0 && now - ts(at) > STALL_THRESHOLD_MS) {
      items.push({
        id: `stalled-${run.run_id}`,
        kind: "stalled",
        title: `A run has been going for ${ago(at, now).replace(" ago", "")} with no update`,
        detail: `Run ${shortId(run.run_id)} · last activity at ${typeof run.current_stage === "string" ? run.current_stage : "an unknown stage"}.`,
        href: `/runs/${run.run_id}`,
        action: "Inspect",
        at,
      });
    }
  }
  return items;
}

export function attentionFromDecisions(
  entries: LedgerEntry[] | undefined,
): AttentionItem[] {
  const items: AttentionItem[] = [];
  for (const entry of entries ?? []) {
    if (!entry?.id) continue;
    // Track B teaching signals. A flag is a human saying "this was wrong" —
    // it must not be reused as precedent, and someone has to decide what
    // replaces it. A paused class means autopilot is off for that class until
    // a human re-opens it, so it silently slows every future run.
    const kindTag = entry.runtime_kind;
    if (kindTag === "decision_flagged") {
      const what = entry.decision || entry.ambiguity_class || "a decision";
      items.push({
        id: `flagged-${entry.id}`,
        kind: "flagged",
        title: `A person flagged "${what}" as wrong`,
        detail: "It won't be reused as precedent. Decide what replaces it.",
        href: `/decisions#decision-${entry.references_entry_id || entry.id}`,
        action: "Review",
        at: entry.created_at || "",
      });
      continue;
    }
    if (kindTag === "class_paused") {
      const cls = entry.paused_class || entry.ambiguity_class || "a class";
      items.push({
        id: `paused-${entry.id}`,
        kind: "flagged",
        title: `Autopilot is paused for "${cls}"`,
        detail: "Every run hitting this class now waits for a human.",
        href: `/decisions#decision-${entry.id}`,
        action: "Review",
        at: entry.created_at || "",
      });
    }
  }
  return items;
}

/** Merge, rank, and cap. `limit` keeps the fold honest — the rest live on their pages.
 *
 * Identical-shaped items are COLLAPSED: six runs blocked at the same stage is
 * one fact ("6 runs waiting at resolver"), not six rows. An operator scanning a
 * wall of identical sentences learns nothing and stops reading. */
export function buildAttentionQueue(
  runs: RunState[] | undefined,
  entries: LedgerEntry[] | undefined,
  opts: { now?: number; limit?: number } = {},
): AttentionItem[] {
  const now = opts.now ?? Date.now();
  const limit = opts.limit ?? 6;
  const merged = [...attentionFromRuns(runs, now), ...attentionFromDecisions(entries)];
  merged.sort((a, b) => {
    const byKind = RANK[a.kind] - RANK[b.kind];
    if (byKind !== 0) return byKind;
    return ts(b.at) - ts(a.at);
  });
  return collapseDuplicates(merged, now).slice(0, limit);
}

/** Group items sharing a kind+title into one row carrying the count.
 *  `now` is injected so the collapsed "oldest Xd ago" copy is deterministic. */
export function collapseDuplicates(
  items: AttentionItem[],
  now: number = Date.now(),
): AttentionItem[] {
  const seen = new Map<string, AttentionItem[]>();
  const order: string[] = [];
  for (const item of items) {
    const key = `${item.kind}::${item.title}`;
    if (!seen.has(key)) {
      seen.set(key, []);
      order.push(key);
    }
    seen.get(key)!.push(item);
  }
  return order.map((key) => {
    const group = seen.get(key)!;
    const head = group[0];
    if (group.length === 1) return head;
    // Newest member drives the timestamp; the row speaks for the whole group.
    return {
      ...head,
      id: `${head.id}-x${group.length}`,
      title: pluralize(head.title, group.length),
      detail: `${group.length} runs, oldest ${ago(group[group.length - 1].at, now)}. Open the queue to work through them.`,
      href: head.kind === "blocked" ? "/runs?view=attention" : head.href,
      action: "Open queue",
      count: group.length,
    };
  });
}

/** "A run is waiting…" → "6 runs are waiting…". Falls back safely. */
function pluralize(title: string, n: number): string {
  if (title.startsWith("A run is waiting")) {
    return title.replace("A run is waiting", `${n} runs are waiting`);
  }
  if (title.startsWith("A run failed")) {
    return title.replace("A run failed", `${n} runs failed`);
  }
  return `${title} (${n}×)`;
}

/** Counts per kind across the FULL queue (not the capped view) — drives the summary chips. */
export function attentionCounts(
  runs: RunState[] | undefined,
  entries: LedgerEntry[] | undefined,
  now: number = Date.now(),
): Record<AttentionKind, number> {
  const all = [...attentionFromRuns(runs, now), ...attentionFromDecisions(entries)];
  const counts: Record<AttentionKind, number> = {
    blocked: 0,
    failed: 0,
    flagged: 0,
    stalled: 0,
  };
  for (const item of all) counts[item.kind] += 1;
  return counts;
}
