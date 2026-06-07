"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  GitBranch,
  Scale,
  Library,
  Bot,
  Activity,
  BookOpen,
  Workflow,
  ShieldCheck,
} from "lucide-react";
import { cn } from "@/lib/utils";

const nav = [
  {
    section: "Overview",
    items: [
      { href: "/", label: "Dashboard", icon: LayoutDashboard, plane: null },
    ],
  },
  {
    section: "Pipeline Plane",
    plane: "pipeline" as const,
    items: [
      { href: "/runs", label: "Runs", icon: GitBranch, plane: "pipeline" },
      { href: "/telemetry", label: "Telemetry", icon: Activity, plane: "pipeline" },
    ],
  },
  {
    section: "Ledger Plane",
    plane: "ledger" as const,
    items: [
      { href: "/decisions", label: "Decisions", icon: Scale, plane: "ledger" },
    ],
  },
  {
    section: "Standards Plane",
    plane: "standards" as const,
    items: [
      { href: "/bundles", label: "Bundles", icon: Library, plane: "standards" },
      { href: "/prompts", label: "Prompt Library", icon: BookOpen, plane: "standards" },
    ],
  },
  {
    section: "Agent HQ",
    plane: "agenthq" as const,
    items: [
      { href: "/agents", label: "Custom Agents", icon: Bot, plane: "agenthq" },
      { href: "/hooks", label: "Hooks", icon: Workflow, plane: "agenthq" },
      { href: "/phi", label: "PHI Classifier", icon: ShieldCheck, plane: "agenthq" },
    ],
  },
];

const planeColor: Record<string, string> = {
  pipeline: "var(--plane-pipeline)",
  ledger: "var(--plane-ledger)",
  standards: "var(--plane-standards)",
  agenthq: "var(--plane-agenthq)",
};

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="hidden lg:flex w-60 shrink-0 flex-col border-r border-[var(--border-default)] bg-[var(--surface)]">
      <div className="px-4 py-4 border-b border-[var(--border-default)]">
        <Link href="/" className="flex items-center gap-2 group">
          <div className="relative h-8 w-8 rounded-md bg-gradient-to-br from-[var(--primary)] to-[var(--secondary)] flex items-center justify-center">
            <span className="text-[10px] font-bold text-[#001018]">LI</span>
          </div>
          <div className="flex flex-col leading-tight">
            <span className="text-sm font-semibold text-[var(--text)] group-hover:text-[var(--primary)] transition-colors">
              Ledger Insights
            </span>
            <span className="text-[10px] text-[var(--text-tertiary)] uppercase tracking-wider">
              agentic-sdlc v0.7
            </span>
          </div>
        </Link>
      </div>
      <nav className="flex-1 overflow-y-auto p-3 space-y-5">
        {nav.map((sec) => (
          <div key={sec.section}>
            <div className="flex items-center gap-1.5 px-2 mb-1.5">
              {sec.plane && (
                <span
                  className="h-1.5 w-1.5 rounded-full"
                  style={{ background: planeColor[sec.plane] }}
                />
              )}
              <span className="text-[10px] font-medium uppercase tracking-wider text-[var(--text-tertiary)]">
                {sec.section}
              </span>
            </div>
            <div className="space-y-0.5">
              {sec.items.map((item) => {
                const active = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      "flex items-center gap-2.5 px-2 py-1.5 rounded-md text-sm transition-colors",
                      active
                        ? "bg-[var(--overlay)] text-[var(--text)]"
                        : "text-[var(--text-secondary)] hover:text-[var(--text)] hover:bg-[var(--overlay)]/50",
                    )}
                  >
                    <Icon className="h-4 w-4 shrink-0" />
                    <span>{item.label}</span>
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>
      <div className="p-3 border-t border-[var(--border-default)]">
        <a
          href="https://github.com/idanshimon/agentic-sdlc"
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-2 px-2 py-1.5 rounded-md text-xs text-[var(--text-tertiary)] hover:text-[var(--text)] transition-colors"
        >
          <svg viewBox="0 0 16 16" fill="currentColor" className="h-3.5 w-3.5" aria-hidden>
            <path d="M8 0C3.58 0 0 3.58 0 8a8 8 0 005.47 7.59c.4.07.55-.17.55-.38v-1.34c-2.23.48-2.7-1.07-2.7-1.07-.36-.92-.89-1.17-.89-1.17-.73-.5.05-.49.05-.49.81.06 1.23.83 1.23.83.72 1.23 1.88.87 2.34.66.07-.52.28-.87.5-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.22 2.2.82a7.6 7.6 0 014 0c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48v2.2c0 .21.15.46.55.38A8 8 0 0016 8c0-4.42-3.58-8-8-8z" />
          </svg>
          <span>idanshimon/agentic-sdlc</span>
        </a>
      </div>
    </aside>
  );
}
