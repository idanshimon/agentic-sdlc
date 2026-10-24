"use client";
import { useMemo } from "react";
import { PageHeader } from "@/components/layout/page-header";
import { MissionCockpit } from "@/components/domain/mission-cockpit";
import { PipelineFlow } from "@/components/domain/pipeline-flow";
import { useRuns, useDecisions } from "@/lib/hooks/use-runs";
import { useAssistantContext } from "@/lib/assist/context";
import { AGENT_SEEDS } from "@/lib/versioning/seeds";
import { agentActivity } from "@/lib/mission";

export default function MissionPage() {
  const { data: runs, isLoading, isError } = useRuns({ limit: 200 });
  const { data: decisions } = useDecisions({ limit: 500 });
  useAssistantContext({ kind: "dashboard", label: "Mission Control" });

  const runList = useMemo(() => runs?.items ?? [], [runs]);
  const entries = useMemo(() => decisions?.entries ?? [], [decisions]);
  const agents = useMemo(
    () => AGENT_SEEDS.map((a) => ({ id: a.id, display_name: a.display_name, description: a.description })),
    [],
  );
  const activity = useMemo(() => agentActivity(entries, agents.map((a) => a.id)), [entries, agents]);

  return (
    <div className="space-y-5">
      <PageHeader
        plane="pipeline"
        title="Mission Control"
        description="Every run, every stage and every agent in one view. Runs closest to the center need a human first."
      />
      {isError ? (
        <p className="rounded-md border border-[var(--danger)] p-3 text-sm text-[var(--danger)]">
          Could not load runs from the orchestrator. The cockpit is not showing an empty system — it is showing nothing.
        </p>
      ) : isLoading ? (
        <div className="skeleton h-[640px] rounded-lg" />
      ) : (
        <>
          <MissionCockpit runs={runList} activity={activity} agents={agents} />
          <PipelineFlow runs={runList} />
        </>
      )}
    </div>
  );
}
