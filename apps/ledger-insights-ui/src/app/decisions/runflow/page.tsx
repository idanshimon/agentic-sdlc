"use client";
/**
 * Run Flow — per-run stage timeline, Cytoscape rendering (matches lineage-v2).
 * Pick a run; a blue stage spine lays out left→right with decision cards under
 * each stage. Click a decision → quick-view modal. Click background → reset.
 * Nodes locked (audit view). The /decisions table is never touched.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import cytoscape, { type Core, type NodeSingular } from "cytoscape";
import dagre from "cytoscape-dagre";
import { Workflow, User, Bot, ShieldAlert, Flag, X, ExternalLink } from "lucide-react";
import { useDecisions } from "@/lib/hooks/use-runs";
import { PageHeader } from "@/components/layout/page-header";
import { buildRunFlow, runIdsFrom } from "@/lib/graph/build-runflow";
import { runFlowToCyElements } from "@/lib/graph/cy-runflow";

if (typeof cytoscape === "function" && !(cytoscape as unknown as { _dagre?: boolean })._dagre) {
  cytoscape.use(dagre);
  (cytoscape as unknown as { _dagre?: boolean })._dagre = true;
}

const CY_STYLE = ([
  {
    selector: "node",
    style: {
      "font-family": "var(--font-geist-sans), system-ui, sans-serif",
      "font-size": 10,
      color: "#E6EDF3",
      "text-wrap": "wrap",
      "text-max-width": "150px",
      "text-valign": "center",
      "text-halign": "center",
      "border-width": 1.5,
    },
  },
  // stage spine node — blue pill
  {
    selector: "node.stage",
    style: {
      shape: "round-rectangle",
      "background-color": "#0C1A2400",
      "background-opacity": 0.15,
      "border-color": "#0EA5E9",
      "border-width": 1.5,
      color: "#38BDF8",
      "font-size": 11,
      "font-weight": 600,
      width: 130,
      height: 40,
      label: "data(label)",
    },
  },
  // agent decision — blue card
  {
    selector: "node.decision.agent",
    style: {
      shape: "round-rectangle",
      "background-color": "#161D26",
      "border-color": "#0EA5E9",
      width: 200,
      height: 58,
      "text-max-width": "178px",
      label: "data(label)",
    },
  },
  // human decision — green card
  {
    selector: "node.decision.human",
    style: {
      shape: "round-rectangle",
      "background-color": "#161D26",
      "border-color": "#22C55E",
      width: 200,
      height: 58,
      "text-max-width": "178px",
      label: "data(label)",
    },
  },
  { selector: "node.flagged", style: { "border-color": "#EF4444", "border-width": 2.5 } },
  { selector: "node.phi", style: { "background-color": "#1A1520" } },
  {
    selector: "edge",
    style: {
      width: 1,
      "line-color": "#475569",
      "target-arrow-color": "#475569",
      "target-arrow-shape": "triangle",
      "curve-style": "bezier",
      opacity: 0.5,
    },
  },
  // spine edge (stage→stage) — solid blue
  {
    selector: 'edge[relation = "of_class"]',
    style: { width: 2, "line-color": "#0EA5E9", "target-arrow-color": "#0EA5E9", opacity: 0.9 },
  },
  // leaf edge (stage→decision) — dashed
  {
    selector: 'edge[relation = "in_run"]',
    style: { "line-style": "dashed", "line-color": "#334155", "target-arrow-shape": "none", opacity: 0.7 },
  },
  { selector: ".focused", style: { opacity: 1, "z-index": 10 } },
  { selector: ".dimmed", style: { opacity: 0.12, "text-opacity": 0.12 } },
  {
    selector: "node.sel",
    style: { "border-color": "#0EA5E9", "border-width": 3, "overlay-color": "#0EA5E9", "overlay-opacity": 0.12, "overlay-padding": 6 },
  },
] as unknown) as cytoscape.StylesheetStyle[];

interface PanelData {
  full: string;
  actorKind: string;
  ambiguityClass: string;
  flagged: boolean;
  phiHigh: boolean;
  entryId: string;
}

export default function RunFlowPage() {
  const router = useRouter();
  const { data, isLoading } = useDecisions({ limit: 200 });
  const entries = useMemo(() => data?.entries ?? [], [data]);
  const runIds = useMemo(() => runIdsFrom(entries), [entries]);

  const [runId, setRunId] = useState<string | null>(null);
  useEffect(() => {
    if (!runId && runIds.length) setRunId(runIds[0]);
  }, [runIds, runId]);

  const graph = useMemo(() => (runId ? buildRunFlow(entries, runId) : null), [entries, runId]);
  const elements = useMemo(() => (graph ? runFlowToCyElements(graph) : []), [graph]);

  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const [panel, setPanel] = useState<PanelData | null>(null);

  useEffect(() => {
    if (!containerRef.current || elements.length === 0) return;
    const cy = cytoscape({
      container: containerRef.current,
      elements: elements as cytoscape.ElementDefinition[],
      style: CY_STYLE,
      minZoom: 0.2,
      maxZoom: 2.5,
      wheelSensitivity: 0.2,
      autoungrabify: true,
      boxSelectionEnabled: false,
    });
    cyRef.current = cy;

    cy.layout({
      name: "dagre",
      rankDir: "LR",
      nodeSep: 24,
      rankSep: 90,
      ranker: "network-simplex",
      animate: false,
      fit: true,
      padding: 40,
    } as cytoscape.LayoutOptions).run();

    const resetView = () => {
      cy.elements().removeClass("focused dimmed sel");
      cy.animate({ fit: { eles: cy.elements(), padding: 40 }, duration: 250 });
      setPanel(null);
    };

    cy.on("tap", (evt) => {
      if (evt.target === cy) resetView();
    });

    cy.on("tap", "node.decision", (evt) => {
      const n = evt.target as NodeSingular;
      const focused = n.closedNeighborhood();
      cy.elements().addClass("dimmed").removeClass("focused sel");
      focused.removeClass("dimmed").addClass("focused");
      n.addClass("sel");
      setPanel({
        full: String(n.data("full") || n.data("label")),
        actorKind: String(n.data("actorKind") || "agent"),
        ambiguityClass: String(n.data("ambiguityClass") || ""),
        flagged: Number(n.data("flagged")) === 1,
        phiHigh: Number(n.data("phiHigh")) === 1,
        entryId: String(n.data("entryId") || n.id()),
      });
    });

    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [elements]);

  const closeModal = () => {
    setPanel(null);
    cyRef.current?.elements().removeClass("focused dimmed sel");
    cyRef.current?.animate({ fit: { eles: cyRef.current.elements(), padding: 40 }, duration: 250 });
  };

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
            <option key={id} value={id}>{id}</option>
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

      <div className="relative h-[70vh] overflow-hidden rounded-lg border border-[var(--border-default)] bg-[var(--bg)]">
        {isLoading ? (
          <div className="flex h-full items-center justify-center text-sm text-[var(--text-tertiary)]">Loading ledger…</div>
        ) : !runId || elements.length === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-[var(--text-tertiary)]">
            No runs in this ledger scope yet. Submit a run from the Runs page.
          </div>
        ) : (
          <>
            <div ref={containerRef} className="h-full w-full" />
            <div className="pointer-events-none absolute left-3 top-3 flex flex-col gap-1 rounded-md border border-[var(--border-default)] bg-[var(--surface)]/90 px-3 py-2 text-[11px] text-[var(--text-secondary)]">
              <span className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-2.5 rounded-sm border-2 border-[#0EA5E9]" /> Stage / agent</span>
              <span className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-2.5 rounded-sm border-2 border-[#22C55E]" /> Human decision</span>
              <span className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-2.5 rounded-sm border-2 border-[#EF4444]" /> Flagged</span>
            </div>
            {panel && (
              <div className="absolute inset-0 z-20 flex items-center justify-center bg-black/50 p-6" onClick={closeModal}>
                <div className="w-[440px] max-w-full rounded-xl border border-[var(--border-default)] bg-[var(--surface)] p-5 shadow-2xl" onClick={(e) => e.stopPropagation()}>
                  <div className="mb-3 flex items-start justify-between gap-2">
                    <span className="flex items-center gap-1.5 text-[12px] font-medium text-[var(--text-secondary)]">
                      {panel.actorKind === "agent" ? <Bot className="h-4 w-4 text-[var(--plane-pipeline)]" /> : <User className="h-4 w-4 text-[var(--plane-ledger)]" />}
                      {panel.actorKind === "agent" ? "agent" : "human"}
                    </span>
                    <button onClick={closeModal} className="text-[var(--text-tertiary)] hover:text-[var(--text)]"><X className="h-4 w-4" /></button>
                  </div>
                  <div className="mb-2.5 flex flex-wrap gap-1.5">
                    {panel.flagged && <span className="inline-flex items-center gap-1 rounded-full bg-[var(--danger)]/15 px-2 py-0.5 text-[10px] text-[var(--danger)]"><Flag className="h-2.5 w-2.5" /> flagged</span>}
                    {panel.phiHigh && <span className="inline-flex items-center gap-1 rounded-full bg-[var(--danger)]/15 px-2 py-0.5 text-[10px] text-[var(--danger)]"><ShieldAlert className="h-2.5 w-2.5" /> PHI high</span>}
                  </div>
                  <p className="mb-3 text-[15px] font-medium leading-snug text-[var(--text)]">{panel.full}</p>
                  {panel.ambiguityClass && (
                    <div className="mb-4"><span className="rounded-full bg-[var(--overlay)] px-2 py-0.5 text-[10px] text-[var(--text-secondary)]">{panel.ambiguityClass}</span></div>
                  )}
                  <button
                    onClick={() => router.push(`/decisions#decision-${panel.entryId}`)}
                    className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border-default)] bg-[var(--elevated)] px-3 py-1.5 text-[12px] text-[var(--text)] hover:border-[var(--plane-pipeline)]"
                  >
                    <ExternalLink className="h-3.5 w-3.5" /> Open full record
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value, danger }: { label: string; value: number; danger?: boolean }) {
  return (
    <span className="rounded-md border px-2.5 py-1" style={{ borderColor: danger ? "var(--danger)" : "var(--border-default)", color: danger ? "var(--danger)" : undefined }}>
      <span className="font-semibold text-[var(--text)]">{value}</span> {label}
    </span>
  );
}
