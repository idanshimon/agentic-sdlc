"use client";
/* HyperFrames-style motion primitives for the operator UI.
 *
 * Same engine and discipline as Content Creator / HyperFrames compositions:
 * one GSAP timeline per surface, built paused, then played — so a motion is a
 * deterministic, seekable composition rather than scattered CSS transitions.
 * Every primitive collapses to its final state under prefers-reduced-motion,
 * and animates ONLY presentation (opacity/transform/stroke) — never data.
 */
import { useEffect, useLayoutEffect, useRef, useState, type RefObject } from "react";
import gsap from "gsap";

const useIso = typeof window === "undefined" ? useEffect : useLayoutEffect;

export function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}

/** Stagger children marked `data-hf` into place once, on mount.
 *  `data-hf="rise" | "fade" | "draw" | "grow-x" | "grow-y"`. */
export function useHyperframe<T extends HTMLElement | SVGElement>(deps: unknown[] = []): RefObject<T | null> {
  const ref = useRef<T | null>(null);
  useIso(() => {
    const root = ref.current;
    if (!root) return;
    const ctx = gsap.context(() => {
      const q = (k: string) => root.querySelectorAll(`[data-hf="${k}"]`);
      if (prefersReducedMotion()) return;
      const tl = gsap.timeline({ paused: true, defaults: { ease: "power3.out" } });
      // clearProps: hand control back to React/attributes once the entrance
      // ends, otherwise inline styles override later state (e.g. dimming).
      tl.from(q("fade"), { opacity: 0, duration: 0.5, stagger: { amount: 0.6 }, clearProps: "opacity" }, 0);
      tl.from(q("rise"), { opacity: 0, y: 14, duration: 0.6, stagger: 0.06, clearProps: "opacity,transform" }, 0.05);
      tl.from(q("grow-x"), { scaleX: 0, transformOrigin: "0% 50%", duration: 0.8, stagger: 0.03, clearProps: "transform" }, 0.15);
      tl.from(q("grow-y"), { scaleY: 0, transformOrigin: "50% 100%", duration: 0.7, stagger: { amount: 0.5 }, clearProps: "transform" }, 0.15);
      root.querySelectorAll<SVGGeometryElement>('[data-hf="draw"]').forEach((el, i) => {
        const len = typeof el.getTotalLength === "function" ? el.getTotalLength() : 0;
        if (!len) return;
        const finalOffset = Number(el.getAttribute("data-hf-offset") ?? 0);
        tl.fromTo(
          el,
          { strokeDasharray: `${len} ${len}`, strokeDashoffset: len },
          { strokeDashoffset: finalOffset, duration: 1.1, ease: "power2.inOut", clearProps: "strokeDasharray,strokeDashoffset" },
          0.2 + Math.min(i, 12) * 0.06,
        );
      });
      tl.play();
    }, root);
    return () => ctx.revert();
  }, deps);
  return ref;
}

/** Number that counts up to its value whenever the value changes. Renders the
 *  final value on the server and under reduced motion. */
export function CountUp({
  value, format = (n) => Math.round(n).toLocaleString(), duration = 1.1, className,
}: {
  value: number;
  format?: (n: number) => string;
  duration?: number;
  className?: string;
}) {
  const [shown, setShown] = useState(value);
  const from = useRef(0);
  useEffect(() => {
    const o = { v: prefersReducedMotion() ? value : from.current };
    const tw = gsap.to(o, {
      v: value, duration: prefersReducedMotion() ? 0 : duration, ease: "power2.out",
      onUpdate: () => setShown(o.v),
      onComplete: () => { from.current = value; },
    });
    return () => { tw.kill(); };
  }, [value, duration]);
  return <span className={className}>{format(shown)}</span>;
}

/** HUD frame: corner brackets + a slow scan line over a canvas pane. Purely
 *  decorative chrome; pointer-events pass through to the graph. */
export function HudFrame({ label, live }: { label?: string; live?: boolean }) {
  const c = "pointer-events-none absolute h-4 w-4 border-[var(--primary)]";
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 z-10">
      <span className={`${c} left-2 top-2 border-l-2 border-t-2`} />
      <span className={`${c} right-2 top-2 border-r-2 border-t-2`} />
      <span className={`${c} bottom-2 left-2 border-b-2 border-l-2`} />
      <span className={`${c} bottom-2 right-2 border-b-2 border-r-2`} />
      <div className="hf-scan absolute inset-x-0 h-24" />
      {label && (
        <div className="absolute right-4 top-3 flex items-center gap-1.5 text-[10px] text-[var(--text-tertiary)]">
          {live && <span className="pulse-dot h-1.5 w-1.5 rounded-full bg-[var(--success)]" />}
          <span className="mono">{label}</span>
        </div>
      )}
    </div>
  );
}
