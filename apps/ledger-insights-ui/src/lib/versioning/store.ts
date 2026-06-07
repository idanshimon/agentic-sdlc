/* Versioned editor store — localStorage-backed version history for editable
 * resources (custom agents, prompts, bundles). Demo-safe (no API), but
 * structured so a real backend can swap in by replacing `loadAll`/`save`.
 *
 * Each resource has:
 *   - `id`     stable identifier (e.g. "architect", "assessor")
 *   - `kind`   resource type ("agent" | "prompt" | "bundle")
 *   - canonical seed (`seed`) — read-only baseline shipped with the repo
 *   - version history — every save creates a new immutable Version
 *   - `current_version` — pointer into history (allows rollback without losing edits)
 *
 * Version object:
 *   - version_id (monotonic int, never reused)
 *   - content (full body — frontmatter + markdown)
 *   - author, message, created_at
 *   - parent_version_id (the version this was edited from)
 *
 * No partial diffs in storage — we always store full snapshots. Diff is
 * computed at read time, which keeps the store simple and the rollback
 * semantics atomic.
 */

const STORAGE_KEY = "agentic-sdlc.versioned-resources";

export type ResourceKind = "agent" | "prompt" | "bundle";

export interface ResourceVersion {
  version_id: number;
  content: string;
  author: string;
  message: string;
  created_at: string;
  parent_version_id: number | null;
}

export interface ResourceEntry {
  id: string;
  kind: ResourceKind;
  /** Read-only baseline shipped from the repo. Never mutated. */
  seed: string;
  versions: ResourceVersion[];
  /** Pointer into versions[] (by version_id). null = use seed. */
  current_version_id: number | null;
}

interface Store {
  entries: Record<string, ResourceEntry>;
}

/* ─────────────── localStorage I/O ─────────────── */

function load(): Store {
  if (typeof window === "undefined") return { entries: {} };
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return { entries: {} };
    return JSON.parse(raw);
  } catch {
    return { entries: {} };
  }
}

function persist(store: Store) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
    window.dispatchEvent(new CustomEvent("versioned-resources-changed"));
  } catch {
    /* quota exceeded — ignore */
  }
}

function entryKey(kind: ResourceKind, id: string): string {
  return `${kind}:${id}`;
}

/* ─────────────── seeding ─────────────── */

/**
 * Ensure an entry exists with the given seed. If the entry already exists,
 * the seed is left alone (we never overwrite user edits silently). This is
 * called at component mount time for every editable resource the page
 * knows about.
 */
export function ensureSeeded(
  kind: ResourceKind,
  id: string,
  seed: string,
): ResourceEntry {
  const store = load();
  const key = entryKey(kind, id);
  if (store.entries[key]) return store.entries[key];
  const entry: ResourceEntry = {
    id,
    kind,
    seed,
    versions: [],
    current_version_id: null,
  };
  store.entries[key] = entry;
  persist(store);
  return entry;
}

/* ─────────────── reads ─────────────── */

export function getEntry(kind: ResourceKind, id: string): ResourceEntry | null {
  const store = load();
  return store.entries[entryKey(kind, id)] ?? null;
}

export function getCurrentContent(entry: ResourceEntry): string {
  if (entry.current_version_id == null) return entry.seed;
  const v = entry.versions.find((x) => x.version_id === entry.current_version_id);
  return v?.content ?? entry.seed;
}

export function getCurrentVersion(entry: ResourceEntry): ResourceVersion | null {
  if (entry.current_version_id == null) return null;
  return entry.versions.find((x) => x.version_id === entry.current_version_id) ?? null;
}

export function listVersions(entry: ResourceEntry): ResourceVersion[] {
  // Newest first.
  return [...entry.versions].sort((a, b) => b.version_id - a.version_id);
}

/* ─────────────── writes ─────────────── */

/**
 * Save a new version of a resource. The content becomes the new "current".
 * Returns the new version. If the entry doesn't exist yet (e.g. localStorage
 * was cleared between mount and save), this auto-seeds with the supplied
 * `seedFallback` so the save isn't lost. If `seedFallback` is also missing
 * the entry, throws.
 */
export function saveVersion(
  kind: ResourceKind,
  id: string,
  content: string,
  message: string,
  author: string = "you",
  seedFallback?: string,
): ResourceVersion {
  const store = load();
  const key = entryKey(kind, id);
  let entry = store.entries[key];

  if (!entry) {
    if (!seedFallback) {
      throw new Error(`Resource ${kind}:${id} not seeded (and no fallback provided)`);
    }
    entry = {
      id,
      kind,
      seed: seedFallback,
      versions: [],
      current_version_id: null,
    };
    store.entries[key] = entry;
  }

  // Idempotency: refuse to save a version identical to the current content.
  if (getCurrentContent(entry) === content) {
    throw new Error("No changes to save");
  }

  const nextId =
    entry.versions.reduce((max, v) => Math.max(max, v.version_id), 0) + 1;
  const version: ResourceVersion = {
    version_id: nextId,
    content,
    author,
    message: message.trim() || `edit v${nextId}`,
    created_at: new Date().toISOString(),
    parent_version_id: entry.current_version_id,
  };
  entry.versions.push(version);
  entry.current_version_id = nextId;
  store.entries[key] = entry;
  persist(store);
  return version;
}

/**
 * Roll back to a previous version. This does NOT delete history — it just
 * moves the current pointer. The rollback itself becomes a new version
 * record so the timeline stays linear.
 */
export function rollbackTo(
  kind: ResourceKind,
  id: string,
  targetVersionId: number | null,
  message?: string,
): ResourceVersion | null {
  const store = load();
  const key = entryKey(kind, id);
  const entry = store.entries[key];
  if (!entry) throw new Error(`Resource ${kind}:${id} not seeded`);

  const target =
    targetVersionId == null
      ? null
      : entry.versions.find((v) => v.version_id === targetVersionId);
  if (targetVersionId != null && !target) {
    throw new Error(`Version ${targetVersionId} not found`);
  }

  const targetContent = target ? target.content : entry.seed;
  if (getCurrentContent(entry) === targetContent) {
    // Already there — no-op
    entry.current_version_id = targetVersionId;
    store.entries[key] = entry;
    persist(store);
    return null;
  }

  // Record the rollback as a new version so the audit trail is honest.
  const nextId =
    entry.versions.reduce((max, v) => Math.max(max, v.version_id), 0) + 1;
  const version: ResourceVersion = {
    version_id: nextId,
    content: targetContent,
    author: "you",
    message:
      message?.trim() ||
      (target
        ? `rollback to v${target.version_id}`
        : "rollback to canonical seed"),
    created_at: new Date().toISOString(),
    parent_version_id: entry.current_version_id,
  };
  entry.versions.push(version);
  entry.current_version_id = nextId;
  store.entries[key] = entry;
  persist(store);
  return version;
}

/**
 * Discard ALL local edits for a resource. Reverts to the canonical seed
 * with empty history. Demo-only escape hatch.
 */
export function resetEntry(kind: ResourceKind, id: string) {
  const store = load();
  const key = entryKey(kind, id);
  const entry = store.entries[key];
  if (!entry) return;
  entry.versions = [];
  entry.current_version_id = null;
  store.entries[key] = entry;
  persist(store);
}

/* ─────────────── diff (line-level, no deps) ─────────────── */

export interface DiffLine {
  type: "context" | "added" | "removed";
  text: string;
  oldLineNum?: number;
  newLineNum?: number;
}

/**
 * Minimal LCS-based line diff. Output is a flat list suitable for a unified
 * diff renderer. Not optimized for huge files — fine for prompt/agent text
 * (rarely >300 lines).
 */
export function computeDiff(oldText: string, newText: string): DiffLine[] {
  const oldLines = oldText.split("\n");
  const newLines = newText.split("\n");
  const m = oldLines.length;
  const n = newLines.length;

  // LCS table.
  const dp: number[][] = Array.from({ length: m + 1 }, () =>
    new Array(n + 1).fill(0),
  );
  for (let i = m - 1; i >= 0; i--) {
    for (let j = n - 1; j >= 0; j--) {
      if (oldLines[i] === newLines[j]) dp[i][j] = dp[i + 1][j + 1] + 1;
      else dp[i][j] = Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }

  const out: DiffLine[] = [];
  let i = 0,
    j = 0,
    oldNum = 1,
    newNum = 1;
  while (i < m && j < n) {
    if (oldLines[i] === newLines[j]) {
      out.push({
        type: "context",
        text: oldLines[i],
        oldLineNum: oldNum,
        newLineNum: newNum,
      });
      i++;
      j++;
      oldNum++;
      newNum++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      out.push({ type: "removed", text: oldLines[i], oldLineNum: oldNum });
      i++;
      oldNum++;
    } else {
      out.push({ type: "added", text: newLines[j], newLineNum: newNum });
      j++;
      newNum++;
    }
  }
  while (i < m) {
    out.push({ type: "removed", text: oldLines[i], oldLineNum: oldNum });
    i++;
    oldNum++;
  }
  while (j < n) {
    out.push({ type: "added", text: newLines[j], newLineNum: newNum });
    j++;
    newNum++;
  }
  return out;
}

export function diffStats(diff: DiffLine[]): { added: number; removed: number } {
  let added = 0;
  let removed = 0;
  for (const line of diff) {
    if (line.type === "added") added++;
    else if (line.type === "removed") removed++;
  }
  return { added, removed };
}
