"use client";
import { Scale, Table as TableIcon, LayoutGrid, Search, X, Users, FlaskConical, AlertTriangle } from "lucide-react";
import { useState, useMemo } from "react";
import { useDecisions } from "@/lib/hooks/use-runs";
import { useAssistantContext } from "@/lib/assist/context";
import { DecisionCard } from "@/components/domain/decision-card";
import { DecisionTable } from "@/components/domain/decision-table";
import { DecisionsInsights } from "@/components/domain/decisions-insights";
import { EmptyState } from "@/components/domain/empty-state";
import { PageHeader } from "@/components/layout/page-header";
import { cn } from "@/lib/utils";
import type { LedgerEntry } from "@/lib/types";

type ViewMode = "table" | "cards";

export default function DecisionsPage() {
  const { data, isLoading } = useDecisions();
  const entries = data?.entries ?? [];

  // Persist the operator's view choice across navigations within the
  // session. localStorage is ephemeral and self-only — operator preference,
  // not a server-side setting.
  const [view, setView] = useState<ViewMode>(() => {
    if (typeof window === "undefined") return "table";
    return (localStorage.getItem("li.decisions.view") as ViewMode) || "table";
  });
  const setViewPersist = (v: ViewMode) => {
    setView(v);
    if (typeof window !== "undefined") localStorage.setItem("li.decisions.view", v);
  };

  useAssistantContext({
    kind: "decisions",
    label: "Decisions",
    payload: { count: entries.length, view },
  });

  return (
    <div className="space-y-5">
      <PageHeader
        plane="ledger"
        title="Decision Ledger"
        description="Every meaningful agent decision is written here — runtime entries (per stage) and meta entries (per standards change). PHI classifier output, bundle citations, model + cost, all queryable. Click a row to inspect the full rationale, provenance, and operator teaching signals."
      />

      {/* Scope chips — make the read scope explicit. KI-1: a run under a
          different team writes to a partition this token can't read, which
          previously looked like a silent empty result. Surfacing the team +
          data source turns that into visible, understandable state. */}
      {!isLoading && (
        <div className="flex flex-wrap items-center gap-2 text-[11px]">
          {data?.team_id && (
            <span
              className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md border border-[var(--border-default)] bg-[var(--card)]"
              title="Decisions are partitioned by team. This token can only read its own team's ledger — a run created under a different team writes to a partition not shown here."
            >
              <Users className="h-3 w-3 text-[var(--text-tertiary)]" />
              <span className="text-[var(--text-tertiary)]">team</span>
              <span className="mono font-medium">{data.team_id}</span>
            </span>
          )}
          {data?.demo && (
            <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md border border-[var(--warning)]/40 bg-[var(--warning)]/[0.06] text-[var(--warning)]">
              <FlaskConical className="h-3 w-3" />
              demo + live blended
            </span>
          )}
          {data?.live_unreachable && (
            <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md border border-[var(--danger)]/40 bg-[var(--danger)]/[0.06] text-[var(--danger)]">
              <AlertTriangle className="h-3 w-3" />
              live ledger unreachable — showing demo only
            </span>
          )}
          <span className="text-[var(--text-tertiary)]">
            {entries.length} entr{entries.length === 1 ? "y" : "ies"}
          </span>
        </div>
      )}

      {!isLoading && entries.length > 0 && <DecisionsInsights entries={entries} />}

      {isLoading ? (
        <div className="space-y-3">
          {[1, 2, 3, 4].map((i) => <div key={i} className="skeleton h-12 rounded-lg" />)}
        </div>
      ) : entries.length === 0 ? (
        <EmptyState
          icon={Scale}
          title="No decisions logged yet"
          description="As soon as the orchestrator runs a stage or you write a meta entry via the MCP server, it shows up here. Submit a run from the Runs page or POST directly to ledger.write_runtime."
        />
      ) : (
        <>
          <div className="flex items-center justify-end gap-2">
            <div className="inline-flex rounded-md border border-[var(--border-default)] bg-[var(--surface)] p-0.5">
              <ViewToggle
                active={view === "table"}
                onClick={() => setViewPersist("table")}
                icon={TableIcon}
                label="Table"
              />
              <ViewToggle
                active={view === "cards"}
                onClick={() => setViewPersist("cards")}
                icon={LayoutGrid}
                label="Cards"
              />
            </div>
          </div>

          {view === "table" ? (
            <DecisionTable entries={entries} />
          ) : (
            <DecisionCardsView entries={entries} />
          )}
        </>
      )}
    </div>
  );
}

function ViewToggle({
  active, onClick, icon: Icon, label,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        "inline-flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors",
        active
          ? "bg-[var(--overlay)] text-[var(--text)]"
          : "text-[var(--text-secondary)] hover:text-[var(--text)] hover:bg-[var(--overlay)]/50",
      )}
    >
      <Icon className="h-3.5 w-3.5" />
      <span>{label}</span>
    </button>
  );
}

/**
 * Cards view with its own search box. Previously the card grid rendered every
 * entry unfiltered (search only lived in the table) — so a user who searched
 * in Cards view saw no filtering, and the page-level "N entries in scope" count
 * contradicted the table's "Showing X of Y". This gives Cards parity with Table:
 * a search that actually filters, and an honest visible/total count.
 */
function DecisionCardsView({ entries }: { entries: LedgerEntry[] }) {
  const [search, setSearch] = useState("");
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return entries;
    return entries.filter((e) => {
      const hay = [
        e.decision, e.rationale, e.actor?.id, e.model_used,
        e.run_id ?? "", e.stage ?? "", e.ambiguity_class ?? "",
        ...(e.bundle_refs ?? []),
      ].join(" ").toLowerCase();
      return hay.includes(q);
    });
  }, [entries, search]);

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <div className="relative flex-1 min-w-[220px] max-w-md">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[var(--text-tertiary)]" />
          <input
            type="text"
            placeholder="Search decision, rationale, actor, model, run…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-8 pr-7 py-1.5 text-xs rounded border border-[var(--border-default)] bg-[var(--surface)] text-[var(--text)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:border-[var(--primary)]"
          />
          {search && (
            <button
              type="button"
              onClick={() => setSearch("")}
              aria-label="clear search"
              className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)] hover:text-[var(--text)]"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
        <div className="text-[11px] text-[var(--text-tertiary)] tabular">
          Showing <span className="text-[var(--text-secondary)]">{filtered.length}</span>
          {filtered.length !== entries.length && <> of <span className="text-[var(--text-secondary)]">{entries.length}</span></>}
          {" "}entries
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="rounded-lg border border-[var(--border-default)] bg-[var(--surface)] px-4 py-12 text-center text-[var(--text-tertiary)] text-sm">
          No decisions match “{search}”.
          <button type="button" onClick={() => setSearch("")} className="ml-2 text-[var(--primary)] hover:underline">
            Clear search
          </button>
        </div>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {filtered.map((e) => <DecisionCard key={e.id} entry={e} />)}
        </div>
      )}
    </div>
  );
}
