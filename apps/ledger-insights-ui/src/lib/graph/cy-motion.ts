"use client";
/* Cytoscape motion layer — the HyperFrames treatment for canvas graphs.
 *
 *   1. Entrance: nodes rise in, staggered by layout order (x then y), so the
 *      structure reads as it builds rather than appearing as a wall.
 *   2. Flow: edges tagged with `flowSelector` get marching dashes — direction of
 *      reuse/teaching is visible without arrows-only.
 *   3. Alarm: nodes tagged with `pulseSelector` breathe a halo (flagged / PHI).
 *
 * All presentation-only, all stopped on cleanup, all skipped under
 * prefers-reduced-motion. Cytoscape draws to canvas, so CSS animation cannot
 * reach it — we drive style from a single rAF loop instead.
 */
import type { Core } from "cytoscape";
import { prefersReducedMotion } from "@/lib/hyperframe";

export interface CyMotionOptions {
  flowSelector?: string;
  pulseSelector?: string;
  pulseColor?: string;
}

export function startCyMotion(cy: Core, opts: CyMotionOptions = {}): () => void {
  if (prefersReducedMotion()) return () => {};
  let stopped = false;

  // 1. entrance
  const nodes = cy.nodes().sort((a, b) => a.position("x") - b.position("x") || a.position("y") - b.position("y"));
  const n = nodes.length;
  const step = n > 200 ? 2 : n > 80 ? 6 : 14;
  nodes.forEach((node, i) => {
    const w = node.width();
    const h = node.height();
    node.style({ opacity: 0, width: w * 0.6, height: h * 0.6 });
    node.delay(Math.min(i * step, 900)).animate(
      { style: { opacity: 1, width: w, height: h } },
      { duration: 420, easing: "ease-out-cubic", complete: () => node.removeStyle("opacity width height") },
    );
  });
  const edges = cy.edges();
  edges.style("opacity", 0);
  edges.delay(Math.min(n * step, 900) * 0.5).animate({ style: { opacity: 1 } }, {
    duration: 500,
    complete: () => edges.removeStyle("opacity"),
  });

  // 2 + 3. loop
  const flow = opts.flowSelector ? cy.edges(opts.flowSelector) : cy.collection();
  const pulse = opts.pulseSelector ? cy.nodes(opts.pulseSelector) : cy.collection();
  if (flow.length) flow.style({ "line-style": "dashed", "line-dash-pattern": [7, 5] });
  if (pulse.length && opts.pulseColor) pulse.style({ "underlay-color": opts.pulseColor, "underlay-padding": 7, "underlay-shape": "ellipse" });

  let raf = 0;
  const t0 = performance.now();
  const tick = (now: number) => {
    if (stopped) return;
    const t = (now - t0) / 1000;
    cy.batch(() => {
      if (flow.length) flow.style("line-dash-offset", -((t * 18) % 12));
      if (pulse.length) pulse.style("underlay-opacity", 0.12 + 0.18 * (0.5 + 0.5 * Math.sin(t * 3)));
    });
    raf = requestAnimationFrame(tick);
  };
  if (flow.length || pulse.length) raf = requestAnimationFrame(tick);

  return () => {
    stopped = true;
    cancelAnimationFrame(raf);
  };
}
