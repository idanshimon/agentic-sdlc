"use client";
import { useState } from "react";
import { BookOpen, ChevronLeft, ExternalLink } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/layout/page-header";
import { VersionedEditor } from "@/components/domain/versioned-editor";
import { PROMPT_SEEDS } from "@/lib/versioning/seeds";
import { useAssistantContext, type ApplyAction } from "@/lib/assist/context";
import { saveVersion } from "@/lib/versioning/store";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

export default function PromptsPage() {
  const [selected, setSelected] = useState<string | null>(null);
  const selectedPrompt = selected
    ? PROMPT_SEEDS.find((p) => p.id === selected)
    : null;

  useAssistantContext(
    selectedPrompt
      ? {
          kind: "prompt-edit",
          id: selectedPrompt.id,
          label: selectedPrompt.display_name,
          payload: { stage: selectedPrompt.stage, variables: selectedPrompt.variables },
        }
      : { kind: "prompts-list", label: "Prompt library" },
    selectedPrompt
      ? async (action: ApplyAction) => {
          if (action.kind === "apply_text_edit") {
            try {
              saveVersion(
                "prompt",
                selectedPrompt.id,
                action.new_content,
                `agent assistant: ${action.description}`,
                "ai-assistant",
                selectedPrompt.content,
              );
              toast.success("Prompt updated", {
                description: "New version saved. Reload editor to view.",
              });
            } catch (e) {
              toast.error("Could not save", {
                description: e instanceof Error ? e.message : String(e),
              });
            }
          }
        }
      : undefined,
  );

  return (
    <div className="space-y-6">
      <PageHeader
        plane="standards"
        title="Prompt library"
        description="Versioned prompts per pipeline stage. Each stage reads its prompt from this catalog so behavior changes go through the same review path as code changes. Click any prompt to edit — versions are tracked, diffed, and rollback-able."
      />

      {selectedPrompt ? (
        <>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setSelected(null)}
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              Back to prompt library
            </Button>
          </div>
          <VersionedEditor
            kind="prompt"
            id={selectedPrompt.id}
            seed={selectedPrompt.content}
            displayName={selectedPrompt.display_name}
            meta={
              <div className="space-y-1.5 mt-1">
                <p className="text-xs text-[var(--text-secondary)]">
                  {selectedPrompt.description}
                </p>
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span className="text-[10px] uppercase tracking-wider text-[var(--text-tertiary)]">
                    stage:
                  </span>
                  <Badge variant="info" className="text-[10px] mono">
                    {selectedPrompt.stage}
                  </Badge>
                </div>
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span className="text-[10px] uppercase tracking-wider text-[var(--text-tertiary)]">
                    variables:
                  </span>
                  {selectedPrompt.variables.map((v) => (
                    <span
                      key={v}
                      className="mono text-[10px] px-1.5 py-0.5 rounded bg-[var(--overlay)] text-[var(--text-secondary)]"
                    >
                      {`{${v}}`}
                    </span>
                  ))}
                </div>
              </div>
            }
          />
        </>
      ) : (
        <div className="space-y-3">
          {PROMPT_SEEDS.map((p) => (
            <button
              key={p.id}
              onClick={() => setSelected(p.id)}
              className="w-full text-left rounded-lg border border-[var(--border-default)] bg-[var(--card)] p-4 hover:border-[var(--text-tertiary)] hover:bg-[var(--overlay)]/40 transition-colors"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <h3 className="text-sm font-semibold mono">{p.id}</h3>
                    <Badge variant="info" className="text-[10px] mono">
                      stage: {p.stage}
                    </Badge>
                  </div>
                  <p className="text-xs text-[var(--text-secondary)] leading-relaxed mb-2">
                    {p.description}
                  </p>
                  <div className="flex items-center gap-1 flex-wrap">
                    <span className="text-[10px] uppercase tracking-wider text-[var(--text-tertiary)] mr-1">
                      vars:
                    </span>
                    {p.variables.map((v) => (
                      <span
                        key={v}
                        className="mono text-[10px] px-1.5 py-0.5 rounded bg-[var(--overlay)] text-[var(--text-secondary)]"
                      >
                        {`{${v}}`}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="text-[10px] text-[var(--primary)] shrink-0 font-medium">
                  Click to edit →
                </div>
              </div>
            </button>
          ))}

          <a
            href="https://ca-orchestrator.whitewater-f74a5db8.eastus2.azurecontainerapps.io/api/prompt-library"
            target="_blank"
            rel="noreferrer"
            className={cn(
              "inline-flex items-center gap-1 text-[11px] text-[var(--primary)] hover:underline pl-2 pt-2",
            )}
          >
            View live orchestrator catalog (raw JSON){" "}
            <ExternalLink className="h-2.5 w-2.5" />
          </a>
        </div>
      )}
    </div>
  );
}
