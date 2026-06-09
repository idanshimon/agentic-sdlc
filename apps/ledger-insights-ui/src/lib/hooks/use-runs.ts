"use client";
import { useQuery } from "@tanstack/react-query";
import { orchestrator } from "@/lib/api/orchestrator";
import { ledgerMcp } from "@/lib/api/ledger-mcp";

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
  return useQuery({
    queryKey: ["runs"],
    queryFn: () => orchestrator.listRuns(),
    refetchInterval: 5_000,
  });
}

export function useRun(runId: string | undefined) {
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

export function usePromptLibrary() {
  return useQuery({
    queryKey: ["prompt-library"],
    queryFn: () => orchestrator.promptLibrary(),
    staleTime: 60_000,
  });
}
