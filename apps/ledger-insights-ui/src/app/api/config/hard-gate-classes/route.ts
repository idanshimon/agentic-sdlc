/**
 * /api/config/hard-gate-classes — server-side proxy to the orchestrator's
 * hard-gate config endpoint. Returns the immovable autonomy floor (the
 * ambiguity classes that can never be auto-resolved — PHI/auth by default).
 *
 * Proxied (not called directly from the browser) so the orchestrator URL and
 * any future auth stay server-side, matching /api/economics.
 */
import { NextResponse } from "next/server";

export const revalidate = 30;

export async function GET() {
  const orchestratorUrl =
    process.env.NEXT_PUBLIC_ORCHESTRATOR_URL ??
    "https://ca-orchestrator-vnet.thankfulflower-0a94d0d3.eastus2.azurecontainerapps.io";

  try {
    const res = await fetch(`${orchestratorUrl}/api/config/hard-gate-classes`, {
      cache: "no-store",
    });
    if (!res.ok) {
      return NextResponse.json(
        { hard_gate_classes: ["auth-policy", "phi-classification"], floor: ["auth-policy", "phi-classification"], error: `orchestrator HTTP ${res.status}` },
        { status: 200 },
      );
    }
    const data = await res.json();
    return NextResponse.json(data);
  } catch (e) {
    // Fail safe to the known default floor so the page still renders.
    return NextResponse.json(
      {
        hard_gate_classes: ["auth-policy", "phi-classification"],
        floor: ["auth-policy", "phi-classification"],
        explainer:
          "PHI and auth are an immovable floor — each requires an explicit, attributed human decision. (orchestrator unreachable; showing default floor.)",
        error: String(e).slice(0, 120),
      },
      { status: 200 },
    );
  }
}
