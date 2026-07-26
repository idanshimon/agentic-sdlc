"use client";
/* DecisionViews — the four ways to look at ONE dataset.
 *
 * These used to be four sibling entries in the left nav, which read as four
 * destinations. They are not: they are a table, a map, a lineage DAG and a run
 * flow over the same ledger. Tabs make the relationship legible and free four
 * slots in the nav. */
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Table as TableIcon, Share2, GitBranch, Workflow } from "lucide-react";
import { cn } from "@/lib/utils";

const VIEWS = [
  { href: "/decisions", label: "Table", icon: TableIcon, help: "The receipts" },
  { href: "/decisions/graph", label: "Map", icon: Share2, help: "How it connects" },
  { href: "/decisions/lineage", label: "Lineage", icon: GitBranch, help: "What reused what" },
  { href: "/decisions/runflow", label: "Run flow", icon: Workflow, help: "Stage by stage" },
] as const;

export function DecisionViews() {
  const pathname = usePathname();
  return (
    <nav
      aria-label="Decision views"
      className="inline-flex rounded-md border border-[var(--border-default)] bg-[var(--surface)] p-0.5"
    >
      {VIEWS.map((view) => {
        // Exact match only — /decisions must not light up on /decisions/graph.
        const active = pathname === view.href;
        const Icon = view.icon;
        return (
          <Link
            key={view.href}
            href={view.href}
            title={view.help}
            aria-current={active ? "page" : undefined}
            className={cn(
              "inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs transition-colors",
              active
                ? "bg-[var(--overlay)] text-[var(--text)]"
                : "text-[var(--text-secondary)] hover:text-[var(--text)] hover:bg-[var(--overlay)]/50",
            )}
          >
            <Icon className="h-3.5 w-3.5" />
            <span>{view.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
