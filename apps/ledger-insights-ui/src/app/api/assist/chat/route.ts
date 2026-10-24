/* POST /api/assist/chat — grounded, read-only operator assistant.
 *
 * prepareContext (scoped retrieval + derived facts + PHI guard) → Azure
 * OpenAI (keyless) → reply + the full grounding record, so the UI can show
 * exactly what the model saw. When no model is configured or the call
 * fails, returns `mode: "unavailable"` with the grounding intact — the
 * client then uses its deterministic composer and labels the reply as such.
 * Never writes to the ledger. */
import { NextResponse } from "next/server";
import { prepareContext, SYSTEM_PROMPT } from "@/lib/server/assist-context";
import { liveSources } from "@/lib/server/assist-sources";
import { chatCompletion, modelConfig } from "@/lib/server/assist-model";
import { parseAssistBody } from "@/lib/server/assist-request";

export const runtime = "nodejs";

export async function POST(req: Request) {
  const parsed = parseAssistBody(await req.json().catch(() => null));
  if ("error" in parsed) return NextResponse.json(parsed, { status: 400 });

  const started = Date.now();
  const { prompt, grounding } = await prepareContext(liveSources(), parsed);
  const cfg = modelConfig();
  if (!cfg) {
    return NextResponse.json({ mode: "unavailable", reason: "No model endpoint configured (ASSIST_AOAI_ENDPOINT).", grounding });
  }
  try {
    const history = parsed.history.slice(-6);
    const { text, usage } = await chatCompletion(cfg, [
      { role: "system", content: SYSTEM_PROMPT },
      ...history,
      { role: "user", content: prompt },
    ]);
    return NextResponse.json({
      mode: "live",
      reply: text,
      model: cfg.deployment,
      usage,
      latency_ms: Date.now() - started,
      grounding,
    });
  } catch (e) {
    return NextResponse.json({
      mode: "unavailable",
      reason: e instanceof Error ? e.message : String(e),
      grounding,
    });
  }
}
