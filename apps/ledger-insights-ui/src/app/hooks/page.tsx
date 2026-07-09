"use client";
import { useQuery } from "@tanstack/react-query";
import {
  Workflow, ShieldCheck, FileEdit, Play, MessageSquare, CheckCircle2,
  ArrowRight, Clock, ShieldAlert, FileWarning, ExternalLink, Github,
} from "lucide-react";
import Link from "next/link";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/layout/page-header";
import { MODE_LABEL } from "@/lib/hooks-config/target";

interface HookMeta {
  file: string;
  name: string;
  description: string;
  events: string[];
  timeout_seconds?: number;
  fail_open?: boolean;
  controls: { service: string; href?: string; mode: string };
  scripts: { shell: string; path: string; exists: boolean }[];
}

const EVENT_ICON: Record<string, typeof Play> = {
  SessionStart: Play,
  UserPromptSubmit: MessageSquare,
  PreToolUse: ShieldCheck,
  PostToolUse: CheckCircle2,
  SessionEnd: FileEdit,
};

const MODE_TONE: Record<string, string> = {
  enforcing: "var(--danger)",
  injecting: "var(--plane-pipeline)",
  observing: "var(--plane-ledger)",
  notifying: "var(--plane-standards)",
};

export default function HooksPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["lifecycle-hooks"],
    queryFn: async () => {
      const res = await fetch("/api/hooks");
      if (!res.ok) throw new Error("Failed to load hooks");
      return (await res.json()) as { hooks: HookMeta[]; hooks_dir: string };
    },
  });

  const hooks = data?.hooks ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        plane="agenthq"
        title="Lifecycle hooks"
        description="Every agent session is wrapped by these hooks — read live from .github/hooks/*.json on disk. Each one binds a lifecycle event and acts on a specific downstream service: some only observe (write to the ledger), one enforces (the PHI guard can block a tool call), one injects context. This is what each hook controls."
        actions={
          <Button variant="ghost" size="sm" asChild>
            <a
              href="https://github.com/idanshimon/agentic-sdlc/tree/main/.github/hooks"
              target="_blank"
              rel="noreferrer"
            >
              <Github className="h-3.5 w-3.5" />
              View on GitHub
            </a>
          </Button>
        }
      />

      {/* Legend: what the modes mean */}
      <Card className="p-3.5 flex flex-wrap items-center gap-x-5 gap-y-2 text-[11px]">
        <span className="font-medium text-[var(--text-secondary)]">Modes:</span>
        {(["enforcing", "injecting", "observing", "notifying"] as const).map((m) => (
          <span key={m} className="inline-flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full" style={{ background: MODE_TONE[m] }} />
            <span className="font-medium capitalize">{m}</span>
            <span className="text-[var(--text-tertiary)]">— {MODE_LABEL[m as keyof typeof MODE_LABEL]}</span>
          </span>
        ))}
      </Card>

      {isLoading ? (
        <div className="grid gap-3 md:grid-cols-2">
          {[1, 2, 3, 4].map((i) => <div key={i} className="skeleton h-44 rounded-lg" />)}
        </div>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {hooks.map((h) => {
            const event = h.events[0] ?? "";
            const Icon = EVENT_ICON[event] ?? Workflow;
            const tone = MODE_TONE[h.controls.mode] ?? "var(--text-tertiary)";
            const missingScript = h.scripts.some((s) => !s.exists);
            return (
              <Card key={h.file} className="p-4 space-y-3">
                <div className="flex items-start gap-2.5">
                  <div className="h-9 w-9 rounded-md flex items-center justify-center shrink-0" style={{ background: `${tone}25` }}>
                    <Icon className="h-4 w-4" style={{ color: tone }} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <h3 className="text-sm font-semibold mono truncate">{event || h.name}</h3>
                    <div className="flex items-center gap-1.5 flex-wrap mt-0.5">
                      {h.events.map((e) => (
                        <Badge key={e} variant="secondary" className="text-[10px]">{e}</Badge>
                      ))}
                    </div>
                  </div>
                </div>

                <p className="text-xs text-[var(--text-secondary)] leading-relaxed">{h.description}</p>

                {/* What it controls — the headline answer */}
                <div className="rounded-md border p-2.5 space-y-1.5" style={{ borderColor: `${tone}55`, background: `${tone}0d` }}>
                  <div className="flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wider" style={{ color: tone }}>
                    {h.controls.mode === "enforcing" ? <ShieldAlert className="h-3 w-3" /> : <ArrowRight className="h-3 w-3" />}
                    Controls
                  </div>
                  <div className="flex items-center gap-2 flex-wrap text-xs">
                    {h.controls.href ? (
                      <Link href={h.controls.href} className="font-medium hover:underline inline-flex items-center gap-1">
                        {h.controls.service}
                        <ExternalLink className="h-3 w-3 opacity-60" />
                      </Link>
                    ) : (
                      <span className="font-medium">{h.controls.service}</span>
                    )}
                  </div>
                  <div className="text-[10px]" style={{ color: tone }}>
                    {MODE_LABEL[h.controls.mode as keyof typeof MODE_LABEL] ?? h.controls.mode}
                  </div>
                </div>

                {/* Runtime posture */}
                <div className="flex items-center gap-3 flex-wrap pt-1 text-[11px] text-[var(--text-secondary)]">
                  {h.timeout_seconds !== undefined && (
                    <span className="inline-flex items-center gap-1">
                      <Clock className="h-3 w-3 text-[var(--text-tertiary)]" /> {h.timeout_seconds}s timeout
                    </span>
                  )}
                  {h.fail_open !== undefined && (
                    <span className="inline-flex items-center gap-1">
                      <span className="text-[var(--text-tertiary)]">▸</span>
                      {h.fail_open ? "fail-open" : "fail-closed"}
                    </span>
                  )}
                  <span className="inline-flex items-center gap-1">
                    <span className="text-[var(--text-tertiary)]">▸</span>
                    {h.scripts.length} script{h.scripts.length === 1 ? "" : "s"}
                  </span>
                  {missingScript && (
                    <span className="inline-flex items-center gap-1 text-[var(--warning)]">
                      <FileWarning className="h-3 w-3" /> script missing
                    </span>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      )}

      <Card className="p-4 bg-gradient-to-r from-[var(--plane-agenthq)]/5 to-[var(--plane-standards)]/5 border-[var(--plane-agenthq)]/30">
        <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
          <span className="font-medium text-[var(--text)]">Editing hooks:</span>{" "}
          hooks are security-critical (the PreToolUse hook can block a tool call on raw PHI),
          so they change through a governed pull request — the same path as agents, bundles,
          and prompts — never a live in-place edit. The JSON under{" "}
          <span className="mono text-[10px]">.github/hooks/</span> is the source of truth.
        </p>
      </Card>
    </div>
  );
}
