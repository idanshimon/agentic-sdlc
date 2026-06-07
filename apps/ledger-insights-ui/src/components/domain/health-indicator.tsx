"use client";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { useHealth } from "@/lib/hooks/use-runs";
import { StatusDot } from "./status-dot";

export function HealthIndicator() {
  const { data, isLoading } = useHealth();
  const orchOk = data?.orchestrator.ok;
  const ledgerOk = data?.ledger.ok;
  const overall = !data
    ? "idle"
    : orchOk && ledgerOk
    ? "ok"
    : orchOk || ledgerOk
    ? "warning"
    : "error";
  const label = !data ? "Checking…" : overall === "ok" ? "All systems live" : overall === "warning" ? "Partial outage" : "Down";

  return (
    <TooltipProvider delayDuration={100}>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            className="flex items-center gap-1.5 h-7 px-2.5 rounded-md border border-[var(--border-default)] bg-[var(--surface)] text-[11px] text-[var(--text-secondary)] hover:bg-[var(--overlay)] transition-colors"
            aria-label={label}
          >
            <StatusDot status={overall} pulse={overall === "ok"} />
            <span>{isLoading ? "checking" : label}</span>
          </button>
        </TooltipTrigger>
        <TooltipContent align="end" className="text-[11px]">
          <div className="space-y-1 min-w-[180px]">
            <div className="flex items-center justify-between gap-3">
              <span className="text-[var(--text-tertiary)]">Orchestrator</span>
              <span className={orchOk ? "text-[var(--success)]" : "text-[var(--danger)]"}>
                {orchOk ? "200 OK" : data?.orchestrator.error ?? "—"}
              </span>
            </div>
            <div className="flex items-center justify-between gap-3">
              <span className="text-[var(--text-tertiary)]">Ledger MCP</span>
              <span className={ledgerOk ? "text-[var(--success)]" : "text-[var(--danger)]"}>
                {ledgerOk ? `v${(data?.ledger as { version?: string })?.version ?? ""}` : "down"}
              </span>
            </div>
            <div className="flex items-center justify-between gap-3 pt-1 border-t border-[var(--border-default)]">
              <span className="text-[var(--text-tertiary)]">MCP tools</span>
              <span className="text-[var(--text-secondary)] tabular">{data?.tools?.length ?? 0}</span>
            </div>
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
