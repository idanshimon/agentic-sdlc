"use client";
/**
 * /autonomy — the control + learning surface.
 *
 * Answers the two questions the "Autonomy earned %" KPI on /decisions raises
 * but can't itself answer:
 *   1. CONTROL — what can the agent NEVER decide on its own? (the invariant
 *      floor: PHI + auth, hard-locked; the envelope the learning loop can't cross)
 *   2. LEARNING — what HAS the agent learned, concretely? (each human-taught
 *      precedent: the class, who taught it, the resolution they set, and how
 *      many later runs auto-resolved from it — the "1 taught precedent" made legible)
 *
 * Both halves derive from the live ledger (useDecisions) + the governance floor
 * (useHardGateClasses). No new backend — the teaching loop was always in the
 * data; this page finally renders it.
 */
import { GraduationCap, Lock, Sprout, Bot, User, ShieldAlert, Info } from "lucide-react";
import { useDecisions, useHardGateClasses } from "@/lib/hooks/use-runs";
import { useAssistantContext } from "@/lib/assist/context";
import { buildLineageIndex, buildAutonomyBuckets, type AutonomyBucket } from "@/lib/lineage";
import { PageHeader } from "@/components/layout/page-header";
import { EmptyState } from "@/components/domain/empty-state";
import { Card } from "@/components/ui/card";
import { relativeTime, cn } from "@/lib/utils";

export default function AutonomyPage() {
  const { data, isLoading } = useDecisions({ limit: 200 });
  const { data: gate } = useHardGateClasses();
  const entries = data?.entries ?? [];

  const { metrics } = buildLineageIndex(entries);
  const buckets = buildAutonomyBuckets(entries);
  const activeCount = buckets.filter((b) => b.status === "active").length;
  const dormantCount = buckets.filter((b) => b.status === "dormant").length;

  useAssistantContext({
    kind: "autonomy",
    label: "Autonomy control",
    payload: {
      autonomyEarnedPct: metrics.autonomyEarnedPct,
      taught: metrics.taughtCount,
      reused: metrics.reusedCount,
      buckets: buckets.length,
    },
  });

  const floor = gate?.hard_gate_classes ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        plane="ledger"
        title="Autonomy control"
        description="How the agent earns autonomy — and the floor it can never cross. A human override becomes precedent; a later run on the same ambiguity auto-resolves from it. That reuse is the loop closing. PHI and auth classes are hard-locked to a human decision no matter how much precedent accrues."
      />

      {/* KPI strip */}
      <div className="grid gap-2.5 grid-cols-2 md:grid-cols-4">
        <Stat
          label="Autonomy earned"
          value={`${metrics.autonomyEarnedPct}%`}
          sub="of stage decisions auto-resolved from human-taught precedent"
          accent={metrics.reusedCount > 0 ? "success" : undefined}
          icon={Sprout}
        />
        <Stat
          label="Precedents taught"
          value={metrics.taughtCount}
          sub={`${metrics.bucketsTaught} distinct ambiguity bucket${metrics.bucketsTaught === 1 ? "" : "s"}`}
          icon={GraduationCap}
        />
        <Stat
          label="Reuses earned"
          value={metrics.reusedCount}
          sub={`${activeCount} active · ${dormantCount} dormant`}
          accent={metrics.reusedCount > 0 ? "success" : undefined}
          icon={Bot}
        />
        <Stat
          label="Control floor"
          value={floor.length || "—"}
          sub={floor.length ? "classes locked to human decision" : "loading…"}
          accent="danger"
          icon={Lock}
        />
      </div>

      {/* CONTROL ENVELOPE */}
      <section className="space-y-3">
        <SectionTitle icon={Lock} title="Control envelope" tone="danger">
          Classes the agent can NEVER auto-resolve — no amount of precedent unlocks them.
        </SectionTitle>
        <Card className="p-4 space-y-3">
          <div className="flex flex-wrap gap-2">
            {floor.length === 0 ? (
              <span className="text-xs text-[var(--text-tertiary)]">Loading governance floor…</span>
            ) : (
              floor.map((c) => (
                <span
                  key={c}
                  className="inline-flex items-center gap-1.5 rounded-md border border-[var(--danger)]/40 bg-[var(--danger)]/10 px-2.5 py-1 text-xs text-[var(--danger)]"
                >
                  <Lock className="h-3 w-3" />
                  {c}
                </span>
              ))
            )}
          </div>
          {gate?.explainer && (
            <p className="flex items-start gap-1.5 text-[11px] text-[var(--text-tertiary)] leading-relaxed">
              <Info className="h-3.5 w-3.5 shrink-0 mt-0.5" />
              {gate.explainer}
            </p>
          )}
        </Card>
      </section>

      {/* LEARNED PRECEDENTS */}
      <section className="space-y-3">
        <SectionTitle icon={Sprout} title="Learned precedents" tone="success">
          Every human override that became reusable precedent — what was taught, by whom, and how much autonomy it earned.
        </SectionTitle>

        {isLoading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => <div key={i} className="skeleton h-14 rounded-lg" />)}
          </div>
        ) : buckets.length === 0 ? (
          <EmptyState
            icon={GraduationCap}
            title="No precedents taught yet"
            description="Accepting the recommended option teaches nothing. Autonomy is earned only when a human SWAPS to a different resolution — that override becomes precedent the agent reuses on the next matching run. Drive a run and swap a routine card to seed the loop."
          />
        ) : (
          <PrecedentTable buckets={buckets} />
        )}
      </section>
    </div>
  );
}

function PrecedentTable({ buckets }: { buckets: AutonomyBucket[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-[var(--border-default)]">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-[var(--border-default)] bg-[var(--surface)] text-left text-[var(--text-tertiary)]">
            <Th>Ambiguity class</Th>
            <Th>What was taught</Th>
            <Th>Taught by</Th>
            <Th className="text-right">Reuses</Th>
            <Th>Status</Th>
            <Th>Last used</Th>
          </tr>
        </thead>
        <tbody>
          {buckets.map((b) => (
            <tr key={b.slotKey} className="border-b border-[var(--border-default)]/50 last:border-0 hover:bg-[var(--overlay)]/40">
              <Td>
                <span className="mono text-[11px] text-[var(--plane-standards)]">{b.ambiguityClass}</span>
                <div className="mono text-[9px] text-[var(--text-tertiary)]">bucket {b.slotKey.slice(0, 10)}</div>
              </Td>
              <Td>
                <div className="max-w-sm text-[var(--text)] leading-snug" title={b.resolutionText}>
                  {b.resolutionText}
                </div>
              </Td>
              <Td>
                <div className="flex items-center gap-1.5">
                  <User className="h-3.5 w-3.5 text-[var(--plane-ledger)]" />
                  <span className="truncate max-w-[150px]" title={b.taughtBy}>{b.taughtBy}</span>
                </div>
              </Td>
              <Td className="text-right tabular">
                <span className={cn("font-semibold", b.reuseCount > 0 ? "text-[var(--success)]" : "text-[var(--text-tertiary)]")}>
                  {b.reuseCount}×
                </span>
              </Td>
              <Td><StatusBadge status={b.status} flagCount={b.flagCount} /></Td>
              <Td>
                <span className="text-[var(--text-tertiary)] tabular">{relativeTime(b.lastUsedAt)}</span>
              </Td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function StatusBadge({ status, flagCount }: { status: AutonomyBucket["status"]; flagCount: number }) {
  const map = {
    active: { label: "active", cls: "text-[var(--success)] border-[var(--success)]/40 bg-[var(--success)]/10", title: "Taught and reused — the loop is closed." },
    dormant: { label: "dormant", cls: "text-[var(--text-tertiary)] border-[var(--border-default)]", title: "Taught but not yet reused — waiting for a matching run." },
    flagged: { label: `flagged ${flagCount}×`, cls: "text-[var(--warning)] border-[var(--warning)]/40 bg-[var(--warning)]/10", title: "An operator flagged this precedent — future reuse is suppressed." },
  }[status];
  return (
    <span className={cn("inline-flex rounded px-1.5 py-0.5 text-[10px] border", map.cls)} title={map.title}>
      {map.label}
    </span>
  );
}

function SectionTitle({
  icon: Icon, title, tone, children,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  tone: "success" | "danger";
  children: React.ReactNode;
}) {
  const color = tone === "danger" ? "text-[var(--danger)]" : "text-[var(--success)]";
  return (
    <div className="space-y-0.5">
      <h2 className={cn("flex items-center gap-2 text-sm font-semibold", color)}>
        <Icon className="h-4 w-4" />
        {title}
      </h2>
      <p className="text-xs text-[var(--text-secondary)] leading-relaxed max-w-2xl">{children}</p>
    </div>
  );
}

function Stat({
  label, value, sub, accent, icon: Icon,
}: {
  label: string;
  value: string | number;
  sub: string;
  accent?: "danger" | "success";
  icon: React.ComponentType<{ className?: string }>;
}) {
  const valueColor =
    accent === "danger" ? "text-[var(--danger)]" :
    accent === "success" ? "text-[var(--success)]" :
    "text-[var(--text)]";
  return (
    <Card className="p-3 space-y-1">
      <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-[var(--text-tertiary)]">
        <Icon className="h-3 w-3" />
        <span>{label}</span>
      </div>
      <div className={`text-xl font-semibold tabular ${valueColor}`}>{value}</div>
      <div className="text-[11px] text-[var(--text-tertiary)] leading-tight">{sub}</div>
    </Card>
  );
}

function Th({ children, className }: { children: React.ReactNode; className?: string }) {
  return <th className={cn("px-3 py-2 font-medium uppercase tracking-wider text-[10px]", className)}>{children}</th>;
}
function Td({ children, className }: { children: React.ReactNode; className?: string }) {
  return <td className={cn("px-3 py-2 align-top", className)}>{children}</td>;
}
