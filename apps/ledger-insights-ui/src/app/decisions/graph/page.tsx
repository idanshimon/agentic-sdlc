"use client";
import { useMemo, useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  type Node,
  type Edge,
  type NodeProps,
  Handle,
  Position,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Scale } from "lucide-react";
import { useDecisions } from "@/lib/hooks/use-runs";
import { PageHeader } from "@/components/layout/page-header";
import { buildGovernanceNetwork, type GraphNodeKind, type GraphEdgeKind } from "@/lib/graph/build-graph";
import { layoutGovernanceMap, type PositionedNode } from "@/lib/graph/layout";
import { applyMapFilters, defaultMapFilters } from "@/lib/graph/map-filters";

/**
 * Governance map — the "how does it all connect" lens over the decision ledger.
 * Additive to /decisions (the table is untouched); reads the SAME useDecisions
 * poll (auto-updates every 10s) and every node click-throughs to
 * /decisions#decision-<id>. Deterministic cluster layout (no force sim).
 */

const KIND_COLOR: Record<GraphNodeKind, string> = {
  bundle: "var(--plane-standards)",
  class: "var(--plane-pipeline)",
  decision: "var(--plane-ledger)",
  run: "var(--text-tertiary)",
  teaching: "var(--warning)",
};

function MapNode({ data }: NodeProps) {
  const d = data as unknown as PositionedNode;
  const isHub = d.kind === "bundle";
  const size = isHub ? Math.min(150, 60 + (d.degree ?? 0) * 8) : d.kind === "class" ? 96 : 64;
  const color = KIND_COLOR[d.kind];
  return (
    <div
      title={d.label}
      style={{
        width: size,
        minHeight: d.kind === "decision" ? 34 : size / 2,
        borderColor: d.flagged ? "var(--danger)" : color,
        boxShadow: d.flagged ? "0 0 0 2px var(--danger), 0 0 12px var(--danger)" : undefined,
        background: d.phiHigh ? "color-mix(in srgb, var(--danger) 14%, var(--surface))" : "var(--surface)",
      }}
      className="rounded-md border px-2 py-1 text-[10px] leading-tight text-[var(--text)] text-center overflow-hidden cursor-pointer hover:brightness-125"
    >
      <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
      <div className="font-medium truncate" style={{ color: d.kind === "bundle" ? color : undefined }}>
        {d.label}
      </div>
      {d.kind === "decision" && d.actorKind && (
        <div className="text-[8px] text-[var(--text-tertiary)]">{d.actorKind}</div>
      )}
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
    </div>
  );
}

const nodeTypes = { map: MapNode };

const EDGE_STYLE: Record<string, { stroke: string; animated?: boolean; dash?: string }> = {
  reuses: { stroke: "var(--success)", animated: true }, // the learning loop — highlighted
  teaches: { stroke: "var(--warning)" },
  grounded_in: { stroke: "var(--border-default)", dash: "3 3" },
  of_class: { stroke: "var(--border-muted)", dash: "1 4" },
  in_run: { stroke: "var(--border-muted)" },
  same_slot: { stroke: "var(--info)", dash: "4 2" },
};

export default function DecisionsGraphPage() {
  const router = useRouter();
  const { data, isLoading } = useDecisions({ limit: 200 });
  const entries = useMemo(() => data?.entries ?? [], [data]);

  // Filter state (scale-survival controls per the legibility critique).
  const [edgeKinds, setEdgeKinds] = useState<Set<GraphEdgeKind>>(() => defaultMapFilters().edgeKinds);
  const [onlyFlagged, setOnlyFlagged] = useState(false);

  const toggleEdge = (k: GraphEdgeKind) =>
    setEdgeKinds((prev) => {
      const next = new Set(prev);
      if (next.has(k)) next.delete(k);
      else next.add(k);
      return next;
    });

  const { graph, positioned } = useMemo(() => {
    const full = buildGovernanceNetwork(entries);
    const filtered = applyMapFilters(full, { ...defaultMapFilters(), edgeKinds, onlyFlagged });
    return { graph: filtered, positioned: layoutGovernanceMap(filtered) };
  }, [entries, edgeKinds, onlyFlagged]);

  const nodes: Node[] = useMemo(
    () => positioned.map((p) => ({ id: p.id, type: "map", position: { x: p.x, y: p.y }, data: p as unknown as Record<string, unknown> })),
    [positioned],
  );
  const edges: Edge[] = useMemo(
    () =>
      graph.edges.map((e) => {
        const s = EDGE_STYLE[e.kind] ?? { stroke: "var(--border-muted)" };
        return {
          id: e.id,
          source: e.source,
          target: e.target,
          animated: s.animated,
          style: { stroke: s.stroke, strokeDasharray: s.dash, strokeWidth: e.kind === "reuses" ? 2 : 1 },
          label: e.kind === "reuses" ? "reused" : undefined,
        };
      }),
    [graph.edges],
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
        plane="ledger"
        title={
          <span className="flex items-center gap-2">
            <Scale className="h-5 w-5" /> Decision Map
          </span>
        }
        description="How decisions, rules, runs and teaching connect. Green animated edges are the learning loop — an autopilot decision reusing a human's precedent. Click any node to open its full record."
      />

      <div className="flex flex-wrap gap-3 text-xs text-[var(--text-secondary)]">
        <Stat label="Decisions" value={graph.stats.decisions} />
        <Stat label="Rules cited" value={graph.stats.bundles} />
        <Stat label="Runs" value={graph.stats.runs} />
        <Stat label="Teaching signals" value={graph.stats.teachingSignals} />
        <Stat label="Learning-loop edges" value={graph.stats.reuseEdges} highlight />
        <Stat label="Flagged" value={graph.stats.flagged} danger />
      </div>

      {/* Scale-survival filter toolbar — toggle edge families + focus flags. */}
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="text-[var(--text-tertiary)]">Edges:</span>
        <EdgeChip label="Learning loop" active={edgeKinds.has("reuses")} color="var(--success)" onClick={() => toggleEdge("reuses")} />
        <EdgeChip label="Teaching" active={edgeKinds.has("teaches")} color="var(--warning)" onClick={() => toggleEdge("teaches")} />
        <EdgeChip label="Cites rule" active={edgeKinds.has("grounded_in")} color="var(--text-secondary)" onClick={() => toggleEdge("grounded_in")} />
        <EdgeChip label="Same bucket" active={edgeKinds.has("same_slot")} color="var(--info)" onClick={() => toggleEdge("same_slot")} />
        <EdgeChip label="In run" active={edgeKinds.has("in_run")} color="var(--text-tertiary)" onClick={() => toggleEdge("in_run")} />
        <EdgeChip label="Of class" active={edgeKinds.has("of_class")} color="var(--text-tertiary)" onClick={() => toggleEdge("of_class")} />
        <span className="mx-1 h-4 w-px bg-[var(--border-default)]" />
        <EdgeChip label="⚑ Only flagged + neighbors" active={onlyFlagged} color="var(--danger)" onClick={() => setOnlyFlagged((v) => !v)} />
      </div>

      <div className="h-[70vh] rounded-lg border border-[var(--border-default)] bg-[var(--bg)]">
        {isLoading ? (
          <div className="flex h-full items-center justify-center text-sm text-[var(--text-tertiary)]">Loading ledger…</div>
        ) : graph.nodes.length === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-[var(--text-tertiary)]">
            No decisions in this ledger scope yet. Submit a run, or check the team token — decisions are team-partitioned.
          </div>
        ) : (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodeClick={onNodeClick}
            fitView
            minZoom={0.1}
            proOptions={{ hideAttribution: true }}
          >
            <Background gap={24} color="var(--border-muted)" />
            <Controls showInteractive={false} />
            <MiniMap
              pannable
              zoomable
              nodeColor={(n) => KIND_COLOR[(n.data as unknown as PositionedNode).kind] ?? "var(--text-tertiary)"}
              maskColor="rgba(10,10,15,0.6)"
              style={{ background: "var(--surface)" }}
            />
          </ReactFlow>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value, highlight, danger }: { label: string; value: number; highlight?: boolean; danger?: boolean }) {
  return (
    <span
      className="rounded-md border px-2.5 py-1"
      style={{
        borderColor: danger ? "var(--danger)" : highlight ? "var(--success)" : "var(--border-default)",
        color: danger ? "var(--danger)" : highlight ? "var(--success)" : undefined,
      }}
    >
      <span className="font-semibold text-[var(--text)]">{value}</span> {label}
    </span>
  );
}

function EdgeChip({ label, active, color, onClick }: { label: string; active: boolean; color: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="rounded-full border px-2.5 py-1 transition-colors"
      style={{
        borderColor: active ? color : "var(--border-default)",
        background: active ? `color-mix(in srgb, ${color} 18%, transparent)` : "transparent",
        color: active ? "var(--text)" : "var(--text-tertiary)",
      }}
    >
      <span className="mr-1.5 inline-block h-2 w-2 rounded-full align-middle" style={{ background: active ? color : "var(--border-default)" }} />
      {label}
    </button>
  );
}
