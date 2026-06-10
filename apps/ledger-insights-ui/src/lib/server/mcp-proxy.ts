/* Shared server-side helper used by /app/api/* route handlers to forward
   requests to the ledger MCP with the bearer token attached. The token lives
   in Container App env vars (set in apps.bicep, mounted as a secret ref);
   keeping it server-side means the browser never sees it. */

import { NextResponse } from "next/server";

const env = process.env;

function ledgerUrl(): string {
  return (
    env["LEDGER_MCP_URL"] ??
    env["NEXT_PUBLIC_LEDGER_MCP_URL"] ??
    "https://ca-ledger-mcp.whitewater-f74a5db8.eastus2.azurecontainerapps.io"
  );
}

function bearer(): string | undefined {
  return env["LEDGER_MCP_TOKEN"] ?? env["LEDGER_MCP_DEMO_TOKEN"];
}

/**
 * Low-level: POST to a tool path on the ledger MCP, return parsed JSON +
 * the upstream HTTP status. Used when a route handler needs to react to the
 * upstream response (e.g. /api/economics computes aggregations on top).
 */
export async function callLedgerMcp(
  toolPath: string,
  body: unknown,
): Promise<{ status: number; data: unknown }> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = bearer();
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${ledgerUrl()}${toolPath}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body ?? {}),
    cache: "no-store",
  });
  const text = await res.text();
  let data: unknown = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { error: "Non-JSON response from ledger-mcp", body: text.slice(0, 500) };
  }
  return { status: res.status, data };
}

/**
 * High-level: forward a request and return a NextResponse mirroring the
 * upstream status/body. Used by simple proxy routes like /api/ledger/query.
 */
export async function forwardToLedgerMcp(toolPath: string, body: unknown) {
  const { status, data } = await callLedgerMcp(toolPath, body);
  return NextResponse.json(data, { status });
}
