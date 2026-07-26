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
  async query(filter: { team_id?: string; run_id?: string; entry_type?: string; limit?: number }): Promise<{
    entries: LedgerEntry[];
    team_id?: string;
    demo?: boolean;
    live_unreachable?: boolean;
  }> {
    if (isDemoMode()) {
      // Demo Mode reads the REAL ledger. Seeded historical entries are merged
      // in (de-duped by id, live wins, newest-first) so a demo has depth of
      // history — but they never replace or mask live data. If the live read
      // fails we say so via `live_unreachable` rather than quietly rendering
      // seed rows as if they were current.
      const demoEntries = listDemoLedgerEntries(filter) as unknown as LedgerEntry[];
      const live = await proxy<{ entries: LedgerEntry[]; team_id?: string }>("/api/ledger/query", filter)
        .catch(() => null);
      if (live === null) {
        return { entries: mergeLedgerEntries(demoEntries, []), demo: true, live_unreachable: true };
      }
      return {
        entries: mergeLedgerEntries(demoEntries, live.entries ?? []),
        team_id: live.team_id,
        demo: true,
      };
    }
    const live = await proxy<{ entries: LedgerEntry[]; team_id?: string }>("/api/ledger/query", filter);
    return { entries: live.entries ?? [], team_id: live.team_id };
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
