import type { RunState, StageEvent } from "@/lib/types";

export interface RunOutcome {
  kind: "failed" | "action_required";
  title: string;
  reason: string;
  stage?: string;
  action: string;
  evidence: string[];
}

function blockerEvidence(payload: Record<string, unknown>): string[] {
  if (!Array.isArray(payload.blockers)) return [];
  return payload.blockers.flatMap((raw) => {
    if (!raw || typeof raw !== "object") return [];
    const blocker = raw as Record<string, unknown>;
    const rule = typeof blocker.rule === "string" ? blocker.rule : "";
    const detail = typeof blocker.detail === "string" ? blocker.detail : "";
    const text = [rule, detail].filter(Boolean).join(": ");
    return text ? [text] : [];
  });
}

function latestEvent(events: StageEvent[], predicate: (event: StageEvent) => boolean): StageEvent | undefined {
  return [...events].reverse().find(predicate);
}

export function classifyRunOutcome(run: RunState): RunOutcome | null {
  const events = run.events ?? [];
  const undelivered = latestEvent(
    events,
    (event) => (event.payload as { delivery_status?: unknown } | undefined)?.delivery_status === "not_delivered",
  );
  if (undelivered) {
    const reason = (undelivered.payload as { delivery_reason?: unknown } | undefined)?.delivery_reason;
    return {
      kind: "action_required",
      title: "Delivery action required",
      stage: String(undelivered.stage),
      reason: typeof reason === "string" && reason ? `Pull request not opened: ${reason}` : "Pull request not opened.",
      action: "Configure delivery and retry",
      evidence: [],
    };
  }

  if (run.status !== "failed") return null;

  const failed = latestEvent(events, (event) => event.status === "failed");
  if (!failed) {
    return {
      kind: "failed",
      title: "Run failed",
      reason: "Failure details are unavailable.",
      action: "Inspect diagnostics and retry",
      evidence: [],
    };
  }

  const payload = failed.payload ?? {};
  const evidence = blockerEvidence(payload);
  const action = String(failed.stage) === "review_scan" || evidence.length > 0
    ? "Inspect blockers and remediate"
    : "Inspect diagnostics and retry";
  return {
    kind: "failed",
    title: "Run failed",
    stage: String(failed.stage),
    reason: failed.message || "The stage failed without a reason.",
    action,
    evidence,
  };
}
