/* Resolve a deep link (?run=&card=) to the ledger entry the operator just
 * created, and summarise how it connects to the agents' decisions.
 *
 * Pure so it is testable. Honest about lag: the ledger write can land a few
 * seconds after the toast, so "not found yet" is a distinct state from
 * "not in the ledger". */
import type { LedgerEntry } from "@/lib/types";

export interface MapFocus {
  status: "found" | "run-only" | "pending";
  entryId?: string;
  runId: string;
  /** Other decisions in the same run, split by who made them. */
  agentInRun: number;
  humanInRun: number;
  /** Later decisions that reused this one as precedent (learning loop). */
  reusedBy: number;
  /** Precedents this decision itself reused. */
  reuses: number;
}

const ts = (e: LedgerEntry) => Date.parse(e.created_at) || 0;
const isAgent = (e: LedgerEntry) =>
  e.confidence_source ? e.confidence_source !== "human" : e.actor?.kind !== "human";

export function resolveMapFocus(entries: LedgerEntry[], runId: string, cardId?: string | null): MapFocus {
  const inRun = entries.filter((e) => e.run_id === runId);
  // Latest human decision for that card (a re-decision supersedes); without a
  // card (bulk approve), the latest human decision in the run.
  const human = inRun
    .filter((e) => !isAgent(e) && (!cardId || e.card_id === cardId))
    .sort((a, b) => ts(b) - ts(a));
  const target = human[0];
  const others = inRun.filter((e) => e.id !== target?.id);
  const base = {
    runId,
    agentInRun: others.filter(isAgent).length,
    humanInRun: others.filter((e) => !isAgent(e)).length,
  };
  if (!target) {
    return { status: inRun.length ? "run-only" : "pending", ...base, reusedBy: 0, reuses: 0 };
  }
  const refs = (e: LedgerEntry) => new Set([e.precedent_id, ...(e.precedent_refs ?? [])].filter(Boolean) as string[]);
  return {
    status: "found",
    entryId: target.id,
    ...base,
    reusedBy: entries.filter((e) => e.id !== target.id && refs(e).has(target.id)).length,
    reuses: refs(target).size,
  };
}
