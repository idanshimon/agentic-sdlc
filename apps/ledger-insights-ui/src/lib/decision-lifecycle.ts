import type { LedgerEntry } from "./types";

export type DecisionLifecycleState = "proposed" | "required" | "resolved" | "applied" | "verified" | "learned";

export interface DecisionLifecycleProjection {
  decisionId: string;
  state: DecisionLifecycleState;
  evidence: Partial<Record<DecisionLifecycleState, LedgerEntry>>;
  missing: DecisionLifecycleState[];
}

const ORDER: DecisionLifecycleState[] = ["proposed", "required", "resolved", "applied", "verified", "learned"];

function stateFor(entry: LedgerEntry): DecisionLifecycleState {
  if (entry.runtime_kind === "plan_proposed") return "proposed";
  if (entry.runtime_kind === "delivered") return "applied";
  if (entry.runtime_kind === "loop_converged") return "verified";
  if (entry.runtime_kind === "feedback_thumbs" || entry.runtime_kind === "class_paused") return "learned";
  if (entry.decision_kind) return "resolved";
  return "required";
}

export function projectDecisionLifecycle(entries: LedgerEntry[]): DecisionLifecycleProjection[] {
  const groups = new Map<string, LedgerEntry[]>();
  for (const entry of entries) {
    const key = entry.references_entry_id ?? entry.precedent_id ?? entry.card_id ?? entry.id ?? entry.run_id ?? "unknown";
    groups.set(key, [...(groups.get(key) ?? []), entry]);
  }
  return [...groups.entries()].map(([decisionId, group]) => {
    const evidence: Partial<Record<DecisionLifecycleState, LedgerEntry>> = {};
    for (const entry of [...group].sort((a, b) => (a.created_at ?? "").localeCompare(b.created_at ?? ""))) {
      evidence[stateFor(entry)] = entry;
    }
    const reached = ORDER.reduce((last, state, index) => evidence[state] ? Math.max(last, index) : last, 0);
    return {
      decisionId,
      state: ORDER[reached],
      evidence,
      missing: ORDER.filter((state, index) => index <= reached && !evidence[state]),
    };
  });
}
