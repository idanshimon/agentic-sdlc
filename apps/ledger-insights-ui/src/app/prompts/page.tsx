"use client";
import { useState } from "react";
import { BookOpen, ChevronDown, ChevronRight, ExternalLink } from "lucide-react";
import { usePromptLibrary } from "@/lib/hooks/use-runs";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/domain/empty-state";
import { PageHeader } from "@/components/layout/page-header";
import { cn } from "@/lib/utils";

export default function PromptsPage() {
  const { data, isLoading } = usePromptLibrary();
  const stages = data?.stages ?? [];
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const toggle = (k: string) => setExpanded((p) => ({ ...p, [k]: !p[k] }));

  return (
    <div className="space-y-6">
      <PageHeader
        plane="standards"
        title="Prompt library"
        description="Versioned prompts per stage × provider. Each stage reads its prompt from this catalog so behavior changes go through the same review as code changes."
      />
      {isLoading ? (
        <div className="grid gap-3 md:grid-cols-2">
          {[1, 2, 3, 4].map((i) => <div key={i} className="skeleton h-24 rounded-lg" />)}
        </div>
      ) : stages.length === 0 ? (
        <EmptyState
          icon={BookOpen}
          title="Catalog not populated"
          description="The orchestrator hasn't returned any cataloged prompts yet. Add one via apps/orchestrator/prompt_library.py and they'll appear here."
        />
      ) : (
        <div className="space-y-3">
          {stages.map((s) => {
            const isOpen = expanded[s.stage_name] ?? false;
            const Caret = isOpen ? ChevronDown : ChevronRight;
            return (
              <Card key={s.stage_name} className="overflow-hidden">
                <button
                  onClick={() => toggle(s.stage_name)}
                  className="w-full flex items-center gap-3 p-4 text-left hover:bg-[var(--overlay)]/40 transition-colors"
                >
                  <Caret className="h-4 w-4 text-[var(--text-tertiary)] shrink-0" />
                  <h3 className="text-sm font-semibold mono flex-1">{s.stage_name}</h3>
                  <Badge variant="secondary" className="text-[10px]">
                    {s.providers?.length ?? 0} provider{(s.providers?.length ?? 0) === 1 ? "" : "s"}
                  </Badge>
                </button>
                {isOpen && (
                  <div className="px-4 pb-4 pt-1 space-y-2 border-t border-[var(--border-muted)]">
                    {(s.providers ?? []).map((p, i) => (
                      <div
                        key={`${p.provider}-${p.model}-${i}`}
                        className="rounded-md border border-[var(--border-muted)] bg-[var(--bg)] p-3 space-y-2"
                      >
                        <div className="flex items-center gap-2 flex-wrap">
                          <Badge variant="info" className="text-[10px] mono">{p.provider}</Badge>
                          <span className="mono text-[11px] text-[var(--text)]">{p.model}</span>
                          <Badge variant="default" className="text-[10px]">{p.prompt_version}</Badge>
                        </div>
                        {p.template_preview && (
                          <p className="text-[11px] text-[var(--text-secondary)] leading-relaxed mono">
                            {p.template_preview.slice(0, 220)}
                            {p.template_preview.length > 220 && "…"}
                          </p>
                        )}
                        {p.model_compat_notes && (
                          <p className="text-[10px] text-[var(--text-tertiary)]">
                            {p.model_compat_notes}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            );
          })}
          <a
            href="https://ca-orchestrator.whitewater-f74a5db8.eastus2.azurecontainerapps.io/api/prompt-library"
            target="_blank"
            rel="noreferrer"
            className={cn(
              "inline-flex items-center gap-1 text-[11px] text-[var(--primary)] hover:underline pl-2 pt-2",
            )}
          >
            View raw catalog JSON <ExternalLink className="h-2.5 w-2.5" />
          </a>
        </div>
      )}
    </div>
  );
}
