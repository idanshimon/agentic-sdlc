/* Human-readable run labels + search.
 *
 * A run is identified by a UUID, which is correct for machines and useless for
 * people: "fd4e8c59-7938-4a64-b93e-2b1a7729c6fb" tells an operator nothing about
 * which run it is. This derives a label from what a human actually remembers —
 * when it ran, which team, what it decided, whether anything is flagged — and
 * supports free-text search across all of it (including the id, so pasting a
 * UUID from a log still works).
 */
import type { LedgerEntry } from "./types";

export interface RunOption {
  runId: string;
  /** Short id for display — full UUID is preserved as the value. */
  shortId: string;
  label: string;
  team?: string;
  decisionCount: number;
  flaggedCount: number;
  classes: string[];
  /** Newest entry timestamp in the run. */
  lastAt: string;
  /** Lowercased haystack for search. */
  haystack: string;
}

function ago(iso: string, now: number): string {
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return "";
  const s = Math.max(0, Math.floor((now - t) / 1000));
  if (s < 90) return "just now";
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

/** Build a labelled, searchable option per run present in the entries. */
export function buildRunOptions(
  entries: LedgerEntry[],
  opts: { now?: number } = {},
): RunOption[] {
  const now = opts.now ?? Date.now();
  const byRun = new Map<string, LedgerEntry[]>();
  for (const e of entries) {
    if (!e.run_id) continue;
    byRun.set(e.run_id, [...(byRun.get(e.run_id) ?? []), e]);
  }

  const options: RunOption[] = [];
  for (const [runId, list] of byRun) {
    const sorted = [...list].sort((a, b) =>
      (b.created_at || "").localeCompare(a.created_at || ""),
    );
    const lastAt = sorted[0]?.created_at ?? "";
    const team = sorted.find((e) => e.team_id)?.team_id;
    const classes = [
      ...new Set(sorted.map((e) => e.ambiguity_class).filter(Boolean)),
    ] as string[];
    const flaggedCount = sorted.filter(
      (e) => e.runtime_kind === "decision_flagged",
    ).length;
    const shortId = runId.slice(0, 8);

    // What a human recognises: when, who, how big, what it was about.
    const teamLabel = (team ?? "").replace(/^team-/, "");
    const parts = [
      ago(lastAt, now),
      teamLabel || undefined,
      `${sorted.length} decision${sorted.length === 1 ? "" : "s"}`,
      classes.length ? classes.slice(0, 2).join(" · ") : undefined,
      flaggedCount ? `${flaggedCount} flagged` : undefined,
    ].filter(Boolean);

    options.push({
      runId,
      shortId,
      label: `${parts.join("  ·  ")}  —  ${shortId}`,
      team,
      decisionCount: sorted.length,
      flaggedCount,
      classes,
      lastAt,
      haystack: [runId, teamLabel, ...classes, ...sorted.map((e) => e.decision ?? "")]
        .join(" ")
        .toLowerCase(),
    });
  }

  // Newest first — the run you just started is the one you want.
  options.sort((a, b) => (b.lastAt || "").localeCompare(a.lastAt || ""));
  return options;
}

/** Filter run options by a free-text query. Empty query returns everything. */
export function filterRunOptions(options: RunOption[], query: string): RunOption[] {
  const q = query.trim().toLowerCase();
  if (!q) return options;
  // All whitespace-separated terms must match somewhere (AND), so
  // "cardiology phi" narrows instead of widening.
  const terms = q.split(/\s+/);
  return options.filter((o) => terms.every((t) => o.haystack.includes(t)));
}
