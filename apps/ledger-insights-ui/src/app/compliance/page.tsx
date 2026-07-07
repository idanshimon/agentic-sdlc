"use client";
import { FileSearch, ShieldAlert, CheckCircle2, AlertTriangle, User, Bot } from "lucide-react";
import { useCallback, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useCompliance } from "@/lib/hooks/use-runs";
import { useAssistantContext } from "@/lib/assist/context";
import { EmptyState } from "@/components/domain/empty-state";
import { PageHeader } from "@/components/layout/page-header";
import { cn } from "@/lib/utils";
import type { ComplianceRow } from "@/lib/api/orchestrator";

// Filters are URL view-state (shareable, back-button-able) — the convention
// across the app. A change rewrites the query string; the hook refetches off
// the new params. Empty string = "any".
type Filters = { phi_class: string; actor_kind: string; team_id: string; window: string };

const PHI_OPTS = [
  { v: "", label: "Any PHI class" },
  { v: "high", label: "PHI: high" },
  { v: "low", label: "PHI: low" },
  { v: "none", label: "PHI: none" },
];
const ACTOR_OPTS = [
  { v: "", label: "Any actor" },
  { v: "human", label: "Human" },
  { v: "agent", label: "Agent" },
];
const WINDOW_OPTS = [
  { v: "24h", label: "Last 24h" },
  { v: "7d", label: "Last 7 days" },
  { v: "30d", label: "Last 30 days" },
];

export default function CompliancePage() {
  // useSearchParams() must sit under a Suspense boundary or Next 16's static
  // export bails with a prerender-error. The inner component holds all the
  // URL-state logic; this wrapper supplies the boundary.
  return (
    <Suspense fallback={<div className="skeleton h-40 rounded-lg" />}>
      <CompliancePageInner />
    </Suspense>
  );
}

function CompliancePageInner() {
  const router = useRouter();
  const sp = useSearchParams();

  const filters: Filters = {
    phi_class: sp.get("phi_class") ?? "high",   // default to the acceptance-query lens
    actor_kind: sp.get("actor_kind") ?? "",
    team_id: sp.get("team_id") ?? "",
    window: sp.get("window") ?? "30d",
  };

  const setFilter = useCallback(
    (key: keyof Filters, value: string) => {
      const next = new URLSearchParams(sp.toString());
      if (value) next.set(key, value);
      else next.delete(key);
      router.replace(`/compliance?${next.toString()}`);
    },
    [router, sp],
  );

  const { data, isLoading } = useCompliance({
    phi_class: filters.phi_class || undefined,
    actor_kind: filters.actor_kind || undefined,
    team_id: filters.team_id || undefined,
    window: filters.window || undefined,
  });

  const rows = data?.rows ?? [];
  const summary = data?.summary ?? { total: 0, complete: 0, incomplete: 0, complete_pct: 100 };

  useAssistantContext({
    kind: "compliance",
    label: "Compliance query",
    payload: { total: summary.total, incomplete: summary.incomplete, filters },
  });

  const isAcceptanceLens = filters.phi_class === "high" && filters.window === "30d";

  return (
    <div className="space-y-5">
      <PageHeader
        plane="ledger"
        title="Compliance query"
        description="Every AI decision, fully attributed: what was decided, WHY (the governing autonomy rule + bundle rule version), WHO decided it (human UPN or agent principal), which model, and the cost. One query across every decision-producing surface. This is the capability's definition of done."
      />

      {/* Filters — URL view-state */}
      <div className="flex flex-wrap items-center gap-2">
        <Select value={filters.phi_class} opts={PHI_OPTS} onChange={(v) => setFilter("phi_class", v)} />
        <Select value={filters.window} opts={WINDOW_OPTS} onChange={(v) => setFilter("window", v)} />
        <Select value={filters.actor_kind} opts={ACTOR_OPTS} onChange={(v) => setFilter("actor_kind", v)} />
        <input
          type="text"
          value={filters.team_id}
          onChange={(e) => setFilter("team_id", e.target.value)}
          placeholder="Team (any)"
          className="px-2.5 py-1.5 text-xs rounded border border-[var(--border-default)] bg-[var(--surface)] text-[var(--text)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:border-[var(--primary)] w-40"
        />
        {isAcceptanceLens && (
          <span className="ml-auto inline-flex items-center gap-1.5 text-[11px] text-[var(--text-tertiary)]">
            <ShieldAlert className="h-3.5 w-3.5" />
            acceptance lens: PHI-high · 30 days
          </span>
        )}
      </div>

      {/* Completeness banner — the money-shot. An incomplete row is itself a
          compliance finding (a decision the system could not fully explain). */}
      {!isLoading && summary.total > 0 && <CompletenessBanner summary={summary} />}

      {isLoading ? (
        <div className="space-y-3">
          {[1, 2, 3, 4].map((i) => <div key={i} className="skeleton h-12 rounded-lg" />)}
        </div>
      ) : rows.length === 0 ? (
        <EmptyState
          icon={FileSearch}
          title="No decisions match this query"
          description="Adjust the filters, or run the pipeline so decisions land in the ledger. With PHI-high over 30 days on a live ledger, this is the auditor's front door."
        />
      ) : (
        <ComplianceTable rows={rows} />
      )}
    </div>
  );
}

function CompletenessBanner({
  summary,
}: {
  summary: { total: number; complete: number; incomplete: number; complete_pct: number };
}) {
  const clean = summary.incomplete === 0;
  return (
    <div
      className={cn(
        "flex items-center gap-3 rounded-lg border px-4 py-3",
        clean
          ? "border-[var(--success)]/30 bg-[var(--success)]/5"
          : "border-[var(--warning)]/30 bg-[var(--warning)]/5",
      )}
    >
      {clean ? (
        <CheckCircle2 className="h-5 w-5 text-[var(--success)] shrink-0" />
      ) : (
        <AlertTriangle className="h-5 w-5 text-[var(--warning)] shrink-0" />
      )}
      <div className="text-sm">
        <span className="font-semibold text-[var(--text)]">
          {summary.complete} of {summary.total}
        </span>{" "}
        <span className="text-[var(--text-secondary)]">
          decisions fully attributed ({summary.complete_pct}%)
        </span>
        {!clean && (
          <span className="text-[var(--text-secondary)]">
            {" "}— <span className="text-[var(--warning)]">{summary.incomplete}</span> missing a
            governing rule, actor, model, or cost. That gap is itself a finding.
          </span>
        )}
      </div>
    </div>
  );
}

function ComplianceTable({ rows }: { rows: ComplianceRow[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-[var(--border-default)]">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-[var(--border-default)] bg-[var(--surface)] text-left text-[var(--text-tertiary)]">
            <Th>Decision</Th>
            <Th>PHI</Th>
            <Th>Actor</Th>
            <Th>Why (rule)</Th>
            <Th>Bundle version</Th>
            <Th>Model</Th>
            <Th className="text-right">Cost</Th>
            <Th>When</Th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={r.id}
              className={cn(
                "border-b border-[var(--border-default)]/50 last:border-0 hover:bg-[var(--overlay)]/40",
                !r.complete && "bg-[var(--warning)]/[0.04]",
              )}
            >
              <Td>
                <div className="max-w-xs truncate text-[var(--text)]" title={r.decision}>
                  {r.decision || <span className="text-[var(--text-tertiary)]">—</span>}
                </div>
                {r.ambiguity_class && (
                  <div className="text-[10px] text-[var(--text-tertiary)]">{r.ambiguity_class}</div>
                )}
              </Td>
              <Td>
                <PhiBadge cls={r.phi_class} />
              </Td>
              <Td>
                <div className="flex items-center gap-1.5">
                  {r.actor_kind === "agent" ? (
                    <Bot className="h-3.5 w-3.5 text-[var(--plane-agenthq)]" />
                  ) : (
                    <User className="h-3.5 w-3.5 text-[var(--plane-ledger)]" />
                  )}
                  <span className="truncate max-w-[140px]" title={r.actor_id}>
                    {r.actor_id || <Missing />}
                  </span>
                </div>
              </Td>
              <Td>
                {r.autonomy_ref ? (
                  <code className="text-[10px] text-[var(--text-secondary)] break-all">{r.autonomy_ref}</code>
                ) : (
                  <Missing />
                )}
              </Td>
              <Td>
                {r.bundle_refs.length ? (
                  <div className="space-y-0.5">
                    {r.bundle_refs.map((b) => (
                      <code key={b} className="block text-[10px] text-[var(--text-secondary)]">{b}</code>
                    ))}
                  </div>
                ) : (
                  <Missing />
                )}
              </Td>
              <Td>{r.model_used || <Missing />}</Td>
              <Td className="text-right tabular">
                {r.cost_usd != null ? `$${r.cost_usd.toFixed(4)}` : <Missing />}
              </Td>
              <Td>
                <span className="text-[var(--text-tertiary)] tabular">
                  {r.created_at ? new Date(r.created_at).toLocaleString() : "—"}
                </span>
              </Td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Th({ children, className }: { children: React.ReactNode; className?: string }) {
  return <th className={cn("px-3 py-2 font-medium uppercase tracking-wider text-[10px]", className)}>{children}</th>;
}
function Td({ children, className }: { children: React.ReactNode; className?: string }) {
  return <td className={cn("px-3 py-2 align-top", className)}>{children}</td>;
}
function Missing() {
  return <span className="text-[var(--warning)] text-[10px] font-medium">missing</span>;
}
function PhiBadge({ cls }: { cls: string }) {
  const map: Record<string, string> = {
    high: "text-[var(--danger)] border-[var(--danger)]/40 bg-[var(--danger)]/10",
    low: "text-[var(--warning)] border-[var(--warning)]/40 bg-[var(--warning)]/10",
    none: "text-[var(--text-tertiary)] border-[var(--border-default)]",
  };
  return (
    <span className={cn("inline-flex rounded px-1.5 py-0.5 text-[10px] border", map[cls] ?? map.none)}>
      {cls}
    </span>
  );
}

function Select({
  value, opts, onChange,
}: {
  value: string;
  opts: { v: string; label: string }[];
  onChange: (v: string) => void;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="px-2.5 py-1.5 text-xs rounded border border-[var(--border-default)] bg-[var(--surface)] text-[var(--text)] focus:outline-none focus:border-[var(--primary)]"
    >
      {opts.map((o) => (
        <option key={o.v} value={o.v}>{o.label}</option>
      ))}
    </select>
  );
}
