"use client";
import { useState } from "react";
import { AgentRoster } from "@/components/domain/agent-roster";
import { ChevronLeft } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/layout/page-header";
import { VersionedEditor } from "@/components/domain/versioned-editor";
import { orchestrator } from "@/lib/api/orchestrator";
import { AGENT_SEEDS } from "@/lib/versioning/seeds";
import { useAssistantContext, type ApplyAction } from "@/lib/assist/context";
import { saveVersion, getCurrentContent, getEntry, ensureSeeded } from "@/lib/versioning/store";
import { toast } from "sonner";

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
        <AgentRoster onSelect={setSelected} />
      )}
    </div>
  );
}
