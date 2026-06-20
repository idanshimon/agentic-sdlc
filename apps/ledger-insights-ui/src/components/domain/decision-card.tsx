import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { StagePill } from "./stage-pill";
import { TeachingSignalBar } from "./teaching-signal-bar";
import { PromptChainBadge } from "./prompt-chain-badge";
import { relativeTime, shortId, fmtUsd } from "@/lib/utils";
import type { LedgerEntry } from "@/lib/types";
import { ShieldAlert, ShieldCheck, ShieldOff, User, Bot, ThumbsUp, ThumbsDown, Flag, RotateCcw, PauseCircle } from "lucide-react";

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
    runtime_kind: raw.runtime_kind,
    references_entry_id: raw.references_entry_id,
    feedback_kind: raw.feedback_kind,
    paused_class: raw.paused_class,
    ambiguity_class: raw.ambiguity_class,
    prompt_resolution_path: Array.isArray(raw.prompt_resolution_path)
      ? raw.prompt_resolution_path
      : null,
    created_at: raw.created_at ?? new Date().toISOString(),
  };
}

/**
 * For teaching-signal entries, the card uses a slightly different visual
 * treatment so operators can scan the ledger and see flags/pauses/replays
 * without reading every word.
 */
function teachingSignalIcon(kind: LedgerEntry["runtime_kind"]) {
  switch (kind) {
    case "feedback_thumbs":
      return null; // Use feedback_kind below for the actual icon
    case "decision_flagged":
      return Flag;
    case "replay_requested":
      return RotateCcw;
    case "class_paused":
      return PauseCircle;
    default:
      return null;
  }
}

/**
 * Human-readable summary for a teaching-signal entry. The raw ledger stores
 * these as runtime_kind + references_entry_id, which renders as
 * "thumbs_up on <uuid>" — meaningless to a human. This turns each kind into a
 * plain-English sentence an operator can scan.
 */
function teachingSignalSummary(entry: LedgerEntry): {
  title: string;
  detail: string | null;
} | null {
  const who = entry.actor?.id && entry.actor.id !== "unknown" ? entry.actor.id : "An operator";
  switch (entry.runtime_kind) {
    case "feedback_thumbs":
      return entry.feedback_kind === "thumbs_down"
        ? { title: "Marked “not helpful”", detail: `${who} gave this decision a thumbs-down.` }
        : { title: "Marked “helpful”", detail: `${who} gave this decision a thumbs-up.` };
    case "decision_flagged":
      return {
        title: "Flagged as wrong",
        detail:
          entry.rationale?.trim()
            ? `${who} flagged this — it won’t be reused as precedent. Reason: ${entry.rationale.trim()}`
            : `${who} flagged this decision — it won’t be reused as precedent.`,
      };
    case "replay_requested":
      return {
        title: "Replay requested",
        detail: `${who} asked to re-run this against the current rules.`,
      };
    case "class_paused":
      return {
        title: `Autopilot paused${entry.paused_class ? ` for “${entry.paused_class}”` : ""}`,
        detail:
          entry.rationale?.trim()
            ? `${who} paused auto-resolution for this class. Reason: ${entry.rationale.trim()}`
            : `${who} paused auto-resolution for this whole class.`,
      };
    default:
      return null;
  }
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

  // Track B: render teaching-signal entries with a kind-specific badge so
  // they're visually distinct from stage_decision entries.
  const tsIcon = teachingSignalIcon(entry.runtime_kind);
  const isThumbsDown =
    entry.runtime_kind === "feedback_thumbs" && entry.feedback_kind === "thumbs_down";
  const isThumbsUp =
    entry.runtime_kind === "feedback_thumbs" && entry.feedback_kind === "thumbs_up";
  const ThumbsIcon = isThumbsUp ? ThumbsUp : isThumbsDown ? ThumbsDown : null;

  // Plain-English summary so teaching-signal rows don't read as
  // "thumbs_up on <uuid>". Null for ordinary stage_decision entries.
  const tsSummary = teachingSignalSummary(entry);

  return (
    <Card className="p-4 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1 min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge variant={entry.entry_type === "meta" ? "secondary" : "info"}>
              {entry.entry_type}
            </Badge>
            {entry.runtime_kind && entry.runtime_kind !== "stage_decision" && (
              <Badge variant="secondary">
                {entry.runtime_kind.replace(/_/g, " ")}
              </Badge>
            )}
            {tsIcon && (() => {
              const Icon = tsIcon;
              return <Icon className="h-3.5 w-3.5 text-[var(--text-tertiary)]" />;
            })()}
            {ThumbsIcon && (
              <ThumbsIcon
                className="h-3.5 w-3.5"
                style={{ color: isThumbsUp ? "var(--success)" : "var(--danger)" }}
              />
            )}
            {entry.stage && <StagePill stage={entry.stage} status="completed" />}
          </div>
          {tsSummary ? (
            <>
              <p className="text-sm font-medium text-[var(--text)] leading-snug">
                {tsSummary.title}
              </p>
              {tsSummary.detail && (
                <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                  {tsSummary.detail}
                </p>
              )}
            </>
          ) : (
            <p className="text-sm text-[var(--text)] leading-snug">{entry.decision}</p>
          )}
        </div>
        <PhiIcon className="h-4 w-4 shrink-0 mt-0.5" style={{ color: phiColor }} aria-label={`PHI ${entry.phi_class}`} />
      </div>
      {entry.rationale && !tsSummary && (
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
        <span className="tabular flex items-center gap-2">
          <span className="mono text-[10px] text-[var(--text-tertiary)]/70" title={`Ledger entry ${entry.id}`}>
            {shortId(entry.id, 8)}
          </span>
          <span>{fmtUsd(entry.cost_usd)} · {relativeTime(entry.created_at)}</span>
        </span>
      </div>
      {/* Phase 5: prompt-chain attribution. Closes the audit loop by
          showing operators exactly which YAML prompt produced this
          decision. Click-through to /prompts opens the catalog for
          drilldown + Edit + open PR. */}
      <div className="px-4 pb-2 -mt-1">
        <PromptChainBadge chain={entry.prompt_resolution_path} variant="card" />
      </div>
      <TeachingSignalBar entry={entry} />
    </Card>
  );
}
