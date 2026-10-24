/* Shared request validation for /api/assist/*. Bounded sizes so the route
 * cannot be used to push arbitrary large prompts at the model. */
import type { PrepareInput } from "@/lib/server/assist-context";

export type AssistBody = PrepareInput & {
  history: Array<{ role: "user" | "assistant"; content: string }>;
};

export function parseAssistBody(raw: unknown): AssistBody | { error: string } {
  if (!raw || typeof raw !== "object") return { error: "JSON body required" };
  const b = raw as Record<string, unknown>;
  const message = typeof b.message === "string" ? b.message.trim() : "";
  if (!message) return { error: "message is required" };
  if (message.length > 2000) return { error: "message too long (max 2000 chars)" };
  const v = (b.view ?? {}) as Record<string, unknown>;
  if (typeof v.kind !== "string" || !v.kind) return { error: "view.kind is required" };
  const history = Array.isArray(b.history)
    ? (b.history as Array<Record<string, unknown>>)
        .filter((h) => (h.role === "user" || h.role === "assistant") && typeof h.content === "string")
        .slice(-6)
        .map((h) => ({ role: h.role as "user" | "assistant", content: String(h.content).slice(0, 2000) }))
    : [];
  return {
    message,
    view: {
      kind: v.kind,
      id: typeof v.id === "string" ? v.id.slice(0, 120) : undefined,
      label: typeof v.label === "string" ? v.label.slice(0, 120) : undefined,
    },
    ground: b.ground !== false,
    limit: typeof b.limit === "number" ? b.limit : undefined,
    history,
  };
}
