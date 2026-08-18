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
import { useCanvasTheme, type CanvasTheme } from "@/lib/graph/canvas-theme";
import { buildPrecedentLineage } from "@/lib/graph/build-lineage";
import { lineageToCyElements } from "@/lib/graph/cy-lineage";

if (typeof cytoscape === "function" && !(cytoscape as unknown as { _dagre?: boolean })._dagre) {
  cytoscape.use(dagre);
  (cytoscape as unknown as { _dagre?: boolean })._dagre = true;
}

// ── dark-theme stylesheet: distinct silhouette per entity type ──
/* Canvas cannot resolve CSS custom properties, so these must be literal
 * values -- resolved from live tokens at render time so lineage follows the
 * active theme instead of pinning to dark. */
const cyStyle = (t: CanvasTheme) => ([
  {
    selector: "node",
    style: {
      "font-family": "var(--font-geist-sans), system-ui, sans-serif",
      "font-size": 11,
      color: t.text,
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
      "background-color": t.surface,
      "background-opacity": 0.6,
      "border-color": t.border,
      "border-width": 1,
      label: "data(label)",
      "text-valign": "top",
      "text-halign": "left",
      "text-margin-y": 14,
      "text-margin-x": 14,
      "text-max-width": "220px",
      "font-size": 11,
      "font-weight": 600,
      color: t.textSecondary,
      padding: "40px",
    },
  },
  // human precedent — shield-ish hexagon, green
  {
    selector: "node.precedent",
    style: {
      shape: "round-hexagon",
      "background-color": t.elevated,
      "border-color": t.success,
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
      "background-color": t.elevated,
      "border-color": t.primary,
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
      "background-color": t.elevated,
      "border-color": t.success,
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
    style: { "border-color": t.danger, "border-width": 2.5 },
  },
  // phi tint
  {
    selector: "node.phi",
    style: { "background-color": t.overlay },
  },
  // edges
  {
    selector: "edge",
    style: {
      width: 1,
      "line-color": t.border,
      "target-arrow-color": t.border,
      "target-arrow-shape": "triangle",
      "curve-style": "bezier",
      opacity: 0.55,
    },
  },
  {
    selector: 'edge[relation = "reuses"]',
    style: {
      width: 2.5,
      "line-color": t.success,
      "target-arrow-color": t.success,
      label: "data(label)",
      "font-size": 9,
      color: t.success,
      "text-background-color": t.bg,
      "text-background-opacity": 0.85,
      "text-background-padding": "2px",
      opacity: 0.9,
    },
  },
  {
    selector: 'edge[relation = "teaches"]',
    style: { "line-style": "dashed", "line-color": t.warning, "target-arrow-color": t.warning, width: 1.5 },
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
    style: { "border-color": t.primary, "border-width": 3, "overlay-color": t.primary, "overlay-opacity": 0.12, "overlay-padding": 6 },
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
  const { data, isLoading } = useDecisions({ limit: 1000 });
  const entries = useMemo(() => data?.entries ?? [], [data]);
  const graph = useMemo(() => buildPrecedentLineage(entries), [entries]);
  const elements = useMemo(() => lineageToCyElements(graph), [graph]);

  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const [panel, setPanel] = useState<PanelData | null>(null);
  // Live token values — re-read on theme switch so the canvas repaints.
  const theme = useCanvasTheme();

  useEffect(() => {
    if (!containerRef.current || elements.length === 0) return;
    const cy = cytoscape({
      container: containerRef.current,
      elements: elements as cytoscape.ElementDefinition[],
      style: cyStyle(theme),
      minZoom: 0.2,
      maxZoom: 2.5,
      wheelSensitivity: 0.2,
      autoungrabify: true, // audit view — nodes are not draggable (stable layout)
      boxSelectionEnabled: false,
    });
    cyRef.current = cy;

    // Layout must match the SHAPE of real precedent, which the card_id fix
    // revealed: many INDEPENDENT 1→1 pairs (one human ruling, one later agent
    // reuse of that same decision card), not one deep or wide tree.
    //
    // Generic layouts get this wrong. dagre and breadthfirst both treat the
    // disconnected pairs as a single rank and emit one flat row that occupies a
    // ~3%-tall strip with the rest of the canvas empty. Since the topology is
    // known, position the components explicitly in a grid instead of asking a
    // force/rank algorithm to infer it.
    const roots = cy.nodes().filter((n) => n.indegree(false) === 0);
    const box = cy.container()?.getBoundingClientRect();
    const usableW = Math.max(640, (box?.width ?? 1200) - 120);
    const colW = 250;
    const rowH = 190;
    const perRow = Math.max(1, Math.floor(usableW / colW));

    roots.forEach((root, i) => {
      const col = i % perRow;
      const row = Math.floor(i / perRow);
      const x = 90 + col * colW;
      const y = 70 + row * rowH;
      root.position({ x, y });
      // Stack this root's reuses directly beneath it so the precedent → reuse
      // relationship stays readable at a glance.
      root.outgoers("node").forEach((child, j) => {
        child.position({ x, y: y + 92 + j * 46 });
      });
    });

    cy.fit(undefined, 44);
    if (cy.zoom() > 1.15) cy.zoom({ level: 1.15, position: { x: 0, y: 0 } });

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
  }, [elements, theme]);

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
        description="Where the agent's answers came from. Each hub is a human ruling; the fan below it is every later decision the agent resolved the same way. Click any node to focus its learning loop — the precedent above it and the reuse below — and open the ledger record."
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
              <span className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-2.5 rounded-sm border-2 border-[var(--success)]" /> Human precedent</span>
              <span className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-2.5 rounded-sm border-2 border-[var(--primary)]" /> Agent decision</span>
              <span className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-2.5 rounded-sm border-2 border-[var(--danger)]" /> Flagged</span>
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
                    {panel.isRoot && <span className="rounded-full bg-[color-mix(in_srgb,var(--success)_var(--tint),transparent)] px-2 py-0.5 text-[10px] text-[var(--success)]">human precedent</span>}
                    {panel.flagged && <span className="inline-flex items-center gap-1 rounded-full bg-[color-mix(in_srgb,var(--danger)_var(--tint),transparent)] px-2 py-0.5 text-[10px] text-[var(--danger)]"><Flag className="h-2.5 w-2.5" /> flagged</span>}
                    {panel.phiHigh && <span className="inline-flex items-center gap-1 rounded-full bg-[color-mix(in_srgb,var(--danger)_var(--tint),transparent)] px-2 py-0.5 text-[10px] text-[var(--danger)]"><ShieldAlert className="h-2.5 w-2.5" /> PHI high</span>}
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
