/**
 * Economics aggregation — converts raw ledger entries into the dashboards
 * Kapil + Manthan + Ravi actually want:
 *
 *   - Money saved by precedent reuse vs the counterfactual "every decision
 *     hits a fresh LLM"
 *   - Autonomy ratio (% agent-executed without human gate)
 *   - Per-team breakdown (multi-tenant scaling story)
 *   - Volume + cost trend over time (drift signal)
 *
 * Design choices:
 *
 * 1. PURE FUNCTION over an entry array. No hooks, no React, no Cosmos.
 *    Same module is used server-side (the /api/economics route) and
 *    client-side (any KPI tile that wants to compute over the visible
 *    decisions). One implementation, one set of tests.
 *
 * 2. COUNTERFACTUAL is explicit. The "$X saved" claim depends entirely on
 *    what we assume the precedent-miss path costs. We assume it equals the
 *    rolling avg of cost_usd across actual non-precedent decisions in the
 *    same window. If there are zero non-precedent decisions, we fall back
 *    to a published constant (FRESH_LLM_FALLBACK_USD) and flag the result
 *    so the UI can show "(estimated from default)" instead of letting the
 *    customer think it's their data.
 *
 * 3. AUTONOMY is OPERATOR-defined. Today: any entry with
 *    actor.kind === "agent" is "agent-driven"; any entry with
 *    actor.kind === "human" or runtime_kind in {plan_proposed} is
 *    "human-gated". Once Track B (feedback) lands, we'll add
 *    feedback_thumbs entries that don't change the autonomy ratio (they
 *    are observation, not action).
 */

import type { LedgerEntry } from "@/lib/types";

/**
 * Default fallback cost when we have zero non-precedent decisions to
 * estimate the counterfactual fresh-LLM call price from. Calibrated against
 * gpt-4o + gpt-5-codex avg invocation in the orchestrator's stage prompts
 * (Sept 2026 prices). When the fixtures populate, this value will be
 * dwarfed by the actual non-precedent average.
 */
export const FRESH_LLM_FALLBACK_USD = 0.30;

export interface EconomicsSummary {
  /** Total decisions in the window. */
  total_decisions: number;
  /** Decisions whose precedent_refs is non-empty (cached precedent path). */
  precedent_hits: number;
  /** Decisions with empty precedent_refs (novel reasoning required). */
  novel_decisions: number;
  /** precedent_hits / total_decisions, 0-1. */
  precedent_hit_rate: number;
  /** Sum of cost_usd, all entries. */
  total_cost_usd: number;
  /** Avg cost on novel decisions; this is the counterfactual unit cost. */
  avg_novel_cost_usd: number;
  /** Avg cost on precedent hits (cheap path). */
  avg_precedent_cost_usd: number;
  /**
   * Estimated dollars saved vs the counterfactual where every decision
   * hits the novel-cost path. precedent_hits * avg_novel_cost_usd -
   * sum(cost on precedent hits).
   */
  estimated_savings_usd: number;
  /** True when avg_novel_cost_usd was synthesized from fallback. */
  novel_cost_is_estimate: boolean;
  /** % of decisions executed by agents without human gate. 0-1. */
  autonomy_ratio: number;
  /** Count of agent-driven decisions. */
  agent_driven: number;
  /** Count of human-gated decisions (kind=human OR plan_proposed). */
  human_gated: number;
}

export interface EconomicsByTeam extends EconomicsSummary {
  team_id: string;
}

/**
 * Aggregate a flat list of LedgerEntry into a single summary.
 */
export function summarize(entries: LedgerEntry[]): EconomicsSummary {
  const total = entries.length;
  if (total === 0) {
    return {
      total_decisions: 0,
      precedent_hits: 0,
      novel_decisions: 0,
      precedent_hit_rate: 0,
      total_cost_usd: 0,
      avg_novel_cost_usd: 0,
      avg_precedent_cost_usd: 0,
      estimated_savings_usd: 0,
      novel_cost_is_estimate: false,
      autonomy_ratio: 0,
      agent_driven: 0,
      human_gated: 0,
    };
  }

  let precedentHits = 0;
  let totalCost = 0;
  let novelCostSum = 0;
  let novelCostCount = 0;
  let precedentCostSum = 0;
  let agentDriven = 0;
  let humanGated = 0;

  for (const e of entries) {
    const cost = typeof e.cost_usd === "number" ? e.cost_usd : 0;
    totalCost += cost;
    const isPrecedent = Array.isArray(e.precedent_refs) && e.precedent_refs.length > 0;
    if (isPrecedent) {
      precedentHits += 1;
      precedentCostSum += cost;
    } else {
      novelCostSum += cost;
      novelCostCount += 1;
    }

    // Autonomy classification.
    // - actor.kind=human → human-gated
    // - runtime_kind=plan_proposed → human-gated (humans approving a plan
    //   before the orchestrator runs the stages)
    // - everything else → agent-driven
    const actorKind = e.actor && typeof e.actor === "object" ? e.actor.kind : undefined;
    const isHumanGated = actorKind === "human" || e.runtime_kind === "plan_proposed";
    if (isHumanGated) humanGated += 1;
    else agentDriven += 1;
  }

  const novel = novelCostCount;
  const novelCostIsEstimate = novel === 0 && precedentHits > 0;
  const avgNovelCost = novel > 0
    ? novelCostSum / novel
    : (novelCostIsEstimate ? FRESH_LLM_FALLBACK_USD : 0);
  const avgPrecedentCost = precedentHits > 0 ? precedentCostSum / precedentHits : 0;
  const counterfactualPrecedentCost = avgNovelCost * precedentHits;
  const savings = Math.max(0, counterfactualPrecedentCost - precedentCostSum);

  return {
    total_decisions: total,
    precedent_hits: precedentHits,
    novel_decisions: novel,
    precedent_hit_rate: precedentHits / total,
    total_cost_usd: totalCost,
    avg_novel_cost_usd: avgNovelCost,
    avg_precedent_cost_usd: avgPrecedentCost,
    estimated_savings_usd: savings,
    novel_cost_is_estimate: novelCostIsEstimate,
    autonomy_ratio: agentDriven / total,
    agent_driven: agentDriven,
    human_gated: humanGated,
  };
}

/**
 * Per-team aggregation. Multi-tenant scaling story: cardiology vs pharmacy
 * vs imaging, side by side, same metric definitions.
 */
export function summarizeByTeam(entries: LedgerEntry[]): EconomicsByTeam[] {
  const byTeam = new Map<string, LedgerEntry[]>();
  for (const e of entries) {
    const teamId = (e as { team_id?: string }).team_id ?? "unknown";
    const list = byTeam.get(teamId) ?? [];
    list.push(e);
    byTeam.set(teamId, list);
  }
  const out: EconomicsByTeam[] = [];
  for (const [team_id, teamEntries] of byTeam.entries()) {
    out.push({ team_id, ...summarize(teamEntries) });
  }
  // Largest first — biggest team dominates the dashboard.
  out.sort((a, b) => b.total_decisions - a.total_decisions);
  return out;
}

/**
 * Bucket entries into time series for the trend chart. We use day-level
 * buckets because customer demos run on day-scale; the same function will
 * accept "hour" or "week" later when ops runs ask for it.
 */
export interface TrendPoint {
  bucket: string; // "YYYY-MM-DD"
  decisions: number;
  precedent_hits: number;
  cost_usd: number;
}

export function trendByDay(entries: LedgerEntry[]): TrendPoint[] {
  const byDay = new Map<string, TrendPoint>();
  for (const e of entries) {
    const ts = (e as { created_at?: string }).created_at;
    if (!ts) continue;
    const day = ts.slice(0, 10);
    const existing = byDay.get(day) ?? {
      bucket: day,
      decisions: 0,
      precedent_hits: 0,
      cost_usd: 0,
    };
    existing.decisions += 1;
    existing.cost_usd += typeof e.cost_usd === "number" ? e.cost_usd : 0;
    if (Array.isArray(e.precedent_refs) && e.precedent_refs.length > 0) {
      existing.precedent_hits += 1;
    }
    byDay.set(day, existing);
  }
  return [...byDay.values()].sort((a, b) => a.bucket.localeCompare(b.bucket));
}
