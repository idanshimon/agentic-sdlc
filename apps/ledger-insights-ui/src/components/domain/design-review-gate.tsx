"use client";
/**
 * DesignReviewGate — operator approval surface for Gate 2 (Design Review).
 *
 * Phase 4.1 (2026-06-16): previously the second gate (design_review) just
 * showed the generic "awaiting_gate" status with no approval surface.
 * Run 66ce4cb5 was stuck there because the UI never offered an Approve
 * button. The orchestrator's /approve endpoint accepts a gate-level
 * approval ({gate: "design_review", decision_kind: "accept"}) and
 * auto-releases the gate via _release_gate(run_id), so this component
 * just needs to fire that one call.
 *
 * Architecture decisions intentionally simpler than ResolverGate:
 *   - No per-card iteration (design_review has no cards — it's a
 *     whole-stage approval of the architecture artifact)
 *   - No finalize step (orchestrator auto-releases for non-resolver gates)
 *   - Surfaces the architecture artifact inline so operator can scan
 *     it before approving (the artifact is on RunState; we read it
 *     from the run prop)
 */
import { useState } from "react";
import { CheckCircle2, AlertTriangle, Loader2, XCircle } from "lucide-react";
import { toast } from "sonner";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { orchestrator } from "@/lib/api/orchestrator";
import { architectureFromEvents } from "@/lib/artifacts";
import type { RunState } from "@/lib/types";

interface Props {
  runId: string;
  run: RunState;
  onApproved: () => void;
}

export function DesignReviewGate({ runId, run, onApproved }: Props) {
  const [submitting, setSubmitting] = useState(false);
  const [showArtifact, setShowArtifact] = useState(false);

  // Try to surface the architecture artifact so the operator has
  // something to review before approving. Multiple shapes the
  // orchestrator might land on; defensive read. Live runs don't populate
  // run.artifacts.architecture — fall back to the ARCHITECT event payload
  // (Fix A, architectureFromEvents), which is where the live pipeline
  // actually emits the drafted architecture.
  const architecture =
    // @ts-expect-error: artifacts.architecture is a runtime-extra field
    (run.artifacts?.architecture as string | undefined) ||
    // @ts-expect-error: same
    (run.architecture as string | undefined) ||
    architectureFromEvents(run.events);

  const handleApprove = async () => {
    setSubmitting(true);
    try {
      await orchestrator.approve(runId, {
        decision_kind: "accept",
        actor: "operator@dashboard",
        confidence_source: "human",
        gate: "design_review",
        resolution_text: "Architecture reviewed and approved.",
        card_id: `design-review-${runId}`,
      });
      toast.success("Design review approved", {
        description: "Pipeline advancing to Test Plan stage.",
      });
      onApproved();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to approve design review";
      toast.error("Design review approve failed", { description: msg });
    } finally {
      setSubmitting(false);
    }
  };

  const handleReject = async () => {
    setSubmitting(true);
    try {
      await orchestrator.approve(runId, {
        decision_kind: "reject",
        actor: "operator@dashboard",
        confidence_source: "human",
        gate: "design_review",
        resolution_text: "Architecture rejected — needs re-architect.",
        card_id: `design-review-${runId}`,
      });
      toast.success("Design review rejected", {
        description: "Pipeline will re-run architect with feedback.",
      });
      onApproved();
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to reject design review";
      toast.error("Design review reject failed", { description: msg });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card className="overflow-hidden border-[var(--info)]/40 bg-[var(--info)]/[0.04]">
      <div className="flex items-start gap-3 p-5 border-b border-[var(--info)]/30 bg-[var(--info)]/5">
        <AlertTriangle className="h-5 w-5 text-[var(--info)] mt-0.5 shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-sm font-semibold">Design Review — Gate 2</h3>
            <Badge variant="info" className="text-[10px]">GATE 2 OF 2</Badge>
          </div>
          <p className="text-xs text-[var(--text-secondary)] leading-relaxed mt-1">
            The Architect agent has drafted the system architecture from the
            approved resolver decisions. Review the architecture before the
            pipeline runs Test Plan → CodeGen → Review → Deliver. Approving
            commits the architecture to the ledger and advances downstream
            stages. Rejecting routes back to architect for a re-draft.
          </p>
        </div>
        <div className="shrink-0 flex items-center gap-2">
          <Button
            variant="ghost"
            size="default"
            onClick={handleReject}
            disabled={submitting}
            className="text-[var(--danger)] hover:bg-[var(--danger)]/10"
          >
            {submitting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <>
                <XCircle className="h-4 w-4" />
                Reject + re-architect
              </>
            )}
          </Button>
          <Button
            variant="primary"
            size="default"
            onClick={handleApprove}
            disabled={submitting}
          >
            {submitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" /> Approving…
              </>
            ) : (
              <>
                <CheckCircle2 className="h-4 w-4" />
                Approve architecture
              </>
            )}
          </Button>
        </div>
      </div>

      {architecture && (
        <div className="p-4 border-b border-[var(--border-muted)]">
          <button
            type="button"
            onClick={() => setShowArtifact((v) => !v)}
            className="text-xs text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"
          >
            {showArtifact ? "▼ Hide architecture preview" : "▶ Show architecture preview"}
            <span className="ml-2 mono">({architecture.length.toLocaleString()} chars)</span>
          </button>
          {showArtifact && (
            <pre className="mono text-[11px] leading-relaxed whitespace-pre-wrap break-words bg-[var(--bg)] border border-[var(--border-muted)] rounded p-3 max-h-[400px] overflow-auto mt-2">
              {architecture}
            </pre>
          )}
        </div>
      )}

      <div className="px-4 py-3 text-[11px] text-[var(--text-tertiary)] bg-[var(--surface-2)]/40">
        Tip: scroll down to the &ldquo;Run artifacts&rdquo; panel below to see the
        full architecture markdown with line numbers, syntax color, and
        download. The buttons above are the same approve/reject endpoint
        regardless of where you read the artifact.
      </div>
    </Card>
  );
}
