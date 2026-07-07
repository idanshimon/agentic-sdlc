"use client";
import {
  createContext, useContext, useState, useEffect, useRef, ReactNode,
} from "react";

/* AgentAssistant context — every page calls `useAssistantContext({ kind, id, ...})`
 * to declare what the agent should know about. The floating Ask-the-agent
 * button reads this context and pre-fills the system prompt, plus the
 * apply-back action handlers. Demo mode replays pre-canned conversations
 * keyed off context.kind; live mode posts to the orchestrator's chat endpoint.
 */

export type AssistContextKind =
  | "dashboard"
  | "runs-list"
  | "run-detail"
  | "run-resolver-gate"
  | "decisions"
  | "telemetry"
  | "bundles"
  | "agents-list"
  | "agent-edit"
  | "prompts-list"
  | "prompt-edit"
  | "phi-classifier"
  | "compliance"
  | "reports";

export interface AssistContext {
  kind: AssistContextKind;
  /** Stable identifier of the focused resource (e.g. agent name, run id). */
  id?: string;
  /** Short label for the agent's heading (e.g. "Architect agent"). */
  label?: string;
  /** Optional payload of the resource currently being edited / viewed. */
  payload?: Record<string, unknown>;
}

export type ApplyAction =
  | { kind: "apply_text_edit"; description: string; new_content: string }
  | { kind: "navigate"; description: string; href: string }
  | { kind: "create_bundle_change"; description: string; dept: string; new_version: string; reasoning: string }
  | { kind: "amend_decision"; description: string; decision_id: string; new_rationale?: string }
  | { kind: "noop"; description: string };

interface AssistApi {
  context: AssistContext | null;
  setContext: (ctx: AssistContext | null) => void;
  open: boolean;
  setOpen: (o: boolean) => void;
  /** Per-render handler the page provides for "apply this edit" actions.
   * Wrapped in an object to avoid React's `setState(fn)` updater interpretation. */
  applyHandler: { run: (action: ApplyAction) => void | Promise<void> } | null;
  setApplyHandler: (h: AssistApi["applyHandler"]) => void;
}

const Ctx = createContext<AssistApi | null>(null);

export function AssistProvider({ children }: { children: ReactNode }) {
  const [context, setContext] = useState<AssistContext | null>(null);
  const [open, setOpen] = useState(false);
  const [applyHandler, setApplyHandler] = useState<AssistApi["applyHandler"]>(null);

  return (
    <Ctx.Provider
      value={{ context, setContext, open, setOpen, applyHandler, setApplyHandler }}
    >
      {children}
    </Ctx.Provider>
  );
}

export function useAssist(): AssistApi {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAssist must be used inside AssistProvider");
  return ctx;
}

/** Page-level hook: declare your context once at the top of a page.
 *
 * The hook stores the latest applyHandler in a ref so the page can pass an
 * inline arrow without thrashing the provider's state. Only PRIMITIVE
 * dependencies (kind, id, label) drive re-publish — `payload` is forwarded
 * to the provider for its replies but does NOT trigger re-renders, because
 * inline `payload: {status, stage}` literals at call sites would otherwise
 * produce a fresh object identity every render and turn `JSON.stringify`
 * into a render-storm trigger on busy pages (run-detail during demo replay,
 * 11-timer setTimeout cascade, 3s polling). The provider's reply engine
 * reads payload via the latest-context ref at reply time, not via React
 * state — so payload doesn't need to live in the dep key.
 *
 * Caught 2026-06-09 live: `/runs/[runId]` after Approve clicked the demo
 * replay engine + the inline payload `{status, stage}` literal at call
 * site triggered an SIGKILL on the renderer, surfacing as Chrome's native
 * "This page couldn't load" page. Fix: drop payload from the dep key,
 * keep it on the live context the provider holds.
 */
export function useAssistantContext(
  context: AssistContext,
  applyHandler?: (action: ApplyAction) => void | Promise<void>,
) {
  const api = useContext(Ctx);
  // Stable dep key — only PRIMITIVE-typed fields. `payload` is intentionally
  // excluded to avoid render-storm triggers on call sites that pass inline
  // object literals like `payload: { status, stage }`.
  const ctxKey = `${context.kind}|${context.id ?? ""}|${context.label ?? ""}`;
  const hasHandler = !!applyHandler;

  // Latest-context ref — the provider's reply engine reads context.payload
  // at reply time via this ref, NOT via React state. Updated on every render
  // (cheap, no setState).
  const contextRef = useRef(context);
  contextRef.current = context;

  // Latest-handler ref — updated by an effect so we don't write during render
  // (React 19 strict mode flags ref writes during render). The effect runs
  // after every render, so the ref is always one render behind — fine for
  // this use case because the provider invokes the handler lazily on user
  // action, by which point the effect has already settled.
  const handlerRef = useRef(applyHandler);
  useEffect(() => {
    handlerRef.current = applyHandler;
  });

  useEffect(() => {
    if (!api) return;
    // Read fresh context from the ref so the provider gets the current
    // payload even though the dep key only watched primitives.
    api.setContext(contextRef.current);
    if (hasHandler) {
      api.setApplyHandler({
        run: (action) =>
          handlerRef.current ? handlerRef.current(action) : undefined,
      });
    } else {
      api.setApplyHandler(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ctxKey, hasHandler]);
}
