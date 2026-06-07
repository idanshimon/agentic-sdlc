import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/layout/page-header";
import { Workflow, ShieldCheck, FileEdit, Play, MessageSquare, CheckCircle2 } from "lucide-react";

const hooks = [
  { id: "SessionStart", icon: Play, color: "var(--plane-pipeline)",
    desc: "Loads AGENTS.md, copilot-instructions, matching path-scoped instructions, the active custom agent, and injects the bundles the agent subscribes to.",
    invariants: ["fail-open on MCP unreachable", "5s timeout", "PHI local fast-path always available"] },
  { id: "PreToolUse", icon: ShieldCheck, color: "var(--plane-agenthq)",
    desc: "Runs BEFORE every tool call. Local PHI guard fires first; on detection it writes a runtime ledger entry and blocks the tool with a structured refusal.",
    invariants: ["local regex first, no network in the hot path", "MUST block before tool invocation"] },
  { id: "PostToolUse", icon: CheckCircle2, color: "var(--plane-ledger)",
    desc: "After a tool returns, writes a runtime ledger entry with the decision, rationale, cost, model, and bundle references cited.",
    invariants: ["ledger.write_runtime is the only sink", "no silent skips"] },
  { id: "FileEdit", icon: FileEdit, color: "var(--plane-pipeline)",
    desc: "Fires on every file modification by an agent. Stamps the change with the agent_session_id so the GitHub audit log can be cross-referenced.",
    invariants: ["one ledger entry per file"] },
  { id: "Notification", icon: MessageSquare, color: "var(--plane-standards)",
    desc: "Outbound notification to the operator (chat / email / topic) on gate awaits, fail-hard scans, and budget alerts.",
    invariants: ["never inside the hot path"] },
];

export default function HooksPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        plane="agenthq"
        title="Lifecycle hooks"
        description="Five hooks wrap every agent session. The bash + powershell scripts under .github/hooks/scripts/ are the canonical implementation; this page documents the contract."
      />
      <div className="grid gap-3 md:grid-cols-2">
        {hooks.map((h) => {
          const Icon = h.icon;
          return (
            <Card key={h.id} className="p-4 space-y-3">
              <div className="flex items-center gap-2.5">
                <div className="h-9 w-9 rounded-md flex items-center justify-center" style={{ background: `${h.color}25` }}>
                  <Icon className="h-4 w-4" style={{ color: h.color }} />
                </div>
                <div>
                  <h3 className="text-sm font-semibold mono">{h.id}</h3>
                  <Badge variant="secondary" className="text-[10px]">
                    <Workflow className="h-2.5 w-2.5" /> lifecycle
                  </Badge>
                </div>
              </div>
              <p className="text-xs text-[var(--text-secondary)] leading-relaxed">{h.desc}</p>
              <div className="pt-2 border-t border-[var(--border-muted)] space-y-1">
                <div className="text-[10px] font-medium uppercase tracking-wider text-[var(--text-tertiary)] mb-1">
                  Invariants
                </div>
                {h.invariants.map((inv) => (
                  <div key={inv} className="text-[11px] text-[var(--text-secondary)] flex items-start gap-1.5">
                    <span className="text-[var(--text-tertiary)] mt-1">▸</span>
                    <span>{inv}</span>
                  </div>
                ))}
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
