import type { LedgerEntry } from "./types";

export type ReviewLoopTerminal =
  | "merged"
  | "passed_awaiting_merge"
  | "escalated"
  | "advisory"
  | "failed"
  | "in_progress";

export interface ReviewLoopProjection {
  loopId: string;
  repo: string;
  prNumber?: number;
  headSha?: string;
  tier?: string;
  hops: LedgerEntry[];
  terminal: ReviewLoopTerminal;
  attempts: number;
}

function legacyRef(ref?: string): { repo?: string; tier?: string; action?: string } {
  const match = ref?.match(/^reviewloop\/([^/]+)\/(.+)\/([^/@]+)@attempt=/);
  return match ? { tier: match[1], repo: match[2], action: match[3] } : {};
}

export function projectReviewLoops(entries: LedgerEntry[]): ReviewLoopProjection[] {
  const groups = new Map<string, LedgerEntry[]>();
  for (const entry of entries) {
    const legacy = legacyRef(entry.autonomy_ref);
    const key = entry.loop_id ?? `${legacy.repo ?? "unknown"}:${entry.pr_number ?? "legacy"}:${entry.head_sha ?? "legacy"}`;
    groups.set(key, [...(groups.get(key) ?? []), entry]);
  }
  return [...groups.entries()].map(([loopId, hops]) => {
    const sorted = [...hops].sort((a, b) => a.created_at.localeCompare(b.created_at));
    const last = sorted.at(-1)!;
    const legacy = legacyRef(last.autonomy_ref);
    const disposition = last.disposition;
    let terminal: ReviewLoopTerminal = "in_progress";
    if (disposition === "MERGED") terminal = "merged";
    else if (disposition === "PASSED_AWAITING_MERGE") terminal = "passed_awaiting_merge";
    else if (disposition === "ESCALATED") terminal = "escalated";
    else if (disposition === "ADVISORY") terminal = "advisory";
    else if (disposition === "FAILED") terminal = "failed";
    else if (last.runtime_kind === "loop_escalated") terminal = legacy.action === "comment_only" ? "advisory" : "escalated";
    else if (last.runtime_kind === "loop_converged") terminal = legacy.action === "await_human_merge" ? "passed_awaiting_merge" : "merged";
    return {
      loopId,
      repo: last.repo ?? legacy.repo ?? "unknown",
      prNumber: last.pr_number,
      headSha: last.head_sha,
      tier: last.tier ?? legacy.tier,
      hops: sorted,
      terminal,
      attempts: sorted.filter((hop) => hop.runtime_kind === "review_remediation").length,
    };
  });
}
