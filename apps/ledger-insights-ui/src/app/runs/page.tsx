"use client";
import Link from "next/link";
import { GitBranch, ArrowRight } from "lucide-react";
import { useRuns } from "@/lib/hooks/use-runs";
import { useAssistantContext } from "@/lib/assist/context";
import { RunCard } from "@/components/domain/run-card";
import { EmptyState } from "@/components/domain/empty-state";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/layout/page-header";

export default function RunsPage() {
  const { data, isLoading } = useRuns();
  const runs = data?.items ?? [];
  useAssistantContext({
    kind: "runs-list",
    label: "Runs",
    payload: { count: runs.length },
  });

  return (
    <div className="space-y-6">
      <PageHeader
        plane="pipeline"
        title="Runs"
        description="Every orchestrator run — submit a PRD, watch it stream through the 7-stage pipeline, gate it manually if it needs review, ship a PR at the end."
        actions={
          <Button variant="primary" asChild>
            <Link href="/runs/new">
              Start a run <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
        }
      />

      {isLoading ? (
        <div className="grid gap-3 md:grid-cols-2">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="skeleton h-32 rounded-lg" />
          ))}
        </div>
      ) : runs.length === 0 ? (
        <EmptyState
          icon={GitBranch}
          title="No runs yet"
          description="Pick a sample PRD on the next screen and watch the pipeline stream through. Demo Mode replays a full healthcare run end-to-end without any backend dependency."
          action={
            <Button variant="primary" asChild>
              <Link href="/runs/new">
                Start a run <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
          }
        />
      ) : (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {runs.map((r) => <RunCard key={r.run_id} run={r} />)}
        </div>
      )}
    </div>
  );
}
