/**
 * /api/settings — aggregated enterprise posture.
 *
 * Server-side (matching /api/economics) so the orchestrator URL and any future
 * auth header never reach the browser.
 *
 * Preferred: orchestrator GET /api/config/settings. When the deployed
 * orchestrator predates that endpoint (404), the posture is composed from the
 * individual config endpoints it does serve, and the response says so
 * (`composed: true`). Sections with no source are returned as explicit error
 * sections.
 *
 * Deliberately does NOT fail open to an empty settings object: a settings page
 * that renders "nothing is configured" when the real answer is "we could not
 * ask" would tell the operator a lie about their own governance posture. An
 * unreachable orchestrator returns 502 with an explicit error.
 */
import { NextResponse } from "next/server";
import { composeLegacySettings, type LegacyInputs } from "@/lib/server/settings-compose";

export const revalidate = 0;

function orchestratorBase(): string {
  return (
    process.env.ORCHESTRATOR_URL ??
    process.env.NEXT_PUBLIC_ORCHESTRATOR_URL ??
    "https://ca-orchestrator-vnet.thankfulflower-0a94d0d3.eastus2.azurecontainerapps.io"
  );
}

async function get<T>(path: string): Promise<{ ok: true; data: T } | { ok: false; error: string }> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 10_000);
  try {
    const res = await fetch(`${orchestratorBase()}${path}`, { cache: "no-store", signal: ctrl.signal });
    if (!res.ok) return { ok: false, error: `${path} returned ${res.status}` };
    return { ok: true, data: (await res.json()) as T };
  } catch (e) {
    return { ok: false, error: `${path}: ${e instanceof Error ? e.message : String(e)}` };
  } finally {
    clearTimeout(t);
  }
}

export async function GET() {
  const native = await get<{ sections: unknown[] }>("/api/config/settings");
  if (native.ok) return NextResponse.json(native.data);

  // Only a missing endpoint justifies composing. Any other failure (auth,
  // outage) is reported as the failure it is.
  if (!/returned 404$/.test(native.error)) {
    return NextResponse.json({ error: `orchestrator unreachable: ${native.error}`, sections: [] }, { status: 502 });
  }

  const [hardGate, pins, repoAutonomy, integrations] = await Promise.all([
    get<LegacyInputs["hardGate"] extends { ok: true; data: infer D } ? D : never>("/api/config/hard-gate-classes"),
    get<LegacyInputs["pins"] extends { ok: true; data: infer D } ? D : never>("/api/config/pins"),
    get<LegacyInputs["repoAutonomy"] extends { ok: true; data: infer D } ? D : never>("/api/config/repo-autonomy"),
    get<LegacyInputs["integrations"] extends { ok: true; data: infer D } ? D : never>("/api/integrations"),
  ]);
  if (!hardGate.ok && !pins.ok && !repoAutonomy.ok) {
    return NextResponse.json(
      { error: `orchestrator serves no configuration endpoints (${hardGate.error})`, sections: [] },
      { status: 502 },
    );
  }
  return NextResponse.json(composeLegacySettings({ hardGate, pins, repoAutonomy, integrations }));
}
