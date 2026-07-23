"use client";
import { useMemo, useCallback, useState } from "react";
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
import { GitBranch, User, Bot, ShieldAlert, ThumbsUp, Flag } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { useDecisions } from "@/lib/hooks/use-runs";
import { PageHeader } from "@/components/layout/page-header";
import { buildPrecedentLineage } from "@/lib/graph/build-lineage";
import { layoutLineageLanes, type PositionedNode, type LaneBand } from "@/lib/graph/layout-lineage";

/**
 * Precedent Lineage — the learning-loop hero view. Reads the SAME useDecisions
 * poll (auto-updates 10s). Human precedents (roots) on the left; each reuse hop
 * moves right, so the human→agent learning loop reads as a timeline. Every node
 * click-throughs to /decisions#decision-<id>.
 */

function LineageNode({ data }: NodeProps) {
  const d = data as unknown as PositionedNode;
  const m = (d.meta ?? {}) as { isRoot?: boolean; role?: string; rule?: string | null };
  const isTeach = d.kind === "teaching";

  // Teaching satellite — matches the house Badge language (rounded-full, /15 tint).
  if (isTeach) {
    const down = d.label.includes("👎") || /not helpful/i.test(d.label);
    const flag = d.label.includes("🚩") || /flag/i.test(d.label);
    const text = d.label.replace(/^[^\w]+\s*/, "");
    const color = flag ? "var(--danger)" : down ? "var(--danger)" : "var(--success)";
    return (
      <div
        className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium tabular"
        style={{ background: `color-mix(in srgb, ${color} 15%, transparent)`, color }}
      >
        <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
        {flag ? <Flag className="h-3 w-3" /> : <ThumbsUp className="h-3 w-3" />}
        {text}
        <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
      </div>
    );
  }

  const ActorIcon = d.actorKind === "agent" ? Bot : User;
  return (
    <div
      title={d.label}
      style={{ width: 236 }}
      className="group relative rounded-lg border border-[var(--border-default)] bg-[var(--surface)] p-3 cursor-pointer transition-colors hover:border-[var(--plane-ledger)]"
    >
      {/* left status rail — flagged=danger, else ledger green */}
      <span
        className="absolute left-0 top-0 bottom-0 w-[3px] rounded-l-lg"
        style={{ background: d.flagged ? "var(--danger)" : "var(--plane-ledger)" }}
      />
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />

      {/* header: actor + status badges (house Badge style) */}
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <span className="flex items-center gap-1 text-[11px] text-[var(--text-secondary)] min-w-0">
          <ActorIcon className="h-3 w-3 shrink-0" />
          <span className="truncate">{m.role}</span>
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

      {/* decision text */}
      <div className="mb-2 text-[12px] leading-snug text-[var(--text)] line-clamp-2">{d.label}</div>

      {/* footer: ambiguity class + rule id (mono, like DecisionCard bundle_refs) */}
      <div className="flex flex-wrap items-center gap-1.5">
        {d.ambiguityClass && (
          <span className="rounded-full bg-[var(--overlay)] px-2 py-0.5 text-[10px] text-[var(--text-secondary)]">
            {d.ambiguityClass}
          </span>
        )}
        {m.rule && (
          <span title={m.rule} className="mono text-[10px] px-1.5 py-0.5 rounded bg-[var(--overlay)] text-[var(--secondary)]">
            {m.rule.replace(/\/v[\d.]+\//, "/")}
          </span>
        )}
      </div>

      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
    </div>
  );
}

const nodeTypes = { lineage: LineageNode, laneHeader: LaneHeaderNode, laneBand: LaneBandNode };

/** Full-width band painted behind a lane — flat surface, house border tokens. */
function LaneBandNode({ data }: NodeProps) {
  const d = data as unknown as { width: number; height: number; flagged?: boolean };
  return (
    <div
      style={{ width: d.width, height: d.height }}
      className="rounded-lg border border-[var(--border-muted)] bg-[var(--surface)]/40"
    />
  );
}

/** Governance header that opens each lane — the plain-language claim (in-theme). */
function LaneHeaderNode({ data }: NodeProps) {
  const d = data as unknown as {
    title: string;
    actorRole: string;
    actorKind?: "human" | "agent";
    ambiguityClass?: string;
    applied: number;
    endorsed: number;
    blocked: number;
  };
  const isHuman = d.actorKind !== "agent";
  const ActorIcon = isHuman ? User : Bot;
  return (
    <div className="w-[248px] pr-3">
      <div className="mb-1.5 flex items-center gap-1.5">
        <ActorIcon className="h-3.5 w-3.5" style={{ color: isHuman ? "var(--plane-ledger)" : "var(--plane-pipeline)" }} />
        <span className="text-[11px] font-medium text-[var(--text-secondary)] truncate">{d.actorRole}</span>
        <Badge variant={isHuman ? "success" : "info"} className="text-[9px] px-1.5 py-0">
          {isHuman ? "human precedent" : "agent convention"}
        </Badge>
      </div>
      <div className="mb-2 text-[13px] font-semibold leading-snug text-[var(--text)]">{d.title}</div>
      <div className="flex flex-wrap items-center gap-1.5 tabular">
        <span className="rounded-full bg-[var(--overlay)] px-2 py-0.5 text-[10px] text-[var(--text-secondary)]">
          Applied <b className="text-[var(--text)]">{d.applied}×</b>
        </span>
        {d.endorsed > 0 && (
          <span className="inline-flex items-center gap-1 rounded-full bg-[var(--success)]/15 px-2 py-0.5 text-[10px] text-[var(--success)]">
            <ThumbsUp className="h-2.5 w-2.5" /> {d.endorsed} endorsed
          </span>
        )}
        {d.blocked > 0 && (
          <span className="inline-flex items-center gap-1 rounded-full bg-[var(--danger)]/15 px-2 py-0.5 text-[10px] text-[var(--danger)]">
            <Flag className="h-2.5 w-2.5" /> {d.blocked} blocked
          </span>
        )}
      </div>
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
    </div>
  );
}

export default function LineagePage() {
  const router = useRouter();
  const { data, isLoading } = useDecisions({ limit: 1000 });
  const entries = useMemo(() => data?.entries ?? [], [data]);

  const { graph, positioned, bands } = useMemo(() => {
    const g = buildPrecedentLineage(entries);
    const { positioned, bands } = layoutLineageLanes(g.nodes, g.edges, g.lanes);
    return { graph: g, positioned, bands };
  }, [entries]);
  const humanRoots = useMemo(() => graph.lanes.filter((l) => l.actorKind !== "agent").length, [graph.lanes]);
  const agentRoots = graph.lanes.length - humanRoots;

  const nodes: Node[] = useMemo(() => {
    const laneById = new Map(graph.lanes.map((l) => [l.rootId, l]));
    const bandWidth = Math.max(900, ...bands.map(() => 0), ...positioned.map((p) => p.x + 260));
    // 1) band backgrounds (behind), 2) lane headers (left gutter), 3) decision/teaching nodes
    const bandNodes: Node[] = bands.map((b: LaneBand) => ({
      id: `band-${b.rootId}`,
      type: "laneBand",
      position: { x: -270, y: b.y },
      draggable: false,
      selectable: false,
      data: { width: bandWidth + 300, height: b.height, flagged: (laneById.get(b.rootId)?.blocked ?? 0) > 0 },
      zIndex: 0,
    }));
    const headerNodes: Node[] = bands.map((b: LaneBand) => {
      const lane = laneById.get(b.rootId)!;
      return {
        id: `header-${b.rootId}`,
        type: "laneHeader",
        position: { x: -258, y: b.y + 18 },
        draggable: false,
        selectable: false,
        data: { title: lane.title, actorRole: lane.actorRole, actorKind: lane.actorKind, ambiguityClass: lane.ambiguityClass, applied: lane.applied, endorsed: lane.endorsed, blocked: lane.blocked },
        zIndex: 1,
      };
    });
    const decisionNodes: Node[] = positioned.map((p) => ({ id: p.id, type: "lineage", position: { x: p.x, y: p.y }, data: p as unknown as Record<string, unknown>, zIndex: 2 }));
    return [...bandNodes, ...headerNodes, ...decisionNodes];
  }, [positioned, bands, graph.lanes]);
  const [focusNode, setFocusNode] = useState<string | null>(null);
  const rootSet = useMemo(() => new Set(graph.roots), [graph.roots]);
  const edges: Edge[] = useMemo(
    () =>
      graph.edges.map((e) => {
        const reuse = e.kind === "reuses";
        // Root cards are replaced by lane headers — reroute root-sourced edges to the header node.
        const source = rootSet.has(e.source) ? `header-${e.source}` : e.source;
        const target = rootSet.has(e.target) ? `header-${e.target}` : e.target;
        // 5.6-sol: animate ONLY the focused lineage, not every edge perpetually.
        const focused = focusNode != null && (source === focusNode || target === focusNode || e.source === focusNode || e.target === focusNode);
        return {
          id: e.id,
          source,
          target,
          type: "smoothstep",
          animated: reuse && focused,
          label: reuse ? "reuses precedent" : undefined,
          labelStyle: { fill: "var(--success)", fontSize: 9, fontWeight: 600 },
          labelBgStyle: { fill: "var(--bg)", fillOpacity: 0.85 },
          labelBgPadding: [4, 2] as [number, number],
          labelBgBorderRadius: 4,
          markerEnd: { type: MarkerType.ArrowClosed, color: reuse ? "var(--success)" : "var(--warning)", width: reuse ? 18 : 12, height: reuse ? 18 : 12 },
          style: {
            stroke: reuse ? "var(--success)" : "var(--warning)",
            strokeWidth: reuse ? (focused ? 3 : 2) : 1,
            strokeOpacity: reuse ? (focusNode && !focused ? 0.25 : 0.85) : 0.4,
            strokeDasharray: reuse ? undefined : "4 3",
            filter: reuse && focused ? "drop-shadow(0 0 4px color-mix(in srgb, var(--success) 60%, transparent))" : undefined,
          },
        };
      }),
    [graph.edges, focusNode],
  );

  const onNodeClick = useCallback(
    (_: unknown, node: Node) => {
      const p = node.data as unknown as PositionedNode;
      if (p.entryId) router.push(`/decisions#decision-${p.entryId}`);
    },
    [router],
  );

  const empty = !isLoading && graph.nodes.length === 0;

  return (
    <div className="space-y-4">
      <PageHeader
        plane="ledger"
        title={
          <span className="flex items-center gap-2">
            <GitBranch className="h-5 w-5" /> Precedent Lineage
          </span>
        }
        description="The learning loop as a timeline. Green nodes on the left are human precedents; each arrow shows an autopilot decision that reused it. A flagged precedent (red) is one a human ruled shouldn't be reused. Click any node for its full record."
      />

      <div className="flex flex-wrap gap-3 text-xs text-[var(--text-secondary)]">
        <Stat label="Precedent chains" value={graph.stats.chains} />
        <Stat label="Human roots" value={humanRoots} success />
        <Stat label="Reuse hops (learning loop)" value={graph.stats.reuseEdges} success />
        <Stat label="Flagged (won't reuse)" value={graph.stats.flagged} danger />
      </div>

      {/* Plain-English "answer at a glance" — outcomes not plumbing (repo rule). */}
      {!empty && (
        <div className="flex items-start gap-2.5 rounded-lg border border-[var(--border-default)] bg-[var(--surface)] px-4 py-3 text-[13px] leading-relaxed text-[var(--text-secondary)]">
          <GitBranch className="h-4 w-4 mt-0.5 shrink-0" style={{ color: "var(--plane-ledger)" }} />
          <p>
            <span className="font-semibold text-[var(--text)]">{graph.stats.roots} precedent{graph.stats.roots === 1 ? "" : "s"}</span>
            {humanRoots > 0 && agentRoots > 0 ? ` (${humanRoots} human, ${agentRoots} agent) ` : " "}
            {"taught "}
            <span className="font-semibold text-[var(--text)]">{graph.stats.reuseEdges} later agent decision{graph.stats.reuseEdges === 1 ? "" : "s"}</span>
            {" — an autopilot decision auto-resolved from an earlier ruling instead of re-deciding."}
            {graph.stats.flagged > 0 && (
              <>
                {" "}
                <span className="font-semibold" style={{ color: "var(--danger)" }}>{graph.stats.flagged} decision{graph.stats.flagged === 1 ? " was" : "s were"} flagged</span>
                {" and removed from safe reuse."}
              </>
            )}
          </p>
        </div>
      )}

      <div className="h-[70vh] rounded-lg border border-[var(--border-default)] bg-[var(--bg)]">
        {isLoading ? (
          <div className="flex h-full items-center justify-center text-sm text-[var(--text-tertiary)]">Loading ledger…</div>
        ) : empty ? (
          <div className="flex h-full flex-col items-center justify-center gap-2 text-center text-sm text-[var(--text-tertiary)]">
            <span>No precedent lineage yet.</span>
            <span className="max-w-md text-xs">
              A lineage appears when an autopilot decision reuses a human precedent (its <code>precedent_refs</code> point at an
              earlier decision). Run the same PRD class twice — the second run&apos;s auto-resolution links back here.
            </span>
          </div>
        ) : (
          <ReactFlow
            colorMode="dark"
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodeClick={onNodeClick}
            onNodeMouseEnter={(_, n) => setFocusNode(n.id)}
            onNodeMouseLeave={() => setFocusNode(null)}
            fitView
            minZoom={0.2}
            proOptions={{ hideAttribution: true }}
          >
            <Background gap={24} color="var(--border-muted)" />
            <Controls showInteractive={false} />
          </ReactFlow>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value, success, danger }: { label: string; value: number; success?: boolean; danger?: boolean }) {
  return (
    <span
      className="rounded-md border px-2.5 py-1"
      style={{
        borderColor: danger ? "var(--danger)" : success ? "var(--success)" : "var(--border-default)",
        color: danger ? "var(--danger)" : success ? "var(--success)" : undefined,
      }}
    >
      <span className="font-semibold text-[var(--text)]">{value}</span> {label}
    </span>
  );
}
