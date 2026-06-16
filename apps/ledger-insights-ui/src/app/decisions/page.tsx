"use client";
import { Scale, Table as TableIcon, LayoutGrid } from "lucide-react";
import { useState } from "react";
import { useDecisions } from "@/lib/hooks/use-runs";
import { useAssistantContext } from "@/lib/assist/context";
import { DecisionCard } from "@/components/domain/decision-card";
import { DecisionTable } from "@/components/domain/decision-table";
import { DecisionsInsights } from "@/components/domain/decisions-insights";
import { EmptyState } from "@/components/domain/empty-state";
import { PageHeader } from "@/components/layout/page-header";
import { cn } from "@/lib/utils";

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
          <div className="flex items-center justify-between gap-2">
            <div className="text-[11px] text-[var(--text-tertiary)]">
              {entries.length} entries in scope
            </div>
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
            <div className="grid gap-3 md:grid-cols-2">
              {entries.map((e) => <DecisionCard key={e.id} entry={e} />)}
            </div>
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
