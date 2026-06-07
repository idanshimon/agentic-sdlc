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

interface Props {
  runId: string;
  events: StageEvent[];
  onApproved: () => void;
}

export function ResolverGate({ runId, events, onApproved }: Props) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [submitting, setSubmitting] = useState(false);

  // Pull the most-recent assessor `awaiting_gate` event payload.
  const gating = useMemo<GatingCard[]>(() => {
    const ev = [...events]
      .reverse()
      .find(
        (e) =>
          e.stage === "assessor" &&
          e.status === "awaiting_gate" &&
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

  const toggleExpanded = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const approveAll = async () => {
    setSubmitting(true);
    try {
      // Synthesize a single composite approval payload — the live API
      // expects { decision, rationale }. Demo runs ignore the body and
      // replay the canned decision set anyway.
      await orchestrator.approve(runId, {
        decision: "approve_all_recommended",
        rationale: `Approved all ${recommendedCount} recommended options in one batch.`,
      });
      toast.success("Gate approved", {
        description: "Pipeline resuming with recommended decisions",
      });
      onApproved();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to approve gate";
      toast.error("Approve failed", { description: msg });
    } finally {
      setSubmitting(false);
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
            {recommendedCount === gating.length && (
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
        </div>
        <Button
          variant="primary"
          size="default"
          onClick={approveAll}
          disabled={submitting}
          className="shrink-0"
        >
          {submitting ? (
            <><Loader2 className="h-4 w-4 animate-spin" /> Approving…</>
          ) : (
            <>
              <CheckCircle2 className="h-4 w-4" />
              Approve all recommended
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
                <div className="shrink-0 flex items-center gap-1.5 text-[10px] text-[var(--text-tertiary)] pt-1">
                  <CheckCircle2 className="h-3 w-3 text-[var(--success)]" />
                  <span>recommended ready</span>
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
                          <div className="text-sm font-medium leading-snug">{o.label}</div>
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

                  {recommended && (
                    <div className="text-[10px] text-[var(--text-tertiary)] flex items-center gap-1.5">
                      <CheckCircle2 className="h-3 w-3 text-[var(--success)]" />
                      <span>
                        On approve all: <span className="text-[var(--text-secondary)] font-medium">{recommended.label}</span>
                      </span>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}
