"use client";
/* AutonomyRules — where the agent is trusted, where it's stopped, and why.
 *
 * The PR review loop is one autonomy mechanism; per-decision autonomy
 * governance is another, and it runs on every single decision. This renders
 * the second from `autonomy_ref`, which the ledger already stamps. */
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Lock, Bot, UserCheck } from "lucide-react";
import type { AutonomyRule, AutonomySummary } from "@/lib/autonomy-governance";

export function AutonomyRules({
  summary,
  isLoading = false,
}: {
  summary: AutonomySummary;
  isLoading?: boolean;
}) {
  // Rendering nothing while the ledger loads is indistinguishable from "this
  // feature is broken" — the exact failure this page already had. Show the
  // skeleton, then either real rules or an explicit reason there are none.
  if (isLoading) {
    return (
      <section className="space-y-3">
        <div className="h-4 w-48 skeleton rounded" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-16 skeleton rounded-lg" />
          ))}
        </div>
        <div className="space-y-2">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-20 skeleton rounded-lg" />
          ))}
        </div>
      </section>
    );
  }

  if (summary.rules.length === 0) {
    return (
      <section className="rounded-lg border border-[var(--border-default)] bg-[var(--surface)] p-4">
        <h2 className="text-base font-semibold text-[var(--text)]">
          Autonomy rules in force
        </h2>
        <p className="mt-1 text-xs leading-relaxed text-[var(--text-secondary)]">
          No decision in the ledger carries an autonomy reference yet. Every
          decision the pipeline makes records which rule allowed the agent to act
          alone — once a run completes, the rules it exercised appear here.
        </p>
      </section>
    );
  }

  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-base font-semibold text-[var(--text)]">
          Autonomy rules in force
        </h2>
        <p className="text-xs text-[var(--text-tertiary)]">
          Every decision records which rule decided whether an agent could act alone.
          Derived from {summary.totalGoverned} governed decisions in the ledger.
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Governed decisions" value={summary.totalGoverned} />
        <Stat label="Agent acted alone" value={summary.autopilotCount} accent="var(--success)" />
        <Stat label="Stopped for a human" value={summary.gatedCount} accent="var(--warning)" />
        <Stat label="Autonomy earned" value={`${summary.autonomyPct}%`} accent="var(--primary)" />
      </div>

      <div className="space-y-2">
        {summary.rules.map((rule) => (
          <RuleRow key={rule.ref} rule={rule} />
        ))}
      </div>
    </section>
  );
}

function Stat({ label, value, accent }: { label: string; value: string | number; accent?: string }) {
  return (
    <Card className="p-3">
      <div className="text-[11px] uppercase tracking-wider text-[var(--text-tertiary)]">{label}</div>
      <div
        className="text-xl font-semibold tabular leading-none mt-1"
        style={accent ? { color: accent } : undefined}
      >
        {value}
      </div>
    </Card>
  );
}

function RuleRow({ rule }: { rule: AutonomyRule }) {
  const isInvariant = rule.family === "invariant";
  const isAutopilot = rule.outcome === "autopilot";
  const Icon = isInvariant ? Lock : isAutopilot ? Bot : UserCheck;
  const color = isInvariant
    ? "var(--danger)"
    : isAutopilot
      ? "var(--success)"
      : "var(--warning)";

  return (
    <Card className="relative flex items-start gap-3 p-4 pl-5">
      <span
        aria-hidden
        className="absolute left-0 top-0 h-full w-[3px] rounded-l-lg"
        style={{ background: color }}
      />
      <Icon className="h-4 w-4 mt-0.5 shrink-0" style={{ color }} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium text-[var(--text)]">{rule.ambiguityClass}</span>
          <Badge variant={isInvariant ? "danger" : isAutopilot ? "success" : "warning"}>
            {isInvariant ? "hard lock" : isAutopilot ? "autopilot" : "human gate"}
          </Badge>
          <span className="mono text-[10px] text-[var(--text-tertiary)]">{rule.ruleId}</span>
        </div>
        <p className="mt-0.5 text-xs text-[var(--text-secondary)] leading-relaxed">
          {rule.explanation}
        </p>
        <div className="mt-1.5 flex flex-wrap gap-3 text-[11px] text-[var(--text-tertiary)] tabular">
          <span>{rule.decisionCount} decisions</span>
          <span>{rule.runCount} runs</span>
          <span>{rule.humanCount} human</span>
          <span>{rule.agentCount} agent</span>
        </div>
      </div>
    </Card>
  );
}
