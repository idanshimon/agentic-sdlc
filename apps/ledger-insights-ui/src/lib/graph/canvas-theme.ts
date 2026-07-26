"use client";
/* Canvas theme bridge.
 *
 * Cytoscape and react-flow style to <canvas>/inline styles via JS objects,
 * which cannot resolve CSS custom properties. DESIGN.md sanctions hard-coded
 * hex in those files ONLY as a mirror of :root — but a frozen mirror breaks the
 * moment the user switches to the light theme, leaving black nodes on a white
 * page.
 *
 * This resolves the real token values off the live DOM and re-resolves them
 * whenever the theme class changes, so graph panes track the theme instead of
 * pinning to dark. Read tokens through `useCanvasTheme()` and pass the result
 * into the graph stylesheet.
 */
import { useEffect, useState } from "react";

export interface CanvasTheme {
  bg: string;
  surface: string;
  elevated: string;
  overlay: string;
  border: string;
  text: string;
  textSecondary: string;
  textTertiary: string;
  primary: string;
  secondary: string;
  success: string;
  warning: string;
  danger: string;
  info: string;
  planeStandards: string;
  planePipeline: string;
  planeLedger: string;
  planeAgentHq: string;
  /** True when the light theme is active — for shadows/opacity that must flip. */
  isLight: boolean;
}

/** Dark-theme fallback, used during SSR where there is no computed style. */
const FALLBACK: CanvasTheme = {
  bg: "#0B0F14",
  surface: "#11161D",
  elevated: "#161D26",
  overlay: "#1E2632",
  border: "#243042",
  text: "#E6EDF3",
  textSecondary: "#9FB0C3",
  textTertiary: "#6B7A8C",
  primary: "#0EA5E9",
  secondary: "#A78BFA",
  success: "#22C55E",
  warning: "#F59E0B",
  danger: "#EF4444",
  info: "#0EA5E9",
  planeStandards: "#A78BFA",
  planePipeline: "#0EA5E9",
  planeLedger: "#10B981",
  planeAgentHq: "#F59E0B",
  isLight: false,
};

const VAR_MAP: Array<[keyof CanvasTheme, string]> = [
  ["bg", "--bg"],
  ["surface", "--surface"],
  ["elevated", "--elevated"],
  ["overlay", "--overlay"],
  ["border", "--border-default"],
  ["text", "--text"],
  ["textSecondary", "--text-secondary"],
  ["textTertiary", "--text-tertiary"],
  ["primary", "--primary"],
  ["secondary", "--secondary"],
  ["success", "--success"],
  ["warning", "--warning"],
  ["danger", "--danger"],
  ["info", "--info"],
  ["planeStandards", "--plane-standards"],
  ["planePipeline", "--plane-pipeline"],
  ["planeLedger", "--plane-ledger"],
  ["planeAgentHq", "--plane-agenthq"],
];

/** Resolve the current token values from the document root. */
export function readCanvasTheme(): CanvasTheme {
  if (typeof window === "undefined" || typeof document === "undefined") {
    return FALLBACK;
  }
  const styles = getComputedStyle(document.documentElement);
  const out = { ...FALLBACK };
  for (const [key, cssVar] of VAR_MAP) {
    const value = styles.getPropertyValue(cssVar).trim();
    if (value) (out as Record<string, string | boolean>)[key] = value;
  }
  out.isLight =
    document.documentElement.classList.contains("light") ||
    document.body.classList.contains("light");
  return out;
}

/**
 * Live token values for canvas-rendered graphs. Re-reads on theme change so
 * Cytoscape/react-flow stylesheets rebuild instead of staying pinned to dark.
 */
export function useCanvasTheme(): CanvasTheme {
  const [theme, setTheme] = useState<CanvasTheme>(FALLBACK);

  useEffect(() => {
    // Read once on mount — SSR gave us the fallback.
    setTheme(readCanvasTheme());

    // next-themes toggles a class on <html>; watch it rather than polling.
    const observer = new MutationObserver(() => setTheme(readCanvasTheme()));
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class", "style", "data-theme"],
    });
    observer.observe(document.body, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, []);

  return theme;
}
