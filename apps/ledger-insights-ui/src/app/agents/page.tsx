"use client";
import { Bot, FileText, Shield, Code, Search, Wrench, GitMerge } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PlaneBadge } from "@/components/domain/plane-badge";
import { PageHeader } from "@/components/layout/page-header";

const agents = [
  {
    name: "assessor",
    role: "Classify PRD ambiguities into typed cards",
    icon: FileText,
    bundles: ["security", "privacy"],
    ledger_writes: ["runtime:classification", "runtime:ambiguity_card"],
    preferred_models: ["gpt-4.1", "claude-sonnet-4.7"],
  },
  {
    name: "architect",
    role: "Propose architecture given resolved decisions",
    icon: Wrench,
    bundles: ["architect", "security"],
    ledger_writes: ["runtime:architecture_proposal", "runtime:design_decision"],
    preferred_models: ["claude-opus-4.7", "gpt-5"],
  },
  {
    name: "codegen",
    role: "Generate code aligned to architecture decisions",
    icon: Code,
    bundles: ["architect", "security"],
    ledger_writes: ["runtime:codegen", "runtime:test_plan"],
    preferred_models: ["claude-sonnet-4.7"],
  },
  {
    name: "review-scan",
    role: "Pre-merge review, SBOM + SAST + secret scan",
    icon: Search,
    bundles: ["security"],
    ledger_writes: ["runtime:scan_result", "runtime:gate_decision"],
    preferred_models: ["gpt-4.1"],
  },
  {
    name: "pipeline-doctor",
    role: "Drift detection + bounded auto-fix + change proposal",
    icon: Shield,
    bundles: ["finops", "all (read-only)"],
    ledger_writes: ["meta:drift_report", "meta:auto_fix"],
    preferred_models: ["claude-sonnet-4.7"],
  },
  {
    name: "standards-change",
    role: "Triage standards-change PRs, draft ADRs, route reviewers",
    icon: GitMerge,
    bundles: ["(all, meta)"],
    ledger_writes: ["meta:change_proposal", "meta:reviewer_routing"],
    preferred_models: ["claude-opus-4.7"],
  },
];

export default function AgentsPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        plane="agenthq"
        title="Custom agents"
        description="Personas defined under `.github/agents/`. Each declares a role, allowed tools, bundle subscriptions, and which ledger entry types it can write. CI rejects PRs that introduce malformed agent frontmatter."
      />
      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
        {agents.map((a) => {
          const Icon = a.icon;
          return (
            <Card key={a.name} className="p-4 space-y-3">
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className="h-9 w-9 rounded-md bg-[var(--plane-agenthq)]/15 flex items-center justify-center shrink-0">
                    <Icon className="h-4 w-4 text-[var(--plane-agenthq)]" />
                  </div>
                  <div className="min-w-0">
                    <h3 className="text-sm font-semibold mono truncate">{a.name}</h3>
                    <PlaneBadge plane="agenthq" size="xs" />
                  </div>
                </div>
              </div>
              <p className="text-xs text-[var(--text-secondary)] leading-relaxed">{a.role}</p>
              <div className="pt-2 space-y-2 border-t border-[var(--border-muted)]">
                <div>
                  <span className="text-[10px] font-medium uppercase tracking-wider text-[var(--text-tertiary)]">
                    Bundles
                  </span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {a.bundles.map((b) => (
                      <Badge key={b} variant="secondary" className="text-[10px]">{b}</Badge>
                    ))}
                  </div>
                </div>
                <div>
                  <span className="text-[10px] font-medium uppercase tracking-wider text-[var(--text-tertiary)]">
                    Writes
                  </span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {a.ledger_writes.map((w) => (
                      <span key={w} className="mono text-[10px] px-1.5 py-0.5 rounded bg-[var(--overlay)] text-[var(--plane-ledger)]">{w}</span>
                    ))}
                  </div>
                </div>
                <div>
                  <span className="text-[10px] font-medium uppercase tracking-wider text-[var(--text-tertiary)]">
                    Models
                  </span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {a.preferred_models.map((m) => (
                      <span key={m} className="text-[10px] text-[var(--text-secondary)]">{m}</span>
                    ))}
                  </div>
                </div>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
