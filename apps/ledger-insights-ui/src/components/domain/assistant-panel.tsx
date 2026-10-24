"use client";
/* Operator assistant — docked, grounded, read-only.
 *
 * Patterns adopted from Atlas's grounded chat:
 *   - Context injection is VISIBLE: every reply carries the exact sources,
 *     computed facts and warnings the model saw ("What I looked at").
 *   - Preview before send: the operator can inspect the context that would be
 *     injected for a question without calling the model.
 *   - Grounding toggle: off sends the question verbatim, labelled as such.
 *   - Inline [n] citations are clickable and resolve to real records
 *     (ledger entry, run, bundle rule, OpenSpec change, GitHub PR/commit).
 *   - PHI guard at the LLM boundary; withheld excerpts are counted, not hidden.
 *   - Honest fallback: when the model is unavailable the deterministic
 *     composer answers and the reply is labelled "offline composer".
 *
 * Docked (non-modal): the page behind stays sharp and usable, so the operator
 * can read the table while asking about it. Never writes to the ledger.
 */
import { useState, useCallback, useRef, useEffect } from "react";
import Link from "next/link";
import {
  Sparkles, Send, X, Loader2, Bot, User, CheckCircle2, ArrowRight, Bookmark,
  Database, GitBranch, Github, ScrollText, FileText, Calculator, ShieldAlert,
  AlertTriangle, Eye, Radar, RotateCcw, Cpu,
} from "lucide-react";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { useAssist, type ApplyAction } from "@/lib/assist/context";
import { pickReply, getSuggestions } from "@/lib/assist/replies";
import { ReplyText } from "@/components/domain/assistant-markdown";
import type { Grounding, GroundingSource, SourceKind } from "@/lib/server/assist-context";
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
  mode?: "live" | "offline";
  model?: string;
  latencyMs?: number;
  tokens?: number;
  grounding?: Grounding;
  offlineReason?: string;
  grounded?: boolean;
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
  compliance: "Compliance",
  reports: "Reports",
};

export const SOURCE_META: Record<SourceKind, { icon: typeof Database; label: string; color: string }> = {
  view: { icon: Eye, label: "View", color: "var(--text-secondary)" },
  ledger: { icon: Database, label: "Ledger", color: "var(--plane-ledger)" },
  run: { icon: GitBranch, label: "Run", color: "var(--plane-pipeline)" },
  rule: { icon: ScrollText, label: "Rule", color: "var(--plane-standards)" },
  openspec: { icon: FileText, label: "OpenSpec", color: "var(--secondary)" },
  github: { icon: Github, label: "GitHub", color: "var(--text)" },
  derived: { icon: Calculator, label: "Computed", color: "var(--warning)" },
};

interface ChatApiResponse {
  mode: "live" | "unavailable";
  reply?: string;
  model?: string;
  latency_ms?: number;
  usage?: { prompt_tokens: number; completion_tokens: number };
  reason?: string;
  grounding: Grounding;
}

export function AssistantPanel() {
  const { context, open, setOpen, applyHandler } = useAssist();
  const [history, setHistory] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const [ground, setGround] = useState(true);
  const [preview, setPreview] = useState<{ loading: boolean; grounding?: Grounding; error?: string } | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const reqId = useRef(0);

  // Reset history when context changes (route navigation). Bumping reqId
  // drops any in-flight reply so an old answer cannot land in a new view.
  useEffect(() => {
    queueMicrotask(() => {
      reqId.current += 1;
      setHistory([]);
      setInput("");
      setPreview(null);
      setThinking(false);
    });
  }, [context?.kind, context?.id]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [history.length, thinking]);

  const view = context
    ? { kind: context.kind, id: context.id, label: context.label ?? KIND_LABELS[context.kind] }
    : null;

  const send = useCallback(
    async (prompt: string) => {
      if (!prompt.trim() || !view || thinking) return;
      const myReq = ++reqId.current;
      const userTurn: ChatTurn = { role: "user", text: prompt, timestamp: new Date().toISOString(), grounded: ground };
      const prior = history
        .filter((t) => t.text)
        .slice(-6)
        .map((t) => ({ role: t.role === "user" ? ("user" as const) : ("assistant" as const), content: t.text }));
      setHistory((prev) => [...prev, userTurn]);
      setInput("");
      setPreview(null);
      setThinking(true);

      let turn: ChatTurn;
      try {
        const res = await fetch("/api/assist/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: prompt, view, ground, history: prior }),
        });
        const data = (await res.json()) as ChatApiResponse;
        if (!res.ok) throw new Error((data as unknown as { error?: string }).error ?? `HTTP ${res.status}`);
        if (data.mode === "live" && data.reply) {
          turn = {
            role: "agent", text: data.reply, actions: [], applied: {}, timestamp: new Date().toISOString(),
            mode: "live", model: data.model, latencyMs: data.latency_ms,
            tokens: data.usage ? data.usage.prompt_tokens + data.usage.completion_tokens : undefined,
            grounding: data.grounding,
          };
        } else {
          const r = pickReply(context, prompt);
          turn = {
            role: "agent", text: r.text, reasoning: r.reasoning, actions: r.actions, citations: r.citations,
            applied: {}, timestamp: new Date().toISOString(), mode: "offline",
            offlineReason: data.reason, grounding: data.grounding,
          };
        }
      } catch (e) {
        const r = pickReply(context, prompt);
        turn = {
          role: "agent", text: r.text, reasoning: r.reasoning, actions: r.actions, citations: r.citations,
          applied: {}, timestamp: new Date().toISOString(), mode: "offline",
          offlineReason: e instanceof Error ? e.message : String(e),
        };
      }
      if (myReq !== reqId.current) return; // view changed while waiting
      // Turn grounding into navigable actions for the records it cited.
      const firstRun = turn.grounding?.sources.find((s) => s.kind === "run" && s.href);
      if (turn.mode === "live" && firstRun?.href && !turn.actions?.length) {
        turn.actions = [{ kind: "navigate", description: `Open ${firstRun.title}`, href: firstRun.href }];
      }
      setHistory((prev) => [...prev, turn]);
      setThinking(false);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [context, view?.kind, view?.id, ground, history, thinking],
  );

  const runPreview = useCallback(async () => {
    if (!view || !input.trim()) return;
    setPreview({ loading: true });
    try {
      const res = await fetch("/api/assist/context", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: input, view, ground }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? `HTTP ${res.status}`);
      setPreview({ loading: false, grounding: data.grounding });
    } catch (e) {
      setPreview({ loading: false, error: e instanceof Error ? e.message : String(e) });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [input, view?.kind, view?.id, ground]);

  const onApply = useCallback(
    async (turnIdx: number, actionIdx: number, action: ApplyAction) => {
      try {
        if (action.kind === "navigate") {
          window.location.assign(action.href);
        } else if (applyHandler) {
          await applyHandler.run(action);
        } else {
          window.dispatchEvent(new CustomEvent("assist-apply", { detail: action }));
        }
        setHistory((prev) =>
          prev.map((t, i) => (i === turnIdx ? { ...t, applied: { ...t.applied, [actionIdx]: "applied" } } : t)),
        );
        if (action.kind !== "navigate") toast.success("Applied", { description: action.description });
      } catch (e) {
        toast.error("Apply failed", { description: e instanceof Error ? e.message : String(e) });
      }
    },
    [applyHandler],
  );

  const onDismiss = useCallback((turnIdx: number, actionIdx: number) => {
    setHistory((prev) =>
      prev.map((t, i) => (i === turnIdx ? { ...t, applied: { ...t.applied, [actionIdx]: "dismissed" } } : t)),
    );
  }, []);

  const suggestions = getSuggestions(context);
  const contextLabel = view?.label ?? "—";

  return (
    // Non-modal + no overlay: a docked work surface, not a blocking dialog.
    // The page stays sharp and interactive behind it.
    <Sheet open={open} onOpenChange={setOpen} modal={false}>
      <SheetContent
        side="right"
        title="Ask the agent"
        description={`Read-only assistant grounded in the ${contextLabel} view, the Decision Ledger, standards bundles, OpenSpec and GitHub.`}
        overlay="none"
        onInteractOutside={(e) => e.preventDefault()}
        className="flex w-full flex-col border-l border-[var(--border-default)] p-0 shadow-[-24px_0_48px_-24px_rgba(0,0,0,0.5)] sm:max-w-[460px]"
      >
        {/* Header */}
        <div className="relative space-y-3 overflow-hidden border-b border-[var(--border-muted)] px-5 pb-4 pt-5">
          <div className="pointer-events-none absolute inset-0 [background:radial-gradient(420px_120px_at_0%_0%,color-mix(in_srgb,var(--plane-agenthq)_14%,transparent),transparent)]" />
          <div className="relative flex items-center gap-2 pr-6">
            <span className="flex h-7 w-7 items-center justify-center rounded-md bg-[color-mix(in_srgb,var(--plane-agenthq)_var(--tint-strong),transparent)]">
              <Sparkles className="h-4 w-4 text-[var(--plane-agenthq)]" />
            </span>
            <div className="min-w-0">
              <h2 className="text-sm font-semibold leading-tight">Ask the agent</h2>
              <div className="flex items-center gap-1.5 text-[10px] text-[var(--text-tertiary)]">
                <span className="pulse-dot h-1.5 w-1.5 rounded-full bg-[var(--success)]" />
                read-only · grounded · PHI-guarded
              </div>
            </div>
            {history.length > 0 && (
              <button
                type="button"
                onClick={() => { reqId.current += 1; setHistory([]); setThinking(false); }}
                className="ml-auto inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px] text-[var(--text-tertiary)] hover:bg-[var(--overlay)] hover:text-[var(--text)]"
              >
                <RotateCcw className="h-3 w-3" /> New chat
              </button>
            )}
          </div>
          {/* Context dock: what the agent is anchored to right now */}
          <div className="relative flex flex-wrap items-center gap-1.5">
            <span className="inline-flex items-center gap-1 rounded-full border border-[var(--border-default)] bg-[var(--elevated)] px-2 py-0.5 text-[10px]">
              <Radar className="h-3 w-3 text-[var(--primary)]" /> {contextLabel}
              {view?.id && <span className="mono text-[var(--text-tertiary)]">· {view.id.slice(0, 8)}</span>}
            </span>
            {(["ledger", "run", "rule", "openspec", "github"] as SourceKind[]).map((k) => {
              const M = SOURCE_META[k];
              const Icon = M.icon;
              return (
                <span key={k} className="inline-flex items-center gap-1 rounded-full bg-[var(--overlay)] px-2 py-0.5 text-[10px] text-[var(--text-secondary)]" title={`${M.label} is searched for every question`}>
                  <Icon className="h-3 w-3" style={{ color: M.color }} /> {M.label}
                </span>
              );
            })}
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 space-y-5 overflow-y-auto px-5 py-4">
          {history.length === 0 && (
            <div className="space-y-3">
              <div className="text-xs font-medium text-[var(--text-secondary)]">Ask about what you are looking at</div>
              <div className="flex flex-col gap-2">
                {[...suggestions, "Which rule is blocking the most runs?", "What changed in the repo recently?"].slice(0, 5).map((s, i) => (
                  <button
                    key={i}
                    onClick={() => send(s)}
                    className="group flex items-center gap-2 rounded-md border border-[var(--border-muted)] px-3 py-2 text-left text-xs transition-colors hover:border-[var(--text-tertiary)] hover:bg-[var(--overlay)]/40"
                  >
                    <span className="flex-1">{s}</span>
                    <ArrowRight className="h-3 w-3 text-[var(--text-tertiary)] opacity-0 transition-opacity group-hover:opacity-100" />
                  </button>
                ))}
              </div>
              <p className="pt-1 text-[11px] leading-relaxed text-[var(--text-tertiary)]">
                Each question is answered from this view plus the live Decision Ledger, run state,
                pinned standards bundles, OpenSpec changes and recent GitHub activity. Every reply
                shows exactly what was injected. It can point you to a record; it cannot approve,
                edit or write to the ledger.
              </p>
            </div>
          )}

          {history.map((turn, i) => (
            <ChatBubble key={i} turn={turn} turnIdx={i} onApply={onApply} onDismiss={onDismiss} />
          ))}

          {thinking && <ThinkingTrace grounded={ground} />}
          <div ref={endRef} />
        </div>

        {/* Context preview */}
        {preview && (
          <div className="max-h-[38%] overflow-y-auto border-t border-[var(--border-muted)] bg-[var(--elevated)] px-5 py-3">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-[11px] font-semibold">Context that would be injected</span>
              <button type="button" onClick={() => setPreview(null)} aria-label="Close preview" className="text-[var(--text-tertiary)] hover:text-[var(--text)]">
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
            {preview.loading ? (
              <div className="flex items-center gap-2 text-xs text-[var(--text-tertiary)]"><Loader2 className="h-3 w-3 animate-spin" /> Retrieving…</div>
            ) : preview.error ? (
              <div className="text-xs text-[var(--danger)]">Preview unavailable: {preview.error}</div>
            ) : preview.grounding ? (
              <GroundingDetail g={preview.grounding} open />
            ) : null}
          </div>
        )}

        {/* Composer */}
        <div className="border-t border-[var(--border-muted)] p-4">
          <div className="rounded-lg border border-[var(--border-default)] bg-[var(--bg)] focus-within:border-[var(--primary)]">
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
              rows={3}
              className="min-h-[72px] resize-none border-0 bg-transparent text-[13px] focus-visible:ring-0"
            />
            <div className="flex items-center gap-2 border-t border-[var(--border-muted)] px-2 py-1.5">
              <label className="inline-flex cursor-pointer items-center gap-1.5 text-[11px] text-[var(--text-secondary)]" title="Off sends the question verbatim, with no retrieved context">
                <input type="checkbox" checked={ground} onChange={(e) => setGround(e.target.checked)} className="accent-[var(--primary)]" />
                Ground on live data
              </label>
              <button
                type="button"
                onClick={runPreview}
                disabled={!input.trim() || !ground}
                className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] text-[var(--text-tertiary)] hover:bg-[var(--overlay)] hover:text-[var(--text)] disabled:opacity-40"
              >
                <Eye className="h-3 w-3" /> Preview context
              </button>
              <Button variant="primary" size="sm" onClick={() => send(input)} disabled={!input.trim() || thinking} className="ml-auto h-7">
                <Send className="h-3.5 w-3.5" /> Send
              </Button>
            </div>
          </div>
          <div className="mt-1.5 text-[10px] text-[var(--text-tertiary)]">Enter to send · Shift+Enter for newline · ⌘K toggles</div>
        </div>
      </SheetContent>
    </Sheet>
  );
}

/** Honest progress: names the steps the server actually runs, in order. */
function ThinkingTrace({ grounded }: { grounded: boolean }) {
  const steps = grounded
    ? ["Reading this view", "Searching ledger, runs, rules, OpenSpec, GitHub", "PHI check on excerpts", "Asking the model"]
    : ["Asking the model (no context)"];
  const [i, setI] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setI((x) => Math.min(x + 1, steps.length - 1)), 900);
    return () => clearInterval(t);
  }, [steps.length]);
  return (
    <div className="flex items-start gap-2">
      <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[color-mix(in_srgb,var(--plane-agenthq)_var(--tint),transparent)]">
        <Loader2 className="h-3 w-3 animate-spin text-[var(--plane-agenthq)]" />
      </div>
      <ol className="space-y-1 text-[11px]">
        {steps.map((s, j) => (
          <li key={s} className={cn("flex items-center gap-1.5 transition-opacity", j > i ? "opacity-55" : "opacity-100")}>
            {j < i ? <CheckCircle2 className="h-3 w-3 text-[var(--success)]" /> : <span className="h-3 w-3 rounded-full border border-[var(--border-default)]" />}
            <span className={j === i ? "text-[var(--text)]" : "text-[var(--text-tertiary)]"}>{s}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

/** "What I looked at" — the exact context injected for this turn. */
function GroundingDetail({ g, open, highlight }: { g: Grounding; open?: boolean; highlight?: number | null }) {
  const counts = g.sources.reduce<Record<string, number>>((m, s) => ({ ...m, [s.kind]: (m[s.kind] ?? 0) + 1 }), {});
  return (
    <details open={open} className="group rounded-md border border-[var(--border-muted)] bg-[var(--surface)]">
      <summary className="flex cursor-pointer list-none flex-wrap items-center gap-1.5 px-2.5 py-1.5 text-[11px] text-[var(--text-secondary)]">
        <Eye className="h-3 w-3" />
        <span className="font-medium">What I looked at</span>
        {Object.entries(counts).map(([k, n]) => {
          const M = SOURCE_META[k as SourceKind];
          const Icon = M.icon;
          return (
            <span key={k} className="inline-flex items-center gap-0.5 rounded bg-[var(--overlay)] px-1.5 py-px text-[10px]">
              <Icon className="h-2.5 w-2.5" style={{ color: M.color }} /> {n}
            </span>
          );
        })}
        {g.derived.length > 0 && (
          <span className="inline-flex items-center gap-0.5 rounded bg-[var(--overlay)] px-1.5 py-px text-[10px]">
            <Calculator className="h-2.5 w-2.5 text-[var(--warning)]" /> {g.derived.length}
          </span>
        )}
        {g.withheld && (
          <span className="inline-flex items-center gap-0.5 rounded bg-[color-mix(in_srgb,var(--danger)_var(--tint),transparent)] px-1.5 py-px text-[10px] text-[var(--danger)]">
            <ShieldAlert className="h-2.5 w-2.5" /> {g.withheld.count} withheld
          </span>
        )}
        {g.warnings.length > 0 && <AlertTriangle className="h-3 w-3 text-[var(--warning)]" />}
      </summary>
      <div className="space-y-2 border-t border-[var(--border-muted)] px-2.5 py-2">
        {g.derived.length > 0 && (
          <div>
            <div className="mb-1 text-[10px] text-[var(--text-tertiary)]">Computed from the record</div>
            <ul className="space-y-0.5">
              {g.derived.map((d, i) => (
                <li key={i} className="text-[11px] text-[var(--text-secondary)]">{d}</li>
              ))}
            </ul>
          </div>
        )}
        {g.sources.length > 0 && (
          <ol className="space-y-1">
            {g.sources.map((s, i) => (
              <SourceRow key={`${s.kind}-${s.ref}`} n={i + 1} s={s} active={highlight === i + 1} />
            ))}
          </ol>
        )}
        {g.withheld && (
          <div className="flex items-start gap-1.5 text-[11px] text-[var(--danger)]">
            <ShieldAlert className="mt-px h-3 w-3 shrink-0" />
            {g.withheld.count} matching excerpt{g.withheld.count === 1 ? " was" : "s were"} withheld from the model by the PHI guard <span className="mono">[{g.withheld.rule}]</span>.
          </div>
        )}
        {g.warnings.map((w, i) => (
          <div key={i} className="flex items-start gap-1.5 text-[11px] text-[var(--warning)]">
            <AlertTriangle className="mt-px h-3 w-3 shrink-0" /> {w}
          </div>
        ))}
        {!g.sources.length && !g.derived.length && (
          <div className="text-[11px] text-[var(--text-tertiary)]">Nothing was injected.</div>
        )}
      </div>
    </details>
  );
}

function SourceRow({ n, s, active }: { n: number; s: GroundingSource; active?: boolean }) {
  const M = SOURCE_META[s.kind];
  const Icon = M.icon;
  const external = s.href?.startsWith("http");
  const body = (
    <>
      <span className="mt-px inline-flex h-4 min-w-4 items-center justify-center rounded bg-[var(--overlay)] px-1 text-[10px] font-semibold tabular">{n}</span>
      <Icon className="mt-0.5 h-3 w-3 shrink-0" style={{ color: M.color }} />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[11px] text-[var(--text)]">{s.title}</span>
        {s.excerpt && <span className="line-clamp-2 block text-[10px] text-[var(--text-tertiary)]">{s.excerpt}</span>}
        {s.matched && <span className="block text-[10px] italic text-[var(--text-tertiary)]">{s.matched}</span>}
      </span>
    </>
  );
  const cls = cn(
    "flex items-start gap-1.5 rounded px-1 py-1 transition-colors",
    active && "bg-[color-mix(in_srgb,var(--primary)_var(--tint),transparent)] ring-1 ring-[var(--primary)]",
    s.href && "hover:bg-[var(--overlay)]",
  );
  return (
    <li id={`src-${n}`}>
      {s.href ? (
        external ? (
          <a href={s.href} target="_blank" rel="noopener noreferrer" className={cls}>{body}</a>
        ) : (
          <Link href={s.href} className={cls}>{body}</Link>
        )
      ) : (
        <div className={cls}>{body}</div>
      )}
    </li>
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
  const [cite, setCite] = useState<number | null>(null);
  if (turn.role === "user") {
    return (
      <div className="flex items-start gap-2 justify-end">
        <div className="max-w-[85%] rounded-lg rounded-tr-sm bg-[color-mix(in_srgb,var(--primary)_var(--tint),transparent)] border border-[var(--primary)]/20 px-3 py-2">
          <p className="text-[13px] leading-relaxed whitespace-pre-wrap">{turn.text}</p>
          {turn.grounded === false && <p className="mt-1 text-[10px] text-[var(--text-tertiary)]">sent without context</p>}
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
        <div className="flex flex-wrap items-center gap-1.5 text-[10px] text-[var(--text-tertiary)]">
          {turn.mode === "live" ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-[color-mix(in_srgb,var(--success)_var(--tint),transparent)] px-1.5 py-px text-[var(--success)]">
              <Cpu className="h-2.5 w-2.5" /> {turn.model}
            </span>
          ) : (
            <span
              className="inline-flex items-center gap-1 rounded-full bg-[color-mix(in_srgb,var(--warning)_var(--tint),transparent)] px-1.5 py-px text-[var(--warning)]"
              title={turn.offlineReason}
            >
              <AlertTriangle className="h-2.5 w-2.5" /> offline composer
            </span>
          )}
          {turn.latencyMs != null && <span className="tabular">{(turn.latencyMs / 1000).toFixed(1)}s</span>}
          {turn.tokens != null && <span className="tabular">· {turn.tokens.toLocaleString()} tokens</span>}
        </div>
        {turn.mode === "live" ? (
          <ReplyText
            text={turn.text}
            sourceCount={turn.grounding?.sources.length}
            onCite={(n) => {
              setCite(n);
              requestAnimationFrame(() => document.getElementById(`src-${n}`)?.scrollIntoView({ behavior: "smooth", block: "nearest" }));
            }}
          />
        ) : (
          <div className="text-xs leading-relaxed text-[var(--text-secondary)] whitespace-pre-wrap">{turn.text}</div>
        )}
        {turn.mode === "offline" && turn.offlineReason && (
          <p className="text-[10px] text-[var(--text-tertiary)]">Model unavailable ({turn.offlineReason}). This answer comes from the deterministic composer over local demo data.</p>
        )}
        {turn.grounding && <GroundingDetail g={turn.grounding} open={cite != null} highlight={cite} />}
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
      <div className="rounded-md border border-[var(--success)]/30 bg-[color-mix(in_srgb,var(--success)_var(--tint-weak),transparent)] px-3 py-2 flex items-center gap-2">
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
          ? "border-[var(--primary)]/30 bg-[color-mix(in_srgb,var(--primary)_var(--tint-weak),transparent)]"
          : "border-[var(--warning)]/30 bg-[color-mix(in_srgb,var(--warning)_var(--tint-weak),transparent)]",
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
        // Icon-only at rest so it stops covering table cells, chart legends
        // and run cards; the label slides out on hover / keyboard focus.
        "flex items-center h-11 min-w-11 justify-center rounded-full px-3",
        "bg-[var(--plane-agenthq)] text-[var(--on-primary)] font-medium",
        "shadow-lg hover:shadow-xl transition-all",
      )}
      title="Ask the agent for help with this page (⌘K)"
      aria-label="Ask the agent"
    >
      <Sparkles className="h-4 w-4 shrink-0" />
      <span className="max-w-0 overflow-hidden whitespace-nowrap text-xs opacity-0 transition-all duration-300 group-hover:ml-2 group-hover:max-w-40 group-hover:opacity-100 group-focus-visible:ml-2 group-focus-visible:max-w-40 group-focus-visible:opacity-100">
        Ask the agent <span className="mono text-[10px] opacity-60">⌘K</span>
      </span>
    </button>
  );
}
