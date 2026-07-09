import type { LedgerEntry, StandardsBundle } from "../types";
import { isDemoMode, listDemoLedgerEntries } from "@/lib/demo";
import { mergeLedgerEntries } from "./merge-ledger";

/* Browser-side ledger MCP client.
   All MCP calls go through SAME-ORIGIN Next.js route handlers under
   /api/* — those server routes attach the bearer token from env. This
   keeps the token out of the browser. See lib/server/mcp-proxy.ts.

   /healthz and /tools are unauthenticated and can be called direct
   (cross-origin is fine via the Container App corsPolicy). */

import { apiConfig } from "./config";

async function direct<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${apiConfig.ledgerMcpUrl}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`${path} HTTP ${res.status}`);
  return res.json() as Promise<T>;
}

async function proxy<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
    cache: "no-store",
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`${path} HTTP ${res.status}${detail ? `: ${detail.slice(0, 200)}` : ""}`);
  }
  return res.json() as Promise<T>;
}

export const ledgerMcp = {
  health() {
    return direct<{ status: string; version: string }>("/healthz");
  },
  tools() {
    return direct<{ tools: { name: string; description: string }[] }>("/tools");
  },
  async query(filter: { team_id?: string; run_id?: string; entry_type?: string; limit?: number }) {
    if (isDemoMode()) {
      // Demo Mode: merge demo ledger entries with live entries. The merge
      // de-dupes by id (live wins) and sorts newest-first, so a just-written
      // live decision surfaces at the TOP instead of being appended below the
      // demo seed block (the "decisions table shows nothing new / 2d ago" bug).
      const demoEntries = listDemoLedgerEntries(filter) as unknown as LedgerEntry[];
      try {
        const live = await proxy<{ entries: LedgerEntry[] }>("/api/ledger/query", filter);
        return { entries: mergeLedgerEntries(demoEntries, live.entries ?? []) };
      } catch {
        return { entries: mergeLedgerEntries(demoEntries, []) };
      }
    }
    return proxy<{ entries: LedgerEntry[] }>("/api/ledger/query", filter);
  },
  getBundle(dept: string, version: string) {
    return proxy<StandardsBundle>("/api/ledger/bundle", { dept, version });
  },
  classifyPhi(text: string, team_id: string = "team-demo") {
    return proxy<{
      has_phi: boolean;
      phi_class: "none" | "low" | "high";
      matched_patterns: string[];
      bundle_refs: string[];
    }>("/api/phi", { text, team_id });
  },
};
