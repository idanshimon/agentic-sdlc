/**
 * RunsInsights — KPI strip above /runs at scale.
 *
 * Operator scan-bar that derives from whatever set of runs is currently
 * visible (after filters). The numbers respond as the operator filters,
 * so "total spend on haiku runs" is one click away.
 *
 * Five KPIs (mirrors the /decisions strip but scoped to runs):
 *   - Runs total in scope
 *   - Status mix (completed / running / failed)
 *   - Total spend + avg cost per run
 *   - Total tokens + avg tokens per run
 *   - Model split (top 2 models by run count, comparative)
 */
"use client";

import type { RunState } from "@/lib/types";
import { Card } from "@/components/ui/card";
import { Bot, DollarSign, Hash, Activity } from "lucide-react";
import { fmtUsd, cn } from "@/lib/utils";

function modelLabel(run: RunState): string | null {
  if (run.model) return run.model;
  if (run.model_routing) {
    for (const v of Object.values(run.model_routing)) {
      if (v?.model) return v.model;
    }
  }
  return null;
}

function shortModel(m: string): string {
  return m.replace(/^databricks-claude-/, "").replace(/^claude-/, "");
}

export function RunsInsights({ runs }: { runs: RunState[] }) {
  const total = runs.length;
  const completed = runs.filter((r) => r.status === "completed").length;
  const running = runs.filter((r) => r.status === "running").length;
  const failed = runs.filter((r) => r.status === "failed" || r.status === "cancelled").length;

  const totalCost = runs.reduce((s, r) => s + (r.total_cost_usd ?? r.cost_usd ?? 0), 0);
  const totalTokens = runs.reduce((s, r) => s + (r.total_tokens ?? 0), 0);

  // Per-model breakdown: count + sum-cost + sum-tokens
  const byModel = new Map<string, { count: number; cost: number; tokens: number }>();
  for (const r of runs) {
    const m = modelLabel(r);
    if (!m) continue;
    const prev = byModel.get(m) ?? { count: 0, cost: 0, tokens: 0 };
    prev.count += 1;
    prev.cost += r.total_cost_usd ?? r.cost_usd ?? 0;
    prev.tokens += r.total_tokens ?? 0;
    byModel.set(m, prev);
  }
  const topModels = Array.from(byModel.entries())
    .sort((a, b) => b[1].count - a[1].count)
    .slice(0, 2);

  return (
    <div className="grid gap-2.5 grid-cols-2 md:grid-cols-4 xl:grid-cols-5">
      <Stat
        label="Runs"
        value={String(total)}
        sub={
          total === 0
            ? "no runs match"
            : `${completed} done · ${running} live · ${failed} fail`
        }
        icons={[Activity]}
      />
      <Stat
        label="Spend"
        value={fmtUsd(totalCost)}
        sub={total > 0 ? `${fmtUsd(totalCost / total)} avg / run` : "no spend"}
        icons={[DollarSign]}
        accent="primary"
      />
      <Stat
        label="Tokens"
        value={totalTokens.toLocaleString()}
        sub={
          total > 0 && totalTokens > 0
            ? `${Math.round(totalTokens / total).toLocaleString()} avg / run`
            : "no token data"
        }
        icons={[Hash]}
      />
      {topModels.length > 0 ? (
        topModels.map(([m, stats]) => (
          <Stat
            key={m}
            label={shortModel(m)}
            value={`${stats.count} run${stats.count === 1 ? "" : "s"}`}
            sub={`${fmtUsd(stats.cost)} · ${stats.tokens.toLocaleString()} tok`}
            icons={[Bot]}
          />
        ))
      ) : (
        <Stat
          label="Models"
          value="—"
          sub="no model attribution"
          icons={[Bot]}
        />
      )}
    </div>
  );
}

function Stat({
  label, value, sub, accent, icons,
}: {
  label: string;
  value: string;
  sub: string;
  accent?: "primary";
  icons?: React.ComponentType<{ className?: string }>[];
}) {
  return (
    <Card className="p-3 space-y-1">
      <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-[var(--text-tertiary)]">
        {icons?.map((Icon, i) => <Icon key={i} className="h-3 w-3" />)}
        <span className="truncate">{label}</span>
      </div>
      <div className={cn(
        "text-xl font-semibold tabular truncate",
        accent === "primary" ? "text-[var(--primary)]" : "text-[var(--text)]",
      )}>
        {value}
      </div>
      <div className="text-[11px] text-[var(--text-tertiary)] truncate">{sub}</div>
    </Card>
  );
}
