/**
 * /api/integrations/[...path] — proxy for the integrations registry.
 *
 * GET  /api/integrations            -> orchestrator GET  /api/integrations
 * POST /api/integrations/<id>/test  -> orchestrator POST /api/integrations/<id>/test
 *
 * Server-side so the orchestrator URL and auth stay off the browser. Nothing
 * here invents a status: whatever the orchestrator says (including `unknown`)
 * is what the UI renders. A transport failure is a 502 error state, never a
 * silently green or silently empty list.
 */
import { NextResponse } from "next/server";

export const revalidate = 0;

function orchestratorBase(): string {
  return (
    process.env.NEXT_PUBLIC_ORCHESTRATOR_URL ??
    "https://ca-orchestrator-vnet.thankfulflower-0a94d0d3.eastus2.azurecontainerapps.io"
  );
}

/** Only the shapes this proxy is allowed to forward. Prevents the catch-all
 *  segment from being used to reach arbitrary orchestrator paths. */
function resolveTarget(segments: string[], method: "GET" | "POST"): string | null {
  if (method === "GET" && segments.length === 0) return "/api/integrations";
  if (
    method === "POST" &&
    segments.length === 2 &&
    segments[1] === "test" &&
    /^[A-Za-z0-9._-]{1,64}$/.test(segments[0])
  ) {
    return `/api/integrations/${encodeURIComponent(segments[0])}/test`;
  }
  return null;
}

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ path?: string[] }> },
) {
  const { path } = await params;
  const target = resolveTarget(path ?? [], "GET");
  if (!target) {
    return NextResponse.json({ error: "unsupported integrations path" }, { status: 404 });
  }
  try {
    const res = await fetch(`${orchestratorBase()}${target}`, { cache: "no-store" });
    if (!res.ok) {
      return NextResponse.json(
        { error: `orchestrator ${target} returned ${res.status}`, loaded: false, integrations: [] },
        { status: 502 },
      );
    }
    return NextResponse.json(await res.json());
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return NextResponse.json(
      { error: `orchestrator unreachable: ${msg}`, loaded: false, integrations: [] },
      { status: 502 },
    );
  }
}

export async function POST(
  _request: Request,
  { params }: { params: Promise<{ path?: string[] }> },
) {
  const { path } = await params;
  const target = resolveTarget(path ?? [], "POST");
  if (!target) {
    return NextResponse.json({ error: "unsupported integrations path" }, { status: 404 });
  }
  try {
    const res = await fetch(`${orchestratorBase()}${target}`, {
      method: "POST",
      cache: "no-store",
    });
    const body = await res.json().catch(() => ({}));
    // Forward the orchestrator's own verdict verbatim, including its status
    // code — a failing probe is information, not an error to swallow.
    return NextResponse.json(body, { status: res.ok ? 200 : res.status });
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return NextResponse.json(
      { status: "unknown", reason: `probe could not be run: ${msg}` },
      { status: 502 },
    );
  }
}
