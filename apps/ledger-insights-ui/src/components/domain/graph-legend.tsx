"use client";
/**
 * The decoder ring, on every graph surface.
 *
 * Rows are generated from `graph-grammar.ts` — the same module the Cytoscape
 * stylesheets read. A legend that is written by hand drifts from the canvas the
 * first time someone changes an edge color; this one cannot.
 *
 * Collapsible because on a dense graph the legend is scaffolding: needed on
 * first read, noise on the fifth. Defaults to open — an operator who has never
 * seen the view is the one who needs it.
 */
import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { useCanvasTheme } from "@/lib/graph/canvas-theme";
import {
  NODE_LEGEND,
  edgeLegend,
  NODE_SHAPE,
  type EdgeKind,
  type LegendEntry,
} from "@/lib/graph/graph-grammar";

/** Small shape swatch mirroring the node silhouette used on canvas. */
function NodeSwatch({ entry, color }: { entry: LegendEntry; color: string }) {
  const shape = entry.shape ? NODE_SHAPE[entry.shape] : "round-rectangle";
  const base = "inline-block shrink-0 border-2";
  if (shape === "ellipse") {
    return <span className={`${base} h-2.5 w-2.5 rounded-full`} style={{ borderColor: color }} />;
  }
  if (shape === "round-hexagon") {
    return (
      <span
        className={`${base} h-2.5 w-3`}
        style={{ borderColor: color, clipPath: "polygon(25% 0,75% 0,100% 50%,75% 100%,25% 100%,0 50%)" }}
      />
    );
  }
  return <span className={`${base} h-2.5 w-3.5 rounded-[2px]`} style={{ borderColor: color }} />;
}

/** Line swatch: solid = authored/cited, dashed = inferred or structural. */
function EdgeSwatch({ color, dashed }: { color: string; dashed?: boolean }) {
  return (
    <span className="inline-flex h-2.5 w-3.5 shrink-0 items-center">
      <span
        className="block w-full"
        style={{
          borderTopWidth: 2,
          borderTopStyle: dashed ? "dashed" : "solid",
          borderTopColor: color,
        }}
      />
    </span>
  );
}

export interface GraphLegendProps {
  /** Keys from NODE_LEGEND this view actually renders. */
  nodeKinds: Array<keyof typeof NODE_LEGEND>;
  /** Edge kinds this view actually renders. */
  edgeKinds: EdgeKind[];
  /** Optional one-line reading instruction, e.g. "size = times reused". */
  sizeHint?: string;
  className?: string;
}

export function GraphLegend({ nodeKinds, edgeKinds, sizeHint, className = "" }: GraphLegendProps) {
  const t = useCanvasTheme();
  const [open, setOpen] = useState(true);
  const edges = edgeLegend(edgeKinds);

  return (
    <div
      className={`absolute left-3 top-3 z-10 w-[186px] overflow-hidden rounded-md border border-[var(--border-strong,var(--border-default))] bg-[var(--surface)]/95 text-[11px] text-[var(--text-secondary)] shadow-lg backdrop-blur-sm ${className}`}
    >
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-[var(--text-tertiary)] hover:text-[var(--text)]"
        aria-expanded={open}
      >
        Legend
        <ChevronDown className={`h-3 w-3 transition-transform ${open ? "" : "-rotate-90"}`} />
      </button>

      {open && (
        <div className="flex flex-col gap-2 border-t border-[var(--border-default)] px-3 py-2">
          <div className="flex flex-col gap-1">
            {nodeKinds.map((k) => {
              const entry = NODE_LEGEND[k];
              if (!entry) return null;
              return (
                <span key={k} className="flex items-center gap-1.5">
                  <NodeSwatch entry={entry} color={entry.color(t)} />
                  {entry.label}
                </span>
              );
            })}
          </div>

          {edges.length > 0 && (
            <div className="flex flex-col gap-1 border-t border-[var(--border-default)] pt-2">
              {edges.map((e, i) => (
                <span key={i} className="flex items-center gap-1.5">
                  <EdgeSwatch color={e.color(t)} dashed={e.dashed} />
                  {e.label}
                </span>
              ))}
            </div>
          )}

          {sizeHint && (
            <div className="border-t border-[var(--border-default)] pt-2 text-[10px] text-[var(--text-tertiary)]">
              {sizeHint}
            </div>
          )}

          <div className="border-t border-[var(--border-default)] pt-2 text-[10px] leading-snug text-[var(--text-tertiary)]">
            Solid line = cited or authored. Dashed = inferred by the system.
          </div>
        </div>
      )}
    </div>
  );
}
