"use client";

import { useQuery } from "@tanstack/react-query";
import { useAssistantContext } from "@/lib/assist/context";
import { Card } from "@/components/ui/card";
import { PageHeader } from "@/components/layout/page-header";
import { KpiCard } from "@/components/domain/kpi-card";
import { EmptyState } from "@/components/domain/empty-state";
import { fmtUsd, fmtNumber } from "@/lib/utils";
import {
  DollarSign,
  Sparkles,
  Bot,
  Users,
  TrendingUp,
  Scale,
} from "lucide-react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  LineChart,
  Line,
  Legend,
} from "recharts";
import type { EconomicsSummary, EconomicsByTeam, TrendPoint } from "@/lib/economics";

interface EconomicsPayload {
  summary: EconomicsSummary;
  by_team: EconomicsByTeam[];
  trend: TrendPoint[];
  sample_size: number;
  limit_applied: number;
}

function pct(n: number): string {
  return `${(n * 100).toFixed(1)}%`;
}

export default function EconomicsPage() {
  const { data, isLoading, error } = useQuery<EconomicsPayload>({
    queryKey: ["economics"],
    queryFn: async () => {
      const res = await fetch("/api/economics?limit=200");
      if (!res.ok) throw new Error(`/api/economics ${res.status}`);
      return res.json();
    },
    refetchInterval: 30_000,
  });

  useAssistantContext({
    kind: "telemetry",
    label: "Economics",
    payload: data?.summary
      ? { count: data.summary.total_decisions }
      : undefined,
  });

  const summary = data?.summary;
  const teams = data?.by_team ?? [];
  const trend = data?.trend ?? [];

  // Trend chart data: pad to a min set of points so the chart doesn't look
  // bizarre when there are 0-2 entries (common on a fresh demo). Recharts
  // handles single-point datasets ok; we just want guard rails.
  const trendData = trend.map((t) => ({
    date: t.bucket.slice(5), // MM-DD
    decisions: t.decisions,
    precedent_hits: t.precedent_hits,
    cost_usd: Number(t.cost_usd.toFixed(4)),
  }));

  // Team chart data: top 6 teams by volume.
  const teamData = teams.slice(0, 6).map((t) => ({
    team: t.team_id.length > 12 ? t.team_id.slice(0, 12) + "…" : t.team_id,
    saved: Number(t.estimated_savings_usd.toFixed(2)),
    decisions: t.total_decisions,
    autonomy: Number((t.autonomy_ratio * 100).toFixed(1)),
  }));

  return (
    <div className="space-y-6">
      <PageHeader
        plane="ledger"
        title="Economics"
        description="What every decision costs, what precedent reuse saves, who runs autonomously and who still has a human in the loop. Sourced live from the Decision Ledger — same partition, same queries, no derived stores."
      />

      {error ? (
        <EmptyState
          icon={Scale}
          title="Couldn't load economics"
          description={String((error as Error).message)}
        />
      ) : null}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard
          label="Estimated savings"
          value={summary ? fmtUsd(summary.estimated_savings_usd, 2) : "—"}
          icon={DollarSign}
          accent="success"
          hint={
            summary?.novel_cost_is_estimate
              ? "vs. fallback fresh-LLM"
              : summary
                ? `vs. avg novel ${fmtUsd(summary.avg_novel_cost_usd, 4)}`
                : undefined
          }
          loading={isLoading}
        />
        <KpiCard
          label="Precedent hit-rate"
          value={summary ? pct(summary.precedent_hit_rate) : "—"}
          icon={Sparkles}
          accent="ledger"
          hint={
            summary
              ? `${fmtNumber(summary.precedent_hits)} of ${fmtNumber(summary.total_decisions)}`
              : undefined
          }
          loading={isLoading}
        />
        <KpiCard
          label="Autonomy ratio"
          value={summary ? pct(summary.autonomy_ratio) : "—"}
          icon={Bot}
          accent="agenthq"
          hint={
            summary
              ? `${fmtNumber(summary.agent_driven)} agent · ${fmtNumber(summary.human_gated)} gated`
              : undefined
          }
          loading={isLoading}
        />
        <KpiCard
          label="Total spend"
          value={summary ? fmtUsd(summary.total_cost_usd, 2) : "—"}
          icon={TrendingUp}
          accent="warning"
          hint={
            data ? `over ${fmtNumber(data.sample_size)} entries` : undefined
          }
          loading={isLoading}
        />
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <Card className="p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-[var(--text)]">
              Volume + precedent reuse over time
            </h2>
            <span className="text-[11px] text-[var(--text-tertiary)]">
              decisions/day · precedent hits/day
            </span>
          </div>
          {isLoading ? (
            <div className="skeleton h-56 rounded" />
          ) : trendData.length === 0 ? (
            <EmptyState
              icon={TrendingUp}
              title="No trend data yet"
              description="Run a few stages or write entries via ledger.write_runtime; this chart populates as the ledger fills."
            />
          ) : (
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={trendData} margin={{ top: 8, right: 16, left: -8, bottom: 0 }}>
                  <CartesianGrid stroke="var(--border-default)" strokeDasharray="3 3" />
                  <XAxis
                    dataKey="date"
                    tick={{ fill: "var(--text-tertiary)", fontSize: 11 }}
                    stroke="var(--border-default)"
                  />
                  <YAxis
                    tick={{ fill: "var(--text-tertiary)", fontSize: 11 }}
                    stroke="var(--border-default)"
                    allowDecimals={false}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "var(--surface)",
                      border: "1px solid var(--border-default)",
                      borderRadius: 6,
                      fontSize: 12,
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Line
                    type="monotone"
                    dataKey="decisions"
                    stroke="var(--plane-ledger)"
                    strokeWidth={2}
                    dot={{ r: 3 }}
                    name="Decisions"
                  />
                  <Line
                    type="monotone"
                    dataKey="precedent_hits"
                    stroke="var(--success)"
                    strokeWidth={2}
                    dot={{ r: 3 }}
                    name="Precedent hits"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>

        <Card className="p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-[var(--text)]">
              Savings by team
            </h2>
            <span className="text-[11px] text-[var(--text-tertiary)]">
              top 6 by volume
            </span>
          </div>
          {isLoading ? (
            <div className="skeleton h-56 rounded" />
          ) : teamData.length === 0 ? (
            <EmptyState
              icon={Users}
              title="No team data yet"
              description="Multi-team breakdown shows up once two or more team_id values appear in the ledger window."
            />
          ) : (
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={teamData} margin={{ top: 8, right: 16, left: -8, bottom: 0 }}>
                  <CartesianGrid stroke="var(--border-default)" strokeDasharray="3 3" />
                  <XAxis
                    dataKey="team"
                    tick={{ fill: "var(--text-tertiary)", fontSize: 11 }}
                    stroke="var(--border-default)"
                  />
                  <YAxis
                    tick={{ fill: "var(--text-tertiary)", fontSize: 11 }}
                    stroke="var(--border-default)"
                  />
                  <Tooltip
                    contentStyle={{
                      background: "var(--surface)",
                      border: "1px solid var(--border-default)",
                      borderRadius: 6,
                      fontSize: 12,
                    }}
                    formatter={(v: unknown) => fmtUsd(typeof v === "number" ? v : 0, 2)}
                  />
                  <Bar
                    dataKey="saved"
                    fill="var(--success)"
                    radius={[4, 4, 0, 0]}
                    name="Saved $"
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>
      </div>

      <Card className="p-0 overflow-hidden">
        <div className="px-4 py-3 border-b border-[var(--border-default)]">
          <h2 className="text-sm font-semibold text-[var(--text)]">
            Per-team breakdown
          </h2>
          <p className="text-xs text-[var(--text-tertiary)] mt-1">
            Same metric definitions across teams — apples-to-apples scaling
            view. Each team's autonomy ratio + precedent hit-rate tells you
            whether they're early in the precedent-building curve or running
            mostly on cached patterns.
          </p>
        </div>
        {isLoading ? (
          <div className="p-4 space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="skeleton h-10 rounded" />
            ))}
          </div>
        ) : teams.length === 0 ? (
          <div className="p-6">
            <EmptyState
              icon={Users}
              title="No teams in ledger window"
              description="Routes the same data the cards above use; populates once any entries land."
            />
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-[11px] uppercase tracking-wider text-[var(--text-tertiary)] bg-[var(--overlay)]/30">
              <tr>
                <th className="text-left px-4 py-2 font-medium">Team</th>
                <th className="text-right px-4 py-2 font-medium">Decisions</th>
                <th className="text-right px-4 py-2 font-medium">Precedent</th>
                <th className="text-right px-4 py-2 font-medium">Autonomy</th>
                <th className="text-right px-4 py-2 font-medium">Spend</th>
                <th className="text-right px-4 py-2 font-medium">Saved</th>
              </tr>
            </thead>
            <tbody>
              {teams.map((t) => (
                <tr
                  key={t.team_id}
                  className="border-t border-[var(--border-default)] hover:bg-[var(--overlay)]/30"
                >
                  <td className="px-4 py-2 font-medium text-[var(--text)]">
                    {t.team_id}
                  </td>
                  <td className="px-4 py-2 text-right tabular text-[var(--text-secondary)]">
                    {fmtNumber(t.total_decisions)}
                  </td>
                  <td className="px-4 py-2 text-right tabular text-[var(--text-secondary)]">
                    {pct(t.precedent_hit_rate)}
                  </td>
                  <td className="px-4 py-2 text-right tabular text-[var(--text-secondary)]">
                    {pct(t.autonomy_ratio)}
                  </td>
                  <td className="px-4 py-2 text-right tabular text-[var(--text-secondary)]">
                    {fmtUsd(t.total_cost_usd, 2)}
                  </td>
                  <td className="px-4 py-2 text-right tabular text-[var(--success)] font-medium">
                    {fmtUsd(t.estimated_savings_usd, 2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <div className="text-[11px] text-[var(--text-tertiary)] leading-relaxed">
        <strong className="text-[var(--text-secondary)]">How savings is computed.</strong>{" "}
        Counterfactual = "if every precedent-hit decision instead hit a fresh
        LLM call." Per-decision novel cost is the rolling avg of{" "}
        <code className="px-1 py-0.5 rounded bg-[var(--overlay)]">cost_usd</code>{" "}
        on actual non-precedent decisions in the window. When zero novel
        decisions are present we fall back to a published constant and flag
        the result. Source aggregator:{" "}
        <code className="px-1 py-0.5 rounded bg-[var(--overlay)]">
          src/lib/economics/index.ts
        </code>{" "}
        (35 + tests). Every number is queryable from the ledger directly.
      </div>
    </div>
  );
}
