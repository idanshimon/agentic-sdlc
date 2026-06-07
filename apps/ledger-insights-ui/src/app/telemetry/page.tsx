"use client";
import { useTelemetryCost, useTelemetryClasses } from "@/lib/hooks/use-runs";
import { Card } from "@/components/ui/card";
import { PageHeader } from "@/components/layout/page-header";
import { fmtUsd, fmtNumber } from "@/lib/utils";
import { KpiCard } from "@/components/domain/kpi-card";
import { DollarSign, Activity, Brain, Hash } from "lucide-react";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid,
} from "recharts";

export default function TelemetryPage() {
  const { data: cost, isLoading: costLoading } = useTelemetryCost();
  const { data: classes, isLoading: classesLoading } = useTelemetryClasses();

  const classPoints = classes?.classes ?? [];
  const costByStage = cost?.cost_by_stage ?? {};
  const stageBars = Object.entries(costByStage).map(([stage, usd]) => ({
    stage,
    usd: Number(usd) || 0,
  }));

  return (
    <div className="space-y-6">
      <PageHeader
        plane="pipeline"
        title="Telemetry"
        description="Token spend, ambiguity classes, gate counts. Sourced live from the orchestrator telemetry endpoints — every metric is queryable via /api/telemetry/*."
      />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard
          label="Total spend (24h)"
          value={fmtUsd(cost?.total_cost_usd ?? 0, 2)}
          icon={DollarSign}
          accent="warning"
          hint={cost?.window ?? "—"}
          loading={costLoading}
        />
        <KpiCard
          label="Decisions"
          value={fmtNumber(cost?.total_decisions ?? 0)}
          icon={Activity}
          accent="ledger"
          hint={`${cost?.human_decisions ?? 0} human · ${cost?.autopilot_decisions ?? 0} autopilot`}
          loading={costLoading}
        />
        <KpiCard
          label="Tokens (24h)"
          value={fmtNumber(cost?.total_tokens ?? 0)}
          icon={Hash}
          accent="pipeline"
          hint={`mean ${fmtNumber(Math.round(cost?.mean_tokens_per_run ?? 0))}/run`}
          loading={costLoading}
        />
        <KpiCard
          label="Cost per decision"
          value={fmtUsd(cost?.cost_per_decision_usd ?? 0, 4)}
          icon={Brain}
          accent="primary"
          hint="model + tools"
          loading={costLoading}
        />
      </div>

      <Card className="p-5">
        <h3 className="text-sm font-semibold mb-1">Cost by stage</h3>
        <p className="text-xs text-[var(--text-tertiary)] mb-4">
          Breakdown of total spend across the seven pipeline stages.
        </p>
        <div className="h-64">
          {costLoading ? (
            <div className="skeleton h-full" />
          ) : stageBars.every((p) => p.usd === 0) ? (
            <div className="h-full flex items-center justify-center text-xs text-[var(--text-tertiary)]">
              No spend recorded yet — submit a PRD via /api/run to populate this chart
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={stageBars}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-muted)" />
                <XAxis dataKey="stage" stroke="var(--text-tertiary)" fontSize={11} />
                <YAxis
                  stroke="var(--text-tertiary)"
                  fontSize={11}
                  tickFormatter={(v) => fmtUsd(typeof v === "number" ? v : Number(v), 2)}
                />
                <Tooltip
                  contentStyle={{
                    background: "var(--elevated)",
                    border: "1px solid var(--border-default)",
                    borderRadius: 6,
                    color: "var(--text)",
                    fontSize: 12,
                  }}
                  formatter={(v) => fmtUsd(typeof v === "number" ? v : Number(v), 4)}
                />
                <Bar dataKey="usd" fill="var(--plane-pipeline)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </Card>

      <Card className="p-5">
        <h3 className="text-sm font-semibold mb-1">Ambiguity classes</h3>
        <p className="text-xs text-[var(--text-tertiary)] mb-4">
          Where the pipeline is asking for human resolution most often. Window: {classes?.window ?? "—"}
        </p>
        <div className="h-72">
          {classesLoading ? (
            <div className="skeleton h-full" />
          ) : classPoints.length === 0 ? (
            <div className="h-full flex items-center justify-center text-xs text-[var(--text-tertiary)]">
              No ambiguity classifications recorded yet
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={classPoints} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-muted)" />
                <XAxis type="number" stroke="var(--text-tertiary)" fontSize={11} />
                <YAxis
                  type="category"
                  dataKey="ambiguity_class"
                  stroke="var(--text-tertiary)"
                  fontSize={11}
                  width={150}
                />
                <Tooltip
                  contentStyle={{
                    background: "var(--elevated)",
                    border: "1px solid var(--border-default)",
                    borderRadius: 6,
                    color: "var(--text)",
                    fontSize: 12,
                  }}
                />
                <Bar dataKey="count" fill="var(--plane-standards)" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </Card>
    </div>
  );
}
