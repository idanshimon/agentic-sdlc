"use client";
import { ReactNode } from "react";
import { usePathname } from "next/navigation";
import { PlaneBadge } from "@/components/domain/plane-badge";
import { DecisionViews } from "@/components/domain/decision-views";

export function PageHeader({
  plane,
  title,
  description,
  actions,
}: {
  plane?: "standards" | "pipeline" | "ledger" | "agenthq";
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  // The four decision views are one dataset seen four ways. Rendering the
  // switcher here keeps them reachable after they left the left nav, and puts
  // it in the same place on every one of those pages.
  const pathname = usePathname();
  const showDecisionViews = pathname === "/decisions" || pathname.startsWith("/decisions/");

  return (
    <header className="flex flex-col gap-3 pb-4 border-b border-[var(--border-default)]">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
        <div className="space-y-1 min-w-0">
          {plane && <PlaneBadge plane={plane} />}
          <h1 className="text-xl font-semibold text-[var(--text)]">{title}</h1>
          {description && (
            <div className="text-sm text-[var(--text-secondary)] max-w-2xl leading-relaxed">
              {description}
            </div>
          )}
        </div>
        {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
      </div>
      {showDecisionViews && <DecisionViews />}
    </header>
  );
}
