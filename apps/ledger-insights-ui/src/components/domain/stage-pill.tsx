import { cn } from "@/lib/utils";
import type { Stage } from "@/lib/types";

const stageMeta: Record<Stage, { label: string; abbr: string }> = {
  ingest: { label: "Ingest", abbr: "IN" },
  assessor: { label: "Assessor", abbr: "AS" },
  architect: { label: "Architect", abbr: "AR" },
  test_plan: { label: "Test Plan", abbr: "TP" },
  codegen: { label: "CodeGen", abbr: "CG" },
  review_scan: { label: "Review/Scan", abbr: "RS" },
  deliver: { label: "Deliver", abbr: "DE" },
};

/**
 * Defensive label/abbr fallback for stages that aren't in the canonical
 * pipeline map (e.g. "resolver" / "gate" / "design_review" written by
 * upstream tools or seeded fixtures). Without this, an unknown stage
 * crashed the entire /decisions page on `meta.abbr` lookup.
 *
 * Same defense-in-depth lesson as DecisionCard's normalize() — never
 * trust the input shape; never render off `undefined.field`.
 */
function fallbackMeta(stage: string): { label: string; abbr: string } {
  // Title-case the stage name for the label.
  const label = stage
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
    .join(" ");
  // Abbr: first 2 letters of the first 1-2 words, max 4 chars.
  const parts = stage.split(/[_\s-]+/).filter(Boolean);
  const abbr =
    parts.length >= 2
      ? (parts[0][0] + parts[1][0]).toUpperCase()
      : (stage.slice(0, 2)).toUpperCase();
  return { label: label || stage, abbr: abbr || "??" };
}

export function StagePill({
  stage,
  status = "idle",
  className,
}: {
  stage: Stage | string;
  status?: "idle" | "running" | "completed" | "failed" | "awaiting_gate";
  className?: string;
}) {
  const meta = (stageMeta as Record<string, { label: string; abbr: string }>)[stage as string]
    ?? fallbackMeta(String(stage));
  const statusStyles: Record<string, string> = {
    idle: "bg-[var(--overlay)] text-[var(--text-tertiary)] border-[var(--border-default)]",
    running: "bg-[var(--info)]/15 text-[var(--info)] border-[var(--info)]/30",
    completed: "bg-[var(--success)]/15 text-[var(--success)] border-[var(--success)]/30",
    failed: "bg-[var(--danger)]/15 text-[var(--danger)] border-[var(--danger)]/30",
    awaiting_gate: "bg-[var(--warning)]/15 text-[var(--warning)] border-[var(--warning)]/30",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[11px] font-medium border",
        statusStyles[status],
        className,
      )}
    >
      <span className="font-mono text-[10px] opacity-60">{meta.abbr}</span>
      {meta.label}
    </span>
  );
}
