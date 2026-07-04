"use client";
/**
 * /autonomy — the Autonomy Control surface.
 *
 * Answers the three operator questions the rest of the app implies but never
 * puts in one place:
 *
 *   1. HOW DOES THE AGENT IMPROVE?  → the Teaching Loop (hero): human decisions
 *      become precedent; hybrid runs reuse them; autonomy earned climbs.
 *   2. WHERE DO I SEE IT?           → the Autonomy Ladder: every ambiguity class
 *      on a rung (Floor → Learning → Trusted → Autonomous), with live counts.
 *   3. HOW DO I CONTROL IT?         → the Envelope: the immovable PHI/auth floor,
 *      shown as locked, plus per-class posture. Changing the floor is a
 *      standards-change PR (the app is honest that this is governance, not a toggle).
 *
 * All numbers derive from the same ledger the Decisions page shows — no
 * separate source of truth.
 */
import { useMemo } from "react";
import {
  GraduationCap,
  RefreshCw,
  Bot,
  User,
  Lock,
  TrendingUp,
  ArrowRight,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useDecisions } from "@/lib/hooks/use-runs";
import { useQuery } from "@tanstack/react-query";
import { buildLineageIndex } from "@/lib/lineage";
import {
  computeClassAutonomy,
  rungLabel,
  rungTone,
  classLabel,
  type AutonomyRung,
} from "@/lib/autonomy";
import { PageHeader } from "@/components/layout/page-header";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const RUNGS: AutonomyRung[] = ["floor", "learning", "trusted", "autonomous"];

function useHardGateFloor() {
  return useQuery({
    queryKey: ["hard-gate-classes"],
    queryFn: async () => {
      const res = await fetch("/api/config/hard-gate-classes");
      return (await res.json()) as {
        hard_gate_classes: string[];
        floor: string[];
        explainer?: string;
      };
    },
    staleTime: 60_000,
  });
}

export default function AutonomyPage() {
  const { data, isLoading } = useDecisions({ limit: 200 });
  const { data: floorData } = useHardGateFloor();
  const entries = useMemo(() => data?.entries ?? [], [data]);

  const floor = useMemo(
    () => new Set(floorData?.hard_gate_classes ?? ["auth-policy", "phi-classification"]),
    [floorData],
  );

  const { metrics } = useMemo(() => buildLineageIndex(entries), [entries]);
  const classes = useMemo(
    () => computeClassAutonomy(entries, floor),
    [entries, floor],
  );

  const totalStage = classes.reduce((s, c) => s + c.total, 0);
  const totalAgent = classes.reduce((s, c) => s + c.agentCount, 0);
  const totalHuman = totalStage - totalAgent;
  const agentPct = totalStage ? Math.round((totalAgent / totalStage) * 100) : 0;

  return (
    <div className="space-y-6">
      <PageHeader
        plane="ledger"
        title="Autonomy Control"
        description="The agent earns autonomy from real human decisions — and never past the floor you set. See the teaching loop close, watch each ambiguity class climb, and hold the PHI/auth line."
      />

      {/* ─────────────── ZONE 1: THE TEACHING LOOP (hero) ─────────────── */}
      <TeachingLoop
        taught={metrics.taughtCount}
        reused={metrics.reusedCount}
        earnedPct={metrics.autonomyEarnedPct}
        agentPct={agentPct}
        totalAgent={totalAgent}
        totalHuman={totalHuman}
      />

      {/* ─────────────── ZONE 2: THE AUTONOMY LADDER ─────────────── */}
      <section className="space-y-3">
        <div className="flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-[var(--plane-ledger)]" />
          <h2 className="text-sm font-semibold tracking-tight">
            Autonomy ladder — by ambiguity class
          </h2>
          <span className="text-xs text-[var(--text-muted)]">
            where each decision type sits on the trust curve
          </span>
        </div>

        {isLoading ? (
          <div className="grid gap-2">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="skeleton h-16 rounded-lg" />
            ))}
          </div>
        ) : classes.length === 0 ? (
          <Card className="p-8 text-center text-sm text-[var(--text-muted)]">
            No decisions yet. Run the pipeline and resolve a gate to start the
            loop.
          </Card>
        ) : (
          <div className="space-y-2">
            {classes.map((c) => (
              <LadderRow key={c.ambiguityClass} c={c} />
            ))}
          </div>
        )}
      </section>

      {/* ─────────────── ZONE 3: THE ENVELOPE (control) ─────────────── */}
      <EnvelopePanel
        floor={[...floor]}
        explainer={floorData?.explainer}
      />
    </div>
  );
}

/* ═══════════════════════ Zone 1 ═══════════════════════ */

function TeachingLoop({
  taught,
  reused,
  earnedPct,
  agentPct,
  totalAgent,
  totalHuman,
}: {
  taught: number;
  reused: number;
  earnedPct: number;
  agentPct: number;
  totalAgent: number;
  totalHuman: number;
}) {
  return (
    <Card className="overflow-hidden border-[var(--plane-ledger)]/30">
      <div className="grid lg:grid-cols-[1fr_auto] gap-6 p-5">
        {/* the loop diagram */}
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-[var(--plane-ledger)]" />
            <h2 className="text-sm font-semibold tracking-tight">
              The teaching loop
            </h2>
          </div>

          <div className="flex items-stretch gap-2 md:gap-3">
            <LoopNode
              icon={User}
              tone="var(--plane-agenthq, #ec4899)"
              title="Human decides"
              value={`${totalHuman}`}
              sub="operator calls"
            />
            <LoopArrow label="becomes precedent" />
            <LoopNode
              icon={GraduationCap}
              tone="var(--warning, #f59e0b)"
              title="Taught"
              value={`${taught}`}
              sub="precedents set"
            />
            <LoopArrow label="reused on match" />
            <LoopNode
              icon={Bot}
              tone="var(--plane-ledger, #22c55e)"
              title="Agent reuses"
              value={`${reused}`}
              sub="auto-resolved"
            />
            <LoopArrow label="autonomy earned" loop />
          </div>

          <p className="text-xs leading-relaxed text-[var(--text-muted)] max-w-2xl">
            When an operator overrides a recommendation, that call becomes{" "}
            <span className="text-[var(--text-default)] font-medium">
              precedent
            </span>{" "}
            for its ambiguity bucket. The next hybrid run that hits the same
            bucket resolves it automatically — no gate. The loop closes, and the
            agent has earned that decision. PHI and auth never enter the loop.
          </p>
        </div>

        {/* the headline number */}
        <div className="flex flex-col justify-center items-center rounded-xl bg-[var(--surface-raised,rgba(255,255,255,0.03))] px-8 py-4 min-w-[190px]">
          <div className="text-[var(--text-muted)] text-[11px] uppercase tracking-wider">
            Autonomy earned
          </div>
          <div className="text-5xl font-bold tabular-nums text-[var(--plane-ledger)]">
            {earnedPct}
            <span className="text-2xl">%</span>
          </div>
          <div className="mt-1 text-[11px] text-[var(--text-muted)] text-center">
            {reused} of {totalHuman + totalAgent} decisions
            <br />
            auto-resolved from human teaching
          </div>
          <div className="mt-3 flex items-center gap-1.5 text-[11px]">
            <span className="inline-flex items-center gap-1 text-[var(--plane-ledger)]">
              <Bot className="h-3 w-3" /> {agentPct}% agent
            </span>
            <span className="text-[var(--text-muted)]">·</span>
            <span className="inline-flex items-center gap-1 text-[var(--text-muted)]">
              <User className="h-3 w-3" /> {100 - agentPct}% human
            </span>
          </div>
        </div>
      </div>
    </Card>
  );
}

function LoopNode({
  icon: Icon,
  tone,
  title,
  value,
  sub,
}: {
  icon: React.ComponentType<{ className?: string }>;
  tone: string;
  title: string;
  value: string;
  sub: string;
}) {
  return (
    <div className="flex-1 min-w-0 flex flex-col items-center justify-center rounded-lg border border-[var(--border-default)] bg-[var(--surface)] px-2 py-3 text-center">
      <div
        className="mb-1 flex h-8 w-8 items-center justify-center rounded-full"
        style={{ background: `color-mix(in srgb, ${tone} 18%, transparent)` }}
      >
        <Icon className="h-4 w-4" />
      </div>
      <div className="text-2xl font-bold tabular-nums leading-none" style={{ color: tone }}>
        {value}
      </div>
      <div className="mt-1 text-[11px] font-medium">{title}</div>
      <div className="text-[10px] text-[var(--text-muted)]">{sub}</div>
    </div>
  );
}

function LoopArrow({ label, loop }: { label: string; loop?: boolean }) {
  return (
    <div className="hidden md:flex flex-col items-center justify-center px-0.5">
      {loop ? (
        <RefreshCw className="h-4 w-4 text-[var(--plane-ledger)]" />
      ) : (
        <ArrowRight className="h-4 w-4 text-[var(--text-muted)]" />
      )}
      <span className="mt-1 max-w-[68px] text-center text-[10px] leading-tight text-[var(--text-muted)]">
        {label}
      </span>
    </div>
  );
}

/* ═══════════════════════ Zone 2 ═══════════════════════ */

function LadderRow({ c }: { c: ReturnType<typeof computeClassAutonomy>[number] }) {
  const tone = rungTone(c.rung);
  const rungIndex = RUNGS.indexOf(c.rung);

  return (
    <Card className="p-3.5">
      <div className="flex items-center gap-4">
        {/* class + rung */}
        <div className="min-w-[190px]">
          <div className="flex items-center gap-1.5">
            {c.isFloor && <Lock className="h-3 w-3 text-[var(--danger,#ef4444)]" />}
            <span className="text-sm font-semibold">
              {classLabel(c.ambiguityClass)}
            </span>
          </div>
          <span
            className="mt-0.5 inline-block rounded-full px-2 py-0.5 text-[10px] font-medium"
            style={{
              color: tone,
              background: `color-mix(in srgb, ${tone} 15%, transparent)`,
            }}
          >
            {rungLabel(c.rung)}
          </span>
        </div>

        {/* the 4-rung ladder */}
        <div className="flex-1 grid grid-cols-4 gap-1">
          {RUNGS.map((r, i) => {
            const active = i <= rungIndex;
            const isCurrent = i === rungIndex;
            return (
              <div key={r} className="flex flex-col items-center gap-1">
                <div
                  className={cn(
                    "h-1.5 w-full rounded-full transition-all",
                  )}
                  style={{
                    background: active
                      ? rungTone(r)
                      : "var(--border-default, rgba(255,255,255,0.08))",
                    opacity: active ? (isCurrent ? 1 : 0.5) : 1,
                  }}
                />
                <span
                  className={cn(
                    "text-[9px] leading-none",
                    isCurrent ? "font-semibold" : "text-[var(--text-muted)]",
                  )}
                  style={isCurrent ? { color: rungTone(r) } : undefined}
                >
                  {rungLabel(r).split(" ")[0]}
                </span>
              </div>
            );
          })}
        </div>

        {/* live counts */}
        <div className="flex items-center gap-4 text-right">
          <Metric value={c.total} label="decisions" />
          <Metric value={c.precedentBuckets} label="precedents" accent="var(--warning,#f59e0b)" />
          <Metric
            value={`${c.autonomyPct}%`}
            label="autonomous"
            accent={c.isFloor ? "var(--danger,#ef4444)" : "var(--plane-ledger,#22c55e)"}
          />
        </div>
      </div>
    </Card>
  );
}

function Metric({
  value,
  label,
  accent,
}: {
  value: string | number;
  label: string;
  accent?: string;
}) {
  return (
    <div className="min-w-[62px]">
      <div className="text-base font-bold tabular-nums" style={accent ? { color: accent } : undefined}>
        {value}
      </div>
      <div className="text-[10px] text-[var(--text-muted)]">{label}</div>
    </div>
  );
}

/* ═══════════════════════ Zone 3 ═══════════════════════ */

function EnvelopePanel({
  floor,
  explainer,
}: {
  floor: string[];
  explainer?: string;
}) {
  return (
    <section className="space-y-3">
      <div className="flex items-center gap-2">
        <ShieldCheck className="h-4 w-4 text-[var(--danger,#ef4444)]" />
        <h2 className="text-sm font-semibold tracking-tight">
          The envelope — what the agent may never decide alone
        </h2>
      </div>

      <Card className="p-4">
        <div className="flex flex-wrap items-center gap-2 mb-3">
          {floor.map((c) => (
            <span
              key={c}
              className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--danger,#ef4444)]/40 bg-[var(--danger,#ef4444)]/10 px-3 py-1.5 text-xs font-medium"
            >
              <Lock className="h-3 w-3 text-[var(--danger,#ef4444)]" />
              {classLabel(c)}
              <span className="text-[10px] text-[var(--text-muted)]">
                human-only
              </span>
            </span>
          ))}
        </div>

        <p className="text-xs leading-relaxed text-[var(--text-muted)] max-w-3xl">
          {explainer ??
            "PHI and auth are an immovable floor — each requires an explicit, attributed human decision. No amount of precedent lets the agent take these calls."}
        </p>

        <div className="mt-4 flex items-start gap-2 rounded-lg border border-[var(--border-default)] bg-[var(--surface-raised,rgba(255,255,255,0.02))] p-3">
          <Lock className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--text-muted)]" />
          <p className="text-[11px] leading-relaxed text-[var(--text-muted)]">
            <span className="font-medium text-[var(--text-default)]">
              Changing the floor is a standards change, not a toggle.
            </span>{" "}
            Expanding or shrinking this set requires an OpenSpec change proposal
            and reviewer approval per the bundle roster — the envelope is
            governed, not switched. Pipeline Doctor may auto-tune thresholds
            <em> within</em> the envelope, but can never relax a floor class.
          </p>
        </div>
      </Card>
    </section>
  );
}
