"use client";
/**
 * Precedent Lineage v2 — Cytoscape.js spike (feature-flagged, additive).
 *
 * Proves the gpt-5.6-sol library-switch thesis on the REAL ledger data:
 *   - native compound nodes = precedent lanes (no manual band math)
 *   - stylesheet theming = distinct silhouettes per entity type
 *   - click-to-focus via neighborhood()/successors()/predecessors()
 *   - dagre deterministic layout
 *   - detail side-panel on select (rich content lives here, not in canvas nodes)
 *
 * The react-flow /decisions/lineage view is UNCHANGED and still the default.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import cytoscape, { type Core, type NodeSingular } from "cytoscape";
import dagre from "cytoscape-dagre";
import { GitBranch, User, Bot, ShieldAlert, Flag, X, ExternalLink } from "lucide-react";
import { useDecisions } from "@/lib/hooks/use-runs";
import { PageHeader } from "@/components/layout/page-header";
import { buildPrecedentLineage } from "@/lib/graph/build-lineage";
import { lineageToCyElements } from "@/lib/graph/cy-lineage";

if (typeof cytoscape === "function" && !(cytoscape as unknown as { _dagre?: boolean })._dagre) {
  cytoscape.use(dagre);
  (cytoscape as unknown as { _dagre?: boolean })._dagre = true;
}

// ── dark-theme stylesheet: distinct silhouette per entity type ──
const CY_STYLE = ([
  {
    selector: "node",
    style: {
      "font-family": "var(--font-geist-sans), system-ui, sans-serif",
      "font-size": 11,
      color: "#E6EDF3",
      "text-wrap": "wrap",
      "text-max-width": "150px",
      "text-valign": "center",
      "text-halign": "center",
      "border-width": 1.5,
    },
  },
  // compound lane container
  {
    selector: "node.lane",
    style: {
      shape: "round-rectangle",
      "background-color": "#11161D",
      "background-opacity": 0.6,
      "border-color": "#243042",
      "border-width": 1,
      label: "data(label)",
      "text-valign": "top",
      "text-halign": "left",
      "text-margin-y": 14,
      "text-margin-x": 14,
      "text-max-width": "220px",
      "font-size": 11,
      "font-weight": 600,
      color: "#9FB0C3",
      padding: "40px",
    },
  },
  // human precedent — shield-ish hexagon, green
  {
    selector: "node.precedent",
    style: {
      shape: "round-hexagon",
      "background-color": "#161D26",
      "border-color": "#22C55E",
      "border-width": 2,
      width: 190,
      height: 74,
      "font-size": 10,
      "text-max-width": "150px",
      label: "data(label)",
    },
  },
  // agent decision — rounded rectangle, blue
  {
    selector: "node.agent",
    style: {
      shape: "round-rectangle",
      "background-color": "#161D26",
      "border-color": "#0EA5E9",
      width: 190,
      height: 58,
      "font-size": 10,
      "text-max-width": "168px",
      label: "data(label)",
    },
  },
  // teaching signal — small round satellite
  {
    selector: "node.teaching",
    style: {
      shape: "ellipse",
      "background-color": "#161D26",
      "border-color": "#22C55E",
      width: 20,
      height: 20,
      "font-size": 9,
      label: "data(label)",
      "text-valign": "bottom",
      "text-margin-y": 4,
    },
  },
  // flagged overrides border → danger red
  {
    selector: "node.flagged",
    style: { "border-color": "#EF4444", "border-width": 2.5 },
  },
  // phi tint
  {
    selector: "node.phi",
    style: { "background-color": "#1A1520" },
  },
  // edges
  {
    selector: "edge",
    style: {
      width: 1,
      "line-color": "#475569",
      "target-arrow-color": "#475569",
      "target-arrow-shape": "triangle",
      "curve-style": "bezier",
      opacity: 0.55,
    },
  },
  {
    selector: 'edge[relation = "reuses"]',
    style: {
      width: 2.5,
      "line-color": "#22C55E",
      "target-arrow-color": "#22C55E",
      label: "data(label)",
      "font-size": 9,
      color: "#22C55E",
      "text-background-color": "#0B0F14",
      "text-background-opacity": 0.85,
      "text-background-padding": "2px",
      opacity: 0.9,
    },
  },
  {
    selector: 'edge[relation = "teaches"]',
    style: { "line-style": "dashed", "line-color": "#F59E0B", "target-arrow-color": "#F59E0B", width: 1.5 },
  },
  // focus / dim states
  {
    selector: ".focused",
    style: { opacity: 1, "z-index": 10 },
  },
  {
    selector: ".dimmed",
    style: { opacity: 0.12, "text-opacity": 0.12 },
  },
  {
    selector: "node.sel",
    style: { "border-color": "#0EA5E9", "border-width": 3, "overlay-color": "#0EA5E9", "overlay-opacity": 0.12, "overlay-padding": 6 },
  },
] as unknown) as cytoscape.StylesheetStyle[];

interface PanelData {
  id: string;
  label: string;
  full: string;
  role: string;
  actorKind: string;
  ambiguityClass: string;
  rule: string;
  flagged: boolean;
  phiHigh: boolean;
  isRoot: boolean;
  entryId: string;
  upstream: string[];
  downstream: string[];
}

export default function LineageV2Page() {
  const router = useRouter();
  const { data, isLoading } = useDecisions({ limit: 200 });
  const entries = useMemo(() => data?.entries ?? [], [data]);
  const graph = useMemo(() => buildPrecedentLineage(entries), [entries]);
  const elements = useMemo(() => lineageToCyElements(graph), [graph]);

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
      autoungrabify: true, // audit view — nodes are not draggable (stable layout)
      boxSelectionEnabled: false,
    });
    cyRef.current = cy;

    // dagre left→right DAG — clean lineage flow, no compound overlap
    cy.layout({
      name: "dagre",
      rankDir: "LR",
      nodeSep: 34,
      rankSep: 120,
      edgeSep: 12,
      ranker: "network-simplex",
      animate: false,
      fit: true,
      padding: 48,
    } as cytoscape.LayoutOptions).run();

    const resetView = () => {
      cy.elements().removeClass("focused dimmed sel");
      cy.animate({ fit: { eles: cy.elements(), padding: 48 }, duration: 300 });
      setPanel(null);
    };

    cy.on("tap", (evt) => {
      if (evt.target === cy) resetView();
    });

    cy.on("tap", "node.agent, node.precedent", (evt) => {
      const n = evt.target as NodeSingular;
      focusNode(n);
    });

    // demo hook: auto-focus a node so a headless screenshot can show focus mode
    if (typeof window !== "undefined" && window.location.search.includes("demo=focus")) {
      const target = cy.nodes("node.precedent").first();
      if (target.nonempty()) setTimeout(() => focusNode(target as NodeSingular), 400);
    }

    function focusNode(n: NodeSingular) {
      const focused = n
        .closedNeighborhood()
        .union(n.predecessors())
        .union(n.successors());
      cy.elements().addClass("dimmed").removeClass("focused sel");
      focused.removeClass("dimmed").addClass("focused");
      n.addClass("sel");
      n.parent().removeClass("dimmed");

      const up = n.incomers('edge[relation = "reuses"]').sources().map((s) => String(s.data("label")));
      const down = n.outgoers('edge[relation = "reuses"]').targets().map((t) => String(t.data("label")));
      setPanel({
        id: String(n.id()),
        label: String(n.data("label")),
        full: String(n.data("full") || n.data("label")),
        role: String(n.data("role") || ""),
        actorKind: String(n.data("actorKind") || "agent"),
        ambiguityClass: String(n.data("ambiguityClass") || ""),
        rule: String(n.data("rule") || ""),
        flagged: Number(n.data("flagged")) === 1,
        phiHigh: Number(n.data("phiHigh")) === 1,
        isRoot: Number(n.data("isRoot")) === 1,
        entryId: String(n.data("entryId") || n.id()),
        upstream: up,
        downstream: down,
      });
    }

    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [elements]);

  const empty = !isLoading && graph.nodes.length === 0;

  return (
    <div className="space-y-4">
      <PageHeader
        plane="ledger"
        title={
          <span className="flex items-center gap-2">
            <GitBranch className="h-5 w-5" /> Precedent Lineage
            <span className="rounded-full bg-[var(--plane-pipeline)]/15 px-2 py-0.5 text-[10px] font-semibold text-[var(--plane-pipeline)]">v2 · Cytoscape</span>
          </span>
        }
        description="Cytoscape spike: precedent lanes are native compound nodes; click any decision to focus its learning-loop neighborhood (upstream precedent + downstream reuse) and open its record."
      />

      <div className="relative h-[74vh] overflow-hidden rounded-lg border border-[var(--border-default)] bg-[var(--bg)]">
        {isLoading ? (
          <div className="flex h-full items-center justify-center text-sm text-[var(--text-tertiary)]">Loading ledger…</div>
        ) : empty ? (
          <div className="flex h-full items-center justify-center text-sm text-[var(--text-tertiary)]">No precedent lineage yet.</div>
        ) : (
          <>
            <div ref={containerRef} className="h-full w-full" />
            {/* legend */}
            <div className="pointer-events-none absolute left-3 top-3 flex flex-col gap-1 rounded-md border border-[var(--border-default)] bg-[var(--surface)]/90 px-3 py-2 text-[11px] text-[var(--text-secondary)]">
              <span className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-2.5 rounded-sm border-2 border-[#22C55E]" /> Human precedent</span>
              <span className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-2.5 rounded-sm border-2 border-[#0EA5E9]" /> Agent decision</span>
              <span className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-2.5 rounded-sm border-2 border-[#EF4444]" /> Flagged</span>
            </div>
            {/* quick-view modal — centered, dims graph behind it */}
            {panel && (
              <div
                className="absolute inset-0 z-20 flex items-center justify-center bg-black/50 p-6"
                onClick={() => { setPanel(null); cyRef.current?.elements().removeClass("focused dimmed sel"); cyRef.current?.animate({ fit: { eles: cyRef.current.elements(), padding: 48 }, duration: 250 }); }}
              >
                <div
                  className="w-[440px] max-w-full rounded-xl border border-[var(--border-default)] bg-[var(--surface)] p-5 shadow-2xl"
                  onClick={(e) => e.stopPropagation()}
                >
                  <div className="mb-3 flex items-start justify-between gap-2">
                    <span className="flex items-center gap-1.5 text-[12px] font-medium text-[var(--text-secondary)]">
                      {panel.actorKind === "agent" ? <Bot className="h-4 w-4 text-[var(--plane-pipeline)]" /> : <User className="h-4 w-4 text-[var(--plane-ledger)]" />}
                      {panel.role}
                    </span>
                    <button onClick={() => { setPanel(null); cyRef.current?.elements().removeClass("focused dimmed sel"); cyRef.current?.animate({ fit: { eles: cyRef.current.elements(), padding: 48 }, duration: 250 }); }} className="text-[var(--text-tertiary)] hover:text-[var(--text)]">
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                  <div className="mb-2.5 flex flex-wrap gap-1.5">
                    {panel.isRoot && <span className="rounded-full bg-[var(--success)]/15 px-2 py-0.5 text-[10px] text-[var(--success)]">human precedent</span>}
                    {panel.flagged && <span className="inline-flex items-center gap-1 rounded-full bg-[var(--danger)]/15 px-2 py-0.5 text-[10px] text-[var(--danger)]"><Flag className="h-2.5 w-2.5" /> flagged</span>}
                    {panel.phiHigh && <span className="inline-flex items-center gap-1 rounded-full bg-[var(--danger)]/15 px-2 py-0.5 text-[10px] text-[var(--danger)]"><ShieldAlert className="h-2.5 w-2.5" /> PHI high</span>}
                  </div>
                  <p className="mb-3 text-[15px] font-medium leading-snug text-[var(--text)]">{panel.full || panel.label}</p>
                  <div className="mb-4 flex flex-wrap gap-1.5">
                    {panel.ambiguityClass && <span className="rounded-full bg-[var(--overlay)] px-2 py-0.5 text-[10px] text-[var(--text-secondary)]">{panel.ambiguityClass}</span>}
                    {panel.rule && <span className="mono rounded bg-[var(--overlay)] px-1.5 py-0.5 text-[10px] text-[var(--secondary)]">{panel.rule}</span>}
                  </div>
                  {(panel.upstream.length > 0 || panel.downstream.length > 0) && (
                    <div className="mb-4 grid grid-cols-2 gap-3 border-t border-[var(--border-default)] pt-3">
                      <div>
                        <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">Reused from</div>
                        {panel.upstream.length ? panel.upstream.map((u, i) => <div key={i} className="text-[12px] text-[var(--text-secondary)]">← {u}</div>) : <div className="text-[12px] text-[var(--text-tertiary)]">—</div>}
                      </div>
                      <div>
                        <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">Reused by</div>
                        {panel.downstream.length ? panel.downstream.map((u, i) => <div key={i} className="text-[12px] text-[var(--text-secondary)]">→ {u}</div>) : <div className="text-[12px] text-[var(--text-tertiary)]">—</div>}
                      </div>
                    </div>
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
