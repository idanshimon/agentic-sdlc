/**
 * DecisionTable — dense, table-shaped view of the Decision Ledger.
 *
 * The DecisionCard view is great for skim + sentiment but operators can't
 * actually OPERATE from a 2-column card grid: too few rows visible at once,
 * actor + model + cost not aligned column-to-column, no sort/filter.
 *
 * This component is the operating view: one entry per row, columns aligned,
 * click a row to expand inline detail (rationale, bundle refs, references_entry_id,
 * full teaching-signal bar). PHI / actor-kind / stage rendered as compact pills.
 *
 * Filters: stage, actor kind (human/agent), PHI class, runtime_kind, search.
 * Sort: column header click — created_at (default), cost, stage, actor.
 *
 * Renders defensively via the same normalize() shape DecisionCard uses;
 * any non-canonical row falls back to "(unknown)" instead of crashing.
 */
"use client";

import { useMemo, useState } from "react";
import {
  ShieldAlert, ShieldCheck, ShieldOff, User, Bot,
  ChevronDown, ChevronRight, Filter, Search, X,
  ThumbsUp, ThumbsDown, Flag, RotateCcw, PauseCircle,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { TeachingSignalBar } from "./teaching-signal-bar";
import { StagePill } from "./stage-pill";
import { relativeTime, shortId, fmtUsd, cn } from "@/lib/utils";
import { PromptChainBadge } from "./prompt-chain-badge";
import type { LedgerEntry } from "@/lib/types";

type RawEntry = Partial<LedgerEntry> & {
  created_by?: string;
  resolution_text?: string;
};

function normalize(raw: RawEntry): LedgerEntry {
  const actor = raw.actor && typeof raw.actor === "object" && "kind" in raw.actor
    ? raw.actor
    : { kind: "agent" as const, id: raw.created_by ?? "unknown" };
  return {
    id: raw.id ?? "unknown",
    entry_type: raw.entry_type ?? "runtime",
    actor,
    decision: raw.decision ?? raw.resolution_text ?? raw.ambiguity_class ?? "(no decision text)",
    rationale: raw.rationale ?? "",
    phi_class: raw.phi_class ?? "none",
    cost_usd: typeof raw.cost_usd === "number" ? raw.cost_usd : 0,
    model_used: raw.model_used ?? "",
    bundle_refs: Array.isArray(raw.bundle_refs) ? raw.bundle_refs : [],
    precedent_refs: Array.isArray(raw.precedent_refs) ? raw.precedent_refs : [],
    stage: raw.stage,
    run_id: raw.run_id,
    agent_session_id: raw.agent_session_id,
    runtime_kind: raw.runtime_kind,
    references_entry_id: raw.references_entry_id,
    feedback_kind: raw.feedback_kind,
    paused_class: raw.paused_class,
    ambiguity_class: raw.ambiguity_class,
    prompt_resolution_path: Array.isArray(raw.prompt_resolution_path)
      ? raw.prompt_resolution_path
      : null,
    created_at: raw.created_at ?? new Date().toISOString(),
  };
}

function teachingKindIcon(kind: LedgerEntry["runtime_kind"], feedbackKind?: string) {
  if (kind === "feedback_thumbs") {
    return feedbackKind === "thumbs_up" ? ThumbsUp : ThumbsDown;
  }
  if (kind === "decision_flagged") return Flag;
  if (kind === "replay_requested") return RotateCcw;
  if (kind === "class_paused") return PauseCircle;
  return null;
}

type SortKey = "created_at" | "cost_usd" | "stage" | "actor";
type SortDir = "asc" | "desc";

interface Filters {
  search: string;
  stage: string;
  actorKind: "" | "human" | "agent";
  phi: "" | "none" | "low" | "high";
  runtimeKind: string;
  hasTeachingSignal: "" | "yes" | "no";
}

const DEFAULT_FILTERS: Filters = {
  search: "",
  stage: "",
  actorKind: "",
  phi: "",
  runtimeKind: "",
  hasTeachingSignal: "",
};

export function DecisionTable({ entries }: { entries: LedgerEntry[] }) {
  const normalized = useMemo(() => entries.map((e) => normalize(e as RawEntry)), [entries]);

  // Build a Set of references_entry_id values that DO have at least one
  // teaching signal pointing at them — used for the hasTeachingSignal filter
  // and for the "↳ N signals" indicator in the row.
  const teachingSignalsByTarget = useMemo(() => {
    const m = new Map<string, LedgerEntry[]>();
    for (const e of normalized) {
      if (e.references_entry_id) {
        const prev = m.get(e.references_entry_id) ?? [];
        prev.push(e);
        m.set(e.references_entry_id, prev);
      }
    }
    return m;
  }, [normalized]);

  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS);
  const [sortKey, setSortKey] = useState<SortKey>("created_at");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const stages = useMemo(() => {
    const s = new Set<string>();
    normalized.forEach((e) => e.stage && s.add(e.stage));
    return Array.from(s).sort();
  }, [normalized]);

  const runtimeKinds = useMemo(() => {
    const s = new Set<string>();
    normalized.forEach((e) => e.runtime_kind && s.add(e.runtime_kind));
    return Array.from(s).sort();
  }, [normalized]);

  const filtered = useMemo(() => {
    const q = filters.search.trim().toLowerCase();
    return normalized.filter((e) => {
      if (filters.stage && e.stage !== filters.stage) return false;
      if (filters.actorKind && e.actor.kind !== filters.actorKind) return false;
      if (filters.phi && e.phi_class !== filters.phi) return false;
      if (filters.runtimeKind && e.runtime_kind !== filters.runtimeKind) return false;
      if (filters.hasTeachingSignal === "yes" && !teachingSignalsByTarget.has(e.id)) return false;
      if (filters.hasTeachingSignal === "no" && teachingSignalsByTarget.has(e.id)) return false;
      if (q) {
        const hay = [
          e.decision, e.rationale, e.actor.id, e.model_used,
          e.run_id ?? "", e.stage ?? "", e.ambiguity_class ?? "",
          ...e.bundle_refs,
        ].join(" ").toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [normalized, filters, teachingSignalsByTarget]);

  const sorted = useMemo(() => {
    const copy = [...filtered];
    copy.sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case "created_at":
          cmp = a.created_at.localeCompare(b.created_at);
          break;
        case "cost_usd":
          cmp = a.cost_usd - b.cost_usd;
          break;
        case "stage":
          cmp = (a.stage ?? "").localeCompare(b.stage ?? "");
          break;
        case "actor":
          cmp = `${a.actor.kind}|${a.actor.id}`.localeCompare(`${b.actor.kind}|${b.actor.id}`);
          break;
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
    return copy;
  }, [filtered, sortKey, sortDir]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir(key === "cost_usd" ? "desc" : key === "created_at" ? "desc" : "asc");
    }
  };

  const toggleExpanded = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const filterCount =
    (filters.search ? 1 : 0) +
    (filters.stage ? 1 : 0) +
    (filters.actorKind ? 1 : 0) +
    (filters.phi ? 1 : 0) +
    (filters.runtimeKind ? 1 : 0) +
    (filters.hasTeachingSignal ? 1 : 0);

  return (
    <div className="space-y-3">
      <FilterBar
        filters={filters}
        onChange={setFilters}
        stages={stages}
        runtimeKinds={runtimeKinds}
        filterCount={filterCount}
        totalRows={normalized.length}
        visibleRows={sorted.length}
      />

      <div className="rounded-lg border border-[var(--border-default)] bg-[var(--surface)] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[var(--overlay)]/40 text-[11px] uppercase tracking-wider text-[var(--text-tertiary)]">
              <tr>
                <th className="w-8 px-2 py-2 text-left" aria-label="expand" />
                <SortableTh keyName="stage" label="Stage" sortKey={sortKey} sortDir={sortDir} onClick={toggleSort} className="w-28" />
                <th className="px-3 py-2 text-left">Decision</th>
                <SortableTh keyName="actor" label="Actor" sortKey={sortKey} sortDir={sortDir} onClick={toggleSort} className="w-44" />
                <th className="px-3 py-2 text-left w-36">Model</th>
                <th className="px-3 py-2 text-left w-16">PHI</th>
                <SortableTh keyName="cost_usd" label="Cost" sortKey={sortKey} sortDir={sortDir} onClick={toggleSort} className="w-20 text-right" align="right" />
                <SortableTh keyName="created_at" label="When" sortKey={sortKey} sortDir={sortDir} onClick={toggleSort} className="w-24" />
                <th className="px-3 py-2 text-left w-28">Signals</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-muted)]">
              {sorted.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-4 py-12 text-center text-[var(--text-tertiary)]">
                    No decisions match the current filters.
                    {filterCount > 0 && (
                      <button
                        type="button"
                        onClick={() => setFilters(DEFAULT_FILTERS)}
                        className="ml-2 text-[var(--primary)] hover:underline"
                      >
                        Clear filters
                      </button>
                    )}
                  </td>
                </tr>
              ) : (
                sorted.map((entry) => (
                  <DecisionRow
                    key={entry.id}
                    entry={entry}
                    expanded={expanded.has(entry.id)}
                    onToggle={() => toggleExpanded(entry.id)}
                    teachingSignals={teachingSignalsByTarget.get(entry.id) ?? []}
                  />
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function SortableTh({
  keyName, label, sortKey, sortDir, onClick, className, align,
}: {
  keyName: SortKey;
  label: string;
  sortKey: SortKey;
  sortDir: SortDir;
  onClick: (k: SortKey) => void;
  className?: string;
  align?: "left" | "right";
}) {
  const isActive = sortKey === keyName;
  return (
    <th className={cn("px-3 py-2", align === "right" ? "text-right" : "text-left", className)}>
      <button
        type="button"
        onClick={() => onClick(keyName)}
        className={cn(
          "inline-flex items-center gap-1 text-[11px] uppercase tracking-wider",
          "hover:text-[var(--text)] transition-colors",
          isActive ? "text-[var(--text)]" : "text-[var(--text-tertiary)]",
        )}
      >
        <span>{label}</span>
        {isActive && (
          <span className="text-[10px]">{sortDir === "asc" ? "▲" : "▼"}</span>
        )}
      </button>
    </th>
  );
}

function FilterBar({
  filters, onChange, stages, runtimeKinds, filterCount, totalRows, visibleRows,
}: {
  filters: Filters;
  onChange: (f: Filters) => void;
  stages: string[];
  runtimeKinds: string[];
  filterCount: number;
  totalRows: number;
  visibleRows: number;
}) {
  return (
    <div className="rounded-lg border border-[var(--border-default)] bg-[var(--surface)] p-3 space-y-2">
      <div className="flex items-center gap-2 flex-wrap">
        <div className="relative flex-1 min-w-[220px] max-w-md">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[var(--text-tertiary)]" />
          <input
            type="text"
            placeholder="Search decision, rationale, actor, model, run, bundle…"
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
          label="Stage"
          value={filters.stage}
          onChange={(v) => onChange({ ...filters, stage: v })}
          options={stages.map((s) => ({ value: s, label: s }))}
        />
        <Select
          label="Actor"
          value={filters.actorKind}
          onChange={(v) => onChange({ ...filters, actorKind: v as Filters["actorKind"] })}
          options={[{ value: "human", label: "Human" }, { value: "agent", label: "Agent" }]}
        />
        <Select
          label="PHI"
          value={filters.phi}
          onChange={(v) => onChange({ ...filters, phi: v as Filters["phi"] })}
          options={[
            { value: "none", label: "None" },
            { value: "low", label: "Low" },
            { value: "high", label: "High" },
          ]}
        />
        <Select
          label="Kind"
          value={filters.runtimeKind}
          onChange={(v) => onChange({ ...filters, runtimeKind: v })}
          options={runtimeKinds.map((k) => ({ value: k, label: k.replace(/_/g, " ") }))}
        />
        <Select
          label="Has feedback"
          value={filters.hasTeachingSignal}
          onChange={(v) => onChange({ ...filters, hasTeachingSignal: v as Filters["hasTeachingSignal"] })}
          options={[{ value: "yes", label: "Yes" }, { value: "no", label: "No" }]}
        />

        {filterCount > 0 && (
          <button
            type="button"
            onClick={() => onChange(DEFAULT_FILTERS)}
            className="text-[11px] text-[var(--text-secondary)] hover:text-[var(--text)] inline-flex items-center gap-1 px-2 py-1 rounded border border-[var(--border-default)] hover:bg-[var(--overlay)]"
          >
            <X className="h-3 w-3" />
            Clear ({filterCount})
          </button>
        )}
      </div>

      <div className="flex items-center justify-between text-[11px] text-[var(--text-tertiary)]">
        <div className="flex items-center gap-1.5">
          <Filter className="h-3 w-3" />
          <span>
            Showing <span className="text-[var(--text-secondary)] tabular">{visibleRows}</span>
            {visibleRows !== totalRows && (
              <> of <span className="text-[var(--text-secondary)] tabular">{totalRows}</span></>
            )}
            {" "}entries
          </span>
        </div>
      </div>
    </div>
  );
}

function Select({
  label, value, onChange, options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      aria-label={label}
      className={cn(
        "text-xs rounded border bg-[var(--surface)] py-1.5 pl-2 pr-7 focus:outline-none focus:border-[var(--primary)]",
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
  );
}

function DecisionRow({
  entry, expanded, onToggle, teachingSignals,
}: {
  entry: LedgerEntry;
  expanded: boolean;
  onToggle: () => void;
  teachingSignals: LedgerEntry[];
}) {
  const PhiIcon =
    entry.phi_class === "high" ? ShieldAlert :
    entry.phi_class === "low" ? ShieldOff : ShieldCheck;
  const phiColor =
    entry.phi_class === "high" ? "var(--danger)" :
    entry.phi_class === "low" ? "var(--warning)" : "var(--success)";
  const ActorIcon = entry.actor.kind === "agent" ? Bot : User;
  const TKindIcon = teachingKindIcon(entry.runtime_kind, entry.feedback_kind);
  const isMeta = entry.entry_type === "meta";

  // Derive a display model: model_used wins; otherwise infer from the
  // agent_session_id prefix we set on auto-generated teaching signals.
  const modelDisplay = entry.model_used
    || (entry.runtime_kind && entry.runtime_kind !== "stage_decision" ? "(operator)" : "—");

  return (
    <>
      <tr
        className={cn(
          "hover:bg-[var(--overlay)]/50 cursor-pointer transition-colors",
          expanded && "bg-[var(--overlay)]/30",
        )}
        onClick={onToggle}
      >
        <td className="px-2 py-2 align-top">
          <button type="button" aria-label={expanded ? "collapse" : "expand"} className="text-[var(--text-tertiary)]">
            {expanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
          </button>
        </td>
        <td className="px-3 py-2 align-top">
          {entry.stage ? (
            <StagePill stage={entry.stage} status="completed" />
          ) : isMeta ? (
            <Badge variant="secondary">meta</Badge>
          ) : entry.runtime_kind && entry.runtime_kind !== "stage_decision" ? (
            <Badge variant="secondary">{entry.runtime_kind.replace(/_/g, " ")}</Badge>
          ) : (
            <span className="text-[var(--text-tertiary)] text-[11px]">—</span>
          )}
        </td>
        <td className="px-3 py-2 align-top max-w-md">
          <div className="space-y-0.5">
            <p className="text-sm text-[var(--text)] leading-snug line-clamp-2">{entry.decision}</p>
            <div className="flex items-center gap-1.5 text-[10px] text-[var(--text-tertiary)]">
              <span className="mono">{shortId(entry.id, 8)}</span>
              {entry.ambiguity_class && (
                <span className="px-1 py-0.5 rounded bg-[var(--overlay)] text-[var(--text-secondary)]">
                  {entry.ambiguity_class}
                </span>
              )}
              {entry.references_entry_id && (
                <span className="text-[var(--text-tertiary)]">
                  ↳ <span className="mono">{shortId(entry.references_entry_id, 8)}</span>
                </span>
              )}
            </div>
          </div>
        </td>
        <td className="px-3 py-2 align-top">
          <div className="flex items-center gap-1.5 text-xs">
            <ActorIcon className={cn("h-3.5 w-3.5 shrink-0", entry.actor.kind === "agent" ? "text-[var(--secondary)]" : "text-[var(--primary)]")} />
            <span className="text-[var(--text-secondary)] truncate" title={entry.actor.id}>{entry.actor.id}</span>
          </div>
        </td>
        <td className="px-3 py-2 align-top">
          <span className="mono text-[11px] text-[var(--text-secondary)] truncate block" title={modelDisplay}>
            {modelDisplay}
          </span>
        </td>
        <td className="px-3 py-2 align-top">
          <PhiIcon className="h-3.5 w-3.5" style={{ color: phiColor }} aria-label={`PHI ${entry.phi_class}`} />
        </td>
        <td className="px-3 py-2 align-top text-right tabular text-xs text-[var(--text-secondary)]">
          {fmtUsd(entry.cost_usd)}
        </td>
        <td className="px-3 py-2 align-top text-[11px] text-[var(--text-tertiary)] tabular">
          {relativeTime(entry.created_at)}
        </td>
        <td className="px-3 py-2 align-top">
          <div className="flex items-center gap-1">
            {TKindIcon && <TKindIcon className="h-3.5 w-3.5 text-[var(--text-tertiary)]" />}
            {teachingSignals.length > 0 && (
              <span
                className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--warning)]/15 text-[var(--warning)] tabular"
                title={`${teachingSignals.length} teaching signal${teachingSignals.length === 1 ? "" : "s"} reference this entry`}
              >
                {teachingSignals.length}
              </span>
            )}
            {!TKindIcon && teachingSignals.length === 0 && (
              <span className="text-[var(--text-tertiary)] text-[11px]">—</span>
            )}
          </div>
        </td>
      </tr>
      {expanded && (
        <tr className="bg-[var(--overlay)]/20">
          <td colSpan={9} className="px-4 py-3">
            <DecisionDetail entry={entry} teachingSignals={teachingSignals} />
          </td>
        </tr>
      )}
    </>
  );
}

function DecisionDetail({
  entry, teachingSignals,
}: {
  entry: LedgerEntry;
  teachingSignals: LedgerEntry[];
}) {
  return (
    <div className="space-y-3 text-xs">
      {entry.rationale && (
        <Section title="Rationale">
          <p className="text-[var(--text)] leading-relaxed whitespace-pre-wrap">{entry.rationale}</p>
        </Section>
      )}

      <div className="grid gap-3 md:grid-cols-2">
        <Section title="Provenance">
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-[11px]">
            <Dt>Entry ID</Dt><Dd mono>{entry.id}</Dd>
            <Dt>Run ID</Dt><Dd mono>{entry.run_id ?? "—"}</Dd>
            <Dt>Agent session</Dt><Dd mono>{entry.agent_session_id ?? "—"}</Dd>
            <Dt>Actor</Dt><Dd>{entry.actor.kind} · {entry.actor.id}</Dd>
            <Dt>Model</Dt><Dd mono>{entry.model_used || "—"}</Dd>
            <Dt>Created</Dt><Dd>{entry.created_at}</Dd>
            <Dt>Cost USD</Dt><Dd className="tabular">{fmtUsd(entry.cost_usd)}</Dd>
            <Dt>PHI class</Dt><Dd>{entry.phi_class}</Dd>
          </dl>
        </Section>

        <Section title="Classification">
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-[11px]">
            <Dt>Entry type</Dt><Dd>{entry.entry_type}</Dd>
            <Dt>Stage</Dt><Dd>{entry.stage ?? "—"}</Dd>
            <Dt>Runtime kind</Dt><Dd>{entry.runtime_kind ?? "—"}</Dd>
            <Dt>Ambiguity class</Dt><Dd>{entry.ambiguity_class ?? "—"}</Dd>
            {entry.references_entry_id && <><Dt>References</Dt><Dd mono>{entry.references_entry_id}</Dd></>}
            {entry.feedback_kind && <><Dt>Feedback kind</Dt><Dd>{entry.feedback_kind}</Dd></>}
            {entry.paused_class && <><Dt>Paused class</Dt><Dd>{entry.paused_class}</Dd></>}
          </dl>
        </Section>
      </div>

      {/* Phase 5: full prompt-chain visualization. Operators can see
          every scope the resolver checked and which one matched, with
          the matched prompt's git_sha + owner_persona visible. This
          closes the audit loop: any decision is traceable back to its
          YAML source-of-truth. */}
      <Section title="Prompt resolution">
        <PromptChainBadge chain={entry.prompt_resolution_path} variant="full" />
      </Section>

      {entry.bundle_refs.length > 0 && (
        <Section title={`Bundle citations (${entry.bundle_refs.length})`}>
          <div className="flex flex-wrap gap-1.5">
            {entry.bundle_refs.map((ref) => (
              <span key={ref} className="mono text-[10px] px-2 py-0.5 rounded bg-[var(--overlay)] text-[var(--secondary)]">
                {ref}
              </span>
            ))}
          </div>
        </Section>
      )}

      {teachingSignals.length > 0 && (
        <Section title={`Teaching signals against this entry (${teachingSignals.length})`}>
          <ul className="space-y-1.5">
            {teachingSignals.map((sig) => {
              const SigIcon = teachingKindIcon(sig.runtime_kind, sig.feedback_kind);
              return (
                <li key={sig.id} className="flex items-start gap-2 text-[11px]">
                  {SigIcon && <SigIcon className="h-3.5 w-3.5 mt-0.5 shrink-0 text-[var(--text-tertiary)]" />}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <Badge variant="secondary">
                        {sig.runtime_kind?.replace(/_/g, " ")}
                      </Badge>
                      <span className="text-[var(--text-secondary)]">{sig.actor.id}</span>
                      <span className="text-[var(--text-tertiary)]">· {relativeTime(sig.created_at)}</span>
                    </div>
                    {sig.rationale && (
                      <p className="text-[var(--text-secondary)] mt-0.5 leading-snug">{sig.rationale}</p>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        </Section>
      )}

      <Section title="Operator actions">
        <TeachingSignalBar entry={entry} />
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <h4 className="text-[10px] uppercase tracking-wider text-[var(--text-tertiary)]">
        {title}
      </h4>
      <div>{children}</div>
    </div>
  );
}

function Dt({ children }: { children: React.ReactNode }) {
  return <dt className="text-[var(--text-tertiary)] uppercase text-[10px] tracking-wider">{children}</dt>;
}

function Dd({ children, mono, className }: { children: React.ReactNode; mono?: boolean; className?: string }) {
  return (
    <dd className={cn("text-[var(--text)] break-all", mono && "mono", className)}>
      {children}
    </dd>
  );
}
