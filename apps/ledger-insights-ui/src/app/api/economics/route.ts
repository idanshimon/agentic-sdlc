/**
 * /api/economics — aggregate ledger entries into economics rollups.
 *
 * Phase 7 (2026-06-16): the /economics page was calling /api/economics
 * but the route didn't exist (returned 404). This route fetches recent
 * decisions from the orchestrator's existing /api/telemetry/decisions
 * endpoint and aggregates them via the pure functions in lib/economics
 * (same module used by client-side KPI tiles, so the math is consistent
 * between server-rendered economics dashboards and client-rendered drill-ins).
 *
 * Routes through the orchestrator (NOT direct Cosmos) because:
 *   1. The orchestrator already has Cosmos RBAC + connection pooling
 *   2. The orchestrator's /api/telemetry/decisions handles the team_id
 *      partition-key fanout for us
 *   3. Read-side authentication stays in one place
 */
import { NextResponse } from "next/server";
import {
  summarize,
  summarizeByTeam,
  trendByDay,
} from "@/lib/economics";
import type { LedgerEntry } from "@/lib/types";

// Cache for 10s — economics doesn't change second-to-second, and the
// /economics page polls every 30s anyway.
export const revalidate = 10;

interface TelemetryDecisionsResponse {
  items: LedgerEntry[];
  count: number;
}

export async function GET(request: Request) {
  const url = new URL(request.url);
  const limitParam = url.searchParams.get("limit");
  const limit = limitParam ? Math.min(Math.max(parseInt(limitParam, 10), 1), 500) : 200;

  const orchestratorUrl =
    process.env.NEXT_PUBLIC_ORCHESTRATOR_URL ??
    "https://ca-orchestrator.whitewater-f74a5db8.eastus2.azurecontainerapps.io";

  try {
    const res = await fetch(
      `${orchestratorUrl}/api/telemetry/decisions?limit=${limit}`,
      {
        // Server-side fetch — bypasses CORS, faster than browser request.
        // Cache disabled because we manage staleness via Next's revalidate.
        cache: "no-store",
      },
    );
    if (!res.ok) {
      return NextResponse.json(
        {
          error: `orchestrator /api/telemetry/decisions returned ${res.status}`,
          summary: emptySummary(),
          by_team: [],
          trend: [],
          sample_size: 0,
          limit_applied: limit,
        },
        { status: 502 },
      );
    }
    const data: TelemetryDecisionsResponse = await res.json();
    const entries = (data.items ?? []).filter(
      (e): e is LedgerEntry => !!e && typeof e === "object" && "id" in e,
    );

    return NextResponse.json({
      summary: summarize(entries),
      by_team: summarizeByTeam(entries),
      trend: trendByDay(entries),
      sample_size: entries.length,
      limit_applied: limit,
    });
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return NextResponse.json(
      {
        error: `economics aggregation failed: ${msg}`,
        summary: emptySummary(),
        by_team: [],
        trend: [],
        sample_size: 0,
        limit_applied: limit,
      },
      { status: 500 },
    );
  }
}

function emptySummary() {
  return {
    total_decisions: 0,
    precedent_hits: 0,
    novel_decisions: 0,
    precedent_hit_rate: 0,
    total_cost_usd: 0,
    avg_novel_cost_usd: 0,
    avg_precedent_cost_usd: 0,
    counterfactual_cost_usd: 0,
    cost_saved_usd: 0,
    cost_saved_ratio: 0,
    autonomy_ratio: 0,
    agent_driven: 0,
    human_gated: 0,
    fallback_used: false,
  };
}
