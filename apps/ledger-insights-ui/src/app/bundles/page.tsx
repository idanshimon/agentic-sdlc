"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Library, ExternalLink, Shield, Lock, Activity, DollarSign, Pencil, X } from "lucide-react";
import { ledgerMcp } from "@/lib/api/ledger-mcp";
import { orchestrator } from "@/lib/api/orchestrator";
import { useAssistantContext } from "@/lib/assist/context";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/layout/page-header";
import { VersionedEditor } from "@/components/domain/versioned-editor";
import type { BundleRule } from "@/lib/types";

const bundles = [
  { dept: "security", version: "v0.1.0", icon: Shield, label: "Security", desc: "PHI guard, auth-id rules, secret scanning, supply-chain." },
  { dept: "privacy", version: "v0.1.0", icon: Lock, label: "Privacy", desc: "Data minimization, retention, residency, consent surfaces." },
  { dept: "architect", version: "v0.1.0", icon: Activity, label: "Architect", desc: "Service boundaries, storage choices, telemetry, runtime defaults." },
  { dept: "finops", version: "v0.1.0", icon: DollarSign, label: "FinOps", desc: "Cost budgets, model selection, batch-size rules, alerting." },
];

/**
 * Reconstruct an editable rules.yaml seed from the parsed bundle. The editor
 * writes back to standards-bundles/<dept>/<version>/rules.yaml via a PR — the
 * exact YAML the committee reviews. (getBundle returns parsed rules; we render
 * a faithful YAML view for editing. The PR diff is the source of truth.)
 */
function rulesToYaml(rules: BundleRule[]): string {
  if (!rules?.length) return "rules: []\n";
  const lines = ["rules:"];
  for (const r of rules) {
    lines.push(`  - id: ${r.id}`);
    lines.push(`    title: ${JSON.stringify(r.title)}`);
    if (r.must) lines.push(`    must: ${JSON.stringify(r.must)}`);
    if (r.rationale) lines.push(`    rationale: ${JSON.stringify(r.rationale)}`);
  }
  return lines.join("\n") + "\n";
}

function BundleCard({ dept, version, icon: Icon, label, desc }: typeof bundles[number]) {
  const [editing, setEditing] = useState(false);
  const { data, isLoading } = useQuery({
    queryKey: ["bundle", dept, version],
    queryFn: () => ledgerMcp.getBundle(dept, version),
    staleTime: 60_000,
  });

  const seed = data ? rulesToYaml(data.rules ?? []) : "rules: []\n";

  return (
    <Card className="p-5 space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="h-9 w-9 rounded-md bg-[var(--plane-standards)]/15 flex items-center justify-center">
            <Icon className="h-4 w-4 text-[var(--plane-standards)]" />
          </div>
          <div>
            <h3 className="text-sm font-semibold">{label}</h3>
            <span className="mono text-[11px] text-[var(--text-tertiary)]">{dept}/{version}</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="secondary">pinned</Badge>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-[11px]"
            onClick={() => setEditing((v) => !v)}
            disabled={isLoading || !data}
          >
            {editing ? <><X className="h-3 w-3 mr-1" /> Close</> : <><Pencil className="h-3 w-3 mr-1" /> Edit rules</>}
          </Button>
        </div>
      </div>
      <p className="text-xs text-[var(--text-secondary)] leading-relaxed">{desc}</p>

      {editing ? (
        <div className="space-y-2">
          <div className="text-[11px] text-[var(--text-tertiary)] flex items-center gap-1.5 p-2 rounded bg-[var(--warning)]/10 border border-[var(--warning)]/20">
            <Lock className="h-3 w-3 text-[var(--warning)]" />
            Bundles are governed: saving opens a PR for committee review. The
            standard changes only after the PR is merged — never live.
          </div>
          <VersionedEditor
            kind="bundle"
            id={`${dept}-${version}`}
            seed={seed}
            displayName={`${label} bundle`}
            onPullRequest={async (content, commitMessage) => {
              const res = await orchestrator.saveBundleConfig({
                dept, version, file: "rules.yaml",
                content, commit_message: commitMessage,
                pr_title: `Edit ${label} bundle rules (${dept}/${version})`,
              });
              return res.pr_url;
            }}
          />
        </div>
      ) : isLoading ? (
        <div className="skeleton h-20" />
      ) : !data ? (
        <p className="text-xs text-[var(--text-tertiary)]">Failed to load bundle.</p>
      ) : (
        <div className="space-y-2">
          <div className="flex items-center justify-between text-[10px] uppercase tracking-wider text-[var(--text-tertiary)]">
            <span>Rules ({data.rules?.length ?? 0})</span>
            <span>Reviewers ({data.reviewers?.length ?? 0})</span>
          </div>
          <div className="space-y-1.5">
            {(data.rules ?? []).slice(0, 3).map((r) => (
              <div key={r.id} className="flex items-start gap-2 p-2 rounded bg-[var(--overlay)]/50">
                <span className="mono text-[10px] text-[var(--plane-standards)] mt-0.5">{r.id}</span>
                <span className="text-xs text-[var(--text-secondary)] leading-snug">{r.title}</span>
              </div>
            ))}
            {(data.rules?.length ?? 0) > 3 && (
              <p className="text-[11px] text-[var(--text-tertiary)] pl-2">
                + {(data.rules?.length ?? 0) - 3} more
              </p>
            )}
          </div>
        </div>
      )}
      <a
        href={`https://github.com/idanshimon/agentic-sdlc/tree/main/standards-bundles/${dept}/${version}`}
        target="_blank"
        rel="noreferrer"
        className="flex items-center gap-1 text-[11px] text-[var(--primary)] hover:underline pt-2 border-t border-[var(--border-muted)]"
      >
        View on GitHub <ExternalLink className="h-2.5 w-2.5" />
      </a>
    </Card>
  );
}

export default function BundlesPage() {
  useAssistantContext({ kind: "bundles", label: "Standards bundles" });
  return (
    <div className="space-y-6">
      <PageHeader
        plane="standards"
        title="Standards bundles"
        description="Versioned, signed, committee-approved. Pinned in `standards-bundles/PINS.yaml`. Bundles override every other instruction layer when an agent subscribes to them. Editing a bundle opens a governed PR — it never changes the running standard until merged."
      />
      <div className="grid gap-3 md:grid-cols-2">
        {bundles.map((b) => <BundleCard key={b.dept} {...b} />)}
      </div>
    </div>
  );
}
