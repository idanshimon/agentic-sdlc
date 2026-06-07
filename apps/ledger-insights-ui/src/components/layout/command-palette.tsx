"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  LayoutDashboard,
  GitBranch,
  Library,
  Scale,
  Bot,
  Activity,
  ShieldCheck,
  ExternalLink,
} from "lucide-react";
import {
  CommandDialog,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandGroup,
  CommandItem,
} from "@/components/ui/command";

export function CommandPalette({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
}) {
  const router = useRouter();

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        onOpenChange(!open);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onOpenChange]);

  const go = (path: string) => {
    onOpenChange(false);
    router.push(path);
  };
  const open_ = (url: string) => {
    window.open(url, "_blank");
    onOpenChange(false);
  };

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange}>
      <CommandInput placeholder="Type a command or search…" />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>
        <CommandGroup heading="Navigate">
          <CommandItem onSelect={() => go("/")}>
            <LayoutDashboard className="h-4 w-4 text-[var(--text-tertiary)]" /> Dashboard
          </CommandItem>
          <CommandItem onSelect={() => go("/runs")}>
            <GitBranch className="h-4 w-4 text-[var(--plane-pipeline)]" /> Runs
          </CommandItem>
          <CommandItem onSelect={() => go("/decisions")}>
            <Scale className="h-4 w-4 text-[var(--plane-ledger)]" /> Decisions
          </CommandItem>
          <CommandItem onSelect={() => go("/bundles")}>
            <Library className="h-4 w-4 text-[var(--plane-standards)]" /> Bundles
          </CommandItem>
          <CommandItem onSelect={() => go("/agents")}>
            <Bot className="h-4 w-4 text-[var(--plane-agenthq)]" /> Custom Agents
          </CommandItem>
          <CommandItem onSelect={() => go("/telemetry")}>
            <Activity className="h-4 w-4 text-[var(--plane-pipeline)]" /> Telemetry
          </CommandItem>
          <CommandItem onSelect={() => go("/phi")}>
            <ShieldCheck className="h-4 w-4 text-[var(--plane-agenthq)]" /> PHI Classifier
          </CommandItem>
        </CommandGroup>
        <CommandGroup heading="External">
          <CommandItem onSelect={() => open_("https://github.com/idanshimon/agentic-sdlc")}>
            <ExternalLink className="h-4 w-4" /> Source on GitHub
          </CommandItem>
          <CommandItem
            onSelect={() => open_("https://ca-orchestrator.whitewater-f74a5db8.eastus2.azurecontainerapps.io/docs")}
          >
            <ExternalLink className="h-4 w-4" /> Orchestrator API (Swagger)
          </CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
