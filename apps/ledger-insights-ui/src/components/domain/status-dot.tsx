import { cn } from "@/lib/utils";

type Status = "ok" | "warning" | "error" | "running" | "idle" | "neutral";

const colors: Record<Status, string> = {
  ok: "var(--success)",
  warning: "var(--warning)",
  error: "var(--danger)",
  running: "var(--info)",
  idle: "var(--text-tertiary)",
  neutral: "var(--text-secondary)",
};

export function StatusDot({
  status,
  pulse = false,
  className,
}: {
  status: Status;
  pulse?: boolean;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-block h-2 w-2 rounded-full",
        pulse && "pulse-dot",
        className,
      )}
      style={{ background: colors[status] }}
    />
  );
}
