"use client";
import { useState, useEffect, useMemo, useCallback } from "react";
import {
  History, Save, RotateCcw, GitBranch, Eye, Edit3, ChevronDown,
  ChevronRight, AlertCircle, Sparkles, Trash2, X, Check,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import {
  ensureSeeded,
  getEntry,
  getCurrentContent,
  getCurrentVersion,
  listVersions,
  saveVersion,
  rollbackTo,
  resetEntry,
  computeDiff,
  diffStats,
  type ResourceKind,
  type ResourceEntry,
  type ResourceVersion,
  type DiffLine,
} from "@/lib/versioning/store";
import { cn } from "@/lib/utils";

interface Props {
  kind: ResourceKind;
  id: string;
  /** Canonical seed content shipped from the repo. */
  seed: string;
  /** Optional readonly metadata to render above the editor (badges, etc). */
  meta?: React.ReactNode;
  /** Display name for toasts/buttons (e.g. "Architect agent"). */
  displayName: string;
  /**
   * Optional governed-save hook. When provided, "Save new version" ALSO opens
   * a PR on the underlying config file (via the page-supplied closure, which
   * knows the path fields). Returns the PR URL (or null in dry-run / on a
   * handled failure). The local version history is saved regardless — the PR
   * is the durable, governed source of truth. When omitted, the editor is
   * local-only (legacy behaviour).
   */
  onPullRequest?: (content: string, commitMessage: string) => Promise<string | null>;
}

type TabKey = "edit" | "preview" | "history" | "diff";

export function VersionedEditor({ kind, id, seed, meta, displayName, onPullRequest }: Props) {
  // Seed on mount; never overwrite existing edits.
  useEffect(() => {
    ensureSeeded(kind, id, seed);
  }, [kind, id, seed]);

  const [entry, setEntry] = useState<ResourceEntry | null>(null);
  const [tab, setTab] = useState<TabKey>("edit");
  const [draft, setDraft] = useState<string>("");
  const [commitMsg, setCommitMsg] = useState<string>("");
  const [diffAgainstVersionId, setDiffAgainstVersionId] = useState<number | null>(
    null,
  );
  const [confirmReset, setConfirmReset] = useState(false);

  const refresh = useCallback(() => {
    const e = getEntry(kind, id);
    setEntry(e);
    setDraft(e ? getCurrentContent(e) : seed);
  }, [kind, id, seed]);

  useEffect(() => {
    // Defer state updates one tick so they don't run synchronously inside
    // the effect body (React 19 strict-mode flags cascading-render risk).
    queueMicrotask(refresh);
    // Cross-tab sync: re-read on storage events from other tabs.
    const handler = () => refresh();
    window.addEventListener("storage", handler);
    window.addEventListener("versioned-resources-changed", handler);
    return () => {
      window.removeEventListener("storage", handler);
      window.removeEventListener("versioned-resources-changed", handler);
    };
  }, [refresh]);

  const currentContent = entry ? getCurrentContent(entry) : seed;
  const currentVersion = entry ? getCurrentVersion(entry) : null;
  const versions = entry ? listVersions(entry) : [];
  const isDirty = draft !== currentContent;
  const isEdited = currentVersion !== null;

  // Diff: draft vs current OR a specific historic version vs current.
  const diff = useMemo<DiffLine[]>(() => {
    if (!entry) return [];
    if (tab === "diff") {
      // Compare a selected historic version against current.
      const target = diffAgainstVersionId
        ? versions.find((v) => v.version_id === diffAgainstVersionId)
        : null;
      const baseContent = target ? target.content : entry.seed;
      return computeDiff(baseContent, currentContent);
    }
    if (tab === "edit" && isDirty) {
      return computeDiff(currentContent, draft);
    }
    return [];
  }, [tab, draft, currentContent, diffAgainstVersionId, entry, isDirty, versions]);

  const stats = diffStats(diff);

  const handleSave = useCallback(() => {
    if (!isDirty) {
      toast.info("Nothing to save", { description: "Draft matches current version" });
      return;
    }
    try {
      // Pass the seed as fallback — the saveVersion function will auto-seed
      // if the localStorage entry is missing (e.g. cleared mid-session).
      const v = saveVersion(
        kind,
        id,
        draft,
        commitMsg || `edit ${displayName}`,
        "you",
        seed,
      );
      const savedMsg = commitMsg || `edit ${displayName}`;
      toast.success(`Saved v${v.version_id}`, {
        description: `${displayName} · ${v.message}`,
      });
      setCommitMsg("");
      refresh();

      // Governed save: also open a PR on the real config file (if wired).
      // Local version history is the operator's scratchpad; the PR is the
      // durable, committee-reviewed source of truth the pipeline reads.
      if (onPullRequest) {
        const draftAtSave = draft;
        toast.loading("Opening pull request…", { id: "pr-save" });
        onPullRequest(draftAtSave, savedMsg)
          .then((prUrl) => {
            if (prUrl) {
              toast.success("Pull request opened", {
                id: "pr-save",
                description: prUrl,
                action: {
                  label: "Open",
                  onClick: () => window.open(prUrl, "_blank", "noreferrer"),
                },
              });
            } else {
              toast.info("Saved locally — PR not opened", {
                id: "pr-save",
                description:
                  "Dry-run or PR write-back unavailable in this environment. " +
                  "Your local version is saved; merge requires a PR.",
              });
            }
          })
          .catch((e) => {
            const msg = e instanceof Error ? e.message : "PR failed";
            toast.error("PR write-back failed", {
              id: "pr-save",
              description: `${msg} — local version still saved.`,
            });
          });
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Save failed";
      console.error("[VersionedEditor] save failed:", e);
      toast.error("Save failed", { description: msg });
    }
  }, [isDirty, kind, id, draft, commitMsg, displayName, seed, refresh, onPullRequest]);

  const handleDiscard = useCallback(() => {
    if (!isDirty) return;
    setDraft(currentContent);
    toast.info("Draft discarded");
  }, [isDirty, currentContent]);

  const handleRollback = useCallback(
    (targetId: number | null) => {
      try {
        const v = rollbackTo(kind, id, targetId);
        if (v) {
          toast.success(
            targetId == null ? "Rolled back to canonical" : `Rolled back to v${targetId}`,
            { description: `New checkpoint v${v.version_id} created` },
          );
        }
        refresh();
      } catch (e) {
        toast.error("Rollback failed", {
          description: e instanceof Error ? e.message : String(e),
        });
      }
    },
    [kind, id, refresh],
  );

  const handleReset = useCallback(() => {
    resetEntry(kind, id);
    toast.success("All edits cleared", {
      description: `${displayName} restored to canonical seed; history wiped`,
    });
    setConfirmReset(false);
    refresh();
  }, [kind, id, displayName, refresh]);

  return (
    <Card className="overflow-hidden">
      {/* Header */}
      <div className="border-b border-[var(--border-muted)] p-4 space-y-3">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="text-sm font-semibold mono">{id}</h3>
              {currentVersion ? (
                <Badge variant="info" className="text-[10px]">
                  <GitBranch className="h-2.5 w-2.5 mr-1" />v{currentVersion.version_id}
                </Badge>
              ) : (
                <Badge variant="secondary" className="text-[10px]">
                  canonical
                </Badge>
              )}
              {versions.length > 0 && (
                <Badge variant="default" className="text-[10px]">
                  {versions.length} {versions.length === 1 ? "edit" : "edits"}
                </Badge>
              )}
              {isDirty && (
                <Badge variant="warning" className="text-[10px]">
                  <AlertCircle className="h-2.5 w-2.5 mr-1" />unsaved
                </Badge>
              )}
            </div>
            {meta}
          </div>
          <div className="flex items-center gap-1">
            {isEdited && (
              confirmReset ? (
                <>
                  <span className="text-[10px] text-[var(--text-tertiary)] mr-1">
                    Wipe all history?
                  </span>
                  <Button variant="danger" size="sm" onClick={handleReset}>
                    <Trash2 className="h-3 w-3" /> Yes, reset
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setConfirmReset(false)}
                  >
                    Cancel
                  </Button>
                </>
              ) : (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setConfirmReset(true)}
                  title="Wipe all local edits"
                >
                  <RotateCcw className="h-3 w-3" /> Reset to canonical
                </Button>
              )
            )}
          </div>
        </div>

        {/* Tabs */}
        <div className="flex items-center gap-1 -mb-1">
          {[
            { key: "edit" as TabKey, label: "Edit", icon: Edit3 },
            { key: "preview" as TabKey, label: "Preview", icon: Eye },
            { key: "history" as TabKey, label: "History", icon: History,
              badge: versions.length },
            { key: "diff" as TabKey, label: "Diff", icon: Sparkles },
          ].map((t) => {
            const Icon = t.icon;
            const isActive = tab === t.key;
            return (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className={cn(
                  "flex items-center gap-1.5 h-8 px-3 text-xs font-medium rounded-md transition-colors",
                  isActive
                    ? "bg-[var(--overlay)] text-[var(--text)]"
                    : "text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] hover:bg-[var(--overlay)]/40",
                )}
              >
                <Icon className="h-3 w-3" />
                {t.label}
                {t.badge !== undefined && t.badge > 0 && (
                  <span className="text-[9px] tabular bg-[var(--bg)] px-1 rounded">
                    {t.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Body */}
      {tab === "edit" && (
        <div className="p-4 space-y-3">
          <Textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={24}
            className="mono text-xs leading-relaxed resize-y"
            spellCheck={false}
          />
          {isDirty && (
            <div className="flex items-center gap-2 text-[11px] text-[var(--text-tertiary)] tabular">
              <span className="text-[var(--success)]">+{stats.added}</span>
              <span className="text-[var(--danger)]">−{stats.removed}</span>
              <span>line{stats.added + stats.removed === 1 ? "" : "s"} changed</span>
            </div>
          )}
          <div className="flex items-center gap-2 flex-wrap">
            <Input
              value={commitMsg}
              onChange={(e) => setCommitMsg(e.target.value)}
              placeholder={`Commit message (e.g. "tighten PHI rule citations")`}
              className="flex-1 min-w-[200px] h-9 text-xs"
              disabled={!isDirty}
            />
            <Button
              variant="primary"
              size="default"
              onClick={handleSave}
              disabled={!isDirty}
            >
              <Save className="h-3.5 w-3.5" />
              Save new version
            </Button>
            <Button
              variant="ghost"
              size="default"
              onClick={handleDiscard}
              disabled={!isDirty}
            >
              <X className="h-3.5 w-3.5" />
              Discard draft
            </Button>
          </div>
        </div>
      )}

      {tab === "preview" && (
        <div className="p-4">
          <pre className="mono text-xs leading-relaxed whitespace-pre-wrap break-words bg-[var(--bg)] border border-[var(--border-muted)] rounded p-3 max-h-[600px] overflow-y-auto">
            {currentContent}
          </pre>
        </div>
      )}

      {tab === "history" && (
        <HistoryTimeline
          entry={entry}
          versions={versions}
          currentVersionId={currentVersion?.version_id ?? null}
          onRollback={handleRollback}
          onShowDiff={(targetId) => {
            setDiffAgainstVersionId(targetId);
            setTab("diff");
          }}
        />
      )}

      {tab === "diff" && (
        <DiffView
          versions={versions}
          selectedVersionId={diffAgainstVersionId}
          onSelectVersion={setDiffAgainstVersionId}
          diff={diff}
          stats={stats}
        />
      )}
    </Card>
  );
}

/* ─────────────── History timeline ─────────────── */

function HistoryTimeline({
  entry,
  versions,
  currentVersionId,
  onRollback,
  onShowDiff,
}: {
  entry: ResourceEntry | null;
  versions: ResourceVersion[];
  currentVersionId: number | null;
  onRollback: (versionId: number | null) => void;
  onShowDiff: (versionId: number | null) => void;
}) {
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  const toggle = (id: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  if (!entry) return null;

  return (
    <div className="divide-y divide-[var(--border-muted)]">
      {versions.length === 0 && (
        <div className="p-6 text-center text-xs text-[var(--text-tertiary)]">
          No edits yet. Save changes in the Edit tab to start a version history.
        </div>
      )}
      {versions.map((v) => {
        const isCurrent = v.version_id === currentVersionId;
        const isExpanded = expanded.has(v.version_id);
        return (
          <div key={v.version_id} className="p-3">
            <div className="flex items-start gap-2">
              <button
                onClick={() => toggle(v.version_id)}
                className="pt-0.5 text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]"
              >
                {isExpanded ? (
                  <ChevronDown className="h-4 w-4" />
                ) : (
                  <ChevronRight className="h-4 w-4" />
                )}
              </button>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <Badge variant={isCurrent ? "info" : "secondary"} className="text-[10px]">
                    <GitBranch className="h-2.5 w-2.5 mr-1" />
                    v{v.version_id}
                  </Badge>
                  {isCurrent && (
                    <Badge variant="success" className="text-[10px]">
                      <Check className="h-2.5 w-2.5 mr-1" />current
                    </Badge>
                  )}
                  <span className="text-xs text-[var(--text-secondary)] font-medium">
                    {v.message}
                  </span>
                </div>
                <div className="mt-1 text-[10px] text-[var(--text-tertiary)] tabular flex items-center gap-3 flex-wrap">
                  <span>by {v.author}</span>
                  <span>{new Date(v.created_at).toLocaleString()}</span>
                  {v.parent_version_id !== null && (
                    <span>parent v{v.parent_version_id}</span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onShowDiff(v.version_id)}
                  title="Show diff vs current"
                >
                  <Sparkles className="h-3 w-3" />
                  Diff
                </Button>
                {!isCurrent && (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => onRollback(v.version_id)}
                    title="Restore this version"
                  >
                    <RotateCcw className="h-3 w-3" />
                    Restore
                  </Button>
                )}
              </div>
            </div>
            {isExpanded && (
              <pre className="mono text-[10px] mt-2 ml-6 bg-[var(--bg)] border border-[var(--border-muted)] rounded p-2 max-h-64 overflow-y-auto whitespace-pre-wrap break-words">
                {v.content.slice(0, 1500)}
                {v.content.length > 1500 && "\n…"}
              </pre>
            )}
          </div>
        );
      })}
      {versions.length > 0 && (
        <div className="p-3 bg-[var(--overlay)]/30">
          <div className="flex items-center justify-between gap-2">
            <div className="text-[11px] text-[var(--text-tertiary)]">
              <span className="text-[var(--text-secondary)] font-medium">Canonical seed</span>{" "}
              · the read-only baseline shipped with the repo
            </div>
            {currentVersionId !== null && (
              <Button variant="ghost" size="sm" onClick={() => onRollback(null)}>
                <RotateCcw className="h-3 w-3" />
                Restore canonical
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/* ─────────────── Diff view ─────────────── */

function DiffView({
  versions,
  selectedVersionId,
  onSelectVersion,
  diff,
  stats,
}: {
  versions: ResourceVersion[];
  selectedVersionId: number | null;
  onSelectVersion: (id: number | null) => void;
  diff: DiffLine[];
  stats: { added: number; removed: number };
}) {
  return (
    <div className="p-4 space-y-3">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-[11px] text-[var(--text-tertiary)]">Compare:</span>
        <select
          value={selectedVersionId == null ? "seed" : String(selectedVersionId)}
          onChange={(e) => {
            const v = e.target.value;
            onSelectVersion(v === "seed" ? null : Number(v));
          }}
          className="h-7 px-2 rounded-md border border-[var(--border-default)] bg-[var(--overlay)] text-xs"
        >
          <option value="seed">canonical seed</option>
          {versions.map((v) => (
            <option key={v.version_id} value={v.version_id}>
              v{v.version_id} — {v.message.slice(0, 40)}
              {v.message.length > 40 && "…"}
            </option>
          ))}
        </select>
        <span className="text-[11px] text-[var(--text-tertiary)]">→ current</span>
        <span className="ml-auto text-[11px] tabular">
          <span className="text-[var(--success)]">+{stats.added}</span>{" "}
          <span className="text-[var(--danger)]">−{stats.removed}</span>
        </span>
      </div>
      <div className="border border-[var(--border-muted)] rounded bg-[var(--bg)] overflow-hidden">
        <pre className="mono text-[11px] leading-relaxed max-h-[600px] overflow-auto">
          {diff.length === 0 ? (
            <div className="p-4 text-center text-[var(--text-tertiary)]">
              No differences.
            </div>
          ) : (
            diff.map((line, i) => (
              <div
                key={i}
                className={cn(
                  "px-3 py-0.5 flex gap-3",
                  line.type === "added" && "bg-[var(--success)]/10",
                  line.type === "removed" && "bg-[var(--danger)]/10",
                )}
              >
                <span className="text-[var(--text-tertiary)] tabular w-10 shrink-0 text-right select-none">
                  {line.type === "added" ? "" : line.oldLineNum ?? ""}
                </span>
                <span className="text-[var(--text-tertiary)] tabular w-10 shrink-0 text-right select-none">
                  {line.type === "removed" ? "" : line.newLineNum ?? ""}
                </span>
                <span
                  className={cn(
                    "shrink-0 w-3 select-none font-bold",
                    line.type === "added" && "text-[var(--success)]",
                    line.type === "removed" && "text-[var(--danger)]",
                  )}
                >
                  {line.type === "added" ? "+" : line.type === "removed" ? "−" : " "}
                </span>
                <span className="whitespace-pre-wrap break-words">
                  {line.text || "\u00A0"}
                </span>
              </div>
            ))
          )}
        </pre>
      </div>
    </div>
  );
}
