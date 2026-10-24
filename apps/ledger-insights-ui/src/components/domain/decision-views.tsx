"use client";
/* DecisionViews — the four ways to look at ONE dataset.
 *
 * These used to be four sibling entries in the left nav, which read as four
 * destinations. They are not: they are a table, a map, a lineage DAG and a run
 * flow over the same ledger. Tabs make the relationship legible and free four
 * slots in the nav. Each tab states the question it answers, and a single
 * sliding indicator (GSAP) marks the active lens. */
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useLayoutEffect, useRef } from "react";
import gsap from "gsap";
import { Table as TableIcon, Share2, GitBranch, Workflow } from "lucide-react";
import { cn } from "@/lib/utils";
import { prefersReducedMotion } from "@/lib/hyperframe";

const VIEWS = [
  { href: "/decisions", label: "Table", icon: TableIcon, help: "The receipts" },
  { href: "/decisions/graph", label: "Map", icon: Share2, help: "How it connects" },
  { href: "/decisions/lineage", label: "Lineage", icon: GitBranch, help: "What reused what" },
  { href: "/decisions/runflow", label: "Run flow", icon: Workflow, help: "Stage by stage" },
] as const;

export function DecisionViews() {
  const pathname = usePathname();
  const navRef = useRef<HTMLElement>(null);
  const barRef = useRef<HTMLSpanElement>(null);

  useLayoutEffect(() => {
    const nav = navRef.current;
    const bar = barRef.current;
    if (!nav || !bar) return;
    const active = nav.querySelector<HTMLElement>('[aria-current="page"]');
    if (!active) {
      gsap.set(bar, { opacity: 0 });
      return;
    }
    const target = { x: active.offsetLeft, width: active.offsetWidth, opacity: 1 };
    if (prefersReducedMotion()) gsap.set(bar, target);
    else gsap.to(bar, { ...target, duration: 0.45, ease: "power3.out" });
  }, [pathname]);

  return (
    <nav
      ref={navRef}
      aria-label="Decision views"
      className="relative inline-flex max-w-full overflow-x-auto rounded-lg border border-[var(--border-default)] bg-[var(--surface)] p-1"
    >
      <span
        ref={barRef}
        aria-hidden
        className="absolute bottom-1 left-0 top-1 rounded-md border border-[var(--border-default)] bg-[var(--elevated)] shadow-sm"
        style={{ opacity: 0 }}
      >
        <span className="absolute inset-x-3 -bottom-px h-[2px] rounded-full bg-[var(--plane-ledger)]" />
      </span>
      {VIEWS.map((view) => {
        // Exact match only — /decisions must not light up on /decisions/graph.
        const active = pathname === view.href;
        const Icon = view.icon;
        return (
          <Link
            key={view.href}
            href={view.href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "relative z-10 flex shrink-0 items-center gap-2 rounded-md px-3 py-1.5 text-left transition-colors",
              active ? "text-[var(--text)]" : "text-[var(--text-secondary)] hover:text-[var(--text)]",
            )}
          >
            <Icon className={cn("h-4 w-4", active && "text-[var(--plane-ledger)]")} />
            <span className="flex flex-col leading-tight">
              <span className="text-xs font-medium">{view.label}</span>
              <span className="hidden text-[10px] text-[var(--text-tertiary)] sm:block">{view.help}</span>
            </span>
          </Link>
        );
      })}
    </nav>
  );
}
