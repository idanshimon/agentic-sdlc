"use client";
import { use, useMemo } from "react";
import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useRun } from "@/lib/hooks/use-runs";
import { useRunStream } from "@/lib/hooks/use-run-stream";
import { useAssistantContext } from "@/lib/assist/context";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { StagePill } from "@/components/domain/stage-pill";
import { StatusDot } from "@/components/domain/status-dot";
import { ResolverGate } from "@/components/domain/resolver-gate";
import { RunArtifactsPanel } from "@/components/domain/run-artifacts-panel";
import { PageHeader } from "@/components/layout/page-header";
import { relativeTime, shortId, fmtUsd } from "@/lib/utils";
import type { Stage, StageEvent } from "@/lib/types";
import { Loader2 } from "lucide-react";

const allStages: Stage[] = [
  "ingest", "assessor", "architect", "test_plan", "codegen", "review_scan", "deliver",
];

export default function RunDetailPage({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = use(params);
  const { data: run, isLoading } = useRun(runId);
  const { events: liveEvents, connected } = useRunStream(runId);
  const queryClient = useQueryClient();

  const allEvents = [...(run?.events ?? []), ...liveEvents];
  const awaitingGate = run?.status === "awaiting_gate";

  // Memoize the payload object so its identity is stable across renders that
  // don't change status/stage. Inline `payload: {status, stage}` literals at
  // this call site triggered renderer SIGKILL during the demo replay engine's
  // setTimeout cascade after Approve (caught 2026-06-09 customer-blocking).
  // The provider-side fix in assist/context.tsx makes payload not part of the
  // dep key, so this useMemo is belt-and-suspenders — but it's also the
  // canonical pattern for any future call sites.
  const assistPayload = useMemo(
    () => ({ status: run?.status, stage: run?.current_stage }),
    [run?.status, run?.current_stage],
  );

  useAssistantContext({
    kind: awaitingGate ? "run-resolver-gate" : "run-detail",
    id: runId,
    label: run ? `Run ${shortId(runId, 8)}` : "Run",
    payload: assistPayload,
  });

  const onApproved = () => {
    // Force-refetch run state immediately after approval so the gate panel
    // disappears and the post-resolver stages render without a 3s polling lag.
    queryClient.invalidateQueries({ queryKey: ["run", runId] });
    queryClient.invalidateQueries({ queryKey: ["runs"] });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="sm" asChild>
          <Link href="/runs">
            <ChevronLeft className="h-3.5 w-3.5" />
            Back to all runs
          </Link>
        </Button>
        <span className="text-[var(--text-tertiary)] text-xs">/</span>
        <Button variant="ghost" size="sm" asChild>
          <Link href="/runs/new">
            Start a new run
          </Link>
        </Button>
      </div>

      <PageHeader
        plane="pipeline"
        title={
          <span className="font-mono text-base">{shortId(runId, 16)}</span>
        }
        description={
          run ? (
            <div className="flex items-center gap-3 text-xs text-[var(--text-tertiary)]">
              <span>team <span className="text-[var(--text-secondary)]">{run.team_id}</span></span>
              <span>·</span>
              <span>mode <span className="text-[var(--text-secondary)]">{run.mode}</span></span>
              <span>·</span>
              <span>updated {relativeTime(run.updated_at)}</span>
            </div>
          ) : (
            "Loading run state…"
          )
        }
        actions={
          run && (
            <div className="flex items-center gap-2">
              <Badge variant={connected ? "success" : "default"}>
                <StatusDot status={connected ? "running" : "idle"} pulse={connected} />
                {connected ? "Streaming" : "Idle"}
              </Badge>
              <Badge variant={run.status === "completed" ? "success" : run.status === "failed" ? "danger" : "info"}>
                {run.status.replace("_", " ")}
              </Badge>
            </div>
          )
        }
      />

      {isLoading ? (
        <div className="skeleton h-24 rounded-lg" />
      ) : !run ? (
        <Card className="p-6 text-center text-sm text-[var(--text-tertiary)]">Run not found.</Card>
      ) : (
        <>
          {awaitingGate && (
            <ResolverGate
              runId={runId}
              events={allEvents}
              onApproved={onApproved}
            />
          )}

          <Card className="p-4">
            <h3 className="text-xs font-medium uppercase tracking-wider text-[var(--text-tertiary)] mb-3">
              Stage progress
            </h3>
            <div className="flex flex-wrap items-center gap-2">
              {allStages.map((s, i) => {
                const completed = allEvents.some((e) => e.stage === s && e.status === "completed");
                const failed = allEvents.some((e) => e.stage === s && e.status === "failed");
                const status =
                  failed ? "failed" :
                  completed ? "completed" :
                  run.current_stage === s ? (run.status === "awaiting_gate" ? "awaiting_gate" : "running") :
                  "idle";
                return (
                  <div key={s} className="flex items-center gap-2">
                    <StagePill stage={s} status={status} />
                    {i < allStages.length - 1 && (
                      <span className="text-[var(--text-tertiary)] text-xs">→</span>
                    )}
                  </div>
                );
              })}
            </div>
          </Card>

          <Card className="overflow-hidden">
            <div className="flex items-center justify-between p-4 border-b border-[var(--border-muted)]">
              <h3 className="text-xs font-medium uppercase tracking-wider text-[var(--text-tertiary)]">
                Event stream
              </h3>
              <span className="text-[10px] text-[var(--text-tertiary)] tabular">
                {allEvents.length} events
              </span>
            </div>
            <div className="divide-y divide-[var(--border-muted)] max-h-[600px] overflow-y-auto">
              {allEvents.length === 0 ? (
                <div className="p-6 text-center text-xs text-[var(--text-tertiary)] flex items-center justify-center gap-2">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" /> Waiting for the first event…
                </div>
              ) : (
                allEvents
                  .slice()
                  .reverse()
                  .map((e: StageEvent, idx) => (
                    <div key={idx} className="px-4 py-3 hover:bg-[var(--overlay)]/40 transition-colors">
                      <div className="flex items-start gap-3">
                        <div className="pt-0.5">
                          <StatusDot
                            status={
                              e.status === "completed" ? "ok"
                              : e.status === "failed" ? "error"
                              : e.status === "awaiting_gate" ? "warning"
                              : "running"
                            }
                            pulse={e.status === "in_progress" || e.status === "started"}
                          />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-0.5">
                            <StagePill stage={e.stage} />
                            <span className="text-[11px] text-[var(--text-tertiary)] capitalize">
                              {e.status.replace("_", " ")}
                            </span>
                            <span className="text-[11px] tabular text-[var(--text-tertiary)] ml-auto">
                              {new Date(e.timestamp).toLocaleTimeString()}
                            </span>
                          </div>
                          {e.message && (
                            <p className="text-xs text-[var(--text-secondary)] leading-snug">
                              {e.message}
                            </p>
                          )}
                          {e.payload && Object.keys(e.payload).length > 0 && (
                            <details className="mt-1.5">
                              <summary className="text-[10px] text-[var(--text-tertiary)] cursor-pointer hover:text-[var(--text-secondary)]">
                                Payload
                              </summary>
                              <pre className="mono text-[10px] mt-1 bg-[var(--bg)] p-2 rounded border border-[var(--border-muted)] overflow-x-auto">
                                {JSON.stringify(e.payload, null, 2)}
                              </pre>
                            </details>
                          )}
                        </div>
                      </div>
                    </div>
                  ))
              )}
            </div>
          </Card>

          <RunArtifactsPanel runId={runId} status={run.status} />

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <Card className="p-4">
              <div className="text-[10px] font-medium uppercase tracking-wider text-[var(--text-tertiary)]">
                Spend
              </div>
              <div className="text-2xl font-semibold tabular mt-1">
                {fmtUsd(run.cost_usd ?? 0)}
              </div>
            </Card>
            <Card className="p-4">
              <div className="text-[10px] font-medium uppercase tracking-wider text-[var(--text-tertiary)]">
                Decisions
              </div>
              <div className="text-2xl font-semibold tabular mt-1">
                {run.decisions_count ?? 0}
              </div>
            </Card>
            <Card className="p-4">
              <div className="text-[10px] font-medium uppercase tracking-wider text-[var(--text-tertiary)]">
                Created
              </div>
              <div className="text-sm mt-1.5 text-[var(--text-secondary)]">
                {new Date(run.created_at).toLocaleString()}
              </div>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
