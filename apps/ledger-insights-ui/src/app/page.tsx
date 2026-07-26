"use client";
import Link from "next/link";
import { useMemo } from "react";
import {
  Activity, GitBranch, Library, Scale, Bot, ArrowRight, ExternalLink, Sparkles,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { KpiCard } from "@/components/domain/kpi-card";
import { RunCard } from "@/components/domain/run-card";
import { NeedsAttention } from "@/components/domain/needs-attention";
import { EmptyState } from "@/components/domain/empty-state";
import { useRuns, useTelemetryCost, useDecisions } from "@/lib/hooks/use-runs";
import { useAssistantContext } from "@/lib/assist/context";
import { buildAttentionQueue, attentionCounts } from "@/lib/attention";
import { fmtUsd } from "@/lib/utils";

export default function DashboardPage() {
  const { data: runs, isLoading: runsLoading } = useRuns();
  const { data: cost } = useTelemetryCost();
  const { data: decisions } = useDecisions({ limit: 200 });
  useAssistantContext({ kind: "dashboard", label: "Dashboard" });

  const runsList = useMemo(() => runs?.items ?? [], [runs]);
  const entries = useMemo(() => decisions?.entries ?? [], [decisions]);

  // The attention queue is the whole point of this page. Everything else is
  // context for it.
  const queue = useMemo(
    () => buildAttentionQueue(runsList, entries, { limit: 6 }),
    [runsList, entries],
  );
  const counts = useMemo(() => attentionCounts(runsList, entries), [runsList, entries]);
  const queueTotal = counts.blocked + counts.failed + counts.flagged + counts.stalled;

  const activeRuns = runsList.filter((r) =>
    ["running", "awaiting_gate", "paused", "queued"].includes(r.status),
  ).length;
  // Total failures, not just the 24h alert window. Reporting "0" because every
  // failure is 2 days old is technically true and deeply misleading — a ~50%
  // failure rate is the most important fact on this page.
  const failedTotal = runsList.filter((r) => r.status === "failed").length;
  const totalCost = cost?.total_cost_usd ?? 0;
  const recent = runsList.slice(0, 4);

  return (
    <div className="space-y-6">
      {/* Fold one: what needs a human. Not a pitch. */}
      <NeedsAttention items={queue} loading={runsLoading} total={queueTotal} />

      {/* KPIs are navigation, not decoration — each one filters a real view. */}
      <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard
          label="Active runs"
          value={runsLoading ? null : activeRuns}
          icon={GitBranch}
          accent="pipeline"
          hint="running, awaiting, paused, queued"
          loading={runsLoading}
          href="/runs?view=active"
        />
        <KpiCard
          label="Blocked on a human"
          value={runsLoading ? null : counts.blocked}
          icon={Scale}
          accent={counts.blocked > 0 ? "warning" : "ledger"}
          hint="gates waiting for a decision"
          loading={runsLoading}
          href="/runs?view=attention"
        />
        <KpiCard
          label="Failed runs"
          value={runsLoading ? null : failedTotal}
          icon={Activity}
          accent={failedTotal > 0 ? "danger" : "ledger"}
          hint={
            runsList.length > 0
              ? `${Math.round((failedTotal / runsList.length) * 100)}% of all runs`
              : "produced no delivery"
          }
          loading={runsLoading}
          href="/runs?view=failed"
        />
        <KpiCard
          label="Spend (period)"
          value={fmtUsd(totalCost, 2)}
          icon={Library}
          accent="standards"
          hint="model inference + tools"
          href="/economics"
        />
      </section>

      {/* Recent activity — context, deliberately below the queue. */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold">Recent activity</h2>
            <p className="text-xs text-[var(--text-tertiary)]">
              Latest pipeline runs. Click any run for stage events, decisions, and the gate timeline.
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
            {recent.map((run) => (
              <RunCard key={run.run_id} run={run} />
            ))}
          </div>
        )}
      </section>

      {/* Shortcuts + the architecture explainer, which belongs here — not in the fold. */}
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

      <div className="flex justify-end">
        <Button variant="ghost" size="sm" asChild>
          <a
            href="https://github.com/idanshimon/agentic-sdlc/blob/main/docs/explainer.html"
            target="_blank"
            rel="noreferrer"
          >
            How the four planes fit together <ExternalLink className="h-3 w-3" />
          </a>
        </Button>
      </div>
    </div>
  );
}
