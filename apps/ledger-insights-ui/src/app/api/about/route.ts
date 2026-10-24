/**
 * /api/about — live identity of the backends this UI talks to.
 * Server-side so backend URLs stay out of the browser. Every probe is
 * reported as reachable/unreachable with what it actually returned; nothing
 * is filled in when a backend does not say.
 */
import { NextResponse } from "next/server";

export const revalidate = 0;

const ORCH =
  process.env.ORCHESTRATOR_URL ??
  process.env.NEXT_PUBLIC_ORCHESTRATOR_URL ??
  "https://ca-orchestrator-vnet.thankfulflower-0a94d0d3.eastus2.azurecontainerapps.io";
const MCP = process.env.LEDGER_MCP_URL ?? process.env.NEXT_PUBLIC_LEDGER_MCP_URL;

async function probe(url: string) {
  const t0 = Date.now();
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 6000);
  try {
    const res = await fetch(url, { cache: "no-store", signal: ctrl.signal });
    const ms = Date.now() - t0;
    if (!res.ok) return { reachable: false, status: res.status, ms };
    return { reachable: true, status: res.status, ms, body: await res.json().catch(() => null) };
  } catch (e) {
    return { reachable: false, error: e instanceof Error ? e.message : String(e), ms: Date.now() - t0 };
  } finally {
    clearTimeout(timer);
  }
}

export async function GET() {
  const [orchHealth, orchApi, mcpHealth] = await Promise.all([
    probe(`${ORCH}/healthz`),
    probe(`${ORCH}/openapi.json`),
    MCP ? probe(`${MCP.replace(/\/$/, "")}/healthz`) : Promise.resolve(null),
  ]);
  const info = (orchApi.body as { info?: { title?: string; version?: string }; paths?: object } | null) ?? null;
  return NextResponse.json({
    orchestrator: {
      host: new URL(ORCH).host,
      reachable: orchHealth.reachable,
      latency_ms: orchHealth.ms,
      status: orchHealth.reachable ? (orchHealth.body as { status?: string } | null)?.status ?? "ok" : null,
      api_title: info?.info?.title ?? null,
      api_version: info?.info?.version ?? null,
      endpoints: info?.paths ? Object.keys(info.paths).length : null,
      supports_settings: info?.paths ? "/api/config/settings" in info.paths : null,
    },
    ledger_mcp: MCP
      ? { host: new URL(MCP).host, reachable: mcpHealth?.reachable ?? false, latency_ms: mcpHealth?.ms ?? null }
      : { host: null, reachable: false, note: "LEDGER_MCP_URL not configured" },
    assistant_model: process.env.ASSIST_AOAI_ENDPOINT || process.env.AOAI_ENDPOINT
      ? { configured: true, deployment: process.env.ASSIST_AOAI_DEPLOYMENT ?? "gpt-4-1-mini" }
      : { configured: false },
    server_time: new Date().toISOString(),
  });
}
