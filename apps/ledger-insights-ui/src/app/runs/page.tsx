"use client";
import Link from "next/link";
import { Suspense, useMemo, useState } from "react";
import { GitBranch, ArrowRight, Table as TableIcon, LayoutGrid } from "lucide-react";
import { useRuns } from "@/lib/hooks/use-runs";
import { useAssistantContext } from "@/lib/assist/context";
import { RunCard } from "@/components/domain/run-card";
import { RunsTable } from "@/components/domain/runs-table";
import { RunsInsights } from "@/components/domain/runs-insights";
import {
  RunsFilterBar,
  applyRunsFilters,
  useRunsFiltersFromUrl,
  DEFAULT_RUNS_FILTERS,
} from "@/components/domain/runs-filter-bar";
import { EmptyState } from "@/components/domain/empty-state";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/layout/page-header";
import { cn } from "@/lib/utils";

type ViewMode = "table" | "cards";

export default function RunsPage() {
  return (
    <Suspense fallback={<div className="skeleton h-12 rounded-lg" />}>
      <RunsPageInner />
    </Suspense>
  );
}

function RunsPageInner() {
  const { data, isLoading } = useRuns();
  const runs = data?.items ?? [];

  // URL-synced filters so the operator can share a link to a filtered view
  // ("send me the haiku runs from last week"). Back button restores state.
  const [filters, setFilters] = useRunsFiltersFromUrl();
  const visible = useMemo(() => applyRunsFilters(runs, filters), [runs, filters]);

  // View toggle, persisted in localStorage (same pattern as /decisions).
  const [view, setView] = useState<ViewMode>(() => {
    if (typeof window === "undefined") return "table";
    return (localStorage.getItem("li.runs.view") as ViewMode) || "table";
  });
  const setViewPersist = (v: ViewMode) => {
    setView(v);
    if (typeof window !== "undefined") localStorage.setItem("li.runs.view", v);
  };

  useAssistantContext({
    kind: "runs-list",
    label: "Runs",
    payload: { count: runs.length, visible: visible.length, view },
  });

  return (
    <div className="space-y-5">
      <PageHeader
        plane="pipeline"
        title="Runs"
        description="Every orchestrator run — submit a PRD, watch it stream through the 7-stage pipeline, gate it manually if it needs review, ship a PR at the end."
        actions={
          <Button variant="primary" asChild>
            <Link href="/runs/new">
              Start a run <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
        }
      />

      {isLoading ? (
        <div className="space-y-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="skeleton h-12 rounded-lg" />
          ))}
        </div>
      ) : runs.length === 0 ? (
        <EmptyState
          icon={GitBranch}
          title="No runs yet"
          description="Pick a sample PRD on the next screen and watch the pipeline stream through. Demo Mode replays a full healthcare run end-to-end without any backend dependency."
          action={
            <Button variant="primary" asChild>
              <Link href="/runs/new">
                Start a run <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
          }
        />
      ) : (
        <>
          <RunsInsights runs={visible} />

          <RunsFilterBar
            runs={runs}
            filters={filters}
            onChange={setFilters}
            visibleCount={visible.length}
          />

          <div className="flex items-center justify-between gap-2">
            <div className="text-[11px] text-[var(--text-tertiary)]">
              {visible.length === runs.length
                ? `${runs.length} run${runs.length === 1 ? "" : "s"}`
                : `${visible.length} of ${runs.length} runs`}
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

          {visible.length === 0 ? (
            <div className="rounded-lg border border-[var(--border-default)] bg-[var(--surface)] p-12 text-center text-sm text-[var(--text-tertiary)]">
              No runs match the current filters.
              <button
                type="button"
                onClick={() => setFilters(DEFAULT_RUNS_FILTERS)}
                className="ml-2 text-[var(--primary)] hover:underline"
              >
                Clear filters
              </button>
            </div>
          ) : view === "table" ? (
            <RunsTable runs={visible} />
          ) : (
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {visible.map((r) => <RunCard key={r.run_id} run={r} />)}
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
