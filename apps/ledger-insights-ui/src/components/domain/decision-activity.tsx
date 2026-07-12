"use client";

import { Bot, User, GraduationCap, Flag, PauseCircle, CheckCircle2, GitPullRequest, ChevronRight } from "lucide-react";
import type { LedgerEntry } from "@/lib/types";
import { relativeTime } from "@/lib/utils";

/**
 * DecisionActivity — a plain-language "what just happened" feed for dev leaders.
 *
 * Replaces the old GUID+chips lifecycle grid, which showed internal state
 * machine plumbing nobody could read. This answers the questions a leader
 * actually asks scanning the ledger:
 *   - What did the AI (or a person) decide?
 *   - Who made the call — agent on autopilot, or a human?
 *   - Did anyone teach the system something (flag / thumbs / pause)?
 *   - What did it learn / reuse?
 * Each row is clickable and scrolls to + highlights the full entry in the
 * table below (via a `?focus=<id>` hash the table reads).
 */

export type Kind = "human_decision" | "agent_decision" | "taught" | "flagged" | "paused" | "reused" | "delivered" | "converged";

export function classify(e: LedgerEntry): Kind {
  const rk = e.runtime_kind;
  if (rk === "feedback_thumbs") return "taught";
  if (rk === "decision_flagged") return "flagged";
  if (rk === "class_paused") return "paused";
  if (rk === "delivered") return "delivered";
  if (rk === "loop_converged") return "converged";
  if (e.confidence_source === "autopilot") return "reused";
  if (e.actor?.kind === "human") return "human_decision";
  return "agent_decision";
}

const META: Record<Kind, { icon: typeof Bot; tone: string; verb: string }> = {
  human_decision: { icon: User, tone: "var(--primary)", verb: "A person decided" },
  agent_decision: { icon: Bot, tone: "var(--secondary)", verb: "The agent decided" },
  reused: { icon: GraduationCap, tone: "var(--success)", verb: "Autopilot reused a learned decision" },
  taught: { icon: GraduationCap, tone: "var(--success)", verb: "A person taught the system" },
  flagged: { icon: Flag, tone: "var(--warning)", verb: "A person flagged a decision as wrong" },
  paused: { icon: PauseCircle, tone: "var(--warning)", verb: "A person paused autopilot" },
  delivered: { icon: GitPullRequest, tone: "var(--primary)", verb: "The pipeline delivered code" },
  converged: { icon: CheckCircle2, tone: "var(--success)", verb: "Review loop converged" },
};

export function sentence(e: LedgerEntry, kind: Kind): string {
  const who = e.actor?.id && e.actor.id !== "unknown" ? e.actor.id : (kind.includes("agent") || kind === "reused" ? "the agent" : "an operator");
  const what = e.decision?.trim() || e.ambiguity_class || "a pipeline decision";
  const stage = e.stage ? ` at the ${e.stage} stage` : "";
  switch (kind) {
    case "human_decision": return `${who} resolved “${what}”${stage}.`;
    case "agent_decision": return `The agent resolved “${what}”${stage} on its own.`;
    case "reused": return `Autopilot auto-resolved “${what}” by reusing a decision a human made earlier${stage}.`;
    case "taught": return `${who} gave feedback on “${what}” — the system will weight this next time.`;
    case "flagged": return `${who} flagged “${what}” as wrong — it won’t be reused as precedent.`;
    case "paused": return `${who} paused autopilot${e.paused_class ? ` for the “${e.paused_class}” class` : ""} — these now require a human.`;
    case "delivered": return `The pipeline opened a pull request for “${what}”.`;
    case "converged": return `The automated review loop passed for “${what}”.`;
  }
}

export function DecisionActivity({ entries }: { entries: LedgerEntry[] }) {
  const rows = [...entries]
    .sort((a, b) => (b.created_at ?? "").localeCompare(a.created_at ?? ""))
    .slice(0, 12)
    .map((e) => ({ e, kind: classify(e) }));

  if (rows.length === 0) return null;

  const learned = rows.filter((r) => r.kind === "taught" || r.kind === "reused" || r.kind === "flagged" || r.kind === "paused").length;

  return (
    <section className="rounded-lg border border-[var(--border-default)] bg-[var(--surface)]">
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border-default)]">
        <div>
          <h2 className="text-sm font-semibold">What’s been happening</h2>
          <p className="text-xs text-[var(--text-tertiary)]">
            Plain-language feed of the latest agent + human decisions. Click any row to jump to its full record below.
          </p>
        </div>
        {learned > 0 && (
          <span className="text-[11px] px-2 py-1 rounded-md bg-[var(--success)]/15 text-[var(--success)]">
            {learned} learning event{learned === 1 ? "" : "s"}
          </span>
        )}
      </div>
      <ul className="divide-y divide-[var(--border-muted)]">
        {rows.map(({ e, kind }) => {
          const { icon: Icon, tone } = META[kind];
          return (
            <li key={e.id}>
              <a
                href={`#decision-${e.id}`}
                className="flex items-start gap-3 px-4 py-2.5 hover:bg-[var(--overlay)]/40 transition-colors group"
              >
                <span className="mt-0.5 h-6 w-6 shrink-0 rounded-full grid place-items-center" style={{ background: `color-mix(in srgb, ${tone} 15%, transparent)` }}>
                  <Icon className="h-3.5 w-3.5" style={{ color: tone }} />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-[var(--text)] leading-snug">{sentence(e, kind)}</p>
                  <div className="flex items-center gap-2 text-[10px] text-[var(--text-tertiary)] mt-0.5">
                    {e.run_id && <span className="mono">run {e.run_id.slice(0, 8)}</span>}
                    <span>{relativeTime(e.created_at)}</span>
                    {e.phi_class === "high" && <span className="text-[var(--danger)]">PHI: high</span>}
                  </div>
                </div>
                <ChevronRight className="h-4 w-4 text-[var(--text-tertiary)] opacity-0 group-hover:opacity-100 shrink-0 mt-1" />
              </a>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
