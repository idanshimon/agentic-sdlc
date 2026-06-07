import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { type LucideIcon } from "lucide-react";

export function KpiCard({
  label,
  value,
  delta,
  icon: Icon,
  hint,
  accent,
  loading,
}: {
  label: string;
  value: string | number | null | undefined;
  delta?: string;
  icon?: LucideIcon;
  hint?: string;
  accent?: "primary" | "success" | "warning" | "danger" | "standards" | "pipeline" | "ledger" | "agenthq";
  loading?: boolean;
}) {
  const accentVar: Record<string, string> = {
    primary: "var(--primary)",
    success: "var(--success)",
    warning: "var(--warning)",
    danger: "var(--danger)",
    standards: "var(--plane-standards)",
    pipeline: "var(--plane-pipeline)",
    ledger: "var(--plane-ledger)",
    agenthq: "var(--plane-agenthq)",
  };
  const accentColor = accent ? accentVar[accent] : "var(--text-tertiary)";

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-tertiary)]">
          {label}
        </span>
        {Icon && <Icon className="h-4 w-4" style={{ color: accentColor }} />}
      </div>
      {loading ? (
        <div className="skeleton h-8 w-24" />
      ) : (
        <div className="text-2xl font-semibold tabular text-[var(--text)] leading-none">
          {value ?? "—"}
        </div>
      )}
      <div className="flex items-center justify-between mt-2 min-h-[16px]">
        {delta ? (
          <span className={cn("text-xs tabular", delta.startsWith("-") ? "text-[var(--danger)]" : "text-[var(--success)]")}>
            {delta}
          </span>
        ) : (
          <span />
        )}
        {hint && (
          <span className="text-[11px] text-[var(--text-tertiary)]">{hint}</span>
        )}
      </div>
    </Card>
  );
}
