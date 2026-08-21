"use client";
/**
 * /settings — the enterprise posture surface.
 *
 * One place to answer the three questions an enterprise asks after the demo:
 * how do I connect it to my systems, how do I configure it for my org, and
 * what can I NOT change.
 *
 * Two rules this page must never break:
 *   1. `configured` is not `verified`. A declared integration renders
 *      differently from one whose reachability was actually probed.
 *   2. Governance is read-only here. The hard-gate floor and PHI locks render
 *      as locked chips with the standards-change-PR path stated. There is no
 *      edit affordance because there is no endpoint behind one.
 */
import { useCallback, useEffect, useMemo, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  AlertTriangle,
  Building2,
  Cable,
  CheckCircle2,
  CircleDashed,
  Cpu,
  HelpCircle,
  Lock,
  RefreshCw,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

/* ---------------------------------------------------------------- types */

interface SettingsSection {
  section: string;
  status: "ok" | "error";
  activation: "activated" | "bootstrap" | "unknown";
  editable: "editable_here" | "governed_pr_only";
  explainer?: string;
  error?: string;
  [key: string]: unknown;
}

interface SettingsResponse {
  sections?: SettingsSection[];
  error?: string;
}

interface IntegrationRow {
  id: string;
  kind: string;
  provider: string;
  display_name: string;
  base_url: string;
  identity: string;
  scopes: string[];
  token_env: string;
  credential_present: boolean;
  status: "unconfigured" | "configured" | "verified" | "failing" | "unknown";
  verified: boolean;
  item_url_template?: string;
  target_repo?: string;
  notes?: string;
  last_probe?: { status: string; reason: string; probed_at: string; identity?: string };
}

const TABS = [
  { id: "organization", label: "Organization", icon: Building2 },
  { id: "integrations", label: "Integrations", icon: Cable },
  { id: "models", label: "Models", icon: Cpu },
  { id: "governance", label: "Governance", icon: ShieldCheck },
] as const;

/* ------------------------------------------------------------- helpers */

function ActivationBadge({ activation }: { activation: string }) {
  if (activation === "activated") {
    return <Badge variant="success">Activated</Badge>;
  }
  if (activation === "bootstrap") {
    return <Badge variant="outline">Bootstrap</Badge>;
  }
  return <Badge variant="warning">Unknown</Badge>;
}

/** The honesty control of this page. `configured` and `verified` are visually
 *  distinct on purpose — a well-formed config is not evidence of reachability. */
function StatusBadge({ status }: { status: IntegrationRow["status"] }) {
  switch (status) {
    case "verified":
      return (
        <Badge variant="success">
          <CheckCircle2 className="h-3 w-3" /> Verified
        </Badge>
      );
    case "configured":
      return (
        <Badge variant="info">
          <CircleDashed className="h-3 w-3" /> Configured · unverified
        </Badge>
      );
    case "failing":
      return (
        <Badge variant="danger">
          <XCircle className="h-3 w-3" /> Failing
        </Badge>
      );
    case "unknown":
      return (
        <Badge variant="warning">
          <HelpCircle className="h-3 w-3" /> Unknown
        </Badge>
      );
    default:
      return (
        <Badge variant="outline">
          <CircleDashed className="h-3 w-3" /> Not configured
        </Badge>
      );
  }
}

function SectionShell({
  section,
  children,
}: {
  section?: SettingsSection;
  children: React.ReactNode;
}) {
  if (!section) {
    return (
      <Card className="p-6 text-sm text-[var(--text-secondary)]">
        This section was not returned by the orchestrator.
      </Card>
    );
  }
  if (section.status === "error") {
    return (
      <Card className="p-6">
        <div className="flex items-start gap-2">
          <AlertTriangle className="h-4 w-4 shrink-0 text-[var(--danger)]" />
          <div>
            <div className="text-sm font-medium text-[var(--text)]">
              This section could not be loaded
            </div>
            <div className="mono mt-1 text-xs text-[var(--danger)]">{section.error}</div>
            <p className="mt-2 text-xs text-[var(--text-secondary)]">
              Shown as a failure rather than hidden — an empty panel here would read as
              &ldquo;nothing is configured,&rdquo; which is a different and much worse claim.
            </p>
          </div>
        </div>
      </Card>
    );
  }
  return <>{children}</>;
}

function Explainer({ section }: { section?: SettingsSection }) {
  if (!section?.explainer) return null;
  return (
    <p className="text-sm leading-relaxed text-[var(--text-secondary)]">{section.explainer}</p>
  );
}

function GovernedNote({ section }: { section?: SettingsSection }) {
  if (section?.editable !== "governed_pr_only") return null;
  return (
    <div className="flex items-center gap-1.5 text-xs text-[var(--text-tertiary)]">
      <Lock className="h-3 w-3" />
      Changing this is a standards-change pull request, not a toggle.
    </div>
  );
}

/* ---------------------------------------------------------------- page */

export default function SettingsPage() {
  // useSearchParams() forces client-side bail-out during prerender, so the tab
  // state must sit behind a Suspense boundary or `next build` fails on this
  // route. The fallback mirrors the loading card below.
  return (
    <Suspense
      fallback={
        <Card className="p-6 text-sm text-[var(--text-secondary)]">Reading posture…</Card>
      }
    >
      <SettingsView />
    </Suspense>
  );
}

function SettingsView() {
  const router = useRouter();
  const params = useSearchParams();
  const activeTab = params.get("tab") ?? "organization";

  const [data, setData] = useState<SettingsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [probing, setProbing] = useState<string | null>(null);
  const [probeResults, setProbeResults] = useState<Record<string, IntegrationRow["last_probe"]>>({});

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const res = await fetch("/api/settings", { cache: "no-store" });
      const body: SettingsResponse = await res.json();
      if (!res.ok || body.error) {
        setLoadError(body.error ?? `settings request failed (${res.status})`);
        setData(null);
      } else {
        setData(body);
      }
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : String(e));
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const byName = useMemo(() => {
    const map: Record<string, SettingsSection> = {};
    for (const s of data?.sections ?? []) map[s.section] = s;
    return map;
  }, [data]);

  const setTab = (tab: string) => {
    const next = new URLSearchParams(Array.from(params.entries()));
    next.set("tab", tab);
    router.replace(`/settings?${next.toString()}`, { scroll: false });
  };

  const runProbe = async (id: string) => {
    setProbing(id);
    try {
      const res = await fetch(`/api/integrations/${encodeURIComponent(id)}/test`, {
        method: "POST",
      });
      const body = await res.json();
      setProbeResults((prev) => ({
        ...prev,
        [id]: {
          status: body.status ?? "unknown",
          reason: body.reason ?? "",
          probed_at: body.probed_at ?? new Date().toISOString(),
          identity: body.identity,
        },
      }));
    } catch (e) {
      setProbeResults((prev) => ({
        ...prev,
        [id]: {
          status: "unknown",
          reason: `probe could not be run: ${e instanceof Error ? e.message : String(e)}`,
          probed_at: new Date().toISOString(),
        },
      }));
    } finally {
      setProbing(null);
    }
  };

  return (
    <div className="space-y-5">
      <PageHeader
        plane="standards"
        title="Settings"
        description="How this instance is wired to your organization, your external systems, and the controls you cannot change from here."
        actions={
          <button
            onClick={() => void load()}
            className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border-default)] px-2.5 py-1.5 text-xs text-[var(--text-secondary)] transition-colors hover:bg-[var(--overlay)] hover:text-[var(--text)]"
          >
            <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
            Refresh
          </button>
        }
      />

      {/* tabs */}
      <div className="flex flex-wrap gap-1 border-b border-[var(--border-default)] pb-2">
        {TABS.map((t) => {
          const Icon = t.icon;
          const active = activeTab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm transition-colors",
                active
                  ? "bg-[var(--overlay)] text-[var(--text)]"
                  : "text-[var(--text-secondary)] hover:bg-[var(--overlay)]/50 hover:text-[var(--text)]",
              )}
            >
              <Icon className="h-4 w-4" />
              {t.label}
            </button>
          );
        })}
      </div>

      {loadError && (
        <Card className="p-6">
          <div className="flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 shrink-0 text-[var(--danger)]" />
            <div>
              <div className="text-sm font-medium text-[var(--text)]">
                Could not read the settings posture
              </div>
              <div className="mono mt-1 text-xs text-[var(--danger)]">{loadError}</div>
              <p className="mt-2 text-xs text-[var(--text-secondary)]">
                This is an error, not an empty configuration — the orchestrator could not be
                asked, so nothing below should be read as &ldquo;not configured.&rdquo;
              </p>
            </div>
          </div>
        </Card>
      )}

      {loading && !data && !loadError && (
        <Card className="p-6 text-sm text-[var(--text-secondary)]">Reading posture…</Card>
      )}

      {data && activeTab === "organization" && (
        <OrganizationTab section={byName.organization} />
      )}
      {data && activeTab === "integrations" && (
        <IntegrationsTab
          section={byName.integrations}
          probing={probing}
          probeResults={probeResults}
          onProbe={runProbe}
        />
      )}
      {data && activeTab === "models" && <ModelsTab section={byName.models} />}
      {data && activeTab === "governance" && <GovernanceTab section={byName.governance} />}
    </div>
  );
}

/* ---------------------------------------------------------------- tabs */

function OrganizationTab({ section }: { section?: SettingsSection }) {
  const teams = (section?.teams as string[] | undefined) ?? [];
  const count = (section?.team_count as number | undefined) ?? 0;
  return (
    <SectionShell section={section}>
      <Card className="space-y-4 p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-[var(--text)]">Organization model</h2>
          <ActivationBadge activation={section?.activation ?? "unknown"} />
        </div>
        <Explainer section={section} />
        {section?.activation === "bootstrap" ? (
          <div className="rounded-md border border-[var(--border-muted)] p-4 text-sm text-[var(--text-secondary)]">
            No <span className="mono text-[var(--secondary)]">org.yaml</span> activated. Team
            resolution is permissive — any team id is accepted. Copy{" "}
            <span className="mono text-[var(--secondary)]">config/org.yaml.example</span> and set{" "}
            <span className="mono text-[var(--secondary)]">ORG_MODEL_PATH</span> to make an unknown
            team a refusal at intake.
          </div>
        ) : (
          <div className="space-y-2">
            <div className="text-xs text-[var(--text-tertiary)]">
              <span className="tabular text-[var(--text)]">{count}</span> team
              {count === 1 ? "" : "s"} defined
            </div>
            <div className="flex flex-wrap gap-1.5">
              {teams.map((t) => (
                <span key={t} className="mono text-xs text-[var(--secondary)]">
                  {t}
                </span>
              ))}
            </div>
          </div>
        )}
      </Card>
    </SectionShell>
  );
}

function IntegrationsTab({
  section,
  probing,
  probeResults,
  onProbe,
}: {
  section?: SettingsSection;
  probing: string | null;
  probeResults: Record<string, IntegrationRow["last_probe"]>;
  onProbe: (id: string) => void;
}) {
  const rows = ((section?.integrations as IntegrationRow[] | undefined) ?? []).map((r) => {
    const probe = probeResults[r.id] ?? r.last_probe;
    if (!probe) return r;
    return {
      ...r,
      status: probe.status as IntegrationRow["status"],
      verified: probe.status === "verified",
      last_probe: probe,
    };
  });
  const rejected = (section?.rejected as { id: string; reason: string }[] | undefined) ?? [];
  const loadError = section?.load_error as string | undefined;

  return (
    <SectionShell section={section}>
      <div className="space-y-4">
        <Card className="space-y-3 p-5">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-[var(--text)]">External systems</h2>
            <ActivationBadge activation={section?.activation ?? "unknown"} />
          </div>
          <Explainer section={section} />
        </Card>

        {loadError && (
          <Card className="p-4">
            <div className="flex items-center gap-2 text-sm text-[var(--danger)]">
              <AlertTriangle className="h-4 w-4" />
              <span className="mono text-xs">{loadError}</span>
            </div>
          </Card>
        )}

        {rows.length === 0 ? (
          <Card className="space-y-2 p-6">
            <div className="text-sm font-medium text-[var(--text)]">No integrations declared</div>
            <p className="text-sm text-[var(--text-secondary)]">
              Copy <span className="mono text-[var(--secondary)]">config/integrations.yaml.example</span>{" "}
              to <span className="mono text-[var(--secondary)]">config/integrations.yaml</span>, edit it
              for your organization, and point the orchestrator at it with{" "}
              <span className="mono text-[var(--secondary)]">INTEGRATIONS_PATH</span>.
            </p>
            <p className="text-xs text-[var(--text-tertiary)]">
              Credentials are referenced by environment variable — never written into that file.
            </p>
          </Card>
        ) : (
          <div className="space-y-3">
            {rows.map((row) => (
              <Card key={row.id} className="space-y-3 p-5">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-[var(--text)]">
                        {row.display_name || row.id}
                      </span>
                      <Badge variant="outline">{row.kind.replace("_", " ")}</Badge>
                    </div>
                    <div className="mono mt-1 text-xs text-[var(--secondary)]">
                      {row.provider}
                      {row.base_url ? ` · ${row.base_url}` : ""}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <StatusBadge status={row.status} />
                    <button
                      onClick={() => onProbe(row.id)}
                      disabled={probing === row.id}
                      className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border-default)] px-2.5 py-1 text-xs text-[var(--text-secondary)] transition-colors hover:bg-[var(--overlay)] hover:text-[var(--text)] disabled:opacity-50"
                    >
                      <RefreshCw className={cn("h-3 w-3", probing === row.id && "animate-spin")} />
                      Test
                    </button>
                  </div>
                </div>

                <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-xs sm:grid-cols-4">
                  <div>
                    <dt className="text-[var(--text-tertiary)]">Identity</dt>
                    <dd className="mono text-[var(--text-secondary)]">{row.identity || "—"}</dd>
                  </div>
                  <div>
                    <dt className="text-[var(--text-tertiary)]">Credential</dt>
                    <dd className="text-[var(--text-secondary)]">
                      {row.credential_present ? "present" : "missing"}
                      {row.token_env ? (
                        <span className="mono text-[var(--secondary)]"> ({row.token_env})</span>
                      ) : null}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-[var(--text-tertiary)]">Scopes</dt>
                    <dd className="mono text-[var(--text-secondary)]">
                      {row.scopes?.length ? row.scopes.join(", ") : "—"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-[var(--text-tertiary)]">
                      {row.kind === "code_host" ? "Target repo" : "Item link"}
                    </dt>
                    <dd className="mono truncate text-[var(--text-secondary)]">
                      {row.kind === "code_host"
                        ? row.target_repo || "—"
                        : row.item_url_template || "—"}
                    </dd>
                  </div>
                </dl>

                {row.last_probe ? (
                  <div className="rounded-md border border-[var(--border-muted)] p-3 text-xs">
                    <span className="text-[var(--text-tertiary)]">Last probe · </span>
                    <span className="mono text-[var(--text-secondary)]">
                      {row.last_probe.status}
                    </span>
                    {row.last_probe.reason ? (
                      <span className="text-[var(--text-secondary)]"> — {row.last_probe.reason}</span>
                    ) : null}
                  </div>
                ) : (
                  <div className="text-xs text-[var(--text-tertiary)]">
                    Never probed. Status above is declared configuration only — it is not evidence
                    that this system is reachable.
                  </div>
                )}
              </Card>
            ))}
          </div>
        )}

        {rejected.length > 0 && (
          <Card className="space-y-2 p-5">
            <div className="flex items-center gap-2 text-sm font-medium text-[var(--text)]">
              <AlertTriangle className="h-4 w-4 text-[var(--warning)]" />
              Rejected entries
            </div>
            <p className="text-xs text-[var(--text-secondary)]">
              These were refused at load and are NOT active. Surfaced so a typo is a visible
              finding rather than a silently missing integration.
            </p>
            <ul className="space-y-1">
              {rejected.map((r, i) => (
                <li key={`${r.id}-${i}`} className="text-xs">
                  <span className="mono text-[var(--secondary)]">{r.id}</span>
                  <span className="text-[var(--text-secondary)]"> — {r.reason}</span>
                </li>
              ))}
            </ul>
          </Card>
        )}
      </div>
    </SectionShell>
  );
}

function ModelsTab({ section }: { section?: SettingsSection }) {
  const list = (key: string) => (section?.[key] as string[] | undefined) ?? [];
  const routing = (section?.routing as Record<string, string> | undefined) ?? {};
  return (
    <SectionShell section={section}>
      <Card className="space-y-4 p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-[var(--text)]">Model policy</h2>
          <ActivationBadge activation={section?.activation ?? "unknown"} />
        </div>
        <Explainer section={section} />
        <div className="grid gap-4 sm:grid-cols-3">
          {(["allowlist", "denylist", "phi_eligible"] as const).map((key) => (
            <div key={key}>
              <div className="text-xs text-[var(--text-tertiary)]">
                {key.replace("_", " ")}
              </div>
              <div className="mt-1 space-y-0.5">
                {list(key).length === 0 ? (
                  <span className="text-xs text-[var(--text-secondary)]">—</span>
                ) : (
                  list(key).map((m) => (
                    <div key={m} className="mono text-xs text-[var(--secondary)]">
                      {m}
                    </div>
                  ))
                )}
              </div>
            </div>
          ))}
        </div>
        {Object.keys(routing).length > 0 && (
          <div>
            <div className="text-xs text-[var(--text-tertiary)]">Stage routing</div>
            <div className="mt-1 space-y-0.5">
              {Object.entries(routing).map(([stage, model]) => (
                <div key={stage} className="mono text-xs text-[var(--text-secondary)]">
                  {stage} → <span className="text-[var(--secondary)]">{model}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </Card>
    </SectionShell>
  );
}

function GovernanceTab({ section }: { section?: SettingsSection }) {
  const hardGate = (section?.hard_gate_classes as string[] | undefined) ?? [];
  const floor = (section?.floor as string[] | undefined) ?? [];
  return (
    <SectionShell section={section}>
      <Card className="space-y-4 p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-[var(--text)]">Governance floor</h2>
          <Badge variant="secondary">
            <Lock className="h-3 w-3" /> Read-only
          </Badge>
        </div>
        <Explainer section={section} />

        <div>
          <div className="text-xs text-[var(--text-tertiary)]">
            Hard-gate classes — never auto-resolved, never bulk-approved
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {hardGate.map((c) => (
              <span
                key={c}
                className="inline-flex items-center gap-1 rounded-full border border-[var(--border-default)] px-2 py-0.5 text-[11px] text-[var(--text-secondary)]"
              >
                <Lock className="h-3 w-3" />
                <span className="mono">{c}</span>
              </span>
            ))}
          </div>
        </div>

        <div>
          <div className="text-xs text-[var(--text-tertiary)]">Immovable floor</div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {floor.map((c) => (
              <Badge key={c} variant="danger">
                <Lock className="h-3 w-3" />
                <span className="mono">{c}</span>
              </Badge>
            ))}
          </div>
        </div>

        <GovernedNote section={section} />
      </Card>
    </SectionShell>
  );
}
