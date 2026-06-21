"use client";
import { useState } from "react";
import { Bot, FileText, Shield, Code, Search, Wrench, GitMerge, ChevronLeft } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PlaneBadge } from "@/components/domain/plane-badge";
import { PageHeader } from "@/components/layout/page-header";
import { VersionedEditor } from "@/components/domain/versioned-editor";
import { orchestrator } from "@/lib/api/orchestrator";
import { AGENT_SEEDS } from "@/lib/versioning/seeds";
import { useAssistantContext, type ApplyAction } from "@/lib/assist/context";
import { saveVersion, getCurrentContent, getEntry, ensureSeeded } from "@/lib/versioning/store";
import { toast } from "sonner";

const ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  assessor: FileText,
  architect: Wrench,
  codegen: Code,
  "review-scan": Search,
  "pipeline-doctor": Shield,
  "standards-change": GitMerge,
};

export default function AgentsPage() {
  const [selected, setSelected] = useState<string | null>(null);
  const selectedAgent = selected
    ? AGENT_SEEDS.find((a) => a.id === selected)
    : null;

  // The agent assistant can apply edits to the currently-open agent file.
  // The handler composes the new agent.md content and saves a new version.
  useAssistantContext(
    selectedAgent
      ? {
          kind: "agent-edit",
          id: selectedAgent.id,
          label: `${selectedAgent.display_name} agent`,
          payload: { description: selectedAgent.description },
        }
      : { kind: "agents-list", label: "Custom agents" },
    selectedAgent
      ? async (action: ApplyAction) => {
          if (action.kind === "apply_text_edit") {
            ensureSeeded("agent", selectedAgent.id, selectedAgent.content);
            const current = getCurrentContent(
              getEntry("agent", selectedAgent.id) ?? {
                id: selectedAgent.id,
                kind: "agent",
                seed: selectedAgent.content,
                versions: [],
                current_version_id: null,
              },
            );
            // Compose: append three concrete don'ts to the existing PHI section.
            const enhanced =
              current.replace(
                /## Don'ts/,
                `## Hard rules — addendum (added by agent assistant)

- **PHI in code comments:** never include raw MRN/SSN/DOB in code comments,
  even synthetic-looking. Use \`PT-DEMO-0001\` for samples.
- **Tokenize before logging:** use \`redacted_id()\` helper in every log
  line that touches a patient identifier.
- **Subject reference rule:** never write \`Observation.subject.reference\`
  without first running it through the tokenization service.

## Don'ts`,
              );
            saveVersion(
              "agent",
              selectedAgent.id,
              enhanced,
              "agent assistant: tighten PHI rule with three concrete don'ts",
              "ai-assistant",
              selectedAgent.content,
            );
            toast.success("Saved new agent version", {
              description: "Reload the editor to see it",
            });
          }
        }
      : undefined,
  );

  return (
    <div className="space-y-6">
      <PageHeader
        plane="agenthq"
        title="Custom agents"
        description="Personas defined under .github/agents/. Each declares a role, allowed tools, bundle subscriptions, and which ledger entry types it can write. Click any agent to edit — changes are versioned in your local workspace and produce diffs you can roll back at any time."
      />

      {selectedAgent ? (
        <>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => setSelected(null)}>
              <ChevronLeft className="h-3.5 w-3.5" />
              Back to all agents
            </Button>
          </div>
          <VersionedEditor
            kind="agent"
            id={selectedAgent.id}
            seed={selectedAgent.content}
            displayName={`${selectedAgent.display_name} agent`}
            onPullRequest={async (content, commitMessage) => {
              const res = await orchestrator.saveAgentConfig({
                name: selectedAgent.id,
                content,
                commit_message: commitMessage,
                pr_title: `Edit ${selectedAgent.display_name} agent`,
              });
              return res.pr_url;
            }}
            meta={
              <div className="space-y-1.5 mt-1">
                <p className="text-xs text-[var(--text-secondary)]">
                  {selectedAgent.description}
                </p>
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span className="text-[10px] uppercase tracking-wider text-[var(--text-tertiary)]">
                    bundles:
                  </span>
                  {selectedAgent.bundles.map((b) => (
                    <Badge key={b} variant="secondary" className="text-[10px]">
                      {b}
                    </Badge>
                  ))}
                </div>
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span className="text-[10px] uppercase tracking-wider text-[var(--text-tertiary)]">
                    writes:
                  </span>
                  {selectedAgent.ledger_writes.map((w) => (
                    <span
                      key={w}
                      className="mono text-[10px] px-1.5 py-0.5 rounded bg-[var(--overlay)] text-[var(--plane-ledger)]"
                    >
                      {w}
                    </span>
                  ))}
                </div>
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span className="text-[10px] uppercase tracking-wider text-[var(--text-tertiary)]">
                    models:
                  </span>
                  {selectedAgent.preferred_models.map((m) => (
                    <span
                      key={m}
                      className="mono text-[10px] text-[var(--text-secondary)]"
                    >
                      {m}
                    </span>
                  ))}
                </div>
              </div>
            }
          />
        </>
      ) : (
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {AGENT_SEEDS.map((a) => {
            const Icon = ICONS[a.id] ?? Bot;
            return (
              <button
                key={a.id}
                onClick={() => setSelected(a.id)}
                className="text-left rounded-lg border border-[var(--border-default)] bg-[var(--card)] p-4 space-y-3 hover:border-[var(--text-tertiary)] hover:bg-[var(--overlay)]/40 transition-colors"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div className="h-9 w-9 rounded-md bg-[var(--plane-agenthq)]/15 flex items-center justify-center shrink-0">
                      <Icon className="h-4 w-4 text-[var(--plane-agenthq)]" />
                    </div>
                    <div className="min-w-0">
                      <h3 className="text-sm font-semibold mono truncate">
                        {a.id}
                      </h3>
                      <PlaneBadge plane="agenthq" size="xs" />
                    </div>
                  </div>
                </div>
                <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                  {a.description}
                </p>
                <div className="pt-2 space-y-2 border-t border-[var(--border-muted)]">
                  <div>
                    <span className="text-[10px] font-medium uppercase tracking-wider text-[var(--text-tertiary)]">
                      Bundles
                    </span>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {a.bundles.map((b) => (
                        <Badge key={b} variant="secondary" className="text-[10px]">
                          {b}
                        </Badge>
                      ))}
                    </div>
                  </div>
                  <div>
                    <span className="text-[10px] font-medium uppercase tracking-wider text-[var(--text-tertiary)]">
                      Writes
                    </span>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {a.ledger_writes.map((w) => (
                        <span
                          key={w}
                          className="mono text-[10px] px-1.5 py-0.5 rounded bg-[var(--overlay)] text-[var(--plane-ledger)]"
                        >
                          {w}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div>
                    <span className="text-[10px] font-medium uppercase tracking-wider text-[var(--text-tertiary)]">
                      Models
                    </span>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {a.preferred_models.map((m) => (
                        <span
                          key={m}
                          className="mono text-[10px] text-[var(--text-secondary)]"
                        >
                          {m}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
                <div className="text-[10px] text-[var(--primary)] pt-1 font-medium">
                  Click to edit →
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
