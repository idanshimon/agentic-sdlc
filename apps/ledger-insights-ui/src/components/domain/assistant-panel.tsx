"use client";
import { useState, useCallback, useRef, useEffect } from "react";
import { Sparkles, Send, X, Loader2, Bot, User, CheckCircle2, ArrowRight, Bookmark } from "lucide-react";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { useAssist, type ApplyAction } from "@/lib/assist/context";
import { pickReply, getSuggestions, type AgentReply } from "@/lib/assist/replies";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

interface ChatTurn {
  role: "user" | "agent";
  text: string;
  reasoning?: string;
  actions?: ApplyAction[];
  citations?: { label: string; ref: string }[];
  applied?: Record<number, "applied" | "dismissed">;
  timestamp: string;
}

const KIND_LABELS: Record<string, string> = {
  dashboard: "Dashboard",
  "runs-list": "Runs",
  "run-detail": "Run detail",
  "run-resolver-gate": "Resolver gate",
  decisions: "Decisions",
  telemetry: "Telemetry",
  bundles: "Bundles",
  "agents-list": "Custom agents",
  "agent-edit": "Edit agent",
  "prompts-list": "Prompt library",
  "prompt-edit": "Edit prompt",
  "phi-classifier": "PHI classifier",
  reports: "Reports",
};

export function AssistantPanel() {
  const { context, open, setOpen, applyHandler } = useAssist();
  const [history, setHistory] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  // Reset history when context changes (route navigation).
  useEffect(() => {
    queueMicrotask(() => {
      setHistory([]);
      setInput("");
    });
  }, [context?.kind, context?.id]);

  // Auto-scroll on new turn.
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [history.length, thinking]);

  const send = useCallback(
    async (prompt: string) => {
      if (!prompt.trim()) return;
      const userTurn: ChatTurn = {
        role: "user",
        text: prompt,
        timestamp: new Date().toISOString(),
      };
      setHistory((prev) => [...prev, userTurn]);
      setInput("");
      setThinking(true);

      // Simulate agent reasoning latency. ~1.2s feels alive without dragging.
      await new Promise((res) => setTimeout(res, 900));

      const reply = pickReply(context, prompt);
      const agentTurn: ChatTurn = {
        role: "agent",
        text: reply.text,
        reasoning: reply.reasoning,
        actions: reply.actions,
        citations: reply.citations,
        applied: {},
        timestamp: new Date().toISOString(),
      };
      setHistory((prev) => [...prev, agentTurn]);
      setThinking(false);
    },
    [context],
  );

  const onApply = useCallback(
    async (turnIdx: number, actionIdx: number, action: ApplyAction) => {
      try {
        if (applyHandler) {
          await applyHandler.run(action);
        } else {
          // Fallback: no page-level handler. Dispatch a global event so the
          // matching surface (if listening) can handle it.
          window.dispatchEvent(
            new CustomEvent("assist-apply", { detail: action }),
          );
        }
        setHistory((prev) =>
          prev.map((t, i) =>
            i === turnIdx
              ? { ...t, applied: { ...t.applied, [actionIdx]: "applied" } }
              : t,
          ),
        );
        toast.success("Applied", { description: action.description });
      } catch (e) {
        toast.error("Apply failed", {
          description: e instanceof Error ? e.message : String(e),
        });
      }
    },
    [applyHandler],
  );

  const onDismiss = useCallback((turnIdx: number, actionIdx: number) => {
    setHistory((prev) =>
      prev.map((t, i) =>
        i === turnIdx
          ? { ...t, applied: { ...t.applied, [actionIdx]: "dismissed" } }
          : t,
      ),
    );
  }, []);

  const suggestions = getSuggestions(context);
  const contextLabel = context ? KIND_LABELS[context.kind] ?? context.kind : "—";

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetContent
        side="right"
        className="w-full sm:max-w-xl flex flex-col p-0"
      >
        {/* Header */}
        <div className="px-5 pt-5 pb-4 border-b border-[var(--border-muted)] space-y-2">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-[var(--plane-agenthq)]" />
            <h2 className="text-sm font-semibold">Ask the agent</h2>
            <Badge variant="secondary" className="text-[10px]">
              {contextLabel}
            </Badge>
            {context?.id && (
              <span className="text-[10px] mono text-[var(--text-tertiary)] truncate">
                {context.id}
              </span>
            )}
          </div>
          <p className="text-xs text-[var(--text-tertiary)] leading-relaxed">
            The agent has the full context of this view — bundle rules in scope,
            recent decisions, prompt versions, and the active resource. It can
            propose edits you apply with one click.
          </p>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {history.length === 0 && (
            <div className="space-y-3">
              <div className="text-[11px] uppercase tracking-wider font-medium text-[var(--text-tertiary)]">
                Try asking
              </div>
              <div className="flex flex-col gap-2">
                {suggestions.map((s, i) => (
                  <button
                    key={i}
                    onClick={() => send(s)}
                    className="text-left text-xs px-3 py-2 rounded-md border border-[var(--border-muted)] hover:border-[var(--text-tertiary)] hover:bg-[var(--overlay)]/40 transition-colors"
                  >
                    {s}
                  </button>
                ))}
              </div>
              <div className="text-[10px] text-[var(--text-tertiary)] pt-2 leading-relaxed">
                In production this routes to the orchestrator&apos;s chat agent with
                bundle rules + recent decisions + the active resource as system
                context. In Demo Mode replies are pre-canned but the apply-back
                actions are real (they edit your local versioned store).
              </div>
            </div>
          )}

          {history.map((turn, i) => (
            <ChatBubble
              key={i}
              turn={turn}
              turnIdx={i}
              onApply={onApply}
              onDismiss={onDismiss}
            />
          ))}

          {thinking && (
            <div className="flex items-center gap-2 text-xs text-[var(--text-tertiary)]">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Reasoning over context…
            </div>
          )}
          <div ref={endRef} />
        </div>

        {/* Composer */}
        <div className="border-t border-[var(--border-muted)] p-4">
          <div className="flex items-end gap-2">
            <Textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send(input);
                }
              }}
              placeholder={`Ask about ${contextLabel.toLowerCase()}…`}
              rows={2}
              className="text-xs resize-none"
            />
            <Button
              variant="primary"
              size="sm"
              onClick={() => send(input)}
              disabled={!input.trim() || thinking}
            >
              <Send className="h-3.5 w-3.5" />
              Send
            </Button>
          </div>
          <div className="text-[10px] text-[var(--text-tertiary)] mt-1.5 flex items-center gap-2">
            <span>Enter to send · Shift+Enter for newline</span>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}

function ChatBubble({
  turn,
  turnIdx,
  onApply,
  onDismiss,
}: {
  turn: ChatTurn;
  turnIdx: number;
  onApply: (turnIdx: number, actionIdx: number, action: ApplyAction) => void;
  onDismiss: (turnIdx: number, actionIdx: number) => void;
}) {
  if (turn.role === "user") {
    return (
      <div className="flex items-start gap-2 justify-end">
        <div className="max-w-[80%] rounded-lg bg-[var(--primary)]/10 border border-[var(--primary)]/20 px-3 py-2">
          <p className="text-xs leading-relaxed">{turn.text}</p>
        </div>
        <div className="h-6 w-6 rounded-full bg-[var(--overlay)] flex items-center justify-center shrink-0 mt-0.5">
          <User className="h-3 w-3 text-[var(--text-tertiary)]" />
        </div>
      </div>
    );
  }
  return (
    <div className="flex items-start gap-2">
      <div className="h-6 w-6 rounded-full bg-[var(--plane-agenthq)]/15 flex items-center justify-center shrink-0 mt-0.5">
        <Bot className="h-3 w-3 text-[var(--plane-agenthq)]" />
      </div>
      <div className="flex-1 min-w-0 space-y-2">
        <div className="text-xs leading-relaxed text-[var(--text-secondary)] whitespace-pre-wrap">
          {turn.text}
        </div>
        {turn.reasoning && (
          <details className="text-[11px]">
            <summary className="text-[var(--text-tertiary)] cursor-pointer hover:text-[var(--text-secondary)]">
              Reasoning
            </summary>
            <p className="mt-1 pl-3 border-l-2 border-[var(--border-muted)] text-[var(--text-tertiary)] leading-relaxed">
              {turn.reasoning}
            </p>
          </details>
        )}
        {turn.citations && turn.citations.length > 0 && (
          <div className="flex flex-wrap gap-1.5 items-center">
            <Bookmark className="h-2.5 w-2.5 text-[var(--text-tertiary)]" />
            {turn.citations.map((c, i) => (
              <span
                key={i}
                className="text-[10px] mono px-1.5 py-0.5 rounded bg-[var(--overlay)] text-[var(--secondary)]"
                title={c.ref}
              >
                {c.label}
              </span>
            ))}
          </div>
        )}
        {turn.actions && turn.actions.length > 0 && (
          <div className="space-y-2 pt-1">
            {turn.actions.map((action, ai) => {
              const status = turn.applied?.[ai];
              return (
                <ActionRow
                  key={ai}
                  action={action}
                  status={status}
                  onApply={() => onApply(turnIdx, ai, action)}
                  onDismiss={() => onDismiss(turnIdx, ai)}
                />
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

function ActionRow({
  action,
  status,
  onApply,
  onDismiss,
}: {
  action: ApplyAction;
  status: "applied" | "dismissed" | undefined;
  onApply: () => void;
  onDismiss: () => void;
}) {
  if (status === "applied") {
    return (
      <div className="rounded-md border border-[var(--success)]/30 bg-[var(--success)]/5 px-3 py-2 flex items-center gap-2">
        <CheckCircle2 className="h-3.5 w-3.5 text-[var(--success)]" />
        <span className="text-[11px] text-[var(--text-secondary)] flex-1 truncate">
          {action.description}
        </span>
        <Badge variant="success" className="text-[10px]">
          applied
        </Badge>
      </div>
    );
  }
  if (status === "dismissed") {
    return (
      <div className="rounded-md border border-[var(--border-muted)] px-3 py-2 flex items-center gap-2 opacity-60">
        <span className="text-[11px] text-[var(--text-tertiary)] flex-1 truncate line-through">
          {action.description}
        </span>
      </div>
    );
  }
  const isNav = action.kind === "navigate";
  return (
    <div
      className={cn(
        "rounded-md border px-3 py-2 flex items-start gap-2",
        isNav
          ? "border-[var(--primary)]/30 bg-[var(--primary)]/5"
          : "border-[var(--warning)]/30 bg-[var(--warning)]/5",
      )}
    >
      <div className="flex-1 min-w-0">
        <div className="text-[11px] text-[var(--text)] leading-snug">
          {action.description}
        </div>
        <div className="text-[10px] text-[var(--text-tertiary)] mt-0.5 mono">
          {action.kind}
        </div>
      </div>
      <div className="flex items-center gap-1 shrink-0">
        <Button variant="primary" size="sm" onClick={onApply} className="h-7 text-[11px]">
          {isNav ? <>Open <ArrowRight className="h-3 w-3" /></> : <>Apply</>}
        </Button>
        <Button variant="ghost" size="sm" onClick={onDismiss} className="h-7 px-2">
          <X className="h-3 w-3" />
        </Button>
      </div>
    </div>
  );
}

/**
 * Floating "Ask the agent" button. Pinned bottom-right of every page.
 * Renders only when AssistProvider has wrapped the app.
 */
export function AskAgentButton() {
  const { setOpen, context } = useAssist();
  if (!context) {
    // Safe default: provider is mounted but no page declared its context yet.
  }
  return (
    <button
      onClick={() => setOpen(true)}
      className={cn(
        "fixed bottom-5 right-5 z-40 group",
        "flex items-center gap-2 px-4 h-11 rounded-full",
        "bg-[var(--plane-agenthq)] text-[#001018] font-medium",
        "shadow-lg hover:shadow-xl hover:scale-105 transition-all",
      )}
      title="Ask the agent for help with this page"
    >
      <Sparkles className="h-4 w-4" />
      <span className="text-xs">Ask the agent</span>
      <span className="text-[10px] mono opacity-60 hidden sm:inline">⌘K</span>
    </button>
  );
}
