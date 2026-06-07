"use client";
import {
  Sparkles, ShieldCheck, ShieldAlert, TrendingUp, TrendingDown, Minus,
  DollarSign, Scale, Clock, FileWarning, CheckCircle2, ExternalLink,
  Download,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { KpiCard } from "@/components/domain/kpi-card";
import { PageHeader } from "@/components/layout/page-header";
import { useAssistantContext } from "@/lib/assist/context";
import { fmtUsd, fmtNumber, cn } from "@/lib/utils";
import {
  ResponsiveContainer, LineChart, Line, AreaChart, Area, XAxis, YAxis, Tooltip,
  CartesianGrid, BarChart, Bar, Cell,
} from "recharts";

/* /reports — management dashboard.
 *
 * Audience: engineering leadership, CFO, compliance officer.
 * Different shape from /telemetry: that's the operator's chart-grid;
 * this is the exec narrative. Posture score, cost narrative, autopilot
 * maturity, drift signals, board-ready PDF export.
 *
 * Demo mode renders pre-canned data; live mode would pull aggregates from
 * /api/telemetry/* + the ledger. The narrative copy is the same in both
 * modes — that's the point of the page (it normalizes data into prose).
 */

// Pre-canned but realistic scoring breakdown.
const POSTURE_DETAIL = [
  {
    label: "Bundle-rule coverage",
    value: 100,
    weight: 0.4,
    note: "Every active stage cites at least one bundle rule per decision.",
    trend: 0,
  },
  {
    label: "Citation completeness",
    value: 95,
    weight: 0.3,
    note: "1 decision missing precedent_refs (auto-deferred non-gating card).",
    trend: 2,
  },
  {
    label: "Prompt-version currency",
    value: 75,
    weight: 0.2,
    note: "test_plan.derive is on v0.1.0; v0.2.0 (decision-grounded) ready to roll.",
    trend: 0,
  },
  {
    label: "Autopilot precedent confidence",
    value: 80,
    weight: 0.1,
    note: "Mean precedent-match score 0.84 across last 30 decisions.",
    trend: 4,
  },
];

const COST_TREND = [
  { day: "Mon", spend: 0.42, decisions: 5 },
  { day: "Tue", spend: 0.61, decisions: 7 },
  { day: "Wed", spend: 0.55, decisions: 6 },
  { day: "Thu", spend: 0.78, decisions: 9 },
  { day: "Fri", spend: 0.64, decisions: 7 },
  { day: "Sat", spend: 0.21, decisions: 2 },
  { day: "Sun", spend: 0.62, decisions: 5 },
];

const AUTOPILOT_TREND = [
  { week: "W-4", rate: 4 },
  { week: "W-3", rate: 5 },
  { week: "W-2", rate: 8 },
  { week: "W-1", rate: 10 },
  { week: "Now", rate: 12 },
];

const STAGE_COST_BREAKDOWN = [
  { stage: "codegen", pct: 32, accent: "var(--plane-pipeline)" },
  { stage: "architect", pct: 30, accent: "var(--plane-pipeline)" },
  { stage: "assessor", pct: 18, accent: "var(--plane-pipeline)" },
  { stage: "test_plan", pct: 12, accent: "var(--plane-pipeline)" },
  { stage: "review_scan", pct: 5, accent: "var(--plane-pipeline)" },
  { stage: "ingest", pct: 3, accent: "var(--plane-pipeline)" },
];

const COMPLIANCE_FACTS = [
  { label: "PHI violations (24h)", value: 0, total: 8, ok: true },
  { label: "Secret-scan blockers", value: 0, total: 8, ok: true },
  { label: "License-audit warnings", value: 1, total: 8, ok: false },
  { label: "MI audit failures", value: 0, total: 8, ok: true },
];

const DRIFT_SIGNALS = [
  {
    severity: "warning",
    title: "data-retention class +14% week-over-week",
    detail:
      "Cardiology team filed 3 PRDs without retention windows this week. Consider amending privacy/v0.1.0/RETENTION-001 to require an explicit retention block in PRDs.",
    suggested: "Draft openspec change",
  },
  {
    severity: "info",
    title: "auth-policy class -8% week-over-week",
    detail:
      "Improvement: PRDs are arriving with cleaner auth specs. Likely effect of the auth-checklist published in last sprint.",
    suggested: null,
  },
  {
    severity: "warning",
    title: "test_plan stage prompt is stale",
    detail:
      "v0.1.0 produces generic CRUD tests for streaming APIs (Bug #2 in eval). v0.2.0 ready in prompt library. Move to ship gate.",
    suggested: "Open prompt library",
  },
];

function postureScore(): number {
  return Math.round(
    POSTURE_DETAIL.reduce((acc, p) => acc + (p.value * p.weight), 0),
  );
}

function trendIcon(delta: number) {
  if (delta > 0)
    return { Icon: TrendingUp, color: "var(--success)", label: `+${delta}%` };
  if (delta < 0)
    return { Icon: TrendingDown, color: "var(--danger)", label: `${delta}%` };
  return { Icon: Minus, color: "var(--text-tertiary)", label: "—" };
}

export default function ReportsPage() {
  useAssistantContext({ kind: "reports", label: "Governance reports" });

  const score = postureScore();

  return (
    <div className="space-y-6">
      <PageHeader
        plane="ledger"
        title="Governance reports"
        description="Exec-readable view of the agentic SDLC governance posture. PHI compliance, cost trends, autopilot maturity, and drift signals — all sourced from the Decision Ledger and standards bundles."
        actions={
          <Button variant="secondary" size="sm">
            <Download className="h-3.5 w-3.5" />
            Export PDF
          </Button>
        }
      />

      {/* Posture KPI — the single number execs want */}
      <Card className="p-6 bg-gradient-to-br from-[var(--surface)] to-[var(--elevated)]">
        <div className="flex items-start justify-between gap-6 flex-wrap">
          <div className="space-y-2">
            <div className="text-[10px] uppercase tracking-wider font-medium text-[var(--text-tertiary)]">
              Governance posture score
            </div>
            <div className="flex items-baseline gap-2">
              <span className="text-5xl font-semibold tabular">{score}</span>
              <span className="text-2xl text-[var(--text-tertiary)]">/ 100</span>
              <Badge variant={score >= 90 ? "success" : score >= 75 ? "warning" : "danger"} className="ml-2">
                {score >= 90 ? "Healthy" : score >= 75 ? "Watch" : "At risk"}
              </Badge>
            </div>
            <p className="text-xs text-[var(--text-secondary)] leading-relaxed max-w-xl">
              Weighted average across bundle-rule coverage, citation
              completeness, prompt-version currency, and autopilot precedent
              confidence. Updates with every ledger entry.
            </p>
          </div>
          <div className="space-y-2 min-w-[280px]">
            {POSTURE_DETAIL.map((p) => {
              const t = trendIcon(p.trend);
              return (
                <div key={p.label} className="space-y-1">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-1.5">
                      <span className="text-[11px] text-[var(--text-secondary)]">{p.label}</span>
                      <span className="text-[10px] text-[var(--text-tertiary)] tabular">
                        × {(p.weight * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div className="flex items-center gap-1">
                      <span className="text-xs tabular font-medium">{p.value}</span>
                      <t.Icon className="h-2.5 w-2.5" style={{ color: t.color }} />
                    </div>
                  </div>
                  <div className="h-1 bg-[var(--overlay)] rounded-full overflow-hidden">
                    <div
                      className="h-full transition-all"
                      style={{
                        width: `${p.value}%`,
                        background:
                          p.value >= 90
                            ? "var(--success)"
                            : p.value >= 75
                              ? "var(--warning)"
                              : "var(--danger)",
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </Card>

      {/* KPI strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard
          label="Spend (7d)"
          value={fmtUsd(3.83, 2)}
          icon={DollarSign}
          accent="warning"
          hint="-12% vs prev 7d"
        />
        <KpiCard
          label="Decisions logged"
          value={fmtNumber(41)}
          icon={Scale}
          accent="ledger"
          hint="36 human · 5 autopilot"
        />
        <KpiCard
          label="Mean gate time"
          value="47s"
          icon={Clock}
          accent="pipeline"
          hint="-65% vs prev week"
        />
        <KpiCard
          label="Autopilot rate"
          value="12%"
          icon={Sparkles}
          accent="agenthq"
          hint="+4pp WoW"
        />
      </div>

      {/* 2-column: cost narrative + autopilot maturity */}
      <div className="grid lg:grid-cols-2 gap-3">
        <Card className="p-5 space-y-4">
          <div>
            <h3 className="text-sm font-semibold">Spend by day · last 7d</h3>
            <p className="text-xs text-[var(--text-tertiary)]">
              Cost is bounded — no week has crossed $1.50. Hard savings
              line for finance: $3.83 spent generated 41 audited decisions
              (cost per decision $0.094).
            </p>
          </div>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={COST_TREND}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-muted)" />
                <XAxis dataKey="day" stroke="var(--text-tertiary)" fontSize={11} />
                <YAxis stroke="var(--text-tertiary)" fontSize={11} tickFormatter={(v) => fmtUsd(v, 2)} />
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
                <Area
                  type="monotone"
                  dataKey="spend"
                  stroke="var(--warning)"
                  fill="var(--warning)"
                  fillOpacity={0.2}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <div className="grid grid-cols-3 gap-2 text-xs">
            <div className="space-y-0.5">
              <div className="text-[10px] uppercase tracking-wider text-[var(--text-tertiary)]">Hard savings</div>
              <div className="text-sm tabular">{fmtUsd(3.83, 2)}</div>
              <div className="text-[10px] text-[var(--text-tertiary)]">model + tools</div>
            </div>
            <div className="space-y-0.5">
              <div className="text-[10px] uppercase tracking-wider text-[var(--text-tertiary)]">Cost avoidance</div>
              <div className="text-sm tabular">{fmtUsd(8400, 0)}</div>
              <div className="text-[10px] text-[var(--text-tertiary)]">blast-radius averted</div>
            </div>
            <div className="space-y-0.5">
              <div className="text-[10px] uppercase tracking-wider text-[var(--text-tertiary)]">ROI</div>
              <div className="text-sm tabular">2,194×</div>
              <div className="text-[10px] text-[var(--text-tertiary)]">avoidance / spend</div>
            </div>
          </div>
        </Card>

        <Card className="p-5 space-y-4">
          <div>
            <h3 className="text-sm font-semibold">Autopilot maturity curve</h3>
            <p className="text-xs text-[var(--text-tertiary)]">
              % of decisions resolved without human intervention. Rises
              monotonically as the precedent ledger grows.
            </p>
          </div>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={AUTOPILOT_TREND}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-muted)" />
                <XAxis dataKey="week" stroke="var(--text-tertiary)" fontSize={11} />
                <YAxis stroke="var(--text-tertiary)" fontSize={11} tickFormatter={(v) => `${v}%`} />
                <Tooltip
                  contentStyle={{
                    background: "var(--elevated)",
                    border: "1px solid var(--border-default)",
                    borderRadius: 6,
                    color: "var(--text)",
                    fontSize: 12,
                  }}
                  formatter={(v) => `${v}%`}
                />
                <Line
                  type="monotone"
                  dataKey="rate"
                  stroke="var(--plane-agenthq)"
                  strokeWidth={2}
                  dot={{ r: 4, fill: "var(--plane-agenthq)" }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="text-[11px] text-[var(--text-secondary)] leading-relaxed">
            <span className="text-[var(--success)] font-medium">+4pp WoW.</span>{" "}
            Trajectory says ~25% by Q4 if precedent additions continue. PHI
            and auth-policy classes intentionally remain 0% autopilot —
            those always go to human resolution by bundle rule.
          </p>
        </Card>
      </div>

      {/* Cost breakdown by stage + compliance facts */}
      <div className="grid lg:grid-cols-2 gap-3">
        <Card className="p-5 space-y-4">
          <div>
            <h3 className="text-sm font-semibold">Where the spend went · stage breakdown</h3>
            <p className="text-xs text-[var(--text-tertiary)]">
              Codegen + Architect dominate (62% combined) — that&apos;s where the
              real reasoning happens. Lever to consider: shifting Codegen
              from sonnet-4-6 to haiku-4-5 for runs without security/architect
              bundle citations saves ~40% on that stage.
            </p>
          </div>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={STAGE_COST_BREAKDOWN} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-muted)" />
                <XAxis type="number" stroke="var(--text-tertiary)" fontSize={11} tickFormatter={(v) => `${v}%`} />
                <YAxis
                  type="category"
                  dataKey="stage"
                  stroke="var(--text-tertiary)"
                  fontSize={11}
                  width={90}
                />
                <Tooltip
                  contentStyle={{
                    background: "var(--elevated)",
                    border: "1px solid var(--border-default)",
                    borderRadius: 6,
                    color: "var(--text)",
                    fontSize: 12,
                  }}
                  formatter={(v) => `${v}%`}
                />
                <Bar dataKey="pct" radius={[0, 4, 4, 0]}>
                  {STAGE_COST_BREAKDOWN.map((entry, i) => (
                    <Cell key={i} fill={entry.accent} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card className="p-5 space-y-4">
          <div>
            <h3 className="text-sm font-semibold">Compliance facts · last 24h</h3>
            <p className="text-xs text-[var(--text-tertiary)]">
              Hard-gated by bundle rules. Every fact below is auditable
              from the Decision Ledger.
            </p>
          </div>
          <div className="space-y-2">
            {COMPLIANCE_FACTS.map((f) => {
              const Icon = f.ok ? CheckCircle2 : ShieldAlert;
              return (
                <div
                  key={f.label}
                  className={cn(
                    "rounded-md border px-3 py-2.5 flex items-center gap-3",
                    f.ok
                      ? "border-[var(--success)]/30 bg-[var(--success)]/5"
                      : "border-[var(--warning)]/30 bg-[var(--warning)]/5",
                  )}
                >
                  <Icon
                    className={cn(
                      "h-4 w-4 shrink-0",
                      f.ok ? "text-[var(--success)]" : "text-[var(--warning)]",
                    )}
                  />
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-medium">{f.label}</div>
                    <div className="text-[10px] text-[var(--text-tertiary)] tabular">
                      {f.value} of {f.total} runs
                    </div>
                  </div>
                  <Badge variant={f.ok ? "success" : "warning"} className="text-[10px]">
                    {f.ok ? "PASS" : "WATCH"}
                  </Badge>
                </div>
              );
            })}
          </div>
        </Card>
      </div>

      {/* Drift watch */}
      <Card className="p-5 space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold flex items-center gap-2">
              <FileWarning className="h-4 w-4 text-[var(--warning)]" />
              Drift watch
            </h3>
            <p className="text-xs text-[var(--text-tertiary)]">
              Pipeline Doctor flagged these signals for human review. Each
              has a one-click remediation path.
            </p>
          </div>
        </div>
        <div className="space-y-2">
          {DRIFT_SIGNALS.map((s, i) => (
            <div
              key={i}
              className={cn(
                "rounded-md border px-3 py-3",
                s.severity === "warning"
                  ? "border-[var(--warning)]/30 bg-[var(--warning)]/5"
                  : "border-[var(--border-muted)]",
              )}
            >
              <div className="flex items-start gap-2">
                <Badge
                  variant={s.severity === "warning" ? "warning" : "info"}
                  className="text-[10px] mt-0.5 shrink-0"
                >
                  {s.severity}
                </Badge>
                <div className="flex-1 min-w-0 space-y-1">
                  <div className="text-xs font-medium">{s.title}</div>
                  <p className="text-[11px] text-[var(--text-secondary)] leading-relaxed">
                    {s.detail}
                  </p>
                  {s.suggested && (
                    <Button variant="secondary" size="sm" className="h-7 mt-1">
                      <Sparkles className="h-3 w-3" />
                      {s.suggested}
                    </Button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </Card>

      <Card className="p-4 bg-gradient-to-r from-[var(--plane-agenthq)]/5 to-[var(--plane-ledger)]/5 border-[var(--plane-agenthq)]/30">
        <div className="flex items-center gap-3">
          <Sparkles className="h-5 w-5 text-[var(--plane-agenthq)] shrink-0" />
          <div className="flex-1">
            <div className="text-sm font-medium">
              Want this report explained line-by-line?
            </div>
            <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
              Press <span className="mono text-[10px] px-1 py-0.5 rounded bg-[var(--overlay)]">⌘K</span>{" "}
              and ask &ldquo;explain score&rdquo; or &ldquo;where should I focus this week?&rdquo;.
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
}
