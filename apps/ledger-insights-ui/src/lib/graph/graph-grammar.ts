/**
 * Shared visual grammar for every decision-graph surface.
 *
 * WHY THIS EXISTS
 * Three graph views (map, lineage, run flow) previously each invented their own
 * node shapes, edge colors and focus behaviour. Four node kinds and six edge
 * kinds were encoded in color alone, with no legend on any view reachable from
 * the nav. An operator could see structure but could not decode it.
 *
 * This module is the single source of truth for what a graph *means*. Both the
 * Cytoscape stylesheets and the on-screen <GraphLegend> read from it, so the
 * legend cannot drift from what is actually drawn — the failure mode of every
 * hand-maintained legend.
 *
 * THE FOUR RULES
 *   G1  Weak class anchoring — neighborhoods emerge from pull, not from drawn
 *       lane rectangles. Structure without chrome.
 *   G2  Dual-channel node encoding, never mixed. Core color = decision state.
 *       Border color = governing plane. Size = reuse degree (sublinear).
 *   G3  Typed edges own a color AND a weight. Authored relations draw solid and
 *       tight; inferred/structural relations draw dashed and slack. Provenance
 *       becomes visible in the shape of the graph, not just its palette.
 *   G4  Focus dims, never hides. Selection raises a neighborhood and drops the
 *       rest to low alpha. Nothing disappears, so spatial bearings survive.
 *
 * All color values resolve through `CanvasTheme` (read off live CSS custom
 * properties) rather than hard-coded hex, so graphs track the active theme.
 */
import type { CanvasTheme } from "./canvas-theme";

// ─────────────────────────────────────────────────────────────────────────────
// G2 — node encoding
// ─────────────────────────────────────────────────────────────────────────────

/** What a node IS. Drives silhouette (shape), never color. */
export type NodeKind = "decision" | "precedent" | "stage" | "class" | "teaching";

/** What state a decision is IN. Drives core color, never shape. */
export type DecisionState = "endorsed" | "flagged" | "gating" | "neutral";

export const NODE_SHAPE: Record<NodeKind, string> = {
  // A human ruling is a shield. It is the thing later decisions hide behind.
  precedent: "round-hexagon",
  // An agent decision is a plain card.
  decision: "round-rectangle",
  // A pipeline stage is a wide slab — reads as a container, not a peer.
  stage: "round-rectangle",
  // A grouping bucket, same slab family as stage.
  class: "round-rectangle",
  // A teaching signal is a small satellite orbiting what it corrected.
  teaching: "ellipse",
};

export function stateColor(state: DecisionState, t: CanvasTheme): string {
  switch (state) {
    case "endorsed":
      return t.success;
    case "flagged":
      return t.danger;
    case "gating":
      return t.warning;
    default:
      return t.primary;
  }
}

/**
 * G2 — size encodes reuse degree, sublinearly.
 *
 * Linear sizing lets one hub with 40 reuses swamp a canvas where the median is
 * 2. sqrt compresses the top end so hubs read as "bigger" without erasing
 * everything else.
 */
export function nodeSize(degree: number, base = 46, cap = 108): number {
  return Math.min(cap, base + Math.sqrt(Math.max(0, degree)) * 13);
}

// ─────────────────────────────────────────────────────────────────────────────
// G3 — edge encoding
// ─────────────────────────────────────────────────────────────────────────────

export type EdgeKind =
  | "reuses"       // authored: this decision cited that precedent
  | "teaches"      // authored: a human corrected this decision
  | "grounded_in"  // authored: decision bound to a standards bundle
  | "in_run"       // structural: decision belongs to this run/stage
  | "of_class"     // structural: spine ordering / class membership
  | "same_slot";   // inferred: same slot across runs

export interface EdgeStyle {
  /** Solid = authored by a human or an explicit citation. Dashed = derived. */
  authored: boolean;
  width: number;
  opacity: number;
  color: (t: CanvasTheme) => string;
  label: string;
}

export const EDGE_STYLE: Record<EdgeKind, EdgeStyle> = {
  reuses: {
    authored: true,
    width: 2.5,
    opacity: 0.9,
    color: (t) => t.success,
    label: "reuses precedent",
  },
  teaches: {
    authored: false, // dashed by intent: a correction, drawn as an intervention
    width: 1.75,
    opacity: 0.85,
    color: (t) => t.warning,
    label: "human correction",
  },
  grounded_in: {
    authored: true,
    width: 1.5,
    opacity: 0.7,
    color: (t) => t.planeStandards,
    label: "grounded in bundle",
  },
  of_class: {
    authored: true,
    width: 2,
    opacity: 0.75,
    color: (t) => t.planePipeline,
    label: "stage order",
  },
  in_run: {
    authored: false,
    width: 1,
    opacity: 0.45,
    color: (t) => t.border,
    label: "belongs to stage",
  },
  same_slot: {
    authored: false,
    width: 1,
    opacity: 0.3,
    color: (t) => t.border,
    label: "same slot, other run",
  },
};

// ─────────────────────────────────────────────────────────────────────────────
// G4 — focus
// ─────────────────────────────────────────────────────────────────────────────

/** Dim level for out-of-focus elements. Low, but never zero — see G4. */
export const DIM_OPACITY = 0.1;
export const DIM_TEXT_OPACITY = 0.08;

// ─────────────────────────────────────────────────────────────────────────────
// Shared stylesheet fragment
// ─────────────────────────────────────────────────────────────────────────────

/**
 * The parts of a Cytoscape stylesheet that must be identical across all graph
 * views: typography, edge typing, focus/dim states, selection ring.
 *
 * Views append their own node selectors for view-specific silhouettes; they do
 * NOT redefine edges or focus behaviour.
 */
export function baseStylesheet(t: CanvasTheme): unknown[] {
  const edgeRules = (Object.keys(EDGE_STYLE) as EdgeKind[]).map((kind) => {
    const s = EDGE_STYLE[kind];
    return {
      selector: `edge[kind = "${kind}"]`,
      style: {
        width: s.width,
        opacity: s.opacity,
        "line-color": s.color(t),
        "target-arrow-color": s.color(t),
        "line-style": s.authored ? "solid" : "dashed",
      },
    };
  });

  return [
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
    {
      selector: "edge",
      style: {
        "curve-style": "bezier",
        "target-arrow-shape": "triangle",
        "arrow-scale": 0.8,
        width: 1,
        "line-color": t.border,
        "target-arrow-color": t.border,
        opacity: 0.5,
      },
    },
    ...edgeRules,
    // G4 — focus dims, never hides.
    { selector: ".focused", style: { opacity: 1, "z-index": 10 } },
    {
      selector: ".dimmed",
      style: { opacity: DIM_OPACITY, "text-opacity": DIM_TEXT_OPACITY },
    },
    {
      selector: "node.sel",
      style: {
        "border-color": t.primary,
        "border-width": 3,
        "overlay-color": t.primary,
        "overlay-opacity": 0.12,
        "overlay-padding": 6,
      },
    },
  ];
}

// ─────────────────────────────────────────────────────────────────────────────
// Legend source of truth
// ─────────────────────────────────────────────────────────────────────────────

export interface LegendEntry {
  label: string;
  /** Resolved at render time from the same theme the canvas uses. */
  color: (t: CanvasTheme) => string;
  shape?: NodeKind;
  dashed?: boolean;
}

/** Node-kind legend rows for a given view's vocabulary. */
export const NODE_LEGEND: Record<string, LegendEntry> = {
  precedent: { label: "Human precedent", color: (t) => t.success, shape: "precedent" },
  decision: { label: "Agent decision", color: (t) => t.primary, shape: "decision" },
  flagged: { label: "Flagged by a human", color: (t) => t.danger, shape: "decision" },
  gating: { label: "Awaiting gate", color: (t) => t.warning, shape: "decision" },
  stage: { label: "Pipeline stage", color: (t) => t.planePipeline, shape: "stage" },
  teaching: { label: "Teaching signal", color: (t) => t.success, shape: "teaching" },
  // Map-view vocabulary — these are grouping hubs, not decisions.
  bundle: { label: "Rule hub", color: (t) => t.warning, shape: "class" },
  class: { label: "Ambiguity class", color: (t) => t.primary, shape: "class" },
};

/** Edge legend rows, derived from EDGE_STYLE so they cannot drift. */
export function edgeLegend(kinds: EdgeKind[]): LegendEntry[] {
  return kinds.map((k) => ({
    label: EDGE_STYLE[k].label,
    color: EDGE_STYLE[k].color,
    dashed: !EDGE_STYLE[k].authored,
  }));
}
