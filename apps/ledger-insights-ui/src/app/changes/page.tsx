"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  GitMerge, Sparkles, ChevronLeft, FileText, ListChecks, Layers,
  CheckCircle2, Circle, ExternalLink, Github,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/layout/page-header";
import { useAssistantContext } from "@/lib/assist/context";
import { STATUS_LABEL, STATUS_HELP } from "@/lib/openspec/status";
import { cn } from "@/lib/utils";

interface ChangeMeta {
  id: string;
  title: string;
  status: "draft" | "in-progress" | "ready" | "merged";
  authors: string[];
  date?: string;
  capabilities_touched: string[];
  why_excerpt: string;
  task_total: number;
  task_done: number;
  spec_count: number;
  proposal_path: string;
  archived: boolean;
}

interface ChangeDetail {
  id: string;
  proposal: string;
  tasks: string;
  specs: { capability: string; spec_md: string }[];
}

function statusVariant(status: ChangeMeta["status"]) {
  if (status === "merged") return "success" as const;
  if (status === "ready") return "success" as const;
  if (status === "in-progress") return "warning" as const;
  return "secondary" as const;
}

export default function ChangesPage() {
  const [selected, setSelected] = useState<string | null>(null);
  useAssistantContext({
    kind: selected ? "bundles" : "bundles",
    label: "OpenSpec changes",
    id: selected ?? undefined,
  });

  const { data, isLoading } = useQuery({
    queryKey: ["openspec-changes"],
    queryFn: async () => {
      const res = await fetch("/api/openspec/changes");
      if (!res.ok) throw new Error("Failed to load changes");
      return (await res.json()) as { changes: ChangeMeta[] };
    },
  });

  const changes = data?.changes ?? [];
  const selectedChange = changes.find((c) => c.id === selected);

  if (selected && selectedChange) {
    return <ChangeDetailView change={selectedChange} onBack={() => setSelected(null)} />;
  }

  // Group by the derived status for a clear "what needs attention" hierarchy.
  const byStatus = {
    ready: changes.filter((c) => c.status === "ready"),
    "in-progress": changes.filter((c) => c.status === "in-progress"),
    draft: changes.filter((c) => c.status === "draft"),
    merged: changes.filter((c) => c.status === "merged"),
  };

  const totalDone = changes.reduce((acc, c) => acc + c.task_done, 0);
  const totalTasks = changes.reduce((acc, c) => acc + c.task_total, 0);

  return (
    <div className="space-y-6">
      <PageHeader
        plane="standards"
        title="OpenSpec changes"
        description="A live index of every proposed change to how this system works — read straight from openspec/changes/ on disk. Each card is one change: what it does, why, which capabilities it touches, and how far along it is."
        actions={
          <Button variant="ghost" size="sm" asChild>
            <a
              href="https://github.com/idanshimon/agentic-sdlc/tree/main/openspec/changes"
              target="_blank"
              rel="noreferrer"
            >
              <Github className="h-3.5 w-3.5" />
              View on GitHub
            </a>
          </Button>
        }
      />

      {/* Plain-English orientation — what this page is and how to use it, for
          anyone who hasn't met OpenSpec before. */}
      <Card className="p-4 border-[var(--plane-standards)]/30 bg-[var(--plane-standards)]/[0.03]">
        <div className="flex items-start gap-3">
          <FileText className="h-5 w-5 text-[var(--plane-standards)] shrink-0 mt-0.5" />
          <div className="space-y-2 text-xs text-[var(--text-secondary)] leading-relaxed">
            <p>
              <span className="font-semibold text-[var(--text)]">What is this?</span>{" "}
              OpenSpec is how any non-trivial change here gets proposed before it&apos;s built —
              by a human or an agent. Each change is a folder on disk with a{" "}
              <span className="mono text-[10px]">proposal.md</span> (the why + what),
              a <span className="mono text-[10px]">tasks.md</span> checklist (the work),
              and typed <span className="mono text-[10px]">spec deltas</span> (the exact
              capability changes). This page just renders those files.
            </p>
            <p>
              <span className="font-semibold text-[var(--text)]">Why it&apos;s here:</span>{" "}
              it&apos;s the audit trail for <em>intent</em> — the same governance the pipeline
              applies to code, applied to its own design. Click any card to read the full
              proposal, tick through its task checklist, and see the spec deltas.
            </p>
            <p className="flex flex-wrap items-center gap-x-3 gap-y-1 pt-0.5">
              <span className="font-semibold text-[var(--text)]">Status is derived from the work, not a label:</span>
              {(["ready", "in-progress", "draft", "merged"] as const).map((s) => (
                <span key={s} className="inline-flex items-center gap-1.5">
                  <Badge variant={statusVariant(s)} className="text-[10px]">{STATUS_LABEL[s]}</Badge>
                  <span className="text-[var(--text-tertiary)]">{STATUS_HELP[s]}</span>
                </span>
              ))}
            </p>
          </div>
        </div>
      </Card>

      {/* KPI strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card className="p-4 space-y-1">
          <div className="text-[10px] uppercase tracking-wider text-[var(--text-tertiary)]">
            Ready to merge
          </div>
          <div className="text-2xl font-semibold tabular">{byStatus["ready"].length}</div>
          <div className="text-[10px] text-[var(--text-tertiary)]">
            all tasks complete
          </div>
        </Card>
        <Card className="p-4 space-y-1">
          <div className="text-[10px] uppercase tracking-wider text-[var(--text-tertiary)]">
            In progress
          </div>
          <div className="text-2xl font-semibold tabular">{byStatus["in-progress"].length}</div>
          <div className="text-[10px] text-[var(--text-tertiary)]">
            {byStatus["draft"].length} not started yet
          </div>
        </Card>
        <Card className="p-4 space-y-1">
          <div className="text-[10px] uppercase tracking-wider text-[var(--text-tertiary)]">
            Tasks done
          </div>
          <div className="text-2xl font-semibold tabular">
            {totalDone} <span className="text-sm text-[var(--text-tertiary)]">/ {totalTasks}</span>
          </div>
          <div className="text-[10px] text-[var(--text-tertiary)]">
            {totalTasks > 0 ? Math.round((totalDone / totalTasks) * 100) : 0}% across all changes
          </div>
        </Card>
        <Card className="p-4 space-y-1">
          <div className="text-[10px] uppercase tracking-wider text-[var(--text-tertiary)]">
            Merged
          </div>
          <div className="text-2xl font-semibold tabular">{byStatus["merged"].length}</div>
          <div className="text-[10px] text-[var(--text-tertiary)]">shipped &amp; archived</div>
        </Card>
      </div>

      {isLoading ? (
        <div className="grid gap-3 md:grid-cols-2">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="skeleton h-32 rounded-lg" />
          ))}
        </div>
      ) : (
        <div className="space-y-6">
          {(["ready", "in-progress", "draft", "merged"] as const).map((status) => {
            const list = byStatus[status];
            if (list.length === 0) return null;
            return (
              <div key={status} className="space-y-3">
                <div className="flex items-center gap-2">
                  <h2 className="text-sm font-semibold capitalize">
                    {STATUS_LABEL[status]}
                  </h2>
                  <Badge variant="secondary" className="text-[10px]">{list.length}</Badge>
                  <span className="text-[11px] text-[var(--text-tertiary)]">{STATUS_HELP[status]}</span>
                </div>
                <div className="grid gap-3 md:grid-cols-2">
                  {list.map((c) => (
                    <ChangeCard key={c.id} change={c} onSelect={setSelected} />
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      <Card className="p-4 bg-gradient-to-r from-[var(--plane-standards)]/5 to-[var(--plane-agenthq)]/5 border-[var(--plane-standards)]/30">
        <div className="flex items-center gap-3">
          <Sparkles className="h-5 w-5 text-[var(--plane-standards)] shrink-0" />
          <div className="flex-1">
            <div className="text-sm font-medium">
              Need to propose a new change?
            </div>
            <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
              Press <span className="mono text-[10px] px-1 py-0.5 rounded bg-[var(--overlay)]">⌘K</span>{" "}
              and ask <span className="font-medium text-[var(--plane-standards)]">&ldquo;draft an openspec change for X&rdquo;</span>.
              The agent will compose proposal.md + tasks.md + spec deltas with the right roster.
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
}

function ChangeCard({
  change,
  onSelect,
}: {
  change: ChangeMeta;
  onSelect: (id: string) => void;
}) {
  const pct = change.task_total > 0 ? (change.task_done / change.task_total) * 100 : 0;
  return (
    <button
      onClick={() => onSelect(change.id)}
      className="text-left rounded-lg border border-[var(--border-default)] bg-[var(--card)] p-4 space-y-3 hover:border-[var(--text-tertiary)] hover:bg-[var(--overlay)]/40 transition-colors"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <Badge variant={statusVariant(change.status)} className="text-[10px]">
              {STATUS_LABEL[change.status]}
            </Badge>
            {change.date && (
              <span className="text-[10px] text-[var(--text-tertiary)] tabular">
                {change.date}
              </span>
            )}
          </div>
          <h3 className="text-sm font-semibold leading-snug mb-1">{change.title}</h3>
          <code className="text-[10px] text-[var(--text-tertiary)] mono">{change.id}</code>
        </div>
      </div>

      {change.why_excerpt && (
        <p className="text-xs text-[var(--text-secondary)] leading-relaxed line-clamp-3">
          {change.why_excerpt}
        </p>
      )}

      {change.capabilities_touched.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {change.capabilities_touched.slice(0, 4).map((cap) => (
            <span
              key={cap}
              className="text-[10px] mono px-1.5 py-0.5 rounded bg-[var(--overlay)] text-[var(--secondary)]"
            >
              {cap}
            </span>
          ))}
          {change.capabilities_touched.length > 4 && (
            <span className="text-[10px] text-[var(--text-tertiary)]">
              +{change.capabilities_touched.length - 4}
            </span>
          )}
        </div>
      )}

      <div className="flex items-center justify-between pt-2 border-t border-[var(--border-muted)] text-[11px] text-[var(--text-tertiary)]">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1">
            <ListChecks className="h-3 w-3" />
            <span className="tabular">
              {change.task_done}/{change.task_total} tasks
            </span>
          </div>
          {change.spec_count > 0 && (
            <div className="flex items-center gap-1">
              <Layers className="h-3 w-3" />
              <span className="tabular">{change.spec_count} spec{change.spec_count === 1 ? "" : "s"}</span>
            </div>
          )}
        </div>
        {change.task_total > 0 && (
          <div className="flex items-center gap-1.5">
            <div className="h-1 w-12 bg-[var(--overlay)] rounded-full overflow-hidden">
              <div
                className="h-full bg-[var(--success)] transition-all"
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="tabular">{Math.round(pct)}%</span>
          </div>
        )}
      </div>
    </button>
  );
}

function ChangeDetailView({ change, onBack }: { change: ChangeMeta; onBack: () => void }) {
  const [tab, setTab] = useState<"proposal" | "tasks" | "specs">("proposal");

  const { data: detail, isLoading } = useQuery({
    queryKey: ["openspec-change", change.id],
    queryFn: async () => {
      const res = await fetch(`/api/openspec/changes/${encodeURIComponent(change.id)}`);
      if (!res.ok) throw new Error("Failed to load change detail");
      return (await res.json()) as ChangeDetail;
    },
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="sm" onClick={onBack}>
          <ChevronLeft className="h-3.5 w-3.5" />
          Back to all changes
        </Button>
      </div>

      <PageHeader
        plane="standards"
        title={change.title}
        description={
          <div className="flex items-center gap-2 flex-wrap text-xs text-[var(--text-tertiary)]">
            <Badge variant={statusVariant(change.status)} className="text-[10px]">
              {STATUS_LABEL[change.status]}
            </Badge>
            <code className="mono text-[var(--text-secondary)]">{change.id}</code>
            {change.authors.length > 0 && (
              <>
                <span>·</span>
                <span>by {change.authors.join(", ")}</span>
              </>
            )}
            {change.date && (
              <>
                <span>·</span>
                <span className="tabular">{change.date}</span>
              </>
            )}
          </div>
        }
        actions={
          <Button variant="ghost" size="sm" asChild>
            <a
              href={`https://github.com/idanshimon/agentic-sdlc/tree/main/${change.proposal_path.replace("/proposal.md", "")}`}
              target="_blank"
              rel="noreferrer"
            >
              <ExternalLink className="h-3 w-3" />
              GitHub
            </a>
          </Button>
        }
      />

      {/* Tabs */}
      <Card className="overflow-hidden">
        <div className="flex items-center gap-1 px-4 pt-3 border-b border-[var(--border-muted)]">
          {([
            { key: "proposal", label: "Proposal", icon: FileText, disabled: false },
            { key: "tasks", label: `Tasks (${change.task_done}/${change.task_total})`, icon: ListChecks, disabled: false },
            { key: "specs", label: `Spec deltas (${change.spec_count})`, icon: Layers, disabled: change.spec_count === 0 },
          ] as Array<{ key: "proposal" | "tasks" | "specs"; label: string; icon: typeof FileText; disabled: boolean }>).map((t) => {
            const isActive = tab === t.key;
            const isDisabled = t.disabled;
            const Icon = t.icon;
            return (
              <button
                key={t.key}
                onClick={() => !isDisabled && setTab(t.key)}
                disabled={isDisabled}
                className={cn(
                  "flex items-center gap-1.5 h-9 px-3 text-xs font-medium rounded-t-md transition-colors -mb-px",
                  isActive
                    ? "bg-[var(--card)] text-[var(--text)] border-x border-t border-[var(--border-muted)]"
                    : "text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]",
                  isDisabled && "opacity-40 cursor-not-allowed",
                )}
              >
                <Icon className="h-3 w-3" />
                {t.label}
              </button>
            );
          })}
        </div>
        <div className="p-4">
          {isLoading ? (
            <div className="skeleton h-64 rounded" />
          ) : tab === "proposal" ? (
            <MarkdownView md={detail?.proposal ?? ""} />
          ) : tab === "tasks" ? (
            <TasksView md={detail?.tasks ?? ""} />
          ) : (
            <SpecsView specs={detail?.specs ?? []} />
          )}
        </div>
      </Card>

      <Card className="p-4 bg-gradient-to-r from-[var(--plane-standards)]/5 to-[var(--plane-agenthq)]/5 border-[var(--plane-standards)]/30">
        <div className="flex items-center gap-3">
          <Sparkles className="h-5 w-5 text-[var(--plane-standards)] shrink-0" />
          <div className="flex-1">
            <div className="text-sm font-medium">
              Want the agent to summarize this change in plain English?
            </div>
            <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
              Press <span className="mono text-[10px] px-1 py-0.5 rounded bg-[var(--overlay)]">⌘K</span>{" "}
              and ask <span className="font-medium text-[var(--plane-standards)]">&ldquo;summarize this change for the security team&rdquo;</span>.
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
}

/* ─────────────── lightweight markdown rendering ─────────────── */

function MarkdownView({ md }: { md: string }) {
  // Quick-and-cheap renderer: headings, bullets, code fences, paragraphs.
  // Not a full parser — good enough for OpenSpec proposals which follow a
  // narrow shape. The pre-formatted sections (## Why, ## What Changes, etc.)
  // render as you'd expect in a code-block-aware viewer.
  return (
    <pre className="mono text-xs leading-relaxed whitespace-pre-wrap break-words bg-[var(--bg)] border border-[var(--border-muted)] rounded p-4 max-h-[700px] overflow-auto">
      {md || "—"}
    </pre>
  );
}

function TasksView({ md }: { md: string }) {
  if (!md) {
    return (
      <p className="text-xs text-[var(--text-tertiary)]">
        No tasks.md for this change.
      </p>
    );
  }
  // Parse checkbox lines + section headers into a structured list.
  const lines = md.split("\n");
  return (
    <div className="space-y-1.5 text-xs">
      {lines.map((raw, i) => {
        const line = raw;
        const checkbox = line.match(/^(\s*)-\s+\[([ x])\]\s+(.+)$/);
        const heading = line.match(/^(#{1,3})\s+(.+)$/);
        if (heading) {
          const level = heading[1].length;
          const text = heading[2];
          return (
            <h3
              key={i}
              className={cn(
                "font-semibold mt-3 mb-1",
                level === 1 ? "text-sm" : "text-xs uppercase tracking-wider text-[var(--text-tertiary)]",
              )}
            >
              {text}
            </h3>
          );
        }
        if (checkbox) {
          const indent = checkbox[1].length;
          const done = checkbox[2] === "x";
          const text = checkbox[3];
          return (
            <div
              key={i}
              className={cn(
                "flex items-start gap-2",
                done && "text-[var(--text-tertiary)]",
              )}
              style={{ paddingLeft: `${Math.min(indent, 8) * 6}px` }}
            >
              {done ? (
                <CheckCircle2 className="h-3.5 w-3.5 text-[var(--success)] shrink-0 mt-0.5" />
              ) : (
                <Circle className="h-3.5 w-3.5 text-[var(--text-tertiary)] shrink-0 mt-0.5" />
              )}
              <span className={cn(done && "line-through")}>{text}</span>
            </div>
          );
        }
        if (line.trim()) {
          return (
            <p key={i} className="text-[var(--text-secondary)] leading-relaxed">
              {line}
            </p>
          );
        }
        return null;
      })}
    </div>
  );
}

function SpecsView({ specs }: { specs: { capability: string; spec_md: string }[] }) {
  if (specs.length === 0) {
    return (
      <p className="text-xs text-[var(--text-tertiary)]">
        No spec deltas for this change.
      </p>
    );
  }
  return (
    <div className="space-y-4">
      {specs.map((s) => (
        <div key={s.capability} className="space-y-2">
          <div className="flex items-center gap-2">
            <Layers className="h-3.5 w-3.5 text-[var(--plane-standards)]" />
            <h3 className="text-sm font-semibold mono">{s.capability}</h3>
            <Badge variant="secondary" className="text-[10px]">
              capability
            </Badge>
          </div>
          <pre className="mono text-[11px] leading-relaxed whitespace-pre-wrap break-words bg-[var(--bg)] border border-[var(--border-muted)] rounded p-3 max-h-[500px] overflow-auto">
            {s.spec_md}
          </pre>
        </div>
      ))}
    </div>
  );
}
