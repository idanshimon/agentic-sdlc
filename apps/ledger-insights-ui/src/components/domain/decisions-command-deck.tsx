"use client";
/* Decisions command deck — the mission-control header shared by all four
 * Decisions views (table / map / lineage / run flow). One dataset, one deck:
 *
 *   [ autonomy gauge ] [ human-vs-agent daily timeline ] [ class autonomy matrix ]
 *
 * Every figure is derived from the same entries the view below renders, so a
 * number here can always be reconciled against a row there. Clicking a class
 * opens the table filtered to it. Motion via the HyperFrames timeline hook.
 */
import Link from "next/link";
import { useMemo } from "react";
import { Bot, User, Sprout, Flag, ShieldAlert, DollarSign } from "lucide-react";
import { Card } from "@/components/ui/card";
import type { LedgerEntry } from "@/lib/types";
import { classBreakdown, dailyTimeline, decidedBy, stageDecisions } from "@/lib/decision-signal";
import { buildLineageIndex } from "@/lib/lineage";
import { CountUp, useHyperframe } from "@/lib/hyperframe";
import { fmtUsd } from "@/lib/utils";

export function DecisionsCommandDeck({ entries, compact }: { entries: LedgerEntry[]; compact?: boolean }) {
  const d = useMemo(() => {
    const decisions = stageDecisions(entries);
    const agent = decisions.filter((e) => decidedBy(e) === "agent").length;
    const human = decisions.length - agent;
    const costed = decisions.filter((e) => typeof e.cost_usd === "number" && e.cost_usd > 0);
    const spend = costed.reduce((s, e) => s + e.cost_usd, 0);
    const phiHigh = decisions.filter((e) => e.phi_class === "high").length;
    const flagged = entries.filter((e) => e.runtime_kind === "decision_flagged").length;
    const signals = entries.length - decisions.length;
    const { metrics } = buildLineageIndex(entries);
    return {
      total: decisions.length, agent, human, spend, costed: costed.length, phiHigh, flagged, signals, metrics,
      timeline: dailyTimeline(entries),
      classes: classBreakdown(entries),
    };
  }, [entries]);

  const ref = useHyperframe<HTMLDivElement>([d.total]);
  const pct = d.total ? d.agent / d.total : 0;

  return (
    <div ref={ref} className={`grid gap-3 ${compact ? "lg:grid-cols-[220px_minmax(0,1fr)]" : "lg:grid-cols-[220px_minmax(0,1.3fr)_minmax(0,1fr)]"}`}>
      {/* Gauge */}
      <Card data-hf="rise" className="relative flex flex-col items-center justify-center overflow-hidden p-4">
        <Gauge pct={pct} />
        <div className="-mt-14 text-center">
          <div className="tabular text-3xl font-semibold leading-none">
            <CountUp value={Math.round(pct * 100)} />%
          </div>
          <div className="mt-1 text-[11px] text-[var(--text-secondary)]">decided by agents</div>
        </div>
        <div className="mt-4 grid w-full grid-cols-2 gap-2 text-center text-[11px]">
          <div className="rounded-md bg-[var(--elevated)] py-1.5">
            <Bot className="mx-auto mb-0.5 h-3.5 w-3.5 text-[var(--secondary)]" />
            <CountUp value={d.agent} className="tabular text-sm font-semibold" />
            <div className="text-[var(--text-tertiary)]">agent</div>
          </div>
          <div className="rounded-md bg-[var(--elevated)] py-1.5">
            <User className="mx-auto mb-0.5 h-3.5 w-3.5 text-[var(--primary)]" />
            <CountUp value={d.human} className="tabular text-sm font-semibold" />
            <div className="text-[var(--text-tertiary)]">human</div>
          </div>
        </div>
      </Card>

      {/* Timeline + KPI ticker */}
      <Card data-hf="rise" className="flex min-w-0 flex-col p-4">
        <div className="mb-2 flex flex-wrap items-center gap-x-5 gap-y-1">
          <Kpi label="Decisions" value={<CountUp value={d.total} />} />
          <Kpi
            label="Autonomy earned"
            icon={<Sprout className="h-3 w-3 text-[var(--success)]" />}
            value={<><CountUp value={d.metrics.autonomyEarnedPct} />%</>}
            hint={d.metrics.taughtCount ? `${d.metrics.reusedCount} reused from ${d.metrics.taughtCount} taught` : "no human override reused yet"}
          />
          <Kpi label="Flagged" icon={<Flag className="h-3 w-3 text-[var(--warning)]" />} value={<CountUp value={d.flagged} />} />
          <Kpi label="PHI high" icon={<ShieldAlert className="h-3 w-3 text-[var(--danger)]" />} value={<CountUp value={d.phiHigh} />} />
          <Kpi
            label="Spend"
            icon={<DollarSign className="h-3 w-3 text-[var(--text-tertiary)]" />}
            value={d.costed ? fmtUsd(d.spend, 2) : "not recorded"}
            hint={d.costed ? `${d.costed} of ${d.total} costed` : undefined}
          />
        </div>
        <Timeline buckets={d.timeline} />
      </Card>

      {/* Class autonomy matrix */}
      {!compact && (
        <Card data-hf="rise" className="min-w-0 p-4">
          <div className="mb-2 flex items-baseline justify-between">
            <h3 className="text-xs font-semibold">Autonomy by ambiguity class</h3>
            <span className="text-[10px] text-[var(--text-tertiary)]">agent share · click to filter</span>
          </div>
          <ul className="space-y-1.5">
            {d.classes.rows.slice(0, 7).map((r) => (
              <li key={r.klass}>
                <Link
                  href={`/decisions?q=${encodeURIComponent(r.klass)}`}
                  className="group grid grid-cols-[minmax(0,1fr)_96px_28px] items-center gap-2 rounded px-1 py-0.5 hover:bg-[var(--overlay)]"
                >
                  <span className="mono truncate text-[11px] text-[var(--text-secondary)] group-hover:text-[var(--text)]">{r.klass}</span>
                  <span className="flex h-2 overflow-hidden rounded-full bg-[color-mix(in_srgb,var(--primary)_var(--tint-strong),transparent)]" title={`${r.agent} agent · ${r.human} human`}>
                    <span data-hf="grow-x" className="block h-full bg-[var(--secondary)]" style={{ width: `${r.autonomy * 100}%` }} />
                  </span>
                  <span className="tabular text-right text-[11px] text-[var(--text)]">{r.total}</span>
                </Link>
              </li>
            ))}
          </ul>
          {d.classes.unclassified > 0 && (
            <div className="mt-2 text-[10px] text-[var(--text-tertiary)]">+ {d.classes.unclassified} without an ambiguity class</div>
          )}
          {d.signals > 0 && (
            <div className="mt-1 text-[10px] text-[var(--text-tertiary)]">{d.signals} teaching signals excluded from these counts</div>
          )}
        </Card>
      )}
    </div>
  );
}

function Kpi({ label, value, icon, hint }: { label: string; value: React.ReactNode; icon?: React.ReactNode; hint?: string }) {
  return (
    <div data-hf="fade" title={hint}>
      <div className="flex items-center gap-1 text-[10px] text-[var(--text-tertiary)]">{icon}{label}</div>
      <div className="tabular text-base font-semibold">{value}</div>
      {hint && <div className="max-w-[160px] truncate text-[10px] text-[var(--text-tertiary)]">{hint}</div>}
    </div>
  );
}

/** Semicircle gauge. Arc length animates via the draw primitive. */
function Gauge({ pct }: { pct: number }) {
  const R = 70;
  const L = Math.PI * R; // half circumference
  const arc = `M ${90 - R} 90 A ${R} ${R} 0 0 1 ${90 + R} 90`;
  const ticks = Array.from({ length: 11 }, (_, i) => {
    const a = Math.PI * (1 - i / 10);
    return { x1: 90 + (R + 8) * Math.cos(a), y1: 90 - (R + 8) * Math.sin(a), x2: 90 + (R + (i % 5 ? 12 : 15)) * Math.cos(a), y2: 90 - (R + (i % 5 ? 12 : 15)) * Math.sin(a) };
  });
  const needle = Math.PI * (1 - pct);
  return (
    <svg viewBox="0 0 180 100" className="w-full max-w-[200px]" role="img" aria-label={`${Math.round(pct * 100)} percent of decisions made by agents`}>
      {ticks.map((t, i) => (
        <line key={i} {...t} stroke="var(--border-default)" strokeWidth={i % 5 ? 1 : 2} />
      ))}
      <path d={arc} fill="none" stroke="var(--overlay)" strokeWidth={12} strokeLinecap="round" />
      <path
        data-hf="draw"
        d={arc}
        fill="none"
        stroke="var(--secondary)"
        strokeWidth={12}
        strokeLinecap="round"
        strokeDasharray={`${L} ${L}`}
        data-hf-offset={L * (1 - pct)}
        strokeDashoffset={L * (1 - pct)}
      />
      <circle cx={90 + R * Math.cos(needle)} cy={90 - R * Math.sin(needle)} r={4} fill="var(--text)" />
    </svg>
  );
}

/** Stacked daily bars: agent on top of human, teaching signals as a dot. */
function Timeline({ buckets }: { buckets: { day: string; human: number; agent: number; signals: number }[] }) {
  if (!buckets.length) {
    return <div className="flex flex-1 items-center text-xs text-[var(--text-tertiary)]">No dated decisions to plot.</div>;
  }
  const max = Math.max(1, ...buckets.map((b) => b.human + b.agent));
  const first = buckets[0].day;
  const last = buckets[buckets.length - 1].day;
  return (
    <div className="flex min-h-[110px] flex-1 flex-col">
      <div
        className="flex flex-1 items-end gap-[2px]"
        role="img"
        aria-label={`Daily decisions from ${first} to ${last}. Peak ${max} in one day.`}
      >
        {buckets.map((b) => {
          const h = ((b.human + b.agent) / max) * 100;
          return (
            <div
              key={b.day}
              className="group relative flex h-full min-w-[3px] flex-1 flex-col justify-end"
              title={`${b.day}: ${b.agent} agent · ${b.human} human${b.signals ? ` · ${b.signals} signals` : ""}`}
            >
              {b.signals > 0 && <span className="mx-auto mb-0.5 h-1.5 w-1.5 rounded-full bg-[var(--warning)]" />}
              <div data-hf="grow-y" className="flex flex-col overflow-hidden rounded-t-sm" style={{ height: `${h}%` }}>
                <div style={{ flex: b.agent }} className="bg-[var(--secondary)]" />
                <div style={{ flex: b.human }} className="bg-[var(--primary)] opacity-80" />
              </div>
              {h === 0 && <div className="h-px bg-[var(--border-default)]" />}
            </div>
          );
        })}
      </div>
      <div className="mt-1.5 flex flex-wrap items-center justify-between gap-x-3 gap-y-1 text-[10px] text-[var(--text-tertiary)]">
        <span className="mono">{first}</span>
        <span className="order-last flex w-full flex-wrap gap-3 sm:order-none sm:w-auto">
          <span className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-sm bg-[var(--secondary)]" />agent</span>
          <span className="inline-flex items-center gap-1"><span className="h-2 w-2 rounded-sm bg-[var(--primary)]" />human</span>
          <span className="inline-flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full bg-[var(--warning)]" />teaching signal</span>
        </span>
        <span className="mono">{last}</span>
      </div>
    </div>
  );
}
