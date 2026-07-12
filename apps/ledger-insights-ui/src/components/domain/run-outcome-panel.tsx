"use client";

import { AlertTriangle, ExternalLink, RotateCcw, ShieldAlert } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import type { RunOutcome } from "@/lib/run-outcome";

export function RunOutcomePanel({
  outcome,
  onRetry,
  retrying = false,
}: {
  outcome: RunOutcome;
  onRetry?: () => void;
  retrying?: boolean;
}) {
  const failed = outcome.kind === "failed";
  const Icon = failed ? ShieldAlert : AlertTriangle;
  const color = failed ? "var(--danger)" : "var(--warning)";
  return (
    <Card className="overflow-hidden" style={{ borderColor: `color-mix(in srgb, ${color} 45%, transparent)` }}>
      <div className="flex items-start gap-3 p-4" style={{ background: `color-mix(in srgb, ${color} 8%, transparent)` }}>
        <Icon className="h-5 w-5 shrink-0 mt-0.5" style={{ color }} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h2 className="text-sm font-semibold">{outcome.title}</h2>
            {outcome.stage && (
              <span className="mono text-[10px] px-1.5 py-0.5 rounded bg-[var(--overlay)] text-[var(--text-secondary)]">
                {outcome.stage.replace(/_/g, " ")}
              </span>
            )}
          </div>
          <p className="text-xs text-[var(--text-secondary)] mt-1">{outcome.reason}</p>
          {outcome.evidence.length > 0 && (
            <ul className="mt-2 space-y-1">
              {outcome.evidence.map((item) => (
                <li key={item} className="mono text-[11px] text-[var(--text-secondary)]">{item}</li>
              ))}
            </ul>
          )}
        </div>
        {onRetry ? (
          <Button variant={failed ? "danger" : "primary"} size="sm" onClick={onRetry} disabled={retrying}>
            {failed ? <ShieldAlert className="h-3.5 w-3.5" /> : <RotateCcw className="h-3.5 w-3.5" />}
            {retrying ? "Starting retry…" : outcome.action}
          </Button>
        ) : (
          <Button variant="ghost" size="sm" asChild><a href="#event-stream">Inspect evidence <ExternalLink className="h-3 w-3" /></a></Button>
        )}
      </div>
    </Card>
  );
}
