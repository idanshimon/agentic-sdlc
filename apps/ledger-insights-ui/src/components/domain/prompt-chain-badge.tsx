"use client";
/**
 * PromptChainBadge — visual rendering of LedgerEntry.prompt_resolution_path.
 *
 * Phase 5 (2026-06-16): closes the user-facing audit loop. Every
 * stage_decision now carries the prompt chain that produced its
 * ambiguity-card recommendation (Phase 2.6 pinning). This component
 * makes that data visible on every DecisionCard so operators can answer
 * "which prompt produced this?" without going to Cosmos or the orchestrator
 * API directly.
 *
 * Three render modes:
 *   variant="inline"   — compact one-liner for table rows
 *   variant="card"     — multi-line for the DecisionCard layout
 *   variant="full"     — expanded chain with all steps + reasons (drilldown)
 *
 * Click on the matched prompt → /prompts page filtered to that prompt_id.
 * Hover on git_sha → tooltip with the full SHA (truncated to 16 in display).
 */
import Link from "next/link";
import { GitBranch, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

type ChainStep = {
  scope: "team" | "persona" | "global";
  matched: boolean;
  reason?: string;
  prompt_id?: string;
  version?: string;
  git_sha?: string;
  owner_persona?: string;
};

const PERSONA_COLORS: Record<string, string> = {
  pm: "text-blue-500 dark:text-blue-300",
  architect: "text-purple-500 dark:text-purple-300",
  qa: "text-green-500 dark:text-green-300",
  sre: "text-orange-500 dark:text-orange-300",
  seceng: "text-red-500 dark:text-red-300",
  compliance: "text-indigo-500 dark:text-indigo-300",
};

interface Props {
  chain: ChainStep[] | null | undefined;
  variant?: "inline" | "card" | "full";
  className?: string;
}

export function PromptChainBadge({ chain, variant = "card", className }: Props) {
  // Pre-Phase-2.6 entries: no chain pinned. Render small grey hint
  // so operators can distinguish "no chain" from "chain not yet
  // loaded" instead of seeing a silent blank.
  if (!chain || chain.length === 0) {
    if (variant === "inline") return null; // table rows hide this; less noise
    return (
      <div
        className={cn(
          "text-[10px] text-[var(--text-tertiary)] italic",
          className,
        )}
      >
        chain unavailable (pre-v2)
      </div>
    );
  }

  const matched = chain.find((s) => s.matched);

  // INLINE — table cell, one line, click-through to /prompts
  if (variant === "inline") {
    if (!matched) return <span className="text-[10px] text-[var(--text-tertiary)]">no match</span>;
    return (
      <Link
        href={`/prompts`}
        className={cn(
          "inline-flex items-center gap-1 text-[10px] font-mono hover:underline group",
          className,
        )}
        title={`Prompt: ${matched.prompt_id} ${matched.version} · git_sha ${matched.git_sha}`}
      >
        <GitBranch className="h-2.5 w-2.5 shrink-0" />
        <span className="text-[var(--text-secondary)]">{matched.prompt_id}</span>
        <span className="text-[var(--text-tertiary)]">{matched.version}</span>
        {matched.owner_persona && (
          <span
            className={cn(
              "text-[10px] font-medium",
              PERSONA_COLORS[matched.owner_persona] ?? "text-[var(--text-tertiary)]",
            )}
          >
            · {matched.owner_persona}
          </span>
        )}
      </Link>
    );
  }

  // CARD — DecisionCard footer, two lines, fuller info
  if (variant === "card") {
    if (!matched) {
      return (
        <div className={cn("text-[11px] text-[var(--text-tertiary)]", className)}>
          Resolved without prompt match — {chain.length} scopes checked
        </div>
      );
    }
    return (
      <Link
        href={`/prompts`}
        className={cn(
          "inline-flex items-start gap-2 text-[11px] hover:bg-[var(--surface-2)] -m-1 p-1 rounded transition-colors group",
          className,
        )}
      >
        <GitBranch className="h-3 w-3 mt-0.5 text-[var(--text-tertiary)] shrink-0" />
        <div className="leading-tight">
          <div className="flex items-center gap-1.5">
            <span className="font-mono text-[var(--text-secondary)] group-hover:text-[var(--text-primary)]">
              {matched.prompt_id}
            </span>
            <span className="font-mono text-[var(--text-tertiary)]">{matched.version}</span>
            {matched.owner_persona && (
              <span
                className={cn(
                  "font-medium",
                  PERSONA_COLORS[matched.owner_persona] ?? "text-[var(--text-tertiary)]",
                )}
              >
                · {matched.owner_persona}
              </span>
            )}
          </div>
          <div className="text-[10px] text-[var(--text-tertiary)] font-mono mt-0.5">
            git_sha {(matched.git_sha ?? "?").slice(0, 16)}
            {(matched.git_sha?.length ?? 0) > 16 && "…"}
            <span className="mx-1.5">·</span>
            matched at <span className="capitalize">{matched.scope}</span> scope
          </div>
        </div>
      </Link>
    );
  }

  // FULL — drilldown view, all steps + reasons, visual walk
  return (
    <div className={cn("space-y-1.5", className)}>
      <div className="text-[10px] uppercase tracking-wider font-medium text-[var(--text-tertiary)] mb-1">
        Prompt inheritance chain
      </div>
      {chain.map((step, i) => (
        <div key={i} className="flex items-center gap-2 text-[11px]">
          {i > 0 && <ChevronRight className="h-3 w-3 text-[var(--text-tertiary)] shrink-0" />}
          <div
            className={cn(
              "inline-flex items-center gap-1.5 rounded px-2 py-0.5 ring-1 ring-inset",
              step.matched
                ? "bg-[var(--success)]/10 ring-[var(--success)]/30 text-[var(--text-primary)] font-medium"
                : "bg-[var(--surface-2)] ring-[var(--border-muted)] text-[var(--text-tertiary)]",
            )}
          >
            <span className="capitalize">{step.scope}</span>
            {step.matched && (
              <>
                <span className="text-[var(--text-secondary)]">{step.prompt_id}</span>
                <span className="font-mono text-[var(--text-tertiary)]">{step.version}</span>
              </>
            )}
            {!step.matched && step.reason && (
              <span className="text-[10px] italic">{step.reason}</span>
            )}
          </div>
        </div>
      ))}
      {matched && (
        <div className="pt-1 text-[10px] text-[var(--text-tertiary)]">
          git_sha{" "}
          <code className="font-mono text-[var(--text-secondary)]">
            {(matched.git_sha ?? "?").slice(0, 20)}
            {(matched.git_sha?.length ?? 0) > 20 && "…"}
          </code>{" "}
          · owner persona{" "}
          <span
            className={cn(
              "font-medium",
              PERSONA_COLORS[matched.owner_persona ?? ""] ?? "text-[var(--text-tertiary)]",
            )}
          >
            {matched.owner_persona}
          </span>
        </div>
      )}
    </div>
  );
}
