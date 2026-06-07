"use client";
import { Scale } from "lucide-react";
import { useDecisions } from "@/lib/hooks/use-runs";
import { DecisionCard } from "@/components/domain/decision-card";
import { EmptyState } from "@/components/domain/empty-state";
import { PageHeader } from "@/components/layout/page-header";

export default function DecisionsPage() {
  const { data, isLoading } = useDecisions();
  const entries = data?.entries ?? [];
  return (
    <div className="space-y-6">
      <PageHeader
        plane="ledger"
        title="Decision Ledger"
        description="Every meaningful agent decision is written here — runtime entries (per stage) and meta entries (per standards change). PHI classifier output, bundle citations, model + cost, all queryable."
      />
      {isLoading ? (
        <div className="space-y-3">
          {[1, 2, 3, 4].map((i) => <div key={i} className="skeleton h-32 rounded-lg" />)}
        </div>
      ) : entries.length === 0 ? (
        <EmptyState
          icon={Scale}
          title="No decisions logged yet"
          description="As soon as the orchestrator runs a stage or you write a meta entry via the MCP server, it shows up here. Submit a run from the Runs page or POST directly to ledger.write_runtime."
        />
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {entries.map((e) => <DecisionCard key={e.id} entry={e} />)}
        </div>
      )}
    </div>
  );
}
