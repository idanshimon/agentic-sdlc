/**
 * Hook → target-service derivation, shared + pure + unit-tested.
 *
 * Each lifecycle hook wraps an agent session and acts on a real downstream
 * surface ("what it controls / might control"). We derive that surface from the
 * hook's lifecycle event + name so the Hooks page can show it explicitly instead
 * of leaving the operator to infer it. Grounded in .github/hooks/README.md.
 */
export type HookEvent =
  | "SessionStart"
  | "UserPromptSubmit"
  | "PreToolUse"
  | "PostToolUse"
  | "SessionEnd"
  | "FileEdit"
  | "Notification"
  | string;

export interface HookTarget {
  /** The downstream surface this hook controls or feeds. */
  service: string;
  /** A route/page in this UI where that surface is visible, if any. */
  href?: string;
  /** Whether the hook can BLOCK the agent (enforcing) or only observe/record. */
  mode: "enforcing" | "observing" | "injecting" | "notifying";
}

/**
 * Map a hook to the service it controls. Precedence: an explicit `controls`
 * field on the hook JSON wins (author intent); otherwise we derive from the
 * lifecycle event, which is stable and matches the README contract.
 */
export function deriveHookTarget(
  event: HookEvent,
  opts?: { explicitControls?: string; name?: string },
): HookTarget {
  if (opts?.explicitControls) {
    return { service: opts.explicitControls, mode: inferMode(event, opts.name) };
  }
  switch (event) {
    case "PreToolUse":
      // The PHI guard: runs the classifier and BLOCKS on raw PHI.
      return { service: "PHI Classifier (blocks tool calls on raw PHI)", href: "/phi", mode: "enforcing" };
    case "PostToolUse":
      return { service: "Decision Ledger (writes a runtime entry per tool call)", href: "/decisions", mode: "observing" };
    case "SessionEnd":
      return { service: "Decision Ledger (writes a session-summary entry)", href: "/decisions", mode: "observing" };
    case "UserPromptSubmit":
      return { service: "Decision Ledger (captures prompt intent)", href: "/decisions", mode: "observing" };
    case "SessionStart":
      return { service: "Standards Bundles + AGENTS.md (context injection)", href: "/bundles", mode: "injecting" };
    case "FileEdit":
      return { service: "Decision Ledger (stamps each file change with session id)", href: "/decisions", mode: "observing" };
    case "Notification":
      return { service: "Operator notifications (gate awaits, fail-hard scans, budget)", mode: "notifying" };
    default:
      return { service: "Unknown surface", mode: "observing" };
  }
}

function inferMode(event: HookEvent, name?: string): HookTarget["mode"] {
  const n = (name ?? "").toLowerCase();
  if (event === "PreToolUse" || n.includes("guard") || n.includes("phi")) return "enforcing";
  if (event === "SessionStart" || n.includes("inject")) return "injecting";
  if (event === "Notification" || n.includes("notify")) return "notifying";
  return "observing";
}

export const MODE_LABEL: Record<HookTarget["mode"], string> = {
  enforcing: "can BLOCK the agent",
  observing: "records only (never blocks)",
  injecting: "injects context",
  notifying: "notifies operator",
};
