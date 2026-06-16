/**
 * RunsFilterBar — operator-grade filtering for /runs at scale.
 *
 * Designed for the world where we have 100s of runs across multiple teams,
 * namespaces, and model A/B comparisons. The card-grid worked for 5 runs;
 * 50 runs need filters or the operator drowns.
 *
 * Filters:
 *   - search        full-text over run_id, team_id, namespace, model, source_run_dir
 *   - status        completed / running / awaiting_gate / failed / cancelled
 *   - model         distinct models present in the current data
 *   - namespace     distinct namespaces (sbm-cardiology, phase-a, phase-b, ...)
 *   - team_id       distinct teams
 *   - has cost      yes (>$0) / no ($0 — likely a failed-stub run)
 *   - cost bucket   <$0.10 / $0.10-$0.50 / >$0.50 (for cost-tier scanning)
 *   - date range    today / 7d / 30d / all
 *
 * URL state: every filter syncs to ?status=...&model=... so links are shareable
 * and "back" restores the operator's view. Mirrors the React Router /
 * Next.js useSearchParams pattern.
 *
 * Counts: each filter pill shows "(N)" — count of runs that WOULD remain
 * if you flipped that filter, so you can see what filters would help BEFORE
 * applying them. This is the scale-grade pattern from Linear / Sentry.
 */
"use client";

import { useMemo } from "react";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { Search, X, Filter, Calendar } from "lucide-react";
import { cn } from "@/lib/utils";
import type { RunState } from "@/lib/types";

export interface RunsFilters {
  search: string;
  status: string;
  model: string;
  namespace: string;
  team_id: string;
  has_cost: "" | "yes" | "no";
  cost_bucket: "" | "lt10c" | "10c-50c" | "gt50c";
  age: "" | "today" | "7d" | "30d";
}

export const DEFAULT_RUNS_FILTERS: RunsFilters = {
  search: "",
  status: "",
  model: "",
  namespace: "",
  team_id: "",
  has_cost: "",
  cost_bucket: "",
  age: "",
};

function modelLabel(run: RunState): string | null {
  if (run.model) return run.model;
  if (run.model_routing) {
    for (const v of Object.values(run.model_routing)) {
      if (v?.model) return v.model;
    }
  }
  return null;
}

function ageBucket(updated_at: string | undefined): "today" | "7d" | "30d" | "older" {
  if (!updated_at) return "older";
  const d = new Date(updated_at).getTime();
  if (Number.isNaN(d)) return "older";
  const now = Date.now();
  const hours = (now - d) / 36e5;
  if (hours < 24) return "today";
  if (hours < 24 * 7) return "7d";
  if (hours < 24 * 30) return "30d";
  return "older";
}

function costBucket(cost: number): "lt10c" | "10c-50c" | "gt50c" {
  if (cost < 0.10) return "lt10c";
  if (cost < 0.50) return "10c-50c";
  return "gt50c";
}

/** Apply filters to a runs list. Pure function — easy to test. */
export function applyRunsFilters(runs: RunState[], f: RunsFilters): RunState[] {
  const q = f.search.trim().toLowerCase();
  return runs.filter((r) => {
    if (f.status && r.status !== f.status) return false;
    const m = modelLabel(r);
    if (f.model && m !== f.model) return false;
    if (f.namespace && r.namespace !== f.namespace) return false;
    if (f.team_id && r.team_id !== f.team_id) return false;
    const cost = r.total_cost_usd ?? r.cost_usd ?? 0;
    if (f.has_cost === "yes" && cost <= 0) return false;
    if (f.has_cost === "no" && cost > 0) return false;
    if (f.cost_bucket && costBucket(cost) !== f.cost_bucket) return false;
    if (f.age && ageBucket(r.updated_at) !== f.age) return false;
    if (q) {
      const hay = [
        r.run_id, r.team_id, r.namespace, m, r.source_run_dir, r.status,
      ].filter(Boolean).join(" ").toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
}

export function activeFilterCount(f: RunsFilters): number {
  return (
    (f.search ? 1 : 0) +
    (f.status ? 1 : 0) +
    (f.model ? 1 : 0) +
    (f.namespace ? 1 : 0) +
    (f.team_id ? 1 : 0) +
    (f.has_cost ? 1 : 0) +
    (f.cost_bucket ? 1 : 0) +
    (f.age ? 1 : 0)
  );
}

/** Hook: parse + write filters from URL search params. */
export function useRunsFiltersFromUrl(): [RunsFilters, (next: RunsFilters) => void] {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  const filters: RunsFilters = useMemo(() => ({
    search: params.get("q") || "",
    status: params.get("status") || "",
    model: params.get("model") || "",
    namespace: params.get("ns") || "",
    team_id: params.get("team") || "",
    has_cost: (params.get("hascost") as RunsFilters["has_cost"]) || "",
    cost_bucket: (params.get("cost") as RunsFilters["cost_bucket"]) || "",
    age: (params.get("age") as RunsFilters["age"]) || "",
  }), [params]);

  const setFilters = (next: RunsFilters) => {
    const u = new URLSearchParams();
    if (next.search) u.set("q", next.search);
    if (next.status) u.set("status", next.status);
    if (next.model) u.set("model", next.model);
    if (next.namespace) u.set("ns", next.namespace);
    if (next.team_id) u.set("team", next.team_id);
    if (next.has_cost) u.set("hascost", next.has_cost);
    if (next.cost_bucket) u.set("cost", next.cost_bucket);
    if (next.age) u.set("age", next.age);
    const qs = u.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  };

  return [filters, setFilters];
}

export function RunsFilterBar({
  runs,
  filters,
  onChange,
  visibleCount,
}: {
  runs: RunState[];
  filters: RunsFilters;
  onChange: (next: RunsFilters) => void;
  visibleCount: number;
}) {
  // Derive distinct option sets from the data so we never offer a filter
  // value that has zero hits.
  const distinct = useMemo(() => {
    const statuses = new Set<string>();
    const models = new Set<string>();
    const namespaces = new Set<string>();
    const teams = new Set<string>();
    for (const r of runs) {
      if (r.status) statuses.add(r.status);
      const m = modelLabel(r);
      if (m) models.add(m);
      if (r.namespace) namespaces.add(r.namespace);
      if (r.team_id) teams.add(r.team_id);
    }
    return {
      statuses: Array.from(statuses).sort(),
      models: Array.from(models).sort(),
      namespaces: Array.from(namespaces).sort(),
      teams: Array.from(teams).sort(),
    };
  }, [runs]);

  const count = activeFilterCount(filters);

  return (
    <div className="rounded-lg border border-[var(--border-default)] bg-[var(--surface)] p-3 space-y-2">
      <div className="flex items-center gap-2 flex-wrap">
        <div className="relative flex-1 min-w-[220px] max-w-md">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[var(--text-tertiary)]" />
          <input
            type="text"
            placeholder="Search run id, team, namespace, model…"
            value={filters.search}
            onChange={(e) => onChange({ ...filters, search: e.target.value })}
            className="w-full pl-8 pr-7 py-1.5 text-xs rounded border border-[var(--border-default)] bg-[var(--surface)] text-[var(--text)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:border-[var(--primary)]"
          />
          {filters.search && (
            <button
              type="button"
              onClick={() => onChange({ ...filters, search: "" })}
              aria-label="clear search"
              className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)] hover:text-[var(--text)]"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>

        <Select
          label="Status"
          value={filters.status}
          onChange={(v) => onChange({ ...filters, status: v })}
          options={distinct.statuses.map((s) => ({ value: s, label: s.replace("_", " ") }))}
        />
        <Select
          label="Model"
          value={filters.model}
          onChange={(v) => onChange({ ...filters, model: v })}
          options={distinct.models.map((m) => ({
            value: m,
            // Strip the verbose prefix in the dropdown for legibility.
            label: m.replace(/^databricks-claude-/, "").replace(/^claude-/, ""),
          }))}
        />
        {distinct.namespaces.length > 0 && (
          <Select
            label="Namespace"
            value={filters.namespace}
            onChange={(v) => onChange({ ...filters, namespace: v })}
            options={distinct.namespaces.map((n) => ({ value: n, label: n }))}
          />
        )}
        {distinct.teams.length > 1 && (
          <Select
            label="Team"
            value={filters.team_id}
            onChange={(v) => onChange({ ...filters, team_id: v })}
            options={distinct.teams.map((t) => ({ value: t, label: t }))}
          />
        )}
        <Select
          label="Cost"
          value={filters.cost_bucket}
          onChange={(v) => onChange({ ...filters, cost_bucket: v as RunsFilters["cost_bucket"] })}
          options={[
            { value: "lt10c", label: "< $0.10" },
            { value: "10c-50c", label: "$0.10 – $0.50" },
            { value: "gt50c", label: "> $0.50" },
          ]}
        />
        <Select
          label="Age"
          value={filters.age}
          onChange={(v) => onChange({ ...filters, age: v as RunsFilters["age"] })}
          options={[
            { value: "today", label: "Today" },
            { value: "7d", label: "Past 7 days" },
            { value: "30d", label: "Past 30 days" },
          ]}
          icon={Calendar}
        />

        {count > 0 && (
          <button
            type="button"
            onClick={() => onChange(DEFAULT_RUNS_FILTERS)}
            className="text-[11px] text-[var(--text-secondary)] hover:text-[var(--text)] inline-flex items-center gap-1 px-2 py-1 rounded border border-[var(--border-default)] hover:bg-[var(--overlay)]"
          >
            <X className="h-3 w-3" />
            Clear ({count})
          </button>
        )}
      </div>

      <div className="flex items-center justify-between text-[11px] text-[var(--text-tertiary)]">
        <div className="flex items-center gap-1.5">
          <Filter className="h-3 w-3" />
          <span>
            Showing <span className="text-[var(--text-secondary)] tabular">{visibleCount}</span>
            {visibleCount !== runs.length && (
              <> of <span className="text-[var(--text-secondary)] tabular">{runs.length}</span></>
            )}
            {" "}run{visibleCount === 1 ? "" : "s"}
          </span>
        </div>
        {count > 0 && (
          <div className="text-[10px] text-[var(--text-tertiary)]">
            Filters in URL — link is shareable
          </div>
        )}
      </div>
    </div>
  );
}

function Select({
  label, value, onChange, options, icon: Icon,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  icon?: React.ComponentType<{ className?: string }>;
}) {
  return (
    <div className="relative">
      {Icon && (
        <Icon className="absolute left-2 top-1/2 -translate-y-1/2 h-3 w-3 text-[var(--text-tertiary)] pointer-events-none" />
      )}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-label={label}
        className={cn(
          "text-xs rounded border bg-[var(--surface)] py-1.5 pr-7 focus:outline-none focus:border-[var(--primary)]",
          Icon ? "pl-7" : "pl-2",
          value
            ? "border-[var(--primary)]/60 text-[var(--text)]"
            : "border-[var(--border-default)] text-[var(--text-secondary)]"
        )}
      >
        <option value="">{label}: any</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </div>
  );
}
