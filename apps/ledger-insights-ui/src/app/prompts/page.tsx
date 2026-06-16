/**
 * /prompts — catalog browser backed by the live YAML prompt library.
 *
 * Phase 3 replacement for the previous localStorage seed-based page.
 * Loads from the deployed orchestrator's GET /api/prompts/catalog
 * (which reads /app/prompts/<scope>/<stage>/v<N>.yaml at runtime).
 *
 * Operator surfaces:
 *   - Table: every prompt, sortable by stage / persona / version / scope
 *   - Filter chips: persona, stage, scope
 *   - KPI strip: total prompts, # personas, # stages, current git_sha range
 *   - Click row → drilldown with full template + version history + metadata
 *
 * Edit path is "Open PR on GitHub" — clicking Edit opens a deeplink to
 * the YAML file in the repo with a /edit suffix so the operator can use
 * GitHub's web editor. Closes the Phase 3 / 3.1 spec.
 */
"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ExternalLink, FileText, GitBranch, Users, Layers } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { orchestrator, type PromptCatalogEntry, type PromptDetailResponse } from "@/lib/api/orchestrator";

const GITHUB_REPO = "idanshimon/agentic-sdlc";

function PersonaBadge({ persona }: { persona: string }) {
  const colors: Record<string, string> = {
    pm: "bg-blue-500/10 text-blue-600 dark:text-blue-300 ring-blue-500/30",
    architect: "bg-purple-500/10 text-purple-600 dark:text-purple-300 ring-purple-500/30",
    qa: "bg-green-500/10 text-green-600 dark:text-green-300 ring-green-500/30",
    sre: "bg-orange-500/10 text-orange-600 dark:text-orange-300 ring-orange-500/30",
    seceng: "bg-red-500/10 text-red-600 dark:text-red-300 ring-red-500/30",
    compliance: "bg-indigo-500/10 text-indigo-600 dark:text-indigo-300 ring-indigo-500/30",
  };
  const cls = colors[persona] ?? "bg-zinc-500/10 text-zinc-600 dark:text-zinc-300 ring-zinc-500/30";
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${cls}`}>
      {persona}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    published: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-300 ring-emerald-500/30",
    draft: "bg-amber-500/10 text-amber-600 dark:text-amber-300 ring-amber-500/30",
    superseded: "bg-zinc-500/10 text-zinc-600 dark:text-zinc-300 ring-zinc-500/30",
  };
  const cls = colors[status] ?? colors.draft;
  return (
    <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ring-1 ring-inset ${cls}`}>
      {status}
    </span>
  );
}

function ScopeBadge({ scope }: { scope: string }) {
  return (
    <span className="inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-zinc-600 dark:text-zinc-300">
      {scope}
    </span>
  );
}

function KPIStrip({ entries }: { entries: PromptCatalogEntry[] }) {
  const personas = new Set(entries.map((e) => e.owner_persona));
  const stages = new Set(entries.map((e) => e.stage));
  const totalChars = entries.reduce((acc, e) => acc + e.template_chars, 0);
  const tiles = [
    { label: "Prompts", value: entries.length, icon: FileText },
    { label: "Personas", value: personas.size, icon: Users },
    { label: "Stages", value: stages.size, icon: Layers },
    { label: "Template bytes", value: totalChars.toLocaleString(), icon: GitBranch },
  ];
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
      {tiles.map(({ label, value, icon: Icon }) => (
        <div key={label} className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3 flex items-center gap-3">
          <div className="rounded-md p-2 bg-[var(--surface-2)]">
            <Icon className="w-4 h-4 text-[var(--text-secondary)]" />
          </div>
          <div>
            <div className="text-xs text-[var(--text-tertiary)] uppercase tracking-wider">{label}</div>
            <div className="text-lg font-semibold text-[var(--text-primary)]">{value}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

function PromptDrawer({ promptId, onClose }: { promptId: string; onClose: () => void }) {
  const [detail, setDetail] = useState<PromptDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    orchestrator
      .promptDetail(promptId)
      .then(setDetail)
      .catch((e: unknown) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [promptId]);

  // Build GitHub edit URL: prompts/<scope>/<stage>/<version>.yaml
  // Inferred from detail; scope=global → prompts/global/<stage>/<version>.yaml
  const githubPath = detail
    ? `prompts/${detail.scope}/${detail.stage}/${detail.version}.yaml`
    : null;
  const githubViewUrl = githubPath ? `https://github.com/${GITHUB_REPO}/blob/main/${githubPath}` : null;
  const githubEditUrl = githubPath ? `https://github.com/${GITHUB_REPO}/edit/main/${githubPath}` : null;

  return (
    <div className="fixed inset-0 z-50 flex" onClick={onClose}>
      <div className="absolute inset-0 bg-black/60" />
      <div
        className="relative ml-auto w-full max-w-3xl h-full overflow-y-auto bg-[var(--bg)] border-l border-[var(--border)] p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <button onClick={onClose} className="text-[var(--text-tertiary)] hover:text-[var(--text-primary)]">
            ✕ Close
          </button>
          {githubViewUrl && (
            <div className="flex gap-2">
              <a
                href={githubViewUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 rounded-md border border-[var(--border)] px-3 py-1.5 text-sm hover:bg-[var(--surface-2)]"
              >
                <ExternalLink className="w-3.5 h-3.5" /> View on GitHub
              </a>
              <a
                href={githubEditUrl!}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 rounded-md bg-blue-600 hover:bg-blue-700 px-3 py-1.5 text-sm text-white"
              >
                <ExternalLink className="w-3.5 h-3.5" /> Edit + open PR
              </a>
            </div>
          )}
        </div>

        {loading && <div className="text-[var(--text-secondary)]">Loading…</div>}
        {error && <div className="text-red-500">Error: {error}</div>}
        {detail && (
          <div className="space-y-5">
            <div>
              <div className="text-xs uppercase tracking-wider text-[var(--text-tertiary)]">Prompt</div>
              <h2 className="text-2xl font-semibold text-[var(--text-primary)]">{detail.prompt_id}</h2>
              <div className="text-sm text-[var(--text-secondary)] mt-0.5">
                stage <code className="font-mono text-[var(--text-primary)]">{detail.stage}</code> · scope{" "}
                <code className="font-mono text-[var(--text-primary)]">{detail.scope}</code> · owned by{" "}
                <PersonaBadge persona={detail.owner_persona} />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3">
                <div className="text-xs text-[var(--text-tertiary)] uppercase tracking-wider">Current version</div>
                <div className="text-base font-medium">
                  {detail.version} <StatusBadge status={detail.status} />
                </div>
                <div className="text-xs text-[var(--text-secondary)] mt-1">since {detail.effective_from}</div>
              </div>
              <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3">
                <div className="text-xs text-[var(--text-tertiary)] uppercase tracking-wider">git_sha</div>
                <code className="text-xs font-mono text-[var(--text-primary)] break-all">{detail.git_sha}</code>
                <div className="text-xs text-[var(--text-secondary)] mt-1">by {detail.authored_by}</div>
              </div>
            </div>

            {detail.reason && (
              <div>
                <div className="text-xs uppercase tracking-wider text-[var(--text-tertiary)] mb-1">Reason</div>
                <div className="text-sm text-[var(--text-secondary)]">{detail.reason}</div>
              </div>
            )}

            {detail.model_compat_notes && (
              <div>
                <div className="text-xs uppercase tracking-wider text-[var(--text-tertiary)] mb-1">Model compat notes</div>
                <div className="text-sm text-[var(--text-secondary)] whitespace-pre-wrap">{detail.model_compat_notes}</div>
              </div>
            )}

            <div>
              <div className="text-xs uppercase tracking-wider text-[var(--text-tertiary)] mb-1">
                Template ({detail.template.length.toLocaleString()} chars)
              </div>
              <pre className="text-xs leading-relaxed bg-[var(--surface)] border border-[var(--border)] rounded-lg p-4 overflow-x-auto whitespace-pre-wrap text-[var(--text-primary)]">
                {detail.template}
              </pre>
            </div>

            {detail.versions.length > 1 && (
              <div>
                <div className="text-xs uppercase tracking-wider text-[var(--text-tertiary)] mb-1">All versions</div>
                <ul className="space-y-1">
                  {detail.versions.map((v) => (
                    <li key={v.version} className="text-sm flex items-center gap-2">
                      <code className="font-mono">{v.version}</code> <StatusBadge status={v.status} />
                      <span className="text-[var(--text-tertiary)]">{v.effective_from}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function PromptsPageV2() {
  const [entries, setEntries] = useState<PromptCatalogEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadedFrom, setLoadedFrom] = useState<string>("");
  const [filterPersona, setFilterPersona] = useState<string | null>(null);
  const [filterStage, setFilterStage] = useState<string | null>(null);
  const [filterScope, setFilterScope] = useState<string | null>(null);
  const [drawerId, setDrawerId] = useState<string | null>(null);

  useEffect(() => {
    orchestrator
      .promptCatalog()
      .then((d: { prompts: PromptCatalogEntry[]; loaded_from: string }) => {
        setEntries(d.prompts);
        setLoadedFrom(d.loaded_from);
      })
      .catch((e: unknown) => setError(String(e)));
  }, []);

  const filtered = useMemo(() => {
    if (!entries) return [];
    return entries.filter(
      (e) =>
        (!filterPersona || e.owner_persona === filterPersona) &&
        (!filterStage || e.stage === filterStage) &&
        (!filterScope || e.scope === filterScope),
    );
  }, [entries, filterPersona, filterStage, filterScope]);

  const allPersonas = useMemo(() => Array.from(new Set(entries?.map((e) => e.owner_persona) ?? [])), [entries]);
  const allStages = useMemo(() => Array.from(new Set(entries?.map((e) => e.stage) ?? [])), [entries]);
  const allScopes = useMemo(() => Array.from(new Set(entries?.map((e) => e.scope) ?? [])), [entries]);

  return (
    <div className="container mx-auto px-6 py-6 max-w-6xl">
      <PageHeader
        plane="standards"
        title="Prompt library"
        description="System prompts that drive every pipeline stage. Versioned in git under prompts/<scope>/<stage>/v<N>.yaml; resolved at run time via team → persona → global inheritance; pinned on every decision in the ledger."
      />

      {error && (
        <div className="rounded-lg bg-red-500/10 border border-red-500/30 px-4 py-3 text-red-600 dark:text-red-300 mb-4">
          Failed to load catalog: {error}
        </div>
      )}

      {entries && (
        <>
          <KPIStrip entries={filtered} />

          <div className="mb-4 flex flex-wrap gap-3 items-center">
            <FilterPill
              label="Persona"
              value={filterPersona}
              options={allPersonas}
              onChange={setFilterPersona}
            />
            <FilterPill label="Stage" value={filterStage} options={allStages} onChange={setFilterStage} />
            <FilterPill label="Scope" value={filterScope} options={allScopes} onChange={setFilterScope} />
            {(filterPersona || filterStage || filterScope) && (
              <button
                onClick={() => {
                  setFilterPersona(null);
                  setFilterStage(null);
                  setFilterScope(null);
                }}
                className="text-xs text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"
              >
                Clear filters
              </button>
            )}
            <div className="ml-auto text-xs text-[var(--text-tertiary)] font-mono">
              loaded from <code className="text-[var(--text-secondary)]">{loadedFrom}</code>
            </div>
          </div>

          <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-[var(--surface-2)] text-xs uppercase tracking-wider text-[var(--text-tertiary)]">
                <tr>
                  <th className="text-left px-4 py-2 font-medium">Prompt</th>
                  <th className="text-left px-3 py-2 font-medium">Stage</th>
                  <th className="text-left px-3 py-2 font-medium">Scope</th>
                  <th className="text-left px-3 py-2 font-medium">Owner</th>
                  <th className="text-left px-3 py-2 font-medium">Version</th>
                  <th className="text-left px-3 py-2 font-medium">Status</th>
                  <th className="text-right px-3 py-2 font-medium">Bytes</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((e) => (
                  <tr
                    key={`${e.prompt_id}-${e.version}`}
                    onClick={() => setDrawerId(e.prompt_id)}
                    className="border-t border-[var(--border)] hover:bg-[var(--surface-2)] cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-3">
                      <div className="font-medium text-[var(--text-primary)]">{e.prompt_id}</div>
                      <div className="text-xs text-[var(--text-tertiary)] truncate max-w-md">
                        {e.template_first_line}
                      </div>
                    </td>
                    <td className="px-3 py-3">
                      <code className="font-mono text-xs">{e.stage}</code>
                    </td>
                    <td className="px-3 py-3">
                      <ScopeBadge scope={e.scope} />
                    </td>
                    <td className="px-3 py-3">
                      <PersonaBadge persona={e.owner_persona} />
                    </td>
                    <td className="px-3 py-3">
                      <code className="font-mono text-xs">{e.version}</code>
                    </td>
                    <td className="px-3 py-3">
                      <StatusBadge status={e.status} />
                    </td>
                    <td className="px-3 py-3 text-right tabular-nums text-[var(--text-secondary)]">
                      {e.template_chars.toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {filtered.length === 0 && (
              <div className="px-4 py-8 text-center text-[var(--text-tertiary)]">No prompts match current filters.</div>
            )}
          </div>
        </>
      )}

      {drawerId && <PromptDrawer promptId={drawerId} onClose={() => setDrawerId(null)} />}
    </div>
  );
}

function FilterPill({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string | null;
  options: string[];
  onChange: (v: string | null) => void;
}) {
  return (
    <select
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value || null)}
      className="rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-sm text-[var(--text-primary)]"
    >
      <option value="">All {label.toLowerCase()}s</option>
      {options.map((o) => (
        <option key={o} value={o}>
          {label}: {o}
        </option>
      ))}
    </select>
  );
}
