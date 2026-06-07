import { cn } from "@/lib/utils";
import { type LucideIcon } from "lucide-react";

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center text-center py-12 px-6 rounded-lg border border-dashed border-[var(--border-default)] bg-[var(--surface)]/40",
        className,
      )}
    >
      {Icon && (
        <div className="mb-3 h-10 w-10 rounded-full bg-[var(--overlay)] flex items-center justify-center">
          <Icon className="h-5 w-5 text-[var(--text-tertiary)]" />
        </div>
      )}
      <h3 className="text-sm font-semibold text-[var(--text)]">{title}</h3>
      {description && (
        <p className="mt-1 text-xs text-[var(--text-tertiary)] max-w-sm">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
