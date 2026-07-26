"use client";
/* RunsTriage — urgency-grouped view of the runs list.
 *
 * The flat reverse-chronological table buries the two runs that actually need
 * a human under eleven failures. This groups by "what do I do about it",
 * newest-first inside each band, and lets the operator collapse the noise. */
import { useMemo, useState } from "react";
import { ChevronDown, PauseCircle, AlertTriangle, ShieldAlert, Clock, Play, CheckCircle2 } from "lucide-react";
import type { RunState } from "@/lib/types";
import { RunsTable } from "@/components/domain/runs-table";
import { Badge } from "@/components/ui/badge";
import { STALL_THRESHOLD_MS, FAILURE_WINDOW_MS } from "@/lib/attention";
import { cn } from "@/lib/utils";

export type TriageBand = "needs_you" | "blocked" | "failed" | "running" | "done";

export interface TriageGroup {
  band: TriageBand;
  runs: RunState[];
}

const BAND_META: Record<
  TriageBand,
  { label: string; help: string; color: string; icon: typeof Play; defaultOpen: boolean }
> = {
  needs_you: {
    label: "Needs you",
    help: "Stopped at a gate. Nothing proceeds until a human answers.",
    color: "var(--warning)",
    icon: PauseCircle,
    defaultOpen: true,
  },
  blocked: {
    label: "Blocked by policy",
    // NOT "failed". A BLOCK rule refusing the code is the governance layer
    // doing its job. "Triage or retry" is actively wrong advice here — you do
    // not retry a PHI violation, you fix the code or challenge the rule
    // through a standards change.
    help: "A standards rule refused the code. Fix the code, or challenge the rule.",
    color: "var(--warning)",
    icon: ShieldAlert,
    defaultOpen: true,
  },
  failed: {
    label: "Failed",
    help: "Produced no delivery. Triage or retry.",
    color: "var(--danger)",
    icon: AlertTriangle,
    defaultOpen: true,
  },
  running: {
    label: "In flight",
    help: "Working. Stalled runs are called out.",
    color: "var(--plane-pipeline)",
    icon: Play,
    defaultOpen: true,
  },
  done: {
    label: "Completed",
    help: "Delivered or cancelled. History.",
    color: "var(--success)",
    icon: CheckCircle2,
    defaultOpen: false,
  },
};

export const BAND_ORDER: TriageBand[] = ["needs_you", "blocked", "failed", "running", "done"];

function ts(v: string | undefined | null): number {
  if (!v) return 0;
  const p = Date.parse(v);
  return Number.isNaN(p) ? 0 : p;
}

/** Pure classifier — unit-testable, no React. */
export function bandFor(run: RunState, now: number = Date.now()): TriageBand {
  if (run.status === "awaiting_gate" || run.status === "paused") return "needs_you";
  // A policy block is a governance outcome, not a fault. Only route genuine
  // defects to the red "Failed" band.
  if (run.status === "failed") {
    return run.failure_kind === "policy_block" ? "blocked" : "failed";
  }
  if (run.status === "running" || run.status === "queued") return "running";
  return "done";
}

/** Group + sort newest-first within each band. Empty bands are dropped. */
export function groupRuns(runs: RunState[], now: number = Date.now()): TriageGroup[] {
  const buckets = new Map<TriageBand, RunState[]>();
  for (const band of BAND_ORDER) buckets.set(band, []);
  for (const run of runs) buckets.get(bandFor(run, now))!.push(run);
  return BAND_ORDER.map((band) => ({
    band,
    runs: buckets
      .get(band)!
      .slice()
      .sort((a, b) => ts(b.updated_at || b.created_at) - ts(a.updated_at || a.created_at)),
  })).filter((g) => g.runs.length > 0);
}

/** A running run with no update for a long time is probably wedged. */
export function isStalled(run: RunState, now: number = Date.now()): boolean {
  if (run.status !== "running") return false;
  const at = ts(run.updated_at || run.created_at);
  return at > 0 && now - at > STALL_THRESHOLD_MS;
}

/** Failures inside the alert window — older ones are history, not an alert. */
export function isRecentFailure(run: RunState, now: number = Date.now()): boolean {
  if (run.status !== "failed") return false;
  const at = ts(run.updated_at || run.created_at);
  return at > 0 && now - at <= FAILURE_WINDOW_MS;
}

export function RunsTriage({ runs }: { runs: RunState[] }) {
  const groups = useMemo(() => groupRuns(runs), [runs]);
  const [collapsed, setCollapsed] = useState<Set<TriageBand>>(
    () => new Set(BAND_ORDER.filter((b) => !BAND_META[b].defaultOpen)),
  );

  const toggle = (band: TriageBand) =>
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(band)) next.delete(band);
      else next.add(band);
      return next;
    });

  return (
    <div className="space-y-4">
      {groups.map((group) => {
        const meta = BAND_META[group.band];
        const Icon = meta.icon;
        const open = !collapsed.has(group.band);
        const stalledCount =
          group.band === "running" ? group.runs.filter((r) => isStalled(r)).length : 0;
        return (
          <section key={group.band} className="space-y-2">
            <button
              type="button"
              onClick={() => toggle(group.band)}
              aria-expanded={open}
              className="flex w-full items-center gap-2 text-left group"
            >
              <ChevronDown
                className={cn(
                  "h-4 w-4 shrink-0 text-[var(--text-tertiary)] transition-transform",
                  !open && "-rotate-90",
                )}
              />
              <Icon className="h-4 w-4 shrink-0" style={{ color: meta.color }} />
              <span className="text-sm font-semibold text-[var(--text)]">{meta.label}</span>
              <Badge variant="outline" className="tabular">
                {group.runs.length}
              </Badge>
              {stalledCount > 0 && (
                <Badge variant="warning" className="tabular">
                  <Clock className="h-2.5 w-2.5" />
                  {stalledCount} stalled
                </Badge>
              )}
              <span className="hidden sm:inline text-[11px] text-[var(--text-tertiary)] ml-1">
                {meta.help}
              </span>
            </button>
            {open && <RunsTable runs={group.runs} />}
          </section>
        );
      })}
    </div>
  );
}
