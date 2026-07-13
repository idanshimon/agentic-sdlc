"use client";
import { useMemo, useCallback, useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  ReactFlow,
  Background,
  Controls,
  type Node,
  type Edge,
  type NodeProps,
  Handle,
  Position,
  MarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Workflow, User, Bot, ShieldAlert, Flag } from "lucide-react";
import { useDecisions } from "@/lib/hooks/use-runs";
import { PageHeader } from "@/components/layout/page-header";
import { buildRunFlow, runIdsFrom } from "@/lib/graph/build-runflow";
import { layoutLineageDag, type PositionedNode } from "@/lib/graph/layout-lineage";

/**
 * Run Flow — per-run stage timeline (graph view A, for engineers debugging a
 * run). Pick a run; its decisions lay out left→right under the pipeline stages
 * (or ambiguity buckets when the ledger lacks a stage field). Reuses the same
 * useDecisions poll + dagre layout + node click-through as the other views.
 */

function FlowNode({ data }: NodeProps) {
  const d = data as unknown as PositionedNode;
  const isStage = d.kind === "class";

  if (isStage) {
    return (
      <div
        className="rounded-md border border-[var(--plane-pipeline)] bg-[var(--plane-pipeline)]/15 px-3 py-2 text-[11px] font-medium text-[var(--plane-pipeline)]"
      >
        <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
        {d.label}
        <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
      </div>
    );
  }

  const ActorIcon = d.actorKind === "agent" ? Bot : User;
  return (
    <div
      title={d.label}
      style={{ width: 220 }}
      className="group relative rounded-lg border border-[var(--border-default)] bg-[var(--surface)] p-3 cursor-pointer transition-colors hover:border-[var(--plane-ledger)]"
    >
      <span
        className="absolute left-0 top-0 bottom-0 w-[3px] rounded-l-lg"
        style={{ background: d.flagged ? "var(--danger)" : "var(--plane-ledger)" }}
      />
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <span className="flex items-center gap-1 text-[11px] text-[var(--text-secondary)]">
          <ActorIcon className="h-3 w-3 shrink-0" />
          {d.actorKind === "agent" ? "agent" : "human"}
        </span>
        <span className="flex items-center gap-1 shrink-0">
          {d.phiHigh && <ShieldAlert className="h-3.5 w-3.5" style={{ color: "var(--danger)" }} aria-label="PHI high" />}
          {d.flagged && (
            <span className="inline-flex items-center gap-1 rounded-full bg-[var(--danger)]/15 px-1.5 py-0.5 text-[9px] font-medium text-[var(--danger)]">
              <Flag className="h-2.5 w-2.5" /> flagged
            </span>
          )}
        </span>
      </div>
      <div className="text-[12px] leading-snug text-[var(--text)] line-clamp-2">{d.label}</div>
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
    </div>
  );
}

const nodeTypes = { flow: FlowNode };

export default function RunFlowPage() {
  const router = useRouter();
  const { data, isLoading } = useDecisions({ limit: 200 });
  const entries = useMemo(() => data?.entries ?? [], [data]);
  const runIds = useMemo(() => runIdsFrom(entries), [entries]);

  const [runId, setRunId] = useState<string | null>(null);
  useEffect(() => {
    if (!runId && runIds.length) setRunId(runIds[0]);
  }, [runIds, runId]);

  const { graph, positioned } = useMemo(() => {
    if (!runId) return { graph: null, positioned: [] as PositionedNode[] };
    const g = buildRunFlow(entries, runId);
    const { positioned } = layoutLineageDag(g.nodes, g.edges);
    return { graph: g, positioned };
  }, [entries, runId]);

  const nodes: Node[] = useMemo(
    () => positioned.map((p) => ({ id: p.id, type: "flow", position: { x: p.x, y: p.y }, data: p as unknown as Record<string, unknown> })),
    [positioned],
  );
  const edges: Edge[] = useMemo(
    () =>
      (graph?.edges ?? []).map((e) => {
        const spine = e.kind === "of_class";
        return {
          id: e.id,
          source: e.source,
          target: e.target,
          markerEnd: spine ? { type: MarkerType.ArrowClosed, color: "var(--plane-pipeline)" } : undefined,
          style: {
            stroke: spine ? "var(--plane-pipeline)" : "var(--border-default)",
            strokeWidth: spine ? 2 : 1,
            strokeDasharray: spine ? undefined : "3 3",
          },
        };
      }),
    [graph],
  );

  const onNodeClick = useCallback(
    (_: unknown, node: Node) => {
      const p = node.data as unknown as PositionedNode;
      if (p.entryId) router.push(`/decisions#decision-${p.entryId}`);
    },
    [router],
  );

  return (
    <div className="space-y-4">
      <PageHeader
        plane="pipeline"
        title={
          <span className="flex items-center gap-2">
            <Workflow className="h-5 w-5" /> Run Flow
          </span>
        }
        description="One run, stage by stage. Blue nodes are pipeline stages (or ambiguity buckets); each decision hangs under the stage that made it. Click a decision for its full record."
      />

      <div className="flex flex-wrap items-center gap-3 text-xs">
        <label className="text-[var(--text-tertiary)]">Run:</label>
        <select
          value={runId ?? ""}
          onChange={(e) => setRunId(e.target.value)}
          className="rounded-md border border-[var(--border-default)] bg-[var(--surface)] px-2 py-1 text-[var(--text)]"
        >
          {runIds.map((id) => (
            <option key={id} value={id}>
              {id}
            </option>
          ))}
        </select>
        {graph && (
          <>
            <Stat label="Stages / buckets" value={graph.stats.stages} />
            <Stat label="Decisions" value={graph.stats.decisions} />
            <Stat label="Flagged" value={graph.stats.flagged} danger />
          </>
        )}
      </div>

      <div className="h-[70vh] rounded-lg border border-[var(--border-default)] bg-[var(--bg)]">
        {isLoading ? (
          <div className="flex h-full items-center justify-center text-sm text-[var(--text-tertiary)]">Loading ledger…</div>
        ) : !runId || nodes.length === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-[var(--text-tertiary)]">
            No runs in this ledger scope yet. Submit a run from the Runs page.
          </div>
        ) : (
          <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} onNodeClick={onNodeClick} fitView minZoom={0.2} proOptions={{ hideAttribution: true }}>
            <Background gap={24} color="var(--border-muted)" />
            <Controls showInteractive={false} />
          </ReactFlow>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value, danger }: { label: string; value: number; danger?: boolean }) {
  return (
    <span
      className="rounded-md border px-2.5 py-1"
      style={{ borderColor: danger ? "var(--danger)" : "var(--border-default)", color: danger ? "var(--danger)" : undefined }}
    >
      <span className="font-semibold text-[var(--text)]">{value}</span> {label}
    </span>
  );
}
