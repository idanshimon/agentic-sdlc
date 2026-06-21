/**
 * DecisionsInsights — KPI cards above the ledger table.
 *
 * Surfaces the load-bearing operator questions at a glance:
 *   - How many decisions and over what window
 *   - Human-vs-agent autonomy split (matters for the autonomy economics
 *     pitch — Chen's "how often does the system act on its own")
 *   - PHI exposure profile (how many high/low entries — a compliance
 *     scan-bar without leaving the page)
 *   - Total spend on the visible window (matters for "cost analysis" #4)
 *   - Teaching-signal coverage (% of stage decisions with feedback)
 *
 * All five are derived from the same in-memory entries list so the
 * numbers always match the table below — no separate API call.
 */
"use client";

import type { LedgerEntry } from "@/lib/types";
import { Card } from "@/components/ui/card";
import { Bot, User, ShieldAlert, DollarSign, Sprout } from "lucide-react";
import { fmtUsd } from "@/lib/utils";
import { buildLineageIndex } from "@/lib/lineage";

const TEACHING_KINDS = new Set([
  "feedback_thumbs", "decision_flagged", "replay_requested", "class_paused",
]);

export function DecisionsInsights({ entries }: { entries: LedgerEntry[] }) {
  // Stage decisions only (exclude operator teaching signals from autonomy
  // and cost math — those are operator events, not pipeline decisions).
  const stageDecisions = entries.filter(
    (e) => !e.runtime_kind || !TEACHING_KINDS.has(e.runtime_kind),
  );

  const total = stageDecisions.length;
  const humanCount = stageDecisions.filter((e) => e.actor?.kind === "human").length;
  const agentCount = stageDecisions.filter((e) => e.actor?.kind === "agent").length;
  const humanPct = total ? Math.round((humanCount / total) * 100) : 0;
  const agentPct = total ? Math.round((agentCount / total) * 100) : 0;

  const phiHigh = stageDecisions.filter((e) => e.phi_class === "high").length;
  const phiLow = stageDecisions.filter((e) => e.phi_class === "low").length;

  const totalCost = stageDecisions.reduce((s, e) => s + (e.cost_usd || 0), 0);

  // Teaching-loop autonomy: human swaps that became precedent + the later
  // autopilot decisions that reused them. This is the headline that proves
  // the loop is working — the agent earns autonomy from real human calls.
  const { metrics } = buildLineageIndex(entries);

  return (
    <div className="grid gap-2.5 grid-cols-2 md:grid-cols-4 xl:grid-cols-5">
      <Stat
        label="Decisions"
        value={total}
        sub={total > 0 ? `${stageDecisions.length} stage entries` : "no entries yet"}
      />
      <Stat
        label="Autonomy split"
        value={total > 0 ? `${agentPct}% agent` : "—"}
        sub={total > 0 ? `${humanPct}% human · ${agentCount} / ${humanCount}` : "no entries yet"}
        icons={[Bot, User]}
      />
      <Stat
        label="PHI exposure"
        value={phiHigh > 0 ? `${phiHigh} high` : "0 high"}
        sub={`${phiLow} low · ${total - phiHigh - phiLow} none`}
        accent={phiHigh > 0 ? "danger" : undefined}
        icons={[ShieldAlert]}
      />
      <Stat
        label="Spend"
        value={fmtUsd(totalCost)}
        sub={total > 0 ? `${fmtUsd(totalCost / total)} avg / decision` : "no spend"}
        icons={[DollarSign]}
      />
      <Stat
        label="Autonomy earned"
        value={`${metrics.autonomyEarnedPct}%`}
        sub={
          metrics.taughtCount === 0
            ? "no human-taught precedent yet"
            : `${metrics.reusedCount} auto-resolved from ${metrics.taughtCount} taught · ${metrics.bucketsTaught} bucket${metrics.bucketsTaught === 1 ? "" : "s"}`
        }
        accent={metrics.reusedCount > 0 ? "success" : undefined}
        icons={[Sprout]}
      />
    </div>
  );
}

function Stat({
  label, value, sub, accent, icons,
}: {
  label: string;
  value: string | number;
  sub: string;
  accent?: "danger" | "warning" | "success";
  icons?: React.ComponentType<{ className?: string }>[];
}) {
  const valueColor =
    accent === "danger" ? "text-[var(--danger)]" :
    accent === "warning" ? "text-[var(--warning)]" :
    accent === "success" ? "text-[var(--success)]" :
    "text-[var(--text)]";
  return (
    <Card className="p-3 space-y-1">
      <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-[var(--text-tertiary)]">
        {icons?.map((Icon, i) => <Icon key={i} className="h-3 w-3" />)}
        <span>{label}</span>
      </div>
      <div className={`text-xl font-semibold tabular ${valueColor}`}>{value}</div>
      <div className="text-[11px] text-[var(--text-tertiary)] truncate">{sub}</div>
    </Card>
  );
}
