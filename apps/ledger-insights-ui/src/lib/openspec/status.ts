/**
 * OpenSpec change status derivation — shared, pure, unit-tested.
 *
 * The free-text `> **Status:**` line in every proposal.md is left as "DRAFT"
 * forever, so it never reflects real progress. We derive an honest status from
 * signals that actually change as work happens: archive location + task-checkbox
 * completion, with the author's text as a secondary hint.
 */
export type ChangeStatus = "draft" | "in-progress" | "ready" | "merged";

/**
 * Precedence (first match wins):
 *   1. Archived on disk (openspec/changes/archive/…)   -> merged
 *   2. Author text says partially-shipped               -> in-progress
 *   3. Author text says merged / shipped                -> merged
 *   4. Has tasks and every task checked (100%)          -> ready (to merge)
 *   5. Has tasks and some checked                       -> in-progress
 *   6. otherwise                                        -> draft
 */
export function deriveStatus(
  rawStatusText: string,
  archived: boolean,
  taskTotal: number,
  taskDone: number,
): ChangeStatus {
  if (archived) return "merged";
  const lower = (rawStatusText ?? "").trim().toLowerCase();
  if (lower.includes("partially")) return "in-progress";
  if (lower.includes("merged") || lower.includes("shipped")) return "merged";
  if (taskTotal > 0 && taskDone >= taskTotal) return "ready";
  if (taskTotal > 0 && taskDone > 0) return "in-progress";
  return "draft";
}

export const STATUS_LABEL: Record<ChangeStatus, string> = {
  draft: "draft",
  "in-progress": "in progress",
  ready: "ready to merge",
  merged: "merged",
};

export const STATUS_HELP: Record<ChangeStatus, string> = {
  draft: "Proposal written, no tasks started yet.",
  "in-progress": "Some tasks done — the change is being built.",
  ready: "Every task is checked — the work is complete and awaiting merge.",
  merged: "Shipped and archived into the spec.",
};
