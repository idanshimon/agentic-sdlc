"use client";
import Link from "next/link";
import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { GitBranch, ArrowRight, Table as TableIcon, LayoutGrid, ListChecks, Search, ChevronLeft, ChevronRight } from "lucide-react";
import { useRuns } from "@/lib/hooks/use-runs";
import { useAssistantContext } from "@/lib/assist/context";
import { RunCard } from "@/components/domain/run-card";
import { RunsTable } from "@/components/domain/runs-table";
import { RunsTriage } from "@/components/domain/runs-triage";
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

type ViewMode = "triage" | "table" | "cards";

export default function RunsPage() {
  return (
    <Suspense fallback={<div className="skeleton h-12 rounded-lg" />}>
      <RunsPageInner />
    </Suspense>
  );
}

const PAGE_SIZE = 50;

function RunsPageInner() {
  // Server-side paging + search. The page previously fetched a bare 50 rows
  // with no way to reach run 51 and no way to tell "50" from "there are only
  // 50". `search` is sent to the API rather than applied to the fetched page:
  // filtering client-side would search 50 rows and silently miss matches that
  // exist further down, returning an empty result that looks authoritative.
  const [page, setPage] = useState(0);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");

  // Debounce so typing does not fire a request per keystroke.
  useEffect(() => {
    const t = setTimeout(() => {
      setSearch(searchInput);
      setPage(0); // a new query starts at page 1, not mid-way through the old one
    }, 300);
    return () => clearTimeout(t);
  }, [searchInput]);

  const { data, isLoading, isFetching } = useRuns({
    limit: PAGE_SIZE,
    offset: page * PAGE_SIZE,
    search: search || undefined,
  });
  const runs = data?.items ?? [];
  const total = data?.total ?? runs.length;
  const truncated = data?.truncated ?? false;
  const pageStart = runs.length === 0 ? 0 : page * PAGE_SIZE + 1;
  const pageEnd = page * PAGE_SIZE + runs.length;
  const hasPrev = page > 0;
  const hasNext = pageEnd < total;

  // URL-synced filters so the operator can share a link to a filtered view
  // ("send me the haiku runs from last week"). Back button restores state.
  const [filters, setFilters] = useRunsFiltersFromUrl();
  const visible = useMemo(() => applyRunsFilters(runs, filters), [runs, filters]);

  // View toggle, persisted in localStorage (same pattern as /decisions).
  // A `?view=` param from a dashboard KPI wins over the stored preference for
  // that visit — the operator asked for that specific slice by clicking it.
  const params = useSearchParams();
  const urlView = params.get("view");
  const [view, setView] = useState<ViewMode>(() => {
    if (urlView === "attention" || urlView === "failed" || urlView === "active") return "triage";
    if (typeof window === "undefined") return "triage";
    return (localStorage.getItem("li.runs.view") as ViewMode) || "triage";
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
      ) : runs.length === 0 && !search ? (
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
          {/* Server-side search. Distinct from the filter bar below, which
              narrows the CURRENT page; this queries the whole window. */}
          <div className="flex items-center gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--text-tertiary)]" />
              <input
                type="search"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Search all runs by ID, team, status, stage or mode…"
                className="w-full rounded-md border border-[var(--border-default)] bg-[var(--surface)] py-1.5 pl-9 pr-3 text-[12px] text-[var(--text)] placeholder:text-[var(--text-tertiary)] focus:border-[var(--primary)] focus:outline-none"
              />
            </div>
            {isFetching && (
              <span className="text-[10px] text-[var(--text-tertiary)]">updating…</span>
            )}
          </div>

          {runs.length === 0 ? (
            <div className="rounded-lg border border-[var(--border-default)] bg-[var(--surface)] p-12 text-center text-sm text-[var(--text-tertiary)]">
              No runs match <span className="text-[var(--text-secondary)]">“{search}”</span>.
              <button
                type="button"
                onClick={() => setSearchInput("")}
                className="ml-2 text-[var(--primary)] hover:underline"
              >
                Clear search
              </button>
            </div>
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
              {/* Always show the range against the true total. A bare "50" is
                  indistinguishable from "there are only 50 runs". */}
              Showing{" "}
              <span className="text-[var(--text-secondary)] tabular">
                {pageStart}–{pageEnd}
              </span>{" "}
              of{" "}
              <span className="text-[var(--text-secondary)] tabular">
                {truncated ? `${total}+` : total}
              </span>{" "}
              run{total === 1 ? "" : "s"}
              {visible.length !== runs.length && (
                <> · {visible.length} match the filters on this page</>
              )}
              {truncated && (
                <span className="ml-1 text-[var(--text-tertiary)]">
                  — newest {total}; the archive holds more
                </span>
              )}
            </div>
            <div className="inline-flex rounded-md border border-[var(--border-default)] bg-[var(--surface)] p-0.5">
              <ViewToggle
                active={view === "triage"}
                onClick={() => setViewPersist("triage")}
                icon={ListChecks}
                label="Triage"
              />
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
          ) : view === "triage" ? (
            <RunsTriage runs={visible} />
          ) : view === "table" ? (
            <RunsTable runs={visible} />
          ) : (
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {visible.map((r) => <RunCard key={r.run_id} run={r} />)}
            </div>
          )}

          {/* Pager. Rendered whenever more than one page exists so run 51 is
              reachable — previously it was not reachable at all. */}
          {(hasPrev || hasNext) && (
            <div className="flex items-center justify-between gap-2 pt-1">
              <button
                type="button"
                disabled={!hasPrev || isFetching}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                className="inline-flex items-center gap-1 rounded-md border border-[var(--border-default)] bg-[var(--surface)] px-3 py-1.5 text-[12px] text-[var(--text-secondary)] transition-colors hover:text-[var(--text)] disabled:cursor-not-allowed disabled:opacity-40"
              >
                <ChevronLeft className="h-3.5 w-3.5" /> Previous
              </button>
              <span className="text-[11px] text-[var(--text-tertiary)]">
                Page <span className="tabular text-[var(--text-secondary)]">{page + 1}</span>
                {" of "}
                <span className="tabular text-[var(--text-secondary)]">
                  {Math.max(1, Math.ceil(total / PAGE_SIZE))}
                </span>
              </span>
              <button
                type="button"
                disabled={!hasNext || isFetching}
                onClick={() => setPage((p) => p + 1)}
                className="inline-flex items-center gap-1 rounded-md border border-[var(--border-default)] bg-[var(--surface)] px-3 py-1.5 text-[12px] text-[var(--text-secondary)] transition-colors hover:text-[var(--text)] disabled:cursor-not-allowed disabled:opacity-40"
              >
                Next <ChevronRight className="h-3.5 w-3.5" />
              </button>
            </div>
          )}
          </>
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
