/* Settings posture composition — pure, so the fallback is unit-testable.
 *
 * Preferred source: orchestrator GET /api/config/settings (one call, every
 * section). An orchestrator image that predates that endpoint (404) still
 * serves the individual config endpoints, so the posture is composed from
 * them. Every section built this way is marked `source: "composed"`; any
 * section whose source is absent becomes an explicit error section — never an
 * empty "nothing configured" section, which would be a false claim about the
 * operator's own governance.
 */

export interface SettingsSection {
  section: string;
  status: "ok" | "error";
  activation: "activated" | "bootstrap" | "unknown";
  editable: "editable_here" | "governed_pr_only";
  explainer?: string;
  error?: string;
  source?: "native" | "composed";
  [key: string]: unknown;
}

type Fetched<T> = { ok: true; data: T } | { ok: false; error: string };

export interface LegacyInputs {
  hardGate: Fetched<{ hard_gate_classes?: string[]; floor?: string[]; explainer?: string }>;
  pins: Fetched<{ defaults?: Record<string, string>; teams?: Record<string, Record<string, string>>; available?: Record<string, string[]> }>;
  repoAutonomy: Fetched<{ bootstrap?: boolean; default_tier?: string; repos?: unknown[] }>;
  integrations: Fetched<{ integrations?: unknown[]; loaded?: boolean; rejected?: unknown[]; error?: string | null }>;
}

const UPGRADE = "Not exposed by the deployed orchestrator version; upgrade the orchestrator to read this section.";

function missing(section: string, editable: SettingsSection["editable"] = "editable_here", why = UPGRADE): SettingsSection {
  return { section, status: "error", activation: "unknown", editable, error: why, source: "composed" };
}

export function composeLegacySettings(i: LegacyInputs): { sections: SettingsSection[]; composed: true } {
  const sections: SettingsSection[] = [];

  // Organization + models + autonomy matrix have no standalone endpoint on
  // older orchestrators: say so explicitly.
  sections.push(missing("organization"));

  sections.push(
    i.integrations.ok
      ? {
          section: "integrations", status: "ok", source: "composed", editable: "editable_here",
          activation: i.integrations.data.loaded ? "activated" : "bootstrap",
          integrations: i.integrations.data.integrations ?? [],
          rejected: i.integrations.data.rejected ?? [],
          load_error: i.integrations.data.error ?? null,
          explainer: "External systems this instance is wired to. Credentials are referenced by environment variable, never stored here.",
        }
      : missing("integrations", "editable_here", `${UPGRADE} (${i.integrations.error})`),
  );

  sections.push(missing("models"));

  sections.push(
    i.pins.ok
      ? {
          section: "standards_pins", status: "ok", source: "composed", editable: "governed_pr_only",
          activation: Object.keys(i.pins.data.defaults ?? {}).length ? "activated" : "bootstrap",
          pins: i.pins.data,
          explainer: "Pinned standards bundle versions. Bundles are law.",
        }
      : missing("standards_pins", "governed_pr_only", i.pins.error),
  );

  sections.push(
    i.repoAutonomy.ok
      ? {
          section: "repo_autonomy", status: "ok", source: "composed", editable: "editable_here",
          activation: i.repoAutonomy.data.bootstrap ? "bootstrap" : "activated",
          ...i.repoAutonomy.data,
          explainer: "Per-repo autonomy tier for the review loop. PHI/auth/deny always force runtime escalation regardless of tier.",
        }
      : missing("repo_autonomy", "editable_here", i.repoAutonomy.error),
  );

  sections.push(
    i.hardGate.ok
      ? {
          section: "governance", status: "ok", source: "composed", editable: "governed_pr_only",
          activation: "activated",
          hard_gate_classes: i.hardGate.data.hard_gate_classes ?? [],
          floor: i.hardGate.data.floor ?? [],
          explainer: i.hardGate.data.explainer,
        }
      : missing("governance", "governed_pr_only", i.hardGate.error),
  );

  return { sections, composed: true };
}
