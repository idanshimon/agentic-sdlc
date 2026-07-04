"use client";
import Link from "next/link";
import {
  Activity, GitBranch, Library, Scale, Bot, ShieldCheck,
  ArrowRight, ExternalLink, Github, Sparkles,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { KpiCard } from "@/components/domain/kpi-card";
import { RunCard } from "@/components/domain/run-card";
import { ArchitectureMini } from "@/components/domain/architecture-mini";
import { EmptyState } from "@/components/domain/empty-state";
import { useRuns, useTelemetryCost, useHealth } from "@/lib/hooks/use-runs";
import { useAssistantContext } from "@/lib/assist/context";
import { fmtUsd } from "@/lib/utils";

export default function DashboardPage() {
  const { data: runs, isLoading: runsLoading } = useRuns();
  const { data: cost } = useTelemetryCost();
  const { data: health } = useHealth();
  useAssistantContext({ kind: "dashboard", label: "Dashboard" });

  const runsList = runs?.items ?? [];
  const activeRuns = runsList.filter((r) =>
    ["running", "awaiting_gate", "paused", "queued"].includes(r.status),
  ).length;
  const totalCost = cost?.total_cost_usd ?? 0;
  const mcpToolCount = health?.tools?.length ?? 0;

  return (
    <div className="space-y-6">
      {/* Hero */}
      <section className="rounded-xl border border-[var(--border-default)] bg-gradient-to-br from-[var(--surface)] via-[var(--surface)] to-[var(--elevated)] p-6 relative overflow-hidden">
        <div
          className="absolute inset-0 opacity-30 pointer-events-none"
          style={{
            background:
              "radial-gradient(circle at 0% 0%, var(--plane-standards) 0%, transparent 40%), radial-gradient(circle at 100% 0%, var(--plane-pipeline) 0%, transparent 40%), radial-gradient(circle at 0% 100%, var(--plane-ledger) 0%, transparent 40%), radial-gradient(circle at 100% 100%, var(--plane-agenthq) 0%, transparent 40%)",
          }}
        />
        <div className="relative flex flex-col lg:flex-row gap-6 items-start justify-between">
          <div className="flex-1 min-w-0 space-y-3">
            <Badge variant="secondary" className="text-[10px]">
              <Sparkles className="h-2.5 w-2.5" />
              v0.7-rc1 · live
            </Badge>
            <h1 className="text-3xl font-semibold tracking-tight text-[var(--text)] max-w-2xl">
              Governed agentic SDLC, made auditable.
            </h1>
            <p className="text-sm text-[var(--text-secondary)] max-w-2xl leading-relaxed">
              Four planes — <span className="text-[var(--plane-standards)] font-medium">Standards</span>,{" "}
              <span className="text-[var(--plane-pipeline)] font-medium">Pipeline</span>,{" "}
              <span className="text-[var(--plane-ledger)] font-medium">Ledger + Doctor</span>, and{" "}
              <span className="text-[var(--plane-agenthq)] font-medium">Agent HQ</span> — wired so every
              AI-agent decision is captured, every standards change is committee-approved, and every
              PHI rule is enforced at the hook layer before a single token is generated.
            </p>
            <div className="flex flex-wrap gap-2 pt-1">
              <Button variant="primary" asChild>
                <Link href="/runs">View live runs <ArrowRight className="h-4 w-4" /></Link>
              </Button>
              <Button variant="secondary" asChild>
                <a href="https://github.com/idanshimon/agentic-sdlc" target="_blank" rel="noreferrer">
                  <Github className="h-4 w-4" /> Source
                </a>
              </Button>
              <Button variant="ghost" asChild>
                <a
                  href="https://ca-orchestrator-vnet.thankfulflower-0a94d0d3.eastus2.azurecontainerapps.io/docs"
                  target="_blank"
                  rel="noreferrer"
                >
                  API docs <ExternalLink className="h-3.5 w-3.5" />
                </a>
              </Button>
            </div>
          </div>
          <Card className="w-full lg:w-[280px] p-4 bg-[var(--bg)]/50 border-[var(--border-default)]">
            <div className="text-[10px] font-medium uppercase tracking-wider text-[var(--text-tertiary)] mb-3">
              Live infrastructure
            </div>
            <div className="space-y-2.5 text-xs">
              <div className="flex items-center justify-between gap-3">
                <span className="text-[var(--text-secondary)]">Orchestrator</span>
                <span className="mono text-[10px] text-[var(--success)] truncate">200 OK</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-[var(--text-secondary)]">Ledger MCP</span>
                <span className="mono text-[10px] text-[var(--success)]">v0.7.0</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-[var(--text-secondary)]">MCP tools</span>
                <span className="mono text-[10px] tabular text-[var(--text)]">{mcpToolCount}</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-[var(--text-secondary)]">Region</span>
                <span className="mono text-[10px] text-[var(--text)]">eastus2</span>
              </div>
              <div className="flex items-center justify-between gap-3 pt-2 border-t border-[var(--border-default)]">
                <span className="text-[var(--text-secondary)]">Auth</span>
                <span className="mono text-[10px] text-[var(--text)]">Managed Identity</span>
              </div>
            </div>
          </Card>
        </div>
      </section>

      {/* KPIs */}
      <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard
          label="Active runs"
          value={runsLoading ? null : activeRuns}
          icon={GitBranch}
          accent="pipeline"
          hint="running, awaiting, paused, queued"
          loading={runsLoading}
        />
        <KpiCard
          label="Decisions logged"
          value={runsLoading ? null : runsList.reduce((acc, r) => acc + (r.decisions_count ?? 0), 0) || (cost?.total_decisions ?? 0)}
          icon={Scale}
          accent="ledger"
          hint="across all runs"
          loading={runsLoading}
        />
        <KpiCard
          label="Spend (period)"
          value={fmtUsd(totalCost, 2)}
          icon={Activity}
          accent="warning"
          hint="model inference + tools"
        />
        <KpiCard
          label="Active bundles"
          value={4}
          icon={Library}
          accent="standards"
          hint="security · privacy · architect · finops"
        />
      </section>

      {/* Architecture mini */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold">Architecture</h2>
            <p className="text-xs text-[var(--text-tertiary)]">
              The four planes you&apos;re operating against.
            </p>
          </div>
          <Button variant="ghost" size="sm" asChild>
            <a
              href="https://github.com/idanshimon/agentic-sdlc/blob/main/docs/explainer.html"
              target="_blank"
              rel="noreferrer"
            >
              Full explainer <ExternalLink className="h-3 w-3" />
            </a>
          </Button>
        </div>
        <ArchitectureMini />
      </section>

      {/* Recent runs */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold">Recent runs</h2>
            <p className="text-xs text-[var(--text-tertiary)]">
              Pipeline activity in the last 24h. Click any run to drill into stage events, decisions, and the gate timeline.
            </p>
          </div>
          <Button variant="ghost" size="sm" asChild>
            <Link href="/runs">All runs <ArrowRight className="h-3 w-3" /></Link>
          </Button>
        </div>
        {runsLoading ? (
          <div className="grid gap-3 md:grid-cols-2">
            <div className="skeleton h-32 rounded-lg" />
            <div className="skeleton h-32 rounded-lg" />
          </div>
        ) : runsList.length === 0 ? (
          <EmptyState
            icon={GitBranch}
            title="No runs yet"
            description="Start a new run from a sample PRD or paste your own. Every run streams through the 7-stage pipeline; gates pause for human review when ambiguity is high."
            action={
              <Button variant="primary" asChild>
                <Link href="/runs/new">
                  Start a run <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
            }
          />
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {runsList.slice(0, 6).map((run) => (
              <RunCard key={run.run_id} run={run} />
            ))}
          </div>
        )}
      </section>

      {/* Plane shortcuts — Reports is the management surface */}
      <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          { href: "/reports", title: "Reports", desc: "Exec-readable governance posture, cost, drift.", icon: Sparkles, plane: "ledger" },
          { href: "/decisions", title: "Decisions", desc: "Read the audit trail of every agent decision.", icon: Scale, plane: "ledger" },
          { href: "/bundles", title: "Bundles", desc: "Inspect the rules and pinned versions.", icon: Library, plane: "standards" },
          { href: "/agents", title: "Custom agents", desc: "Personas, bundle subscriptions, ledger writes.", icon: Bot, plane: "agenthq" },
        ].map((t) => {
          const Icon = t.icon;
          return (
            <Link key={t.href} href={t.href} className="group">
              <Card className="p-4 h-full hover:border-[var(--text-tertiary)] transition-colors">
                <div className="flex items-center gap-2 mb-2">
                  <Icon className="h-4 w-4" style={{ color: `var(--plane-${t.plane})` }} />
                  <h3 className="text-sm font-semibold">{t.title}</h3>
                  <ArrowRight className="h-3.5 w-3.5 ml-auto text-[var(--text-tertiary)] opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
                <p className="text-xs text-[var(--text-tertiary)] leading-relaxed">{t.desc}</p>
              </Card>
            </Link>
          );
        })}
      </section>
    </div>
  );
}
