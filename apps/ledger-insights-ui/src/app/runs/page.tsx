"use client";
import { GitBranch, ExternalLink } from "lucide-react";
import { useRuns } from "@/lib/hooks/use-runs";
import { RunCard } from "@/components/domain/run-card";
import { EmptyState } from "@/components/domain/empty-state";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/layout/page-header";

export default function RunsPage() {
  const { data, isLoading } = useRuns();
  const runs = data?.items ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        plane="pipeline"
        title="Runs"
        description="Every orchestrator run — submit a PRD, watch it stream through the 7-stage pipeline, gate it manually if it needs review, ship a PR at the end."
        actions={
          <Button variant="primary" asChild>
            <a
              href="https://ca-orchestrator.whitewater-f74a5db8.eastus2.azurecontainerapps.io/docs#/default/create_run_api_run_post"
              target="_blank"
              rel="noreferrer"
            >
              Start a run <ExternalLink className="h-4 w-4" />
            </a>
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
          description="Use POST /api/run with a PRD body to kick off a run. Open the API docs to try it interactively — every event is streamed back via SSE on /api/runs/{id}/stream."
          action={
            <Button variant="primary" asChild>
              <a
                href="https://ca-orchestrator.whitewater-f74a5db8.eastus2.azurecontainerapps.io/docs"
                target="_blank"
                rel="noreferrer"
              >
                Open Swagger <ExternalLink className="h-3.5 w-3.5" />
              </a>
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
