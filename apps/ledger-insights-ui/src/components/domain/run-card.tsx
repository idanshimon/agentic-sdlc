import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { StagePill } from "./stage-pill";
import { StatusDot } from "./status-dot";
import { relativeTime, shortId, fmtUsd } from "@/lib/utils";
import type { RunState, Stage } from "@/lib/types";
import { ArrowUpRight } from "lucide-react";

const allStages: Stage[] = [
  "ingest", "assessor", "architect", "test_plan", "codegen", "review_scan", "deliver",
];

const statusVariant: Record<string, "success" | "warning" | "danger" | "info" | "default"> = {
  completed: "success",
  running: "info",
  awaiting_gate: "warning",
  paused: "warning",
  failed: "danger",
  cancelled: "danger",
  queued: "default",
};

export function RunCard({ run }: { run: RunState }) {
  const completedStages = new Set(
    run.events.filter((e) => e.status === "completed").map((e) => e.stage),
  );
  const failedStages = new Set(
    run.events.filter((e) => e.status === "failed").map((e) => e.stage),
  );
  return (
    <Link href={`/runs/${run.run_id}`} className="group block">
      <Card className="p-4 transition-colors hover:border-[var(--text-tertiary)]">
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <StatusDot
                status={
                  run.status === "running" ? "running"
                  : run.status === "completed" ? "ok"
                  : run.status === "awaiting_gate" || run.status === "paused" ? "warning"
                  : run.status === "failed" || run.status === "cancelled" ? "error"
                  : "idle"
                }
                pulse={run.status === "running"}
              />
              <span className="mono text-[12px] text-[var(--text-secondary)]">
                {shortId(run.run_id, 12)}
              </span>
              <Badge variant={statusVariant[run.status] ?? "default"}>
                {run.status.replace("_", " ")}
              </Badge>
            </div>
            <div className="text-xs text-[var(--text-tertiary)]">
              team <span className="text-[var(--text-secondary)]">{run.team_id}</span> · mode <span className="text-[var(--text-secondary)]">{run.mode}</span>
            </div>
          </div>
          <ArrowUpRight className="h-4 w-4 text-[var(--text-tertiary)] opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>
        <div className="flex flex-wrap gap-1 mb-3">
          {allStages.map((s) => {
            const status =
              failedStages.has(s) ? "failed" :
              completedStages.has(s) ? "completed" :
              run.current_stage === s ? (run.status === "awaiting_gate" ? "awaiting_gate" : "running") :
              "idle";
            return <StagePill key={s} stage={s} status={status} />;
          })}
        </div>
        <div className="flex items-center justify-between text-[11px] text-[var(--text-tertiary)] pt-2 border-t border-[var(--border-muted)]">
          <span>updated {relativeTime(run.updated_at)}</span>
          <span className="tabular">
            cost {fmtUsd(run.cost_usd ?? 0)} · {run.decisions_count ?? 0} decisions
          </span>
        </div>
      </Card>
    </Link>
  );
}
