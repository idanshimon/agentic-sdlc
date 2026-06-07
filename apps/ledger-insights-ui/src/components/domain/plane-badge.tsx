import { cn } from "@/lib/utils";

const planes = {
  standards: {
    color: "var(--plane-standards)",
    label: "Standards",
  },
  pipeline: {
    color: "var(--plane-pipeline)",
    label: "Pipeline",
  },
  ledger: {
    color: "var(--plane-ledger)",
    label: "Ledger",
  },
  agenthq: {
    color: "var(--plane-agenthq)",
    label: "Agent HQ",
  },
} as const;

export function PlaneBadge({
  plane,
  showLabel = true,
  size = "sm",
  className,
}: {
  plane: keyof typeof planes;
  showLabel?: boolean;
  size?: "xs" | "sm" | "md";
  className?: string;
}) {
  const meta = planes[plane];
  const dot = size === "xs" ? "h-1.5 w-1.5" : size === "md" ? "h-2.5 w-2.5" : "h-2 w-2";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 font-medium",
        size === "xs" ? "text-[10px]" : "text-xs",
        className,
      )}
    >
      <span className={cn("rounded-full", dot)} style={{ background: meta.color }} />
      {showLabel && <span style={{ color: meta.color }}>{meta.label}</span>}
    </span>
  );
}
