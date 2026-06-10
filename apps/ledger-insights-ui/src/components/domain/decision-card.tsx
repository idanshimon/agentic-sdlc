import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { StagePill } from "./stage-pill";
import { relativeTime, shortId, fmtUsd } from "@/lib/utils";
import type { LedgerEntry } from "@/lib/types";
import { ShieldAlert, ShieldCheck, ShieldOff, User, Bot } from "lucide-react";

/**
 * DecisionCard — defensive renderer for ledger entries.
 *
 * Entries come from two sources with slightly different shapes:
 *   1. The decision-ledger-mcp Cosmos backend (canonical LedgerEntry schema)
 *   2. The demo fixtures in lib/demo/fixtures.ts (resolver-decision rows
 *      that get listed via listDemoLedgerEntries — historically a different
 *      shape, with `created_by` instead of `actor: {kind, id}`)
 *
 * Rendering a fixture row that doesn't match the canonical shape used to
 * crash the whole page on `entry.actor.kind` (2026-06-10 customer-blocking
 * — the crash chained from a Cosmos firewall regression that flooded the
 * UI with malformed retry fallbacks). Every field is now coerced behind a
 * normalizer so non-canonical inputs render as "unknown" cards instead
 * of taking down /decisions.
 */

type RawEntry = Partial<LedgerEntry> & {
  // Tolerated legacy field names from demo fixtures.
  created_by?: string;
  resolution_text?: string;
  ambiguity_class?: string;
};

function normalize(raw: RawEntry): LedgerEntry {
  const actor = raw.actor && typeof raw.actor === "object" && "kind" in raw.actor
    ? raw.actor
    : {
        kind: "agent" as const,
        id: raw.created_by ?? "unknown",
      };
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
    created_at: raw.created_at ?? new Date().toISOString(),
  };
}

export function DecisionCard({ entry: raw }: { entry: LedgerEntry }) {
  const entry = normalize(raw as RawEntry);
  const phiIcon =
    entry.phi_class === "high" ? ShieldAlert :
    entry.phi_class === "low" ? ShieldOff : ShieldCheck;
  const phiColor =
    entry.phi_class === "high" ? "var(--danger)" :
    entry.phi_class === "low" ? "var(--warning)" : "var(--success)";
  const PhiIcon = phiIcon;
  const ActorIcon = entry.actor.kind === "agent" ? Bot : User;

  return (
    <Card className="p-4 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1 min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge variant={entry.entry_type === "meta" ? "secondary" : "info"}>
              {entry.entry_type}
            </Badge>
            {entry.stage && <StagePill stage={entry.stage} status="completed" />}
            <span className="mono text-[11px] text-[var(--text-tertiary)]">
              {shortId(entry.id, 10)}
            </span>
          </div>
          <p className="text-sm text-[var(--text)] leading-snug">{entry.decision}</p>
        </div>
        <PhiIcon className="h-4 w-4 shrink-0 mt-0.5" style={{ color: phiColor }} aria-label={`PHI ${entry.phi_class}`} />
      </div>
      {entry.rationale && (
        <p className="text-xs text-[var(--text-secondary)] leading-relaxed line-clamp-3">
          {entry.rationale}
        </p>
      )}
      <div className="flex items-center justify-between flex-wrap gap-2 pt-2 border-t border-[var(--border-muted)] text-[11px] text-[var(--text-tertiary)]">
        <div className="flex items-center gap-2.5 flex-wrap">
          <span className="flex items-center gap-1">
            <ActorIcon className="h-3 w-3" />
            <span className="text-[var(--text-secondary)]">{entry.actor.id}</span>
          </span>
          {entry.bundle_refs.map((ref) => (
            <span key={ref} className="mono text-[10px] px-1.5 py-0.5 rounded bg-[var(--overlay)] text-[var(--secondary)]">
              {ref}
            </span>
          ))}
        </div>
        <span className="tabular">
          {fmtUsd(entry.cost_usd)} · {relativeTime(entry.created_at)}
        </span>
      </div>
    </Card>
  );
}
