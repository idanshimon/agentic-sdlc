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

export function StagePill({
  stage,
  status = "idle",
  className,
}: {
  stage: Stage;
  status?: "idle" | "running" | "completed" | "failed" | "awaiting_gate";
  className?: string;
}) {
  const meta = stageMeta[stage];
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
