"use client";
/**
 * Decision Map — cross-run governance network, Cytoscape rendering.
 * The "how does it all connect" lens. Uses fcose (organic force) layout since
 * it's a network hairball, keeps the edge-family filter toolbar + flagged focus,
 * click-to-focus neighborhood + quick-view modal. /decisions table untouched.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import cytoscape, { type Core, type NodeSingular } from "cytoscape";
import fcose from "cytoscape-fcose";
import { Scale, User, Bot, ShieldAlert, Flag, X, ExternalLink } from "lucide-react";
import { useDecisions } from "@/lib/hooks/use-runs";
import { PageHeader } from "@/components/layout/page-header";
import { buildGovernanceNetwork, type GraphEdgeKind } from "@/lib/graph/build-graph";
import { applyMapFilters, defaultMapFilters } from "@/lib/graph/map-filters";
import { mapToCyElements } from "@/lib/graph/cy-map";

if (typeof cytoscape === "function" && !(cytoscape as unknown as { _fcose?: boolean })._fcose) {
  cytoscape.use(fcose);
  (cytoscape as unknown as { _fcose?: boolean })._fcose = true;
}

const CY_STYLE = ([
  {
    selector: "node",
    style: {
      "font-family": "var(--font-geist-sans), system-ui, sans-serif",
      "font-size": 9,
      color: "#C9D4E0",
      "text-wrap": "wrap",
      "text-max-width": "90px",
      "text-valign": "center",
      "text-halign": "center",
      "border-width": 1.5,
    },
  },
  // bundle / rule hub — amber diamond, sized by degree
  {
    selector: "node.bundle",
    style: {
      shape: "round-diamond",
      "background-color": "#1C1710",
      "border-color": "#F59E0B",
      color: "#FBBF24",
      "font-size": 10,
      width: "mapData(degree, 0, 8, 44, 120)",
      height: "mapData(degree, 0, 8, 44, 120)",
      label: "data(label)",
    },
  },
  // ambiguity class — blue hexagon
  {
    selector: "node.klass",
    style: { shape: "round-hexagon", "background-color": "#0F1822", "border-color": "#0EA5E9", color: "#38BDF8", width: 74, height: 52, label: "data(label)" },
  },
  // decision — green/blue small card
  {
    selector: "node.decision",
    style: { shape: "round-rectangle", "background-color": "#161D26", "border-color": "#22C55E", width: 96, height: 40, label: "data(label)" },
  },
  // run — grey pill
  {
    selector: "node.run",
    style: { shape: "round-rectangle", "background-color": "#12161C", "border-color": "#475569", color: "#94A3B8", width: 70, height: 30, label: "data(label)" },
  },
  // teaching — small warning dot
  {
    selector: "node.teaching",
    style: { shape: "ellipse", "background-color": "#1C1710", "border-color": "#F59E0B", width: 24, height: 24, "font-size": 8, label: "data(label)" },
  },
  { selector: "node.flagged", style: { "border-color": "#EF4444", "border-width": 2.5 } },
  { selector: "node.phi", style: { "background-color": "#1A1520" } },
  {
    selector: "edge",
    style: { width: 1, "line-color": "#334155", "curve-style": "bezier", opacity: 0.4, "target-arrow-shape": "none" },
  },
  { selector: 'edge[relation = "reuses"]', style: { width: 2, "line-color": "#22C55E", opacity: 0.9, label: "data(label)", "font-size": 8, color: "#22C55E", "target-arrow-shape": "triangle", "target-arrow-color": "#22C55E" } },
  { selector: 'edge[relation = "teaches"]', style: { "line-color": "#F59E0B", opacity: 0.6 } },
  { selector: 'edge[relation = "grounded_in"]', style: { "line-style": "dashed", "line-color": "#475569" } },
  { selector: 'edge[relation = "same_slot"]', style: { "line-style": "dashed", "line-color": "#0EA5E9", opacity: 0.5 } },
  { selector: ".focused", style: { opacity: 1, "z-index": 10 } },
  { selector: ".dimmed", style: { opacity: 0.1, "text-opacity": 0.1 } },
  { selector: "node.sel", style: { "border-color": "#0EA5E9", "border-width": 3, "overlay-color": "#0EA5E9", "overlay-opacity": 0.12, "overlay-padding": 6 } },
] as unknown) as cytoscape.StylesheetStyle[];

interface PanelData {
  full: string;
  kind: string;
  actorKind: string;
  flagged: boolean;
  phiHigh: boolean;
  entryId: string;
}

export default function DecisionsMapPage() {
  const router = useRouter();
  const { data, isLoading } = useDecisions({ limit: 200 });
  const entries = useMemo(() => data?.entries ?? [], [data]);

  const [edgeKinds, setEdgeKinds] = useState<Set<GraphEdgeKind>>(() => defaultMapFilters().edgeKinds);
  const [onlyFlagged, setOnlyFlagged] = useState(false);

  const toggleEdge = (k: GraphEdgeKind) =>
    setEdgeKinds((prev) => {
      const next = new Set(prev);
      if (next.has(k)) next.delete(k); else next.add(k);
      return next;
    });

  const graph = useMemo(() => {
    const full = buildGovernanceNetwork(entries);
    return applyMapFilters(full, { ...defaultMapFilters(), edgeKinds, onlyFlagged });
  }, [entries, edgeKinds, onlyFlagged]);
  const elements = useMemo(() => mapToCyElements(graph), [graph]);

  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const [panel, setPanel] = useState<PanelData | null>(null);

  useEffect(() => {
    if (!containerRef.current || elements.length === 0) return;
    const cy = cytoscape({
      container: containerRef.current,
      elements: elements as cytoscape.ElementDefinition[],
      style: CY_STYLE,
      minZoom: 0.1,
      maxZoom: 2.5,
      wheelSensitivity: 0.2,
      autoungrabify: true,
      boxSelectionEnabled: false,
    });
    cyRef.current = cy;

    cy.layout({
      name: "fcose",
      quality: "default",
      animate: false,
      randomize: true,
      nodeSeparation: 90,
      idealEdgeLength: 90,
      nodeRepulsion: 6500,
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

    cy.on("tap", "node", (evt) => {
      const n = evt.target as NodeSingular;
      const focused = n.closedNeighborhood();
      cy.elements().addClass("dimmed").removeClass("focused sel");
      focused.removeClass("dimmed").addClass("focused");
      n.addClass("sel");
      setPanel({
        full: String(n.data("full") || n.data("label")),
        kind: String(n.data("kind") || ""),
        actorKind: String(n.data("actorKind") || ""),
        flagged: Number(n.data("flagged")) === 1,
        phiHigh: Number(n.data("phiHigh")) === 1,
        entryId: String(n.data("entryId") || ""),
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
        plane="ledger"
        title={
          <span className="flex items-center gap-2">
            <Scale className="h-5 w-5" /> Decision Map
          </span>
        }
        description="How decisions, rules, runs and teaching connect. Green edges are the learning loop — an autopilot decision reusing a human's precedent. Click any node to focus its neighborhood and open its record."
      />

      <div className="flex flex-wrap gap-3 text-xs text-[var(--text-secondary)]">
        <Stat label="Decisions" value={graph.stats.decisions} />
        <Stat label="Rules cited" value={graph.stats.bundles} />
        <Stat label="Runs" value={graph.stats.runs} />
        <Stat label="Teaching signals" value={graph.stats.teachingSignals} />
        <Stat label="Learning-loop edges" value={graph.stats.reuseEdges} highlight />
        <Stat label="Flagged" value={graph.stats.flagged} danger />
      </div>

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

      <div className="relative h-[70vh] overflow-hidden rounded-lg border border-[var(--border-default)] bg-[var(--bg)]">
        {isLoading ? (
          <div className="flex h-full items-center justify-center text-sm text-[var(--text-tertiary)]">Loading ledger…</div>
        ) : graph.nodes.length === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-[var(--text-tertiary)]">
            No decisions in this ledger scope yet. Submit a run, or check the team token — decisions are team-partitioned.
          </div>
        ) : (
          <>
            <div ref={containerRef} className="h-full w-full" />
            <div className="pointer-events-none absolute left-3 top-3 flex flex-col gap-1 rounded-md border border-[var(--border-default)] bg-[var(--surface)]/90 px-3 py-2 text-[11px] text-[var(--text-secondary)]">
              <span className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-2.5 rotate-45 border-2 border-[#F59E0B]" /> Rule hub</span>
              <span className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-2.5 rounded-sm border-2 border-[#0EA5E9]" /> Ambiguity class</span>
              <span className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-2.5 rounded-sm border-2 border-[#22C55E]" /> Decision</span>
              <span className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-2.5 rounded-sm border-2 border-[#EF4444]" /> Flagged</span>
            </div>
            {panel && (
              <div className="absolute inset-0 z-20 flex items-center justify-center bg-black/50 p-6" onClick={closeModal}>
                <div className="w-[440px] max-w-full rounded-xl border border-[var(--border-default)] bg-[var(--surface)] p-5 shadow-2xl" onClick={(e) => e.stopPropagation()}>
                  <div className="mb-3 flex items-start justify-between gap-2">
                    <span className="flex items-center gap-1.5 text-[12px] font-medium text-[var(--text-secondary)]">
                      {panel.kind === "decision" ? (panel.actorKind === "agent" ? <Bot className="h-4 w-4 text-[var(--plane-pipeline)]" /> : <User className="h-4 w-4 text-[var(--plane-ledger)]" />) : null}
                      {panel.kind}{panel.kind === "decision" && panel.actorKind ? ` · ${panel.actorKind}` : ""}
                    </span>
                    <button onClick={closeModal} className="text-[var(--text-tertiary)] hover:text-[var(--text)]"><X className="h-4 w-4" /></button>
                  </div>
                  <div className="mb-2.5 flex flex-wrap gap-1.5">
                    {panel.flagged && <span className="inline-flex items-center gap-1 rounded-full bg-[var(--danger)]/15 px-2 py-0.5 text-[10px] text-[var(--danger)]"><Flag className="h-2.5 w-2.5" /> flagged</span>}
                    {panel.phiHigh && <span className="inline-flex items-center gap-1 rounded-full bg-[var(--danger)]/15 px-2 py-0.5 text-[10px] text-[var(--danger)]"><ShieldAlert className="h-2.5 w-2.5" /> PHI high</span>}
                  </div>
                  <p className="mb-4 text-[15px] font-medium leading-snug text-[var(--text)]">{panel.full}</p>
                  {panel.entryId && (
                    <button
                      onClick={() => router.push(`/decisions#decision-${panel.entryId}`)}
                      className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border-default)] bg-[var(--elevated)] px-3 py-1.5 text-[12px] text-[var(--text)] hover:border-[var(--plane-pipeline)]"
                    >
                      <ExternalLink className="h-3.5 w-3.5" /> Open full record
                    </button>
                  )}
                </div>
              </div>
            )}
          </>
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
