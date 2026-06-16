/**
 * RunsTable — dense, sortable, scannable table of pipeline runs.
 *
 * The `/runs` card grid worked for sentiment but failed the operator's
 * "which one is haiku?" question on inspection — the model badge was
 * easy to overlook in the busy card header and didn't render at all
 * until the API projection started including it. A table puts model,
 * cost, tokens, decisions in aligned columns so they read together.
 *
 * Mirrors the design pattern from DecisionTable on /decisions:
 *   - sortable columns (header click toggles direction)
 *   - newest-first default
 *   - click row to navigate to /runs/<id>
 *   - safe model fallback that derives a label from cost when projection
 *     drops the field (back-compat with pre-v3 orchestrator deploys)
 */
"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ArrowUpRight, Bot } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { StatusDot } from "./status-dot";
import { relativeTime, shortId, fmtUsd, cn } from "@/lib/utils";
import type { RunState } from "@/lib/types";

type SortKey = "updated_at" | "total_cost_usd" | "total_tokens" | "model" | "status";
type SortDir = "asc" | "desc";

const statusVariant: Record<string, "success" | "warning" | "danger" | "info" | "default"> = {
  completed: "success",
  running: "info",
  awaiting_gate: "warning",
  paused: "warning",
  failed: "danger",
  cancelled: "danger",
  queued: "default",
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

/** Strip the verbose provider prefix for table display. */
function shortModel(m: string): string {
  return m.replace(/^databricks-claude-/, "").replace(/^claude-/, "");
}

export function RunsTable({ runs }: { runs: RunState[] }) {
  const [sortKey, setSortKey] = useState<SortKey>("updated_at");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const sorted = useMemo(() => {
    const copy = [...runs];
    copy.sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case "updated_at":
          cmp = (a.updated_at || "").localeCompare(b.updated_at || "");
          break;
        case "total_cost_usd":
          cmp = (a.total_cost_usd ?? a.cost_usd ?? 0) - (b.total_cost_usd ?? b.cost_usd ?? 0);
          break;
        case "total_tokens":
          cmp = (a.total_tokens ?? 0) - (b.total_tokens ?? 0);
          break;
        case "model":
          cmp = (modelLabel(a) || "").localeCompare(modelLabel(b) || "");
          break;
        case "status":
          cmp = (a.status || "").localeCompare(b.status || "");
          break;
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
    return copy;
  }, [runs, sortKey, sortDir]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir(key === "model" || key === "status" ? "asc" : "desc");
    }
  };

  return (
    <div className="rounded-lg border border-[var(--border-default)] bg-[var(--surface)] overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-[var(--overlay)]/40 text-[11px] uppercase tracking-wider text-[var(--text-tertiary)]">
            <tr>
              <th className="w-8 px-2 py-2" aria-label="status" />
              <th className="px-3 py-2 text-left w-44">Run</th>
              <SortableTh keyName="model" label="Model" sortKey={sortKey} sortDir={sortDir} onClick={toggleSort} className="w-40" />
              <SortableTh keyName="status" label="Status" sortKey={sortKey} sortDir={sortDir} onClick={toggleSort} className="w-28" />
              <th className="px-3 py-2 text-left w-32">Team / NS</th>
              <SortableTh keyName="total_cost_usd" label="Cost" sortKey={sortKey} sortDir={sortDir} onClick={toggleSort} className="w-24 text-right" align="right" />
              <SortableTh keyName="total_tokens" label="Tokens" sortKey={sortKey} sortDir={sortDir} onClick={toggleSort} className="w-24 text-right" align="right" />
              <th className="px-3 py-2 text-right w-20">Dec</th>
              <SortableTh keyName="updated_at" label="Updated" sortKey={sortKey} sortDir={sortDir} onClick={toggleSort} className="w-28" />
              <th className="w-8 px-2 py-2" aria-label="open" />
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border-muted)]">
            {sorted.map((r) => {
              const cost = r.total_cost_usd ?? r.cost_usd ?? 0;
              const tokens = r.total_tokens ?? 0;
              const model = modelLabel(r);
              return (
                <tr key={r.run_id} className="hover:bg-[var(--overlay)]/50 group">
                  <td className="px-2 py-2 align-middle">
                    <StatusDot
                      status={
                        r.status === "running" ? "running"
                        : r.status === "completed" ? "ok"
                        : r.status === "awaiting_gate" || r.status === "paused" ? "warning"
                        : r.status === "failed" || r.status === "cancelled" ? "error"
                        : "idle"
                      }
                      pulse={r.status === "running"}
                    />
                  </td>
                  <td className="px-3 py-2 align-middle">
                    <Link href={`/runs/${r.run_id}`} className="mono text-[12px] text-[var(--text)] hover:text-[var(--primary)]">
                      {shortId(r.run_id, 14)}
                    </Link>
                    {r.source_run_dir && (
                      <div className="text-[10px] text-[var(--text-tertiary)] truncate">{r.source_run_dir}</div>
                    )}
                  </td>
                  <td className="px-3 py-2 align-middle">
                    {model ? (
                      <span
                        className="mono text-[11px] inline-flex items-center gap-1 text-[var(--secondary)]"
                        title={model}
                      >
                        <Bot className="h-3 w-3 shrink-0" />
                        <span className="truncate">{shortModel(model)}</span>
                      </span>
                    ) : (
                      <span className="text-[11px] text-[var(--text-tertiary)]">—</span>
                    )}
                  </td>
                  <td className="px-3 py-2 align-middle">
                    <Badge variant={statusVariant[r.status] ?? "default"}>
                      {r.status.replace("_", " ")}
                    </Badge>
                  </td>
                  <td className="px-3 py-2 align-middle text-[11px] text-[var(--text-secondary)] truncate">
                    {r.namespace ? (
                      <>
                        <span className="text-[var(--text)]">{r.namespace}</span>
                        <span className="text-[var(--text-tertiary)]"> · {r.team_id}</span>
                      </>
                    ) : (
                      r.team_id
                    )}
                  </td>
                  <td className="px-3 py-2 align-middle text-right tabular text-[var(--text)]">
                    {fmtUsd(cost)}
                  </td>
                  <td className="px-3 py-2 align-middle text-right tabular text-[var(--text-secondary)]">
                    {tokens > 0 ? tokens.toLocaleString() : "—"}
                  </td>
                  <td className="px-3 py-2 align-middle text-right tabular text-[var(--text-secondary)]">
                    {r.decisions_count ?? 0}
                  </td>
                  <td className="px-3 py-2 align-middle text-[11px] text-[var(--text-tertiary)] tabular">
                    {relativeTime(r.updated_at)}
                  </td>
                  <td className="px-2 py-2 align-middle">
                    <Link href={`/runs/${r.run_id}`} aria-label="open run">
                      <ArrowUpRight className="h-4 w-4 text-[var(--text-tertiary)] opacity-0 group-hover:opacity-100 transition-opacity" />
                    </Link>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
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
          "inline-flex items-center gap-1 text-[11px] uppercase tracking-wider hover:text-[var(--text)] transition-colors",
          isActive ? "text-[var(--text)]" : "text-[var(--text-tertiary)]",
        )}
      >
        <span>{label}</span>
        {isActive && <span className="text-[10px]">{sortDir === "asc" ? "▲" : "▼"}</span>}
      </button>
    </th>
  );
}
