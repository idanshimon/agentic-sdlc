"use client";
import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { orchestrator } from "@/lib/api/orchestrator";
import { ledgerMcp } from "@/lib/api/ledger-mcp";
import { isDemoMode, isDemoRun } from "@/lib/demo";

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: async () => {
      const [orch, ledger, tools] = await Promise.allSettled([
        orchestrator.health(),
        ledgerMcp.health(),
        ledgerMcp.tools(),
      ]);
      return {
        orchestrator:
          orch.status === "fulfilled" ? { ok: true, ...orch.value } : { ok: false as const, error: String(orch.reason) },
        ledger:
          ledger.status === "fulfilled" ? { ok: true, ...ledger.value } : { ok: false as const, error: String(ledger.reason) },
        tools:
          tools.status === "fulfilled" ? tools.value.tools : [],
      };
    },
    refetchInterval: 15_000,
  });
}

export function useRuns() {
  const queryClient = useQueryClient();

  // Same demo-store-updated subscription as useRun, but for the list view.
  // Makes the /runs page reflect new demo runs + status flips instantly.
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!isDemoMode()) return;
    const handler = () => {
      queryClient.invalidateQueries({ queryKey: ["runs"] });
    };
    window.addEventListener("demo-store-updated", handler);
    return () => window.removeEventListener("demo-store-updated", handler);
  }, [queryClient]);

  return useQuery({
    queryKey: ["runs"],
    queryFn: () => orchestrator.listRuns(),
    refetchInterval: 5_000,
  });
}

export function useRun(runId: string | undefined) {
  const queryClient = useQueryClient();

  // Demo runs are written to localStorage by the replay engine's setTimeout
  // cascade (lib/demo/index.ts). Pure polling at 3s loses ~3 seconds of
  // latency between a status flip (running → awaiting_gate) and the gate UI
  // appearing — long enough that customers think the dashboard is broken.
  // Subscribe to the same-tab `demo-store-updated` CustomEvent and force-
  // invalidate this query when the demo store changes. Cross-tab updates
  // still come through the native `storage` event (which TanStack's
  // refetchOnWindowFocus + 3s poll cover).
  //
  // Caught 2026-06-09 customer-blocking: localStorage status=awaiting_gate
  // for 12+ seconds, page badge still showed "running", Resolver Gate
  // panel never rendered, customer couldn't approve.
  useEffect(() => {
    if (!runId || typeof window === "undefined") return;
    if (!(isDemoMode() && isDemoRun(runId))) return;
    const handler = () => {
      queryClient.invalidateQueries({ queryKey: ["run", runId] });
    };
    window.addEventListener("demo-store-updated", handler);
    return () => window.removeEventListener("demo-store-updated", handler);
  }, [runId, queryClient]);

  return useQuery({
    queryKey: ["run", runId],
    queryFn: () => orchestrator.getRun(runId!),
    enabled: !!runId,
    // Poll every 3s while the run is active; stop once it reaches a terminal
    // state. Terminal-state polling is dead weight that compounds with the
    // demo replay engine's setTimeout cascade and the AssistantPanel's
    // useAssistantContext ctxKey changes — all three together can SIGKILL
    // the renderer on /runs/[runId] (see assist/context.tsx for the
    // primitive-deps fix).
    refetchInterval: (q) => {
      const status = q.state.data?.status;
      if (status === "completed" || status === "failed" || status === "cancelled") {
        return false;
      }
      return 3_000;
    },
  });
}

export function useTelemetryCost() {
  return useQuery({
    queryKey: ["telemetry", "cost"],
    queryFn: () => orchestrator.telemetryCost(),
    refetchInterval: 30_000,
  });
}

export function useTelemetryClasses() {
  return useQuery({
    queryKey: ["telemetry", "classes"],
    queryFn: () => orchestrator.telemetryClasses(),
    refetchInterval: 30_000,
  });
}

export function useDecisions(filter?: { team_id?: string; run_id?: string; limit?: number }) {
  return useQuery({
    queryKey: ["decisions", filter],
    queryFn: () => ledgerMcp.query({ limit: 50, ...filter }),
    refetchInterval: 10_000,
  });
}

// ── Autonomous review loop (add-autonomous-review-loop) ──────────────────────

const LOOP_KINDS = new Set(["review_remediation", "loop_converged", "loop_escalated"]);

/** Read the review-loop hop entries from the ledger (the 3 loop runtime_kinds)
 *  and group them by PR reference into a per-loop timeline. */
export function useReviewLoops(filter?: { team_id?: string; limit?: number }) {
  return useQuery({
    queryKey: ["review-loops", filter],
    queryFn: async () => {
      const res = await ledgerMcp.query({ limit: 200, ...filter });
      const hops = (res.entries ?? []).filter(
        (e) => e.runtime_kind && LOOP_KINDS.has(e.runtime_kind),
      );
      return { hops };
    },
    refetchInterval: 10_000,
  });
}

/** Per-repo autonomy tier posture (which repos are graduated to auto-merge). */
export function useRepoAutonomy() {
  return useQuery({
    queryKey: ["repo-autonomy"],
    queryFn: () => orchestrator.repoAutonomy(),
    refetchInterval: 30_000,
  });
}


export function usePromptLibrary() {
  return useQuery({
    queryKey: ["prompt-library"],
    queryFn: () => orchestrator.promptLibrary(),
    staleTime: 60_000,
  });
}
