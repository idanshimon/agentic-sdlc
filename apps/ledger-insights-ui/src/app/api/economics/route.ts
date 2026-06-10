import { callLedgerMcp } from "@/lib/server/mcp-proxy";
import { summarize, summarizeByTeam, trendByDay } from "@/lib/economics";
import type { LedgerEntry } from "@/lib/types";

export const runtime = "nodejs";

/**
 * GET /api/economics
 *
 * Server-side aggregation over the ledger. Pulls up to N entries (default 200,
 * the ledger.query max), runs the same aggregator the client uses, returns
 * { summary, by_team, trend }. The client could compute this from a raw
 * /api/ledger/query call, but server-side is cheaper for big tenants and
 * keeps the front-end deterministic.
 *
 * Query params:
 *   - limit (1-200): how many entries to consider (default 200)
 *   - team_id: optional filter; passes through to ledger.query
 *
 * Returns 200 + JSON. Returns the upstream status if the MCP call fails,
 * with the upstream body in the response — we surface errors rather than
 * synthesize zeros (bad data is worse than no data on a finance dashboard).
 */
export async function GET(req: Request) {
  const url = new URL(req.url);
  const limit = Math.min(Number(url.searchParams.get("limit") ?? "200") || 200, 200);
  const teamId = url.searchParams.get("team_id") ?? undefined;

  const queryBody: Record<string, unknown> = { limit };
  if (teamId) queryBody.team_id = teamId;

  const { status, data } = await callLedgerMcp("/tools/ledger.query", queryBody);
  if (status >= 400) {
    return Response.json(data, { status });
  }

  const entries: LedgerEntry[] = (data as { entries?: LedgerEntry[] })?.entries ?? [];

  const summary = summarize(entries);
  const by_team = summarizeByTeam(entries);
  const trend = trendByDay(entries);

  return Response.json({
    summary,
    by_team,
    trend,
    sample_size: entries.length,
    limit_applied: limit,
  });
}
