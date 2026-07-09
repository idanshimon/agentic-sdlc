"use client";
import { useState, useMemo } from "react";
import { CheckCircle2, AlertTriangle, FileWarning, ChevronDown, ChevronRight, Loader2 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { orchestrator } from "@/lib/api/orchestrator";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import type { StageEvent } from "@/lib/types";

/* Resolver Gate panel — surfaces when run.status === "awaiting_gate".
 *
 * Reads the full ambiguity card details from the assessor's
 * `awaiting_gate` event payload (payload.gating[]). Each card shows
 * the prompt/title, surrounding PRD quote, and recommended option with
 * rationale + downstream impact. The user can approve all recommended
 * options in one click (the demo path) or open advanced override.
 *
 * Calls orchestrator.approve() which short-circuits via approveDemoRun()
 * for demo runs and hits POST /api/runs/{id}/approve for live runs. */

interface ResolverOption {
  label: string;
  resolution: string;
  rationale?: string;
  downstream_impact?: string;
  recommended?: boolean;
}

interface GatingCard {
  card_id?: string;
  ambiguity_class: string;
  title?: string;
  detail?: string;
  prompt?: string;
  prd_quote?: string;
  prd_section?: string;
  options: ResolverOption[];
  blast_radius_cost_usd?: number;
  is_hard_gated?: boolean;
}

const CLASS_LABELS: Record<string, string> = {
  "auth-policy": "Authorization Policy",
  "phi-classification": "PHI Classification",
  "data-retention": "Data Retention",
  "auth-token-policy": "Token Policy",
  "ingest-sla": "Ingest SLA",
  "observability-stack": "Observability Stack",
};

function classifyClass(c: string): "compliance" | "security" | "ops" | "default" {
  if (c.startsWith("phi-") || c.includes("retention")) return "compliance";
  if (c.includes("auth") || c.includes("token")) return "security";
  if (c.includes("sla") || c.includes("observability")) return "ops";
  return "default";
}

// Soft PHI guard for the free-text resolution box — warns (never blocks) if the
// operator's text looks like it contains raw PHI, since resolutions land in the
// audit ledger. SSN, MRN, and DOB-style patterns. Exported for unit tests.
export function phiSoftWarn(s?: string): boolean {
  if (!s) return false;
  return (
    /\b\d{3}-\d{2}-\d{4}\b/.test(s) || // SSN
    /\bMRN[:#]?\s*\d+/i.test(s) || // MRN
    /\b\d{2}\/\d{2}\/(19|20)\d{2}\b/.test(s) // DOB mm/dd/yyyy
  );
}

// Which cards a bulk "Approve all" should actually submit: gating cards that
// are NOT hard-gated and NOT already decided. Exported + pure for unit tests —
// this is the tier-2 governance filter that keeps PHI/auth out of bulk approve.
export function bulkApprovableCards<
  T extends { card_id?: string; is_hard_gated?: boolean },
>(gating: T[], decided: Record<string, unknown>): T[] {
  return gating.filter(
    (c) => c.card_id && !c.is_hard_gated && !decided[c.card_id],
  );
}

// Derive the gate's progress state + the ONE next action from the cards and
// what's been decided. Pure + exported so the primary-button label and the
// operator guidance line are unit-tested, not eyeballed. This is the fix for
// "it's not clear the button must be pressed to move on": the label is now
// state-driven and the phase names exactly what to do next.
export interface GateProgress {
  total: number;
  decidedCount: number;
  undecidedCount: number;
  undecidedHardGatedCount: number;
  allDecided: boolean;
  onlyHardGatedRemain: boolean;
  // Primary-button label + whether it should be disabled (locked cards remain).
  primaryLabel: string;
  primaryDisabled: boolean;
  // Which guidance line to show: 'all-decided' | 'hard-gated' | 'partial' | 'none'.
  phase: "all-decided" | "hard-gated" | "partial" | "none";
}

export function gateProgress<
  T extends { card_id?: string; is_hard_gated?: boolean },
>(gating: T[], decided: Record<string, unknown>): GateProgress {
  const total = gating.length;
  const undecided = gating.filter((c) => c.card_id && !decided[c.card_id]);
  const undecidedHardGated = undecided.filter((c) => c.is_hard_gated);
  const decidedCount = total - undecided.length;
  const allDecided = total > 0 && undecided.length === 0;
  const onlyHardGatedRemain =
    undecided.length > 0 && undecided.every((c) => c.is_hard_gated);

  const primaryLabel = allDecided
    ? "Finalize & advance"
    : onlyHardGatedRemain
      ? "Decide the locked card to continue"
      : "Approve all recommended";

  const phase: GateProgress["phase"] = allDecided
    ? "all-decided"
    : onlyHardGatedRemain
      ? "hard-gated"
      : decidedCount > 0
        ? "partial"
        : "none";

  return {
    total,
    decidedCount,
    undecidedCount: undecided.length,
    undecidedHardGatedCount: undecidedHardGated.length,
    allDecided,
    onlyHardGatedRemain,
    primaryLabel,
    primaryDisabled: onlyHardGatedRemain,
    phase,
  };
}

interface Props {
  runId: string;
  events: StageEvent[];
  onApproved: () => void;
}

export function ResolverGate({ runId, events, onApproved }: Props) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [submitting, setSubmitting] = useState(false);
  // Tier-2 + operator-agency: track per-card decided state so the page gives
  // real feedback (not just a transient toast). cardId -> chosen summary.
  const [decided, setDecided] = useState<
    Record<string, { label: string; custom: boolean }>
  >({});
  // Draft text for the "edit recommendation / write your own" textareas.
  const [draft, setDraft] = useState<Record<string, string>>({});

  // Pull the most-recent gate_open event payload. The orchestrator emits
  //   { stage: "resolver", status: "gate_open", payload: { gating: [...] } }
  // — NOT { stage: "assessor", status: "awaiting_gate" } as a previous
  // version of this code assumed. That mismatch caused the gating array
  // to read as [] and the warning card to claim "could not parse" while
  // the JSON sat right there in the event stream (caught 2026-06-16 on
  // run 66ce4cb5). We accept either shape defensively so a future
  // backend rename doesn't silently break the page again.
  const gating = useMemo<GatingCard[]>(() => {
    const ev = [...events]
      .reverse()
      .find(
        (e) =>
          ((e.stage === "resolver" && e.status === "gate_open") ||
            (e.stage === "assessor" && e.status === "awaiting_gate")) &&
          e.payload &&
          Array.isArray((e.payload as { gating?: unknown }).gating),
      );
    if (!ev) return [];
    const raw = (ev.payload as { gating: unknown[] }).gating;
    return raw as GatingCard[];
  }, [events]);

  const recommendedCount = gating.filter((c) =>
    c.options.some((o) => o.recommended),
  ).length;

  const totalBlastRadius = gating.reduce(
    (s, c) => s + (c.blast_radius_cost_usd ?? 0),
    0,
  );

  // How many gating cards still need a decision, and are any of the undecided
  // ones hard-gated? gateProgress() (pure, unit-tested) derives the primary
  // button label + the next-action guidance so the operator always knows the
  // ONE control that advances the pipeline (the reported confusion).
  const progress = useMemo(
    () => gateProgress(gating, decided),
    [gating, decided],
  );
  const {
    decidedCount,
    undecidedHardGatedCount,
    allDecided,
    onlyHardGatedRemain,
    primaryLabel,
  } = progress;

  const toggleExpanded = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  // Bulk soft-approve. Tier-2: SKIPS hard-gated cards (PHI/auth) — those must
  // be decided individually. Also skips already-decided cards. Sends
  // approval_path:"bulk" so the server can enforce the hard-gate rule even if
  // the UI filter is bypassed. Finalizes only when every gating card is decided.
  const approveAll = async () => {
    setSubmitting(true);
    let approved = 0;
    try {
      const toApprove = bulkApprovableCards(gating, decided);
      const nextDecided: Record<string, { label: string; custom: boolean }> = {};
      for (const c of toApprove) {
        const recIdx = c.options.findIndex((o) => o.recommended);
        const idx = recIdx >= 0 ? recIdx : 0;
        await orchestrator.approve(runId, {
          card_id: c.card_id!,
          decision_kind: "accept",
          option_index: idx,
          actor: "operator@dashboard",
          confidence_source: "human",
          approval_path: "bulk",
        });
        nextDecided[c.card_id!] = { label: c.options[idx]?.label ?? "Recommended", custom: false };
        approved += 1;
      }
      const merged = { ...decided, ...nextDecided };
      setDecided(merged);

      // How many gating cards still need an explicit individual decision?
      const remaining = gating.filter((c) => c.card_id && !merged[c.card_id]);
      if (remaining.length === 0) {
        await orchestrator.finalizeGate(runId);
        toast.success(`Approved ${approved} ${approved === 1 ? "card" : "cards"}`, {
          description: "Resolver gate closed — pipeline advancing to Architect.",
        });
        onApproved();
      } else {
        const hardCount = remaining.filter((c) => c.is_hard_gated).length;
        toast.warning(
          `${remaining.length} card${remaining.length === 1 ? "" : "s"} need your explicit decision`,
          {
            description:
              hardCount > 0
                ? `${hardCount} hard-gated (PHI/auth) card${hardCount === 1 ? "" : "s"} cannot be bulk-approved — decide each one individually below.`
                : "Decide the remaining cards individually, then finalize.",
          },
        );
        onApproved();
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to approve gate";
      toast.error(
        approved > 0 ? `Partial approve (${approved} of ${gating.length})` : "Approve failed",
        { description: msg },
      );
    } finally {
      setSubmitting(false);
    }
  };

  // Single-card approve from a per-option "Use this" button. Marks the card
  // decided IN-PAGE (the fix for "Use this gives a toast but nothing changes").
  const approveOne = async (card: GatingCard, optionIndex: number) => {
    if (!card.card_id) return;
    try {
      await orchestrator.approve(runId, {
        card_id: card.card_id,
        decision_kind: "accept",
        option_index: optionIndex,
        actor: "operator@dashboard",
        confidence_source: "human",
        approval_path: "individual",
      });
      setDecided((d) => ({
        ...d,
        [card.card_id!]: { label: card.options[optionIndex]?.label ?? "Selected", custom: false },
      }));
      toast.success(`Card decided: ${card.options[optionIndex]?.label ?? "option"}`, {
        description: "Decision pinned to ledger with full prompt chain.",
      });
      onApproved();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to approve card";
      toast.error("Approve card failed", { description: msg });
    }
  };

  // Operator writes their own / edits the recommended resolution. Sends a
  // swap with free-form text. Because the swap entry lands with the card's
  // slot_value_hash, findPrecedent quotes this operator's wording back on the
  // next run in the same ambiguity bucket — the teaching loop.
  const approveCustom = async (card: GatingCard, text: string) => {
    if (!card.card_id || !text.trim()) return;
    try {
      await orchestrator.approve(runId, {
        card_id: card.card_id,
        decision_kind: "swap",
        resolution_text: text.trim(),
        actor: "operator@dashboard",
        confidence_source: "human",
        approval_path: "individual",
      });
      setDecided((d) => ({
        ...d,
        [card.card_id!]: { label: "Your resolution", custom: true },
      }));
      toast.success("Custom resolution recorded", {
        description:
          "Pinned to the ledger as a human teaching signal — future runs in this class will quote it back.",
      });
      onApproved();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to record custom resolution";
      toast.error("Custom resolution failed", { description: msg });
    }
  };

  if (gating.length === 0) {
    return (
      <Card className="p-5 border-[var(--warning)]/40 bg-[var(--warning)]/5">
        <div className="flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-[var(--warning)] mt-0.5 shrink-0" />
          <div className="flex-1">
            <h3 className="text-sm font-semibold mb-1">Resolver gate open</h3>
            <p className="text-xs text-[var(--text-secondary)]">
              The pipeline is awaiting human decisions, but the gating card
              payload could not be parsed from the event stream.
            </p>
            <Button
              variant="primary"
              size="sm"
              className="mt-3"
              onClick={approveAll}
              disabled={submitting}
            >
              {submitting ? (
                <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Approving…</>
              ) : (
                <>Approve and continue</>
              )}
            </Button>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card className="overflow-hidden border-[var(--warning)]/40 bg-[var(--warning)]/[0.03]">
      <div className="flex items-start gap-3 p-5 border-b border-[var(--warning)]/30 bg-[var(--warning)]/5">
        <FileWarning className="h-5 w-5 text-[var(--warning)] mt-0.5 shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-sm font-semibold">Resolver gate — your decision</h3>
            <Badge variant="warning" className="text-[10px]">
              {gating.length} GATING
            </Badge>
            {Object.keys(decided).length > 0 && (
              <Badge variant="success" className="text-[10px]">
                {Object.keys(decided).length} OF {gating.length} DECIDED
              </Badge>
            )}
            {recommendedCount === gating.length && Object.keys(decided).length === 0 && (
              <Badge variant="success" className="text-[10px]">
                {recommendedCount} RECOMMENDED
              </Badge>
            )}
          </div>
          <p className="text-xs text-[var(--text-secondary)] leading-relaxed mt-1">
            The Assessor flagged {gating.length} ambiguities that the pipeline
            cannot safely resolve automatically. Each one has a recommended
            resolution backed by precedent and bundle rules. Approve all to
            continue, or expand a card to see options and override.
            {totalBlastRadius > 0 && (
              <>
                {" "}
                Estimated combined blast-radius cost of getting these wrong:{" "}
                <span className="text-[var(--warning)] font-medium">
                  ${totalBlastRadius.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </span>
                .
              </>
            )}
          </p>
          {/* State-aware next-action line so the operator is never left wondering
              which control advances the pipeline (the reported confusion). */}
          {allDecided ? (
            <p className="text-xs mt-2 flex items-center gap-1.5 font-medium text-[var(--success)]">
              <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
              All {gating.length} cards decided. Click{" "}
              <span className="font-semibold">“Finalize &amp; advance”</span> to close the gate and continue the pipeline.
            </p>
          ) : onlyHardGatedRemain ? (
            <p className="text-xs mt-2 flex items-center gap-1.5 font-medium text-[var(--danger)]">
              <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
              {undecidedHardGatedCount} locked card{undecidedHardGatedCount === 1 ? "" : "s"} (PHI/auth) still need your explicit decision below — they can’t be bulk-approved. Decide {undecidedHardGatedCount === 1 ? "it" : "them"}, then finalize.
            </p>
          ) : decidedCount > 0 ? (
            <p className="text-xs mt-2 flex items-center gap-1.5 text-[var(--text-secondary)]">
              <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-[var(--success)]" />
              {decidedCount} of {gating.length} decided. “Approve all recommended” will accept the rest and advance.
            </p>
          ) : null}
        </div>
        <Button
          variant="primary"
          size="default"
          onClick={approveAll}
          disabled={submitting || onlyHardGatedRemain}
          className={cn(
            "shrink-0",
            allDecided && "ring-2 ring-[var(--success)] ring-offset-1 ring-offset-[var(--bg)]",
          )}
          title={
            onlyHardGatedRemain
              ? "Decide the locked (PHI/auth) card individually below, then this becomes Finalize & advance."
              : allDecided
                ? "All cards decided — finalize the gate and advance the pipeline."
                : "Accept the recommended resolution for every non-locked card."
          }
        >
          {submitting ? (
            <><Loader2 className="h-4 w-4 animate-spin" /> {allDecided ? "Finalizing…" : "Approving…"}</>
          ) : (
            <>
              <CheckCircle2 className="h-4 w-4" />
              {primaryLabel}
            </>
          )}
        </Button>
      </div>

      <div className="divide-y divide-[var(--border-muted)]">
        {gating.map((c, i) => {
          const cardId = c.card_id ?? `card-${i}`;
          const isExpanded = expanded.has(cardId);
          const recommended = c.options.find((o) => o.recommended) ?? c.options[0];
          const tone = classifyClass(c.ambiguity_class);
          return (
            <div key={cardId} className="p-4">
              <button
                onClick={() => toggleExpanded(cardId)}
                className="w-full flex items-start gap-3 text-left hover:bg-[var(--overlay)]/40 -m-1 p-1 rounded transition-colors"
              >
                <div className="pt-0.5">
                  {isExpanded ? (
                    <ChevronDown className="h-4 w-4 text-[var(--text-tertiary)]" />
                  ) : (
                    <ChevronRight className="h-4 w-4 text-[var(--text-tertiary)]" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <span className="text-[10px] mono text-[var(--text-tertiary)]">
                      Card {i + 1} of {gating.length}
                    </span>
                    <Badge
                      variant={
                        tone === "compliance"
                          ? "danger"
                          : tone === "security"
                            ? "warning"
                            : tone === "ops"
                              ? "info"
                              : "secondary"
                      }
                      className="text-[10px]"
                    >
                      {CLASS_LABELS[c.ambiguity_class] ?? c.ambiguity_class}
                    </Badge>
                    {c.is_hard_gated && (
                      <Badge variant="danger" className="text-[10px]">
                        🔒 EXPLICIT DECISION REQUIRED
                      </Badge>
                    )}
                    {c.blast_radius_cost_usd !== undefined && c.blast_radius_cost_usd > 0 && (
                      <span className="text-[10px] text-[var(--text-tertiary)] tabular">
                        blast-radius ${c.blast_radius_cost_usd.toFixed(0)}
                      </span>
                    )}
                  </div>
                  <h4 className="text-sm font-medium leading-snug">
                    {c.title ?? c.prompt ?? "Untitled ambiguity"}
                  </h4>
                  {!isExpanded && c.detail && (
                    <p className="text-xs text-[var(--text-secondary)] mt-1 line-clamp-2 leading-relaxed">
                      {c.detail}
                    </p>
                  )}
                </div>
                <div className="shrink-0 flex items-center gap-1.5 text-[10px] pt-1">
                  {decided[cardId] ? (
                    <>
                      <CheckCircle2 className="h-3 w-3 text-[var(--success)]" />
                      <span className="text-[var(--success)]">
                        {decided[cardId].custom ? "your resolution" : "decided"}
                      </span>
                    </>
                  ) : c.is_hard_gated ? (
                    <span className="text-[var(--danger)]">needs your decision</span>
                  ) : (
                    <>
                      <CheckCircle2 className="h-3 w-3 text-[var(--success)]" />
                      <span className="text-[var(--text-tertiary)]">recommended ready</span>
                    </>
                  )}
                </div>
              </button>

              {isExpanded && (
                <div className="mt-3 ml-7 space-y-3">
                  {c.detail && (
                    <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                      {c.detail}
                    </p>
                  )}
                  {c.prd_quote && (
                    <blockquote className="text-xs italic text-[var(--text-tertiary)] border-l-2 border-[var(--border-default)] pl-3 py-0.5">
                      <span className="text-[10px] uppercase tracking-wider mr-1.5 not-italic font-medium">
                        PRD ({c.prd_section ?? "quote"}):
                      </span>
                      &ldquo;{c.prd_quote}&rdquo;
                    </blockquote>
                  )}

                  <div className="space-y-2">
                    <div className="text-[10px] uppercase tracking-wider font-medium text-[var(--text-tertiary)]">
                      Resolution options
                    </div>
                    {c.options.map((o, oi) => (
                      <div
                        key={oi}
                        className={cn(
                          "rounded-md border p-3 space-y-1.5",
                          o.recommended
                            ? "border-[var(--success)]/40 bg-[var(--success)]/5"
                            : "border-[var(--border-default)] bg-[var(--bg)]",
                        )}
                      >
                        <div className="flex items-start gap-2">
                          {o.recommended && (
                            <Badge variant="success" className="text-[10px] shrink-0">
                              RECOMMENDED
                            </Badge>
                          )}
                          <div className="text-sm font-medium leading-snug flex-1">{o.label}</div>
                          {/* Phase 3.2: per-card "use this option" button.
                              Sends a single GateDecision for this card+option
                              and stays on the page so operator can decide the
                              remaining cards individually. */}
                          <Button
                            size="sm"
                            variant={o.recommended ? "primary" : "secondary"}
                            onClick={(ev) => {
                              ev.stopPropagation();
                              void approveOne(c, oi);
                            }}
                            disabled={submitting}
                            className="shrink-0 text-[11px] h-6 px-2"
                          >
                            Use this
                          </Button>
                        </div>
                        <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                          {o.resolution}
                        </p>
                        {o.rationale && (
                          <div className="text-[11px] text-[var(--text-tertiary)] leading-relaxed">
                            <span className="font-medium text-[var(--text-secondary)]">
                              Why:
                            </span>{" "}
                            {o.rationale}
                          </div>
                        )}
                        {o.downstream_impact && (
                          <div className="text-[11px] text-[var(--text-tertiary)] leading-relaxed">
                            <span className="font-medium text-[var(--text-secondary)]">
                              Downstream:
                            </span>{" "}
                            {o.downstream_impact}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>

                  {/* Edit the recommendation, or write your own. Sends a swap
                      with free-form text → becomes a precedent (teaching loop). */}
                  <div className="space-y-1.5 rounded-md border border-[var(--border-default)] bg-[var(--bg)] p-3">
                    <div className="text-[10px] uppercase tracking-wider font-medium text-[var(--text-tertiary)]">
                      Edit the recommendation, or write your own
                    </div>
                    <textarea
                      value={draft[cardId] ?? recommended?.resolution ?? ""}
                      onChange={(e) =>
                        setDraft((d) => ({ ...d, [cardId]: e.target.value }))
                      }
                      onClick={(e) => e.stopPropagation()}
                      placeholder="Edit the recommended resolution above, or type your own policy-level resolution…"
                      className="w-full text-xs rounded-md border border-[var(--border-default)] bg-[var(--surface)] p-2 min-h-[72px] leading-relaxed"
                    />
                    {phiSoftWarn(draft[cardId]) && (
                      <p className="text-[11px] text-[var(--warning)] flex items-start gap-1">
                        <AlertTriangle className="h-3 w-3 mt-0.5 shrink-0" />
                        <span>
                          Looks like it may contain PHI. Resolutions are stored in
                          the audit ledger — keep this policy-level, not patient-level.
                        </span>
                      </p>
                    )}
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={(ev) => {
                        ev.stopPropagation();
                        void approveCustom(c, draft[cardId] ?? recommended?.resolution ?? "");
                      }}
                      disabled={submitting}
                      className="text-[11px] h-6 px-2"
                    >
                      Use my version
                    </Button>
                  </div>

                  {decided[cardId] ? (
                    <div className="text-[10px] text-[var(--success)] flex items-center gap-1.5">
                      <CheckCircle2 className="h-3 w-3" />
                      <span>
                        Decided:{" "}
                        <span className="font-medium">{decided[cardId].label}</span>
                        {" — "}
                        <button
                          className="underline hover:text-[var(--text-secondary)]"
                          onClick={(ev) => {
                            ev.stopPropagation();
                            setDecided((d) => {
                              const next = { ...d };
                              delete next[cardId];
                              return next;
                            });
                          }}
                        >
                          change
                        </button>
                      </span>
                    </div>
                  ) : recommended && !c.is_hard_gated ? (
                    <div className="text-[10px] text-[var(--text-tertiary)] flex items-center gap-1.5">
                      <CheckCircle2 className="h-3 w-3 text-[var(--success)]" />
                      <span>
                        On approve all: <span className="text-[var(--text-secondary)] font-medium">{recommended.label}</span>
                      </span>
                    </div>
                  ) : c.is_hard_gated ? (
                    <div className="text-[10px] text-[var(--danger)] flex items-center gap-1.5">
                      <span>🔒 Hard-gated — excluded from bulk approve. Decide this one explicitly above.</span>
                    </div>
                  ) : null}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}
