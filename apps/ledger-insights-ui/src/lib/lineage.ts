/**
 * lineage.ts — reconstruct the decision relationship graph from a flat entries
 * list, so the Decisions surface can show what a plain table cannot: which
 * human decisions TAUGHT the pipeline, which agent decisions REUSED that
 * teaching, and how decisions cluster by ambiguity bucket.
 *
 * The teaching loop (add-graduated-autonomy-tier2) is what turned the ledger
 * from a flat log into a graph:
 *   - A human SWAP (decision_kind="swap") on an ambiguity becomes precedent,
 *     keyed by slot_value_hash (team + class + slot).
 *   - A later HYBRID/AUTOPILOT run hits the same bucket → findPrecedent returns
 *     the swap → the card AUTO-RESOLVES (confidence_source="autopilot") instead
 *     of gating. That reuse is the loop closing.
 *   - A FLAG (decision_flagged) kills a precedent's future reuse.
 *   - A self-heal chain ties 3 entries via heal_id.
 *
 * All edges are latent in fields already on LedgerEntry — this module just
 * materializes them. Pure functions, no React, no I/O → unit-testable.
 */
import type { LedgerEntry } from "@/lib/types";

const TEACHING_KINDS = new Set([
  "feedback_thumbs",
  "decision_flagged",
  "replay_requested",
  "class_paused",
]);

/** A decision is a "stage decision" (pipeline call) vs an operator teaching signal. */
export function isStageDecision(e: LedgerEntry): boolean {
  return !e.runtime_kind || !TEACHING_KINDS.has(e.runtime_kind);
}

export function isTeachingSignal(e: LedgerEntry): boolean {
  return !!e.runtime_kind && TEACHING_KINDS.has(e.runtime_kind);
}

/** Did a human override the recommendation here (the teaching event)? */
export function isHumanSwap(e: LedgerEntry): boolean {
  return (
    isStageDecision(e) &&
    e.decision_kind === "swap" &&
    (e.confidence_source === "human" || e.actor?.kind === "human")
  );
}

/** Was this decision made autonomously by the agent (reused precedent / autopilot)? */
export function isAutopilot(e: LedgerEntry): boolean {
  return isStageDecision(e) && e.confidence_source === "autopilot";
}

export type LineageRole =
  | "taught" // human swap that can become precedent
  | "reused" // autopilot decision that reused a precedent (loop closed)
  | "flagged" // a flag/pause teaching signal acted on this
  | "heal" // part of a self-heal chain
  | "plain"; // ordinary decision, no special lineage

export interface LineageInfo {
  role: LineageRole;
  /** How many OTHER decisions share this decision's ambiguity bucket (slot_value_hash). */
  bucketSize: number;
  /** For a "taught" entry: how many later autopilot decisions reused this bucket. */
  reusedByCount: number;
  /** Teaching signals (flag/thumb/replay/pause) pointing at this entry. */
  signalCount: number;
  /** Other entry ids in the same heal_id chain. */
  healChainIds: string[];
  /** The ambiguity bucket key, if any. */
  slotKey?: string;
}

export interface LineageIndex {
  /** Per-entry lineage info, keyed by entry id. */
  byId: Map<string, LineageInfo>;
  /** Teaching-loop autonomy metrics for the KPI strip. */
  metrics: {
    taughtCount: number; // human swaps that are precedent-eligible
    reusedCount: number; // autopilot decisions that reused a taught bucket
    /** % of stage decisions that were auto-resolved from a human-taught bucket. */
    autonomyEarnedPct: number;
    bucketsTaught: number; // distinct ambiguity buckets with a human swap
    healChains: number; // distinct heal_id chains
  };
}

/**
 * Build the lineage index for a list of entries. O(n) over two passes.
 */
export function buildLineageIndex(entries: LedgerEntry[]): LineageIndex {
  const stage = entries.filter(isStageDecision);
  const signals = entries.filter(isTeachingSignal);

  // --- group stage decisions by ambiguity bucket (slot_value_hash) ---
  const byBucket = new Map<string, LedgerEntry[]>();
  for (const e of stage) {
    if (!e.slot_value_hash) continue;
    const arr = byBucket.get(e.slot_value_hash) ?? [];
    arr.push(e);
    byBucket.set(e.slot_value_hash, arr);
  }

  // buckets that contain a human swap = "taught" buckets
  const taughtBuckets = new Set<string>();
  for (const [hash, arr] of byBucket) {
    if (arr.some(isHumanSwap)) taughtBuckets.add(hash);
  }

  // --- teaching signals pointing at each entry ---
  const signalsByTarget = new Map<string, number>();
  for (const s of signals) {
    if (!s.references_entry_id) continue;
    signalsByTarget.set(
      s.references_entry_id,
      (signalsByTarget.get(s.references_entry_id) ?? 0) + 1,
    );
  }

  // --- heal chains ---
  const byHeal = new Map<string, string[]>();
  for (const e of entries) {
    if (!e.heal_id) continue;
    const arr = byHeal.get(e.heal_id) ?? [];
    arr.push(e.id);
    byHeal.set(e.heal_id, arr);
  }

  const byId = new Map<string, LineageInfo>();
  let taughtCount = 0;
  let reusedCount = 0;

  for (const e of stage) {
    const slotKey = e.slot_value_hash;
    const bucket = slotKey ? byBucket.get(slotKey) ?? [] : [];
    const bucketSize = Math.max(0, bucket.length - 1);
    const signalCount = signalsByTarget.get(e.id) ?? 0;
    const healChainIds = e.heal_id ? (byHeal.get(e.heal_id) ?? []).filter((id) => id !== e.id) : [];

    // count later autopilot reuses in the same bucket (for a taught entry)
    const reusedByCount =
      slotKey && taughtBuckets.has(slotKey)
        ? bucket.filter((b) => isAutopilot(b)).length
        : 0;

    let role: LineageRole = "plain";
    if (e.heal_id) role = "heal";
    else if (signalCount > 0) role = "flagged";
    else if (isHumanSwap(e)) role = "taught";
    else if (isAutopilot(e) && slotKey && taughtBuckets.has(slotKey)) role = "reused";

    if (role === "taught") taughtCount += 1;
    if (role === "reused") reusedCount += 1;

    byId.set(e.id, {
      role,
      bucketSize,
      reusedByCount,
      signalCount,
      healChainIds,
      slotKey,
    });
  }

  const totalStage = stage.length;
  const autonomyEarnedPct = totalStage ? Math.round((reusedCount / totalStage) * 100) : 0;

  return {
    byId,
    metrics: {
      taughtCount,
      reusedCount,
      autonomyEarnedPct,
      bucketsTaught: taughtBuckets.size,
      healChains: byHeal.size,
    },
  };
}

/** Human-readable label + tone for a lineage role (for the table badge). */
export function lineageBadge(info: LineageInfo): { label: string; tone: string; title: string } | null {
  switch (info.role) {
    case "taught":
      return {
        label: info.reusedByCount > 0 ? `taught · reused ${info.reusedByCount}×` : "taught",
        tone: "success",
        title:
          info.reusedByCount > 0
            ? `A human override here became precedent and was reused by ${info.reusedByCount} later autopilot decision(s).`
            : "A human override here became precedent (not yet reused).",
      };
    case "reused":
      return {
        label: "auto · from precedent",
        tone: "info",
        title: "The agent auto-resolved this from a human-taught precedent in the same ambiguity bucket.",
      };
    case "flagged":
      return {
        label: info.signalCount > 1 ? `flagged ${info.signalCount}×` : "flagged",
        tone: "warning",
        title: `${info.signalCount} operator teaching signal(s) act on this decision.`,
      };
    case "heal":
      return {
        label: "heal chain",
        tone: "secondary",
        title: `Part of a self-heal chain (${info.healChainIds.length + 1} linked entries).`,
      };
    default:
      return null;
  }
}
