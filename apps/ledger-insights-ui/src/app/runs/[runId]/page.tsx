"use client";
import { use, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ChevronLeft, GitPullRequest, ExternalLink, AlertTriangle, Scale } from "lucide-react";
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
import { DesignReviewGate } from "@/components/domain/design-review-gate";
import { RunArtifactsPanel } from "@/components/domain/run-artifacts-panel";
import { RunSummaryPanel } from "@/components/domain/run-summary-panel";
import { RunOutcomePanel } from "@/components/domain/run-outcome-panel";
import { classifyRunOutcome } from "@/lib/run-outcome";
import { orchestrator } from "@/lib/api/orchestrator";
import { PageHeader } from "@/components/layout/page-header";
import { relativeTime, shortId, fmtUsd, eventTimeLabel } from "@/lib/utils";
import type { Stage, StageEvent } from "@/lib/types";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

const allStages: Stage[] = [
  "ingest", "assessor", "architect", "test_plan", "codegen", "review_scan", "deliver",
];

export default function RunDetailPage({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = use(params);
  const { data: run, isLoading } = useRun(runId);
  const { events: liveEvents, connected } = useRunStream(runId);
  const queryClient = useQueryClient();
  const router = useRouter();
  const [retrying, setRetrying] = useState(false);

  // Phase 4 (2026-06-16): dedup events from server + live SSE so each
  // stage transition only renders once. Without this, the event-stream
  // panel showed every event twice as polling + SSE both delivered the
  // same payloads. Composite key (stage, status, ts) is the same shape
  // useRunStream uses for its internal dedup.
  const allEvents = useMemo(() => {
    const map = new Map<string, StageEvent>();
    for (const ev of run?.events ?? []) {
      const key = `${ev.stage}|${ev.status}|${ev.ts ?? ""}`;
      map.set(key, ev);
    }
    for (const ev of liveEvents) {
      const key = `${ev.stage}|${ev.status}|${ev.ts ?? ""}`;
      if (!map.has(key)) map.set(key, ev);
    }
    return Array.from(map.values());
  }, [run?.events, liveEvents]);
  const awaitingGate = run?.status === "awaiting_gate";
  const outcome = useMemo(() => run ? classifyRunOutcome(run) : null, [run]);

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

  const onRetry = async () => {
    setRetrying(true);
    try {
      const rerun = await orchestrator.rerun(runId);
      router.push(`/runs/${rerun.run_id}`);
    } catch (e) {
      // Surface the failure instead of silently resetting — otherwise the
      // button just returns to its idle state and looks like a dead click.
      const msg = e instanceof Error ? e.message : "Retry failed";
      toast.error("Couldn't start retry", { description: msg });
    } finally {
      setRetrying(false);
    }
  };

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
              <Button variant="ghost" size="sm" asChild>
                <Link href={`/decisions?run=${encodeURIComponent(runId)}`}>
                  <Scale className="h-3.5 w-3.5" />
                  View decisions
                </Link>
              </Button>
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
          {/* Phase 4: sticky needs-your-attention banner when a gate is open.
              Stays pinned to the top of the viewport while operator scrolls
              through events/payloads — without this, the gate card scrolls
              off-screen and the operator can't tell at a glance that they
              need to act. Click → smooth-scroll to the actual gate card. */}
          {awaitingGate && (
            <div className="sticky top-0 z-40 -mx-2 px-2 py-2 backdrop-blur bg-[var(--warning)]/15 border border-[var(--warning)]/40 rounded-lg flex items-center gap-3">
              <span className="inline-flex h-2 w-2 rounded-full bg-[var(--warning)] animate-pulse shrink-0" />
              <div className="flex-1 text-xs">
                <span className="font-semibold text-[var(--text-primary)]">
                  Pipeline paused at {run.current_stage === "design_review" ? "Design Review" : "Resolver"} gate.
                </span>
                <span className="text-[var(--text-secondary)] ml-1.5">
                  Your decision is needed to advance.
                </span>
              </div>
              <button
                onClick={() => {
                  document.getElementById("resolver-gate-anchor")?.scrollIntoView({
                    behavior: "smooth",
                    block: "start",
                  });
                }}
                className="text-[11px] font-medium px-2.5 py-1 rounded bg-[var(--warning)] text-black hover:opacity-90 shrink-0"
              >
                Jump to gate ↓
              </button>
            </div>
          )}

          {awaitingGate && (
            <div id="resolver-gate-anchor">
              {/* Phase 4.1: route to the right gate component based on stage.
                  Resolver gate = per-card decisions with cards from assessor.
                  Design review gate = whole-stage approve of architecture.
                  Other gates fall back to the generic ResolverGate which
                  shows its "can't parse" hint — never silent. */}
              {run.current_stage === "design_review" ? (
                <DesignReviewGate
                  runId={runId}
                  run={run}
                  onApproved={onApproved}
                />
              ) : (
                <ResolverGate
                  runId={runId}
                  events={allEvents}
                  gateVersion={run.pending_gate?.version ?? run.checkpoint_version}
                  onApproved={onApproved}
                />
              )}
            </div>
          )}

          {outcome && <RunOutcomePanel outcome={outcome} onRetry={onRetry} retrying={retrying} />}

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

          <Card id="event-stream" className="overflow-hidden">
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
                              {eventTimeLabel(e)}
                            </span>
                          </div>
                          {e.message && (
                            <p className="text-xs text-[var(--text-secondary)] leading-snug">
                              {e.message}
                            </p>
                          )}
                          {(() => {
                            const pl = (e.payload ?? {}) as {
                              pr_url?: string | null;
                              delivery_status?: string;
                              delivery_reason?: string;
                              artifact_files?: string[];
                            };
                            // Delivery events get a first-class, honest render:
                            // a real PR link, or a clear "not opened + why" — never
                            // a raw fabricated URL dump.
                            if (pl.pr_url) {
                              return (
                                <a
                                  href={pl.pr_url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="inline-flex items-center gap-1.5 text-xs text-[var(--primary)] hover:underline mt-0.5"
                                >
                                  <GitPullRequest className="h-3.5 w-3.5" />
                                  View pull request
                                  <ExternalLink className="h-2.5 w-2.5" />
                                </a>
                              );
                            }
                            if (pl.delivery_status === "not_delivered") {
                              return (
                                <p className="text-[11px] leading-snug mt-0.5 inline-flex items-start gap-1.5 text-[var(--warning)]">
                                  <AlertTriangle className="h-3 w-3 mt-0.5 shrink-0" />
                                  <span>
                                    PR not opened
                                    {pl.delivery_reason ? ` — ${pl.delivery_reason}` : ""}
                                  </span>
                                </p>
                              );
                            }
                            return null;
                          })()}
                          {e.payload &&
                            Object.keys(e.payload).length > 0 &&
                            !(e.payload as { pr_url?: string }).pr_url &&
                            (e.payload as { delivery_status?: string }).delivery_status !== "not_delivered" && (
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

          <RunArtifactsPanel runId={runId} status={run.status} events={allEvents} />

          <RunSummaryPanel run={run} />
        </>
      )}
    </div>
  );
}
