"use client";
import { Workflow, GitMerge, AlertTriangle, MessageSquare, ShieldCheck } from "lucide-react";
import { useMemo } from "react";
import { useReviewLoops, useRepoAutonomy } from "@/lib/hooks/use-runs";
import { EmptyState } from "@/components/domain/empty-state";
import { PageHeader } from "@/components/layout/page-header";
import { cn } from "@/lib/utils";
import { projectReviewLoops, type ReviewLoopProjection as Loop } from "@/lib/review-loop";
import { deriveAssurance } from "@/lib/assurance";
import { AssurancePanel } from "@/components/domain/assurance-panel";
import type { LedgerEntry, RepoTier } from "@/lib/types";

/** Parse a reviewloop/<tier>/<repo>/<action>@attempt=N[:reason] citation. */
function parseRef(ref?: string): {
  tier?: string; repo?: string; action?: string; attempt?: number; reason?: string;
} {
  if (!ref || !ref.startsWith("reviewloop/")) return {};
  const [head, reason] = ref.split(":");
  const m = head.match(/^reviewloop\/([^/]+)\/(.+)\/([^/@]+)@attempt=(\d+)$/);
  if (!m) return { reason };
  return { tier: m[1], repo: m[2], action: m[3], attempt: Number(m[4]), reason };
}

const TIER_TONE: Record<RepoTier, string> = {
  A: "var(--danger)",       // most autonomous = highest scrutiny color
  B: "var(--warning)",
  C: "var(--text-secondary)",
};

function TerminalChip({ state }: { state: Loop["terminal"] }) {
  const map = {
    merged: { label: "MERGED", icon: GitMerge, color: "var(--success)" },
    passed_awaiting_merge: { label: "PASSED · AWAITING MERGE", icon: ShieldCheck, color: "var(--warning)" },
    escalated: { label: "ESCALATED", icon: AlertTriangle, color: "var(--danger)" },
    advisory: { label: "ADVISORY", icon: MessageSquare, color: "var(--text-secondary)" },
    failed: { label: "FAILED", icon: AlertTriangle, color: "var(--danger)" },
    in_progress: { label: "IN PROGRESS", icon: Workflow, color: "var(--info)" },
  }[state];
  const Icon = map.icon;
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium"
      style={{ color: map.color, background: `color-mix(in srgb, ${map.color} 12%, transparent)` }}>
      <Icon size={12} /> {map.label}
    </span>
  );
}

/** Horizontal attempt-timeline stepper: review → remediate → review … → terminal. */
function Timeline({ hops }: { hops: LedgerEntry[] }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {hops.map((h, i) => {
        const { action, attempt, reason } = parseRef(h.autonomy_ref);
        const label =
          h.runtime_kind === "review_remediation" ? `remediate #${attempt ?? i + 1}`
          : h.runtime_kind === "loop_converged" ? "converged"
          : `escalate${reason ? ` (${reason})` : ""}`;
        const isPhi = reason === "tier_floor_phi";
        return (
          <span key={h.id ?? i} className="inline-flex items-center gap-1.5">
            {i > 0 && <span style={{ color: "var(--border)" }}>→</span>}
            <span
              className="rounded px-2 py-0.5 text-xs"
              title={h.detail || h.autonomy_ref || ""}
              style={{
                background: "var(--surface)",
                color: isPhi ? "var(--danger)" : "var(--text)",
                border: `1px solid ${isPhi ? "var(--danger)" : "var(--border)"}`,
              }}
            >
              {label}
            </span>
          </span>
        );
      })}
    </div>
  );
}

export default function ReviewLoopPage() {
  const { data: loopData, isLoading } = useReviewLoops();
  const { data: posture } = useRepoAutonomy();

  const loops = useMemo(() => projectReviewLoops(loopData?.hops ?? []), [loopData]);
  const escalations = loops.filter((l) => l.terminal === "escalated" || l.terminal === "failed");

  return (
    <div className="space-y-5">
      <PageHeader
        plane="agenthq"
        title="Autonomous Review Loop"
        description="Watch the dark factory run without being in the merge path. Each loop is a Coding Agent's PR reviewed by the deterministic verdict, remediated within bounds, then auto-merged (Tier A), sent for a human merge (Tier B), or escalated. PHI/auth/deny always escalate — model variance is contained, never solved."
      />

      {/* Per-repo autonomy tiers — the "move the dial" control */}
      <section className="rounded-xl border p-4" style={{ borderColor: "var(--border)" }}>
        <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold">
          <ShieldCheck size={16} style={{ color: "var(--accent)" }} /> Per-repo autonomy tiers
        </h2>
        {posture?.bootstrap !== false ? (
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            No repo graduated — every repository is <strong>Tier C (advisory)</strong> by default.{" "}
            Deploying the image changes no repo&apos;s behavior until a human graduates one in{" "}
            <code className="rounded px-1" style={{ background: "var(--surface)" }}>repo_autonomy.yaml</code>.
          </p>
        ) : (
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {posture.repos.map((r) => (
              <div key={r.repo} className="rounded-lg border p-3" style={{ borderColor: "var(--border)" }}>
                <div className="flex items-center justify-between">
                  <span className="font-mono text-sm">{r.repo}</span>
                  <span className="rounded px-2 py-0.5 text-xs font-bold"
                    style={{ color: TIER_TONE[r.tier], border: `1px solid ${TIER_TONE[r.tier]}` }}>
                    Tier {r.tier}
                  </span>
                </div>
                {r.why_capped && (
                  <p className="mt-1.5 text-xs" style={{ color: "var(--text-secondary)" }}>{r.why_capped}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Escalation inbox — the human enters only at the chosen boundary */}
      {escalations.length > 0 && (
        <section className="rounded-xl border p-4" style={{ borderColor: "var(--danger)" }}>
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold" style={{ color: "var(--danger)" }}>
            <AlertTriangle size={16} /> Escalation inbox ({escalations.length})
          </h2>
          <div className="space-y-2">
            {escalations.map((l) => {
              const last = l.hops[l.hops.length - 1];
              const { reason } = parseRef(last?.autonomy_ref);
              return (
                <div key={l.loopId} className="flex items-center justify-between rounded-lg border p-3"
                  style={{ borderColor: "var(--border)" }}>
                  <div>
                    <span className="font-mono text-sm">{l.repo}</span>
                    <span className="ml-2 text-xs" style={{ color: "var(--text-secondary)" }}>
                      {l.attempts} attempt(s) · reason: {reason ?? "unknown"}
                    </span>
                  </div>
                  <TerminalChip state="escalated" />
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* Live loop timelines */}
      {isLoading ? (
        <div className="space-y-3">{[1, 2, 3].map((i) => <div key={i} className="skeleton h-16 rounded-lg" />)}</div>
      ) : loops.length === 0 ? (
        <EmptyState
          icon={Workflow}
          title="No review loops yet"
          description="When a Coding Agent opens a PR on a repo the loop is configured for, its review → remediate → re-review hops land in the ledger and stream here. Each hop links to its ledger entry and the real GitHub PR."
        />
      ) : (
        <div className="overflow-hidden rounded-xl border" style={{ borderColor: "var(--border)" }}>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: "var(--surface)" }}>
                <th className="px-4 py-2 text-left font-medium">Repo</th>
                <th className="px-4 py-2 text-left font-medium">Tier</th>
                <th className="px-4 py-2 text-left font-medium">Attempt timeline</th>
                <th className="px-4 py-2 text-left font-medium">Outcome</th>
              </tr>
            </thead>
            <tbody>
              {loops.map((l) => (
                <tr key={l.loopId} className="border-t" style={{ borderColor: "var(--border)" }}>
                  <td className="px-4 py-3 font-mono text-xs">
                    <div>{l.repo}</div>
                    <div className="mt-1 text-[10px] text-[var(--text-secondary)]">PR #{l.prNumber ?? "?"} · {(l.headSha ?? "unknown").slice(0, 12)}</div>
                    <div className="mt-1 flex gap-2">
                      {l.hops.at(-1)?.check_url && <a className="text-[var(--info)]" href={l.hops.at(-1)?.check_url} target="_blank" rel="noreferrer">check</a>}
                      {l.hops.at(-1)?.comment_url && <a className="text-[var(--info)]" href={l.hops.at(-1)?.comment_url} target="_blank" rel="noreferrer">comment</a>}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    {l.tier && (
                      <span className="rounded px-2 py-0.5 text-xs font-bold"
                        style={{ color: TIER_TONE[(l.tier as RepoTier)] ?? "var(--text-secondary)" }}>
                        {l.tier}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3"><Timeline hops={l.hops} /></td>
                  <td className="px-4 py-3">
                    <div className="space-y-2">
                      <TerminalChip state={l.terminal} />
                      <AssurancePanel assurance={deriveAssurance((l.hops.at(-1) as unknown as Record<string, unknown>) ?? {})} />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
