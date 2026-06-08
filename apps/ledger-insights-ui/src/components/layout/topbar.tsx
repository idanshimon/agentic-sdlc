"use client";
import { useState } from "react";
import { Menu, Search, Command as CommandIcon, Sun, Moon, Sparkles } from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { Sidebar, SidebarBody } from "./sidebar";
import { CommandPalette } from "./command-palette";
import { HealthIndicator } from "@/components/domain/health-indicator";
import { isDemoMode } from "@/lib/demo";
import Link from "next/link";

export function TopBar() {
  const [openCmd, setOpenCmd] = useState(false);
  const { theme, setTheme } = useTheme();
  const demo = isDemoMode();

  return (
    <>
      <header className="sticky top-0 z-40 flex h-14 items-center gap-3 px-4 lg:px-6 border-b border-[var(--border-default)] bg-[var(--bg)]/85 backdrop-blur-xl">
        <Sheet>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon" className="lg:hidden">
              <Menu className="h-5 w-5" />
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="p-0 w-60">
            <SidebarBody />
          </SheetContent>
        </Sheet>
        <button
          onClick={() => setOpenCmd(true)}
          className="flex flex-1 max-w-md items-center gap-2 px-3 h-8 rounded-md border border-[var(--border-default)] bg-[var(--overlay)] text-xs text-[var(--text-tertiary)] hover:border-[var(--text-tertiary)] transition-colors"
        >
          <Search className="h-3.5 w-3.5" />
          <span className="flex-1 text-left">Search runs, decisions, bundles…</span>
          <span className="flex items-center gap-0.5 rounded border border-[var(--border-default)] px-1.5 py-0.5 text-[10px] font-mono">
            <CommandIcon className="h-2.5 w-2.5" />/
          </span>
        </button>
        <div className="flex items-center gap-2">
          {demo && (
            <Link
              href="/runs/new"
              className="hidden md:inline-flex items-center gap-1.5 px-2.5 h-7 rounded-md border border-amber-500/40 bg-amber-500/10 text-amber-400 text-xs font-medium hover:border-amber-400 hover:bg-amber-500/15 transition-colors"
              title="Demo Mode active — pre-canned pipeline replays, no LLM calls"
            >
              <Sparkles className="h-3 w-3" />
              <span>DEMO MODE</span>
            </Link>
          )}
          <HealthIndicator />
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
            aria-label="Toggle theme"
          >
            <Sun className="h-4 w-4 dark:hidden" />
            <Moon className="hidden h-4 w-4 dark:block" />
          </Button>
        </div>
      </header>
      <CommandPalette open={openCmd} onOpenChange={setOpenCmd} />
    </>
  );
}
