/**
 * /prompts — the prompt library, laid out as the pipeline it drives.
 *
 * The 7 system prompts map 1:1 to the pipeline stages and run in sequence
 * (ingest → assessor → architect → test_plan → codegen → codegen-tests →
 * review_scan). So instead of a generic admin table, this page shows them as
 * ordered "stage" cards that read like the pipeline — each card is the prompt
 * that powers that agent. Click a card to inspect the full template, version
 * history, and open an in-app edit (new draft version → governed PR).
 *
 * Backed by GET /api/prompts/catalog (reads /app/prompts/<scope>/<stage>/vN.yaml
 * at run time; resolved via team → persona → global inheritance; pinned on every
 * decision in the ledger).
 */
"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ExternalLink, Pencil, X, Search, ArrowRight, FileText,
  Inbox, ScanSearch, Building2, ClipboardCheck, Code2, FlaskConical, ShieldCheck,
} from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { VersionedEditor } from "@/components/domain/versioned-editor";
import { orchestrator, type PromptCatalogEntry, type PromptDetailResponse } from "@/lib/api/orchestrator";

const GITHUB_REPO = "idanshimon/agentic-sdlc";

// Canonical pipeline order (models.py Stage enum) — drives card sequence.
const STAGE_ORDER = [
  "ingest", "assessor", "architect", "test_plan",
  "codegen", "codegen-tests", "review_scan", "deliver",
];

const STAGE_META: Record<string, { label: string; icon: React.ComponentType<{ className?: string; style?: React.CSSProperties }>; blurb: string }> = {
  ingest: { label: "Ingest", icon: Inbox, blurb: "Normalize the work item into a structured PRD." },
  assessor: { label: "Assessor", icon: ScanSearch, blurb: "Surface ambiguities as gating decision cards." },
  architect: { label: "Architect", icon: Building2, blurb: "Propose architecture from resolved decisions." },
  test_plan: { label: "Test Plan", icon: ClipboardCheck, blurb: "Author tests that verify each decision." },
  codegen: { label: "CodeGen", icon: Code2, blurb: "Produce deployable implementation code." },
  "codegen-tests": { label: "CodeGen · Tests", icon: FlaskConical, blurb: "Produce the contract/pytest suite." },
  review_scan: { label: "Review / Scan", icon: ShieldCheck, blurb: "Run policy + static analysis (fail-hard gate)." },
  deliver: { label: "Deliver", icon: ArrowRight, blurb: "Open the PR / hand off the artifact." },
};

const PERSONA_TONE: Record<string, string> = {
  pm: "var(--info)",
  architect: "var(--secondary)",
  qa: "var(--success)",
  sre: "var(--warning)",
  seceng: "var(--danger)",
  compliance: "var(--primary)",
};

function personaTone(p: string): string {
  return PERSONA_TONE[p] ?? "var(--text-tertiary)";
}

function PersonaBadge({ persona }: { persona: string }) {
  const tone = personaTone(persona);
  return (
    <span
      className="inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium"
      style={{ background: `color-mix(in srgb, ${tone} 14%, transparent)`, color: tone }}
    >
      {persona}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const tone =
    status === "published" ? "var(--success)" :
    status === "draft" ? "var(--warning)" : "var(--text-tertiary)";
  return (
    <span
      className="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide"
      style={{ background: `color-mix(in srgb, ${tone} 14%, transparent)`, color: tone }}
    >
      {status}
    </span>
  );
}

function nextVersion(current: string): string {
  const m = /^v(\d+)$/.exec(current);
  return m ? `v${parseInt(m[1], 10) + 1}` : `${current}-next`;
}

function buildPromptYaml(detail: PromptDetailResponse, newVersion: string, template: string): string {
  return [
    `prompt_id: ${detail.prompt_id ?? `${detail.owner_persona}-${detail.scope}`}`,
    `version: ${newVersion}`,
    `status: draft`,
    `scope: ${detail.scope}`,
    `owner_persona: ${detail.owner_persona}`,
    `stage: ${detail.stage}`,
    `supersedes: ${detail.version}`,
    `effective_from: '${new Date().toISOString()}'`,
    `authored_by: ledger-insights-ui`,
    `reason: |-`,
    `  Edited via the in-app prompt editor (new draft version).`,
    `template: |-`,
    ...template.split("\n").map((line) => `  ${line}`),
  ].join("\n") + "\n";
}

/** One prompt = one pipeline stage, rendered as a numbered flow card. */
function StageCard({ entry, index, onClick }: { entry: PromptCatalogEntry; index: number; onClick: () => void }) {
  const meta = STAGE_META[entry.stage] ?? { label: entry.stage, icon: FileText, blurb: "" };
  const Icon = meta.icon;
  const tone = personaTone(entry.owner_persona);
  return (
    <button
      onClick={onClick}
      className="group relative w-full text-left rounded-xl border border-[var(--border-default)] bg-[var(--surface)] p-4 transition-all hover:border-[var(--primary)]/40 hover:shadow-lg hover:-translate-y-0.5"
    >
      <div className="flex items-start gap-3">
        {/* Stage number + icon rail — reads as an ordered pipeline step */}
        <div className="flex flex-col items-center gap-1.5 shrink-0">
          <span
            className="inline-flex h-5 min-w-5 items-center justify-center rounded-full px-1.5 text-[10px] font-mono font-semibold tabular-nums"
            style={{ background: `color-mix(in srgb, ${tone} 18%, transparent)`, color: tone }}
          >
            {String(index + 1).padStart(2, "0")}
          </span>
          <div
            className="h-9 w-9 rounded-lg flex items-center justify-center"
            style={{ background: `color-mix(in srgb, ${tone} 16%, transparent)` }}
          >
            <Icon className="h-4 w-4" style={{ color: tone }} />
          </div>
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-[var(--text)] truncate">{meta.label}</h3>
            <div className="flex items-center gap-1.5 shrink-0">
              <code className="font-mono text-[11px] text-[var(--text-secondary)]">{entry.version}</code>
              <StatusBadge status={entry.status} />
            </div>
          </div>

          <p className="mt-0.5 text-[11px] text-[var(--text-secondary)] leading-snug line-clamp-1">
            {meta.blurb || entry.template_first_line}
          </p>

          <div className="mt-2.5 rounded-md bg-[var(--overlay)]/50 px-2.5 py-1.5">
            <p className="font-mono text-[11px] text-[var(--text-secondary)] leading-relaxed line-clamp-2">
              {entry.template_first_line}
            </p>
          </div>

          <div className="mt-2 flex items-center gap-2 text-[10px] text-[var(--text-tertiary)]">
            <PersonaBadge persona={entry.owner_persona} />
            <span className="font-mono text-[var(--text-secondary)]">{entry.stage}</span>
            <span className="ml-auto tabular-nums">{entry.template_chars.toLocaleString()} chars</span>
          </div>
        </div>
      </div>

      {/* Hover affordance: explicit "open" hint (vision QA: cards lacked per-card action cue) */}
      <div className="pointer-events-none absolute bottom-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity text-[10px] text-[var(--primary)] inline-flex items-center gap-0.5">
        Open <ArrowRight className="h-3 w-3" />
      </div>
    </button>
  );
}

function PromptDrawer({ promptId, onClose }: { promptId: string; onClose: () => void }) {
  const [detail, setDetail] = useState<PromptDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(null);
    orchestrator
      .promptDetail(promptId)
      .then(setDetail)
      .catch((e: unknown) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [promptId]);

  // Close on Escape.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const githubPath = detail ? `prompts/${detail.scope}/${detail.stage}/${detail.version}.yaml` : null;
  const githubViewUrl = githubPath ? `https://github.com/${GITHUB_REPO}/blob/main/${githubPath}` : null;
  const meta = detail ? (STAGE_META[detail.stage] ?? { label: detail.stage, icon: FileText, blurb: "" }) : null;
  const Icon = meta?.icon ?? FileText;

  return (
    <div className="fixed inset-0 z-50 flex" onClick={onClose}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div
        className="relative ml-auto w-full max-w-3xl h-full overflow-y-auto bg-[var(--bg)] border-l border-[var(--border-default)] shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {loading && <div className="p-6 text-[var(--text-secondary)]">Loading…</div>}
        {error && <div className="p-6 text-[var(--danger)]">Error: {error}</div>}
        {detail && (
          <>
            {/* Sticky header */}
            <div className="sticky top-0 z-10 bg-[var(--bg)]/90 backdrop-blur-xl border-b border-[var(--border-default)] px-6 py-4">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3 min-w-0">
                  <div
                    className="h-10 w-10 rounded-lg flex items-center justify-center shrink-0"
                    style={{ background: `color-mix(in srgb, ${personaTone(detail.owner_persona)} 14%, transparent)` }}
                  >
                    <Icon className="h-5 w-5" style={{ color: personaTone(detail.owner_persona) }} />
                  </div>
                  <div className="min-w-0">
                    <h2 className="text-lg font-semibold text-[var(--text)] truncate">{meta?.label}</h2>
                    <div className="text-xs text-[var(--text-tertiary)] font-mono truncate">{detail.prompt_id}</div>
                  </div>
                </div>
                <button
                  onClick={onClose}
                  className="shrink-0 h-8 w-8 rounded-md flex items-center justify-center text-[var(--text-tertiary)] hover:text-[var(--text)] hover:bg-[var(--overlay)]"
                  aria-label="Close"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center gap-1.5 rounded-md bg-[var(--overlay)]/60 px-2 py-1 text-[11px]">
                  <code className="font-mono text-[var(--text)]">{detail.version}</code>
                  <StatusBadge status={detail.status} />
                </span>
                <PersonaBadge persona={detail.owner_persona} />
                <span className="inline-flex items-center rounded-md border border-[var(--border-default)] px-2 py-1 text-[10px] uppercase tracking-wide text-[var(--text-secondary)]">
                  {detail.scope}
                </span>
                <span className="font-mono text-[11px] text-[var(--text-tertiary)]">{detail.stage}</span>
                {githubViewUrl && (
                  <a
                    href={githubViewUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="ml-auto inline-flex items-center gap-1 text-[11px] text-[var(--primary)] hover:underline"
                  >
                    GitHub <ExternalLink className="h-3 w-3" />
                  </a>
                )}
              </div>
            </div>

            <div className="p-6 space-y-5">
              {/* Metadata grid */}
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-lg border border-[var(--border-default)] bg-[var(--surface)] p-3">
                  <div className="text-[10px] text-[var(--text-tertiary)] uppercase tracking-wider">Effective from</div>
                  <div className="text-sm text-[var(--text)] mt-0.5">{detail.effective_from}</div>
                  <div className="text-[11px] text-[var(--text-tertiary)] mt-0.5">by {detail.authored_by}</div>
                </div>
                <div className="rounded-lg border border-[var(--border-default)] bg-[var(--surface)] p-3">
                  <div className="text-[10px] text-[var(--text-tertiary)] uppercase tracking-wider">git_sha</div>
                  <code className="text-xs font-mono text-[var(--text)] break-all">{detail.git_sha}</code>
                </div>
              </div>

              {detail.reason && (
                <div>
                  <div className="text-[10px] uppercase tracking-wider text-[var(--text-tertiary)] mb-1">Reason</div>
                  <div className="text-sm text-[var(--text-secondary)]">{detail.reason}</div>
                </div>
              )}

              {detail.model_compat_notes && (
                <div>
                  <div className="text-[10px] uppercase tracking-wider text-[var(--text-tertiary)] mb-1">Model compat notes</div>
                  <div className="text-sm text-[var(--text-secondary)] whitespace-pre-wrap">{detail.model_compat_notes}</div>
                </div>
              )}

              {/* Template / editor */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="text-[10px] uppercase tracking-wider text-[var(--text-tertiary)]">
                    Template · {detail.template.length.toLocaleString()} chars
                  </div>
                  <Button
                    variant={editing ? "secondary" : "primary"}
                    size="sm"
                    className="h-7 px-2.5 text-[11px]"
                    onClick={() => setEditing((v) => !v)}
                  >
                    {editing
                      ? <><X className="h-3 w-3 mr-1" /> Close editor</>
                      : <><Pencil className="h-3 w-3 mr-1" /> Edit</>}
                  </Button>
                </div>
                {editing ? (
                  <div className="space-y-2">
                    <div className="text-[11px] text-[var(--text-secondary)] p-2.5 rounded-md bg-[color-mix(in_srgb,var(--warning)_8%,transparent)] border border-[color-mix(in_srgb,var(--warning)_25%,transparent)]">
                      Saving creates <code className="font-mono text-[var(--text)]">{nextVersion(detail.version)}</code> as a{" "}
                      <span className="text-[var(--text)] font-medium">draft</span> and opens a governed PR. The pipeline keeps
                      using the published version until this draft is promoted + merged — nothing changes live.
                    </div>
                    <VersionedEditor
                      kind="prompt"
                      id={`${detail.scope}-${detail.stage}-${detail.version}`}
                      seed={detail.template}
                      displayName={`${meta?.label ?? detail.stage} prompt`}
                      onPullRequest={async (content, commitMessage) => {
                        const newVer = nextVersion(detail.version);
                        const yaml = buildPromptYaml(detail, newVer, content);
                        const res = await orchestrator.savePromptConfig({
                          scope: detail.scope,
                          stage: detail.stage,
                          version: newVer,
                          persona: detail.scope === "global" ? undefined : detail.owner_persona,
                          content: yaml,
                          commit_message: commitMessage,
                          pr_title: `New ${detail.stage} prompt ${newVer} (${detail.scope})`,
                        });
                        return res.pr_url;
                      }}
                    />
                  </div>
                ) : (
                  <pre className="text-xs leading-relaxed bg-[var(--surface)] border border-[var(--border-default)] rounded-lg p-4 overflow-x-auto whitespace-pre-wrap text-[var(--text)] max-h-[28rem]">
                    {detail.template}
                  </pre>
                )}
              </div>

              {detail.versions.length > 1 && (
                <div>
                  <div className="text-[10px] uppercase tracking-wider text-[var(--text-tertiary)] mb-1.5">Version history</div>
                  <ul className="space-y-1">
                    {detail.versions.map((v) => (
                      <li key={v.version} className="text-sm flex items-center gap-2">
                        <code className="font-mono text-[var(--text)]">{v.version}</code>
                        <StatusBadge status={v.status} />
                        <span className="text-[var(--text-tertiary)] text-xs">{v.effective_from}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function PromptsPageV2() {
  const [entries, setEntries] = useState<PromptCatalogEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadedFrom, setLoadedFrom] = useState<string>("");
  const [search, setSearch] = useState("");
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

  // Order by pipeline sequence; search across stage / persona / prompt / first line.
  const ordered = useMemo(() => {
    if (!entries) return [];
    const q = search.trim().toLowerCase();
    const filtered = q
      ? entries.filter((e) =>
          [e.stage, e.owner_persona, e.prompt_id, e.scope, e.template_first_line]
            .join(" ").toLowerCase().includes(q))
      : entries;
    return [...filtered].sort(
      (a, b) => {
        const ia = STAGE_ORDER.indexOf(a.stage); const ib = STAGE_ORDER.indexOf(b.stage);
        return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
      },
    );
  }, [entries, search]);

  const published = entries?.filter((e) => e.status === "published").length ?? 0;
  const drafts = entries?.filter((e) => e.status === "draft").length ?? 0;

  return (
    <div className="space-y-5">
      <PageHeader
        plane="standards"
        title="Prompt library"
        description="The system prompts that drive every pipeline stage — one per agent, in run order. Versioned in git, resolved at run time via team → persona → global inheritance, and pinned on every decision in the ledger. Click a stage to read or edit its prompt (edits open a governed PR)."
      />

      {error && (
        <div className="rounded-lg bg-[color-mix(in_srgb,var(--danger)_10%,transparent)] border border-[color-mix(in_srgb,var(--danger)_30%,transparent)] px-4 py-3 text-[var(--danger)]">
          Failed to load catalog: {error}
        </div>
      )}

      {!entries && !error && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2, 3, 4, 5].map((i) => <div key={i} className="skeleton h-36 rounded-xl" />)}
        </div>
      )}

      {entries && (
        <>
          {/* Lightweight toolbar: search + counts (no heavy KPI strip / 3 dropdowns for 7 items) */}
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative flex-1 min-w-[220px] max-w-md">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[var(--text-tertiary)]" />
              <input
                type="text"
                placeholder="Search stage, persona, prompt…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-8 pr-7 py-1.5 text-xs rounded-md border border-[var(--border-default)] bg-[var(--surface)] text-[var(--text)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:border-[var(--primary)]"
              />
              {search && (
                <button
                  onClick={() => setSearch("")}
                  aria-label="clear"
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)] hover:text-[var(--text)]"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
            <div className="flex items-center gap-3 text-[11px] text-[var(--text-tertiary)]">
              <span><span className="text-[var(--text-secondary)] tabular-nums">{ordered.length}</span> prompts</span>
              <span className="inline-flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full" style={{ background: "var(--success)" }} />{published} published</span>
              {drafts > 0 && <span className="inline-flex items-center gap-1"><span className="h-1.5 w-1.5 rounded-full" style={{ background: "var(--warning)" }} />{drafts} draft</span>}
              <span className="font-mono">{loadedFrom}</span>
            </div>
          </div>

          {/* Pipeline-flow cards */}
          {ordered.length === 0 ? (
            <div className="rounded-xl border border-[var(--border-default)] bg-[var(--surface)] px-4 py-12 text-center text-[var(--text-tertiary)] text-sm">
              No prompts match “{search}”.
              <button onClick={() => setSearch("")} className="ml-2 text-[var(--primary)] hover:underline">Clear</button>
            </div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {ordered.map((e, i) => (
                <StageCard key={`${e.prompt_id}-${e.version}`} entry={e} index={i} onClick={() => setDrawerId(e.prompt_id)} />
              ))}
            </div>
          )}
        </>
      )}

      {drawerId && <PromptDrawer promptId={drawerId} onClose={() => setDrawerId(null)} />}
    </div>
  );
}
