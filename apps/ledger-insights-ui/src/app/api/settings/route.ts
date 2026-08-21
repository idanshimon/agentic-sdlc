/**
 * /api/settings — aggregated enterprise posture.
 *
 * Thin proxy to the orchestrator's GET /api/config/settings. Kept server-side
 * (matching /api/economics) so the orchestrator URL and any future auth header
 * never reach the browser.
 *
 * Deliberately does NOT fail open to an empty settings object: a settings page
 * that renders "nothing is configured" when the real answer is "we could not
 * ask" would tell the operator a lie about their own governance posture. An
 * unreachable orchestrator returns 502 with an explicit error the page renders
 * as an error state.
 */
import { NextResponse } from "next/server";

export const revalidate = 0;

function orchestratorBase(): string {
  return (
    process.env.NEXT_PUBLIC_ORCHESTRATOR_URL ??
    "https://ca-orchestrator-vnet.thankfulflower-0a94d0d3.eastus2.azurecontainerapps.io"
  );
}

export async function GET() {
  try {
    const res = await fetch(`${orchestratorBase()}/api/config/settings`, {
      cache: "no-store",
    });
    if (!res.ok) {
      return NextResponse.json(
        {
          error: `orchestrator /api/config/settings returned ${res.status}`,
          sections: [],
        },
        { status: 502 },
      );
    }
    return NextResponse.json(await res.json());
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return NextResponse.json(
      { error: `orchestrator unreachable: ${msg}`, sections: [] },
      { status: 502 },
    );
  }
}
