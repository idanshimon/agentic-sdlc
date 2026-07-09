import type { LedgerEntry } from "../types";

/**
 * Merge demo-store ledger entries with live (Cosmos-backed) entries for the
 * dashboard's Decisions view when NEXT_PUBLIC_DEMO_MODE=1.
 *
 * The previous blend simply concatenated `[...demo, ...live]` with NO de-dupe
 * and NO re-sort, so:
 *   - a fresh live decision landed at the BOTTOM (after the demo seed block),
 *     making it look like "nothing new appeared" even though it was fetched;
 *   - if the same entry existed in both stores it showed twice.
 *
 * This function de-dupes by `id` (live wins over demo — the live Cosmos row is
 * the source of truth) and sorts newest-first by `created_at`, so a just-written
 * decision always surfaces at the top regardless of the demo seed timestamps.
 */
export function mergeLedgerEntries(
  demo: LedgerEntry[],
  live: LedgerEntry[],
): LedgerEntry[] {
  const byId = new Map<string, LedgerEntry>();
  // Insert demo first, then let live overwrite on id collision (live = truth).
  for (const e of demo) {
    const id = entryId(e);
    if (id) byId.set(id, e);
    else pushKeyless(byId, e);
  }
  for (const e of live) {
    const id = entryId(e);
    if (id) byId.set(id, e);
    else pushKeyless(byId, e);
  }
  const merged = Array.from(byId.values());
  merged.sort((a, b) => String(b.created_at ?? "").localeCompare(String(a.created_at ?? "")));
  return merged;
}

function entryId(e: LedgerEntry): string | undefined {
  const id = (e as { id?: unknown }).id;
  return typeof id === "string" && id.length > 0 ? id : undefined;
}

// Entries without a stable id can't be de-duped; keep them all under unique keys.
let keylessCounter = 0;
function pushKeyless(map: Map<string, LedgerEntry>, e: LedgerEntry): void {
  map.set(`__keyless_${keylessCounter++}`, e);
}
