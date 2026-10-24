/* POST /api/assist/context — preview exactly what WOULD be injected for a
 * question, without calling the model (Atlas "context preview"). */
import { NextResponse } from "next/server";
import { prepareContext } from "@/lib/server/assist-context";
import { liveSources } from "@/lib/server/assist-sources";
import { parseAssistBody } from "@/lib/server/assist-request";

export const runtime = "nodejs";

export async function POST(req: Request) {
  const parsed = parseAssistBody(await req.json().catch(() => null));
  if ("error" in parsed) return NextResponse.json(parsed, { status: 400 });
  const { prompt, grounding } = await prepareContext(liveSources(), parsed);
  return NextResponse.json({ grounding, prompt_chars: prompt.length });
}
