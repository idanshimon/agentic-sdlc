import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium leading-none tabular",
  {
    variants: {
      variant: {
        default: "bg-[var(--overlay)] text-[var(--text-secondary)]",
        success: "bg-[var(--success)]/15 text-[var(--success)]",
        warning: "bg-[var(--warning)]/15 text-[var(--warning)]",
        danger: "bg-[var(--danger)]/15 text-[var(--danger)]",
        info: "bg-[var(--info)]/15 text-[var(--info)]",
        secondary: "bg-[var(--secondary)]/15 text-[var(--secondary)]",
        outline: "border border-[var(--border-default)] text-[var(--text-secondary)]",
      },
    },
    defaultVariants: { variant: "default" },
  },
);
export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}
export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}
