/* Mission Control projection — pure, framework-free.
 *
 * Derives the cockpit view (pipeline stage occupancy, run rings, per-agent
 * activity) from existing RunState + LedgerEntry fields ONLY. Nothing here is
 * invented: an entry that cannot be attributed to a persona is counted as
 * unattributed, never guessed onto an agent.
 */
import type { RunState, LedgerEntry } from "@/lib/types";

/** Canonical pipeline spine shown on the dial. */
export const MISSION_STAGES = [
  { id: "ingest", label: "Ingest" },
  { id: "assessor", label: "Assess" },
  { id: "resolver", label: "Resolve" },
  { id: "architect", label: "Architect" },
  { id: "test_plan", label: "Test plan" },
  { id: "codegen", label: "Codegen" },
  { id: "review_scan", label: "Review" },
  { id: "deliver", label: "Deliver" },
] as const;

export type MissionStageId = (typeof MISSION_STAGES)[number]["id"];

const STAGE_ALIASES: Record<string, MissionStageId> = {
  ingest: "ingest",
  assessor: "assessor",
  assess: "assessor",
  resolver: "resolver",
  gate: "resolver",
  architect: "architect",
  design_review: "architect",
  test_plan: "test_plan",
  testplan: "test_plan",
  codegen: "codegen",
  review_scan: "review_scan",
  "review-scan": "review_scan",
  review: "review_scan",
  deliver: "deliver",
};

export function normalizeStage(stage: string | null | undefined): MissionStageId | null {
  if (!stage) return null;
  return STAGE_ALIASES[stage.toLowerCase()] ?? null;
}

/** Ring = consequence band. 0 is innermost (closest to the human at the hub). */
export type RingKind = "blocked" | "failed" | "active" | "done";
export const RINGS: RingKind[] = ["blocked", "failed", "active", "done"];

export function ringOf(run: RunState): RingKind {
  switch (run.status) {
    case "awaiting_gate":
    case "paused":
      return "blocked";
    case "failed":
    case "cancelled":
      return "failed";
    case "running":
    case "queued":
      return "active";
    default:
      return "done";
  }
}

/** Which stage a run sits at. Completed runs park at deliver. */
export function runStage(run: RunState): MissionStageId {
  const fromGate = normalizeStage(run.pending_gate?.stage ?? null);
  if (fromGate && ringOf(run) === "blocked") return fromGate;
  const cur = normalizeStage(typeof run.current_stage === "string" ? run.current_stage : null);
  if (cur) return cur;
  const failed = normalizeStage(run.failure_stage ?? null);
  if (failed) return failed;
  const events = run.events ?? [];
  for (let i = events.length - 1; i >= 0; i -= 1) {
    const s = normalizeStage(events[i]?.stage);
    if (s) return s;
  }
  return run.status === "completed" ? "deliver" : "ingest";
}

export interface StageOccupancy {
  id: MissionStageId;
  label: string;
  total: number;
  byRing: Record<RingKind, number>;
}

export function stageOccupancy(runs: RunState[]): StageOccupancy[] {
  const out = MISSION_STAGES.map((s) => ({
    id: s.id,
    label: s.label,
    total: 0,
    byRing: { blocked: 0, failed: 0, active: 0, done: 0 } as Record<RingKind, number>,
  }));
  const idx = new Map(out.map((o, i) => [o.id, i]));
  for (const r of runs) {
    if (!r?.run_id) continue;
    const o = out[idx.get(runStage(r))!];
    o.total += 1;
    o.byRing[ringOf(r)] += 1;
  }
  return out;
}

/* ── Agent attribution ─────────────────────────────────────────────── */

/** Persona id → pipeline stages whose decisions it authors. */
export const AGENT_STAGES: Record<string, MissionStageId[]> = {
  assessor: ["assessor"],
  architect: ["architect"],
  codegen: ["codegen"],
  "review-scan": ["review_scan"],
};

/** The stage the producer recorded for this entry: the explicit `stage`
 *  field, else the stage the prompt resolver logged when it resolved the
 *  prompt that produced the decision ("... stage=assessor"). Both are written
 *  by the orchestrator at decision time — neither is inferred here. */
export function recordedStage(e: LedgerEntry): MissionStageId | null {
  const direct = normalizeStage(e.stage ?? null);
  if (direct) return direct;
  const path = e.prompt_resolution_path as unknown;
  if (!path) return null;
  const text = typeof path === "string" ? path : JSON.stringify(path);
  const m = text.match(/stage=([a-z_-]+)/i);
  return m ? normalizeStage(m[1]) : null;
}

export function attributeEntry(e: LedgerEntry): string | null {
  const s = recordedStage(e);
  if (!s) return null;
  for (const [agent, stages] of Object.entries(AGENT_STAGES)) {
    if (stages.includes(s)) return agent;
  }
  return null;
}

export interface AgentActivity {
  id: string;
  decisions: number;
  autonomous: number;
  human: number;
  flagged: number;
  costUsd: number;
  /** Entries that actually carried a cost. 0 means spend is not recorded, not $0. */
  costed: number;
  lastAt: string | null;
  /** Decision counts per bucket (default: weekly over 12 weeks), oldest → newest. */
  spark: number[];
  models: string[];
}

export interface AgentActivityResult {
  agents: Record<string, AgentActivity>;
  unattributed: number;
}

const DAY = 86_400_000;

export function agentActivity(
  entries: LedgerEntry[],
  agentIds: string[],
  opts: { now?: number; buckets?: number; bucketDays?: number } = {},
): AgentActivityResult {
  const now = opts.now ?? Date.now();
  const days = opts.buckets ?? 12;
  const width = (opts.bucketDays ?? 7) * DAY;
  const agents: Record<string, AgentActivity> = {};
  for (const id of agentIds) {
    agents[id] = {
      id, decisions: 0, autonomous: 0, human: 0, flagged: 0, costUsd: 0, costed: 0,
      lastAt: null, spark: new Array(days).fill(0), models: [],
    };
  }
  // flagged = a decision_flagged signal points at an entry this agent authored
  const flaggedTargets = new Set(
    entries
      .filter((e) => e.runtime_kind === "decision_flagged" && e.references_entry_id)
      .map((e) => e.references_entry_id as string),
  );
  let unattributed = 0;
  for (const e of entries) {
    if (e.runtime_kind && e.runtime_kind !== "stage_decision") continue;
    const who = attributeEntry(e);
    if (!who || !agents[who]) {
      unattributed += 1;
      continue;
    }
    const a = agents[who];
    a.decisions += 1;
    // confidence_source is who actually made the call; actor.kind may be a
    // normalizer default on flat live rows, so prefer the explicit field.
    const isHuman = e.confidence_source
      ? e.confidence_source === "human"
      : e.actor?.kind === "human";
    if (isHuman) a.human += 1;
    else a.autonomous += 1;
    if (flaggedTargets.has(e.id)) a.flagged += 1;
    if (typeof e.cost_usd === "number" && Number.isFinite(e.cost_usd)) {
      a.costUsd += e.cost_usd;
      a.costed += 1;
    }
    if (e.created_at && (!a.lastAt || e.created_at > a.lastAt)) a.lastAt = e.created_at;
    if (e.model_used && !a.models.includes(e.model_used)) a.models.push(e.model_used);
    const t = Date.parse(e.created_at);
    if (!Number.isNaN(t)) {
      const ageDays = Math.floor((now - t) / width);
      if (ageDays >= 0 && ageDays < days) a.spark[days - 1 - ageDays] += 1;
    }
  }
  return { agents, unattributed };
}

/* ── Orbit layout (deterministic, so screenshots are reproducible) ── */

export interface OrbitPoint {
  runId: string;
  ring: RingKind;
  stage: MissionStageId;
  angle: number; // radians, 0 = 12 o'clock, clockwise
  radius: number;
}

export function orbitLayout(
  runs: RunState[],
  radii: Record<RingKind, number>,
  opts: { spacing?: number; laneGap?: number; maxLanes?: number } = {},
): OrbitPoint[] {
  const spacing = opts.spacing ?? 15;
  const laneGap = opts.laneGap ?? 11;
  const maxLanes = opts.maxLanes ?? 5;
  const n = MISSION_STAGES.length;
  const sector = (2 * Math.PI) / n;
  const buckets = new Map<string, RunState[]>();
  for (const r of runs) {
    if (!r?.run_id) continue;
    const key = `${runStage(r)}|${ringOf(r)}`;
    const list = buckets.get(key) ?? [];
    list.push(r);
    buckets.set(key, list);
  }
  const out: OrbitPoint[] = [];
  for (const [key, list] of buckets) {
    const [stage, ring] = key.split("|") as [MissionStageId, RingKind];
    const si = MISSION_STAGES.findIndex((s) => s.id === stage);
    const sorted = [...list].sort((a, b) => a.run_id.localeCompare(b.run_id));
    // Crowded sectors stack into concentric lanes around the ring radius so
    // dots never pile on top of each other.
    const arc = 0.8 * sector * radii[ring];
    const lanes = Math.min(maxLanes, Math.max(1, Math.ceil((sorted.length * spacing) / arc)));
    const perLane = Math.ceil(sorted.length / lanes);
    sorted.forEach((r, i) => {
      const lane = Math.floor(i / perLane);
      const k = i % perLane;
      const inLane = Math.min(perLane, sorted.length - lane * perLane);
      const stagger = lane % 2 ? 0.5 / Math.max(1, inLane) : 0;
      const frac = inLane === 1 ? 0.5 : 0.1 + 0.8 * Math.min(1, k / (inLane - 1) + stagger * 0.8);
      out.push({
        runId: r.run_id,
        ring,
        stage,
        angle: si * sector + frac * sector,
        radius: radii[ring] + (lane - (lanes - 1) / 2) * laneGap,
      });
    });
  }
  return out;
}
