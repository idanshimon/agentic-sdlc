import { forwardToLedgerMcp } from "@/lib/server/mcp-proxy";

export const runtime = "nodejs";

export async function POST(req: Request) {
  const body = await req.json();
  return forwardToLedgerMcp("/tools/ledger.classify_phi", body);
}
