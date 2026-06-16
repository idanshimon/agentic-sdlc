/**
 * /api/feedback/* server-side proxy routes for Track B teaching signals.
 *
 * Each subpath forwards to the matching ledger.* tool on the MCP server with
 * the bearer token. Same pattern as /api/ledger/query — token never leaves
 * the server.
 */

import { forwardToLedgerMcp } from "@/lib/server/mcp-proxy";

export const runtime = "nodejs";

const PATH_MAP: Record<string, string> = {
  thumbs: "/tools/ledger.add_feedback",
  flag: "/tools/ledger.flag_decision",
  replay: "/tools/ledger.request_replay",
  "pause-class": "/tools/ledger.pause_class",
};

export async function POST(
  req: Request,
  { params }: { params: Promise<{ kind: string }> },
) {
  const { kind } = await params;
  const target = PATH_MAP[kind];
  if (!target) {
    return Response.json(
      { error: `unknown feedback kind: ${kind}` },
      { status: 400 },
    );
  }
  const body = await req.json();
  return forwardToLedgerMcp(target, body);
}
