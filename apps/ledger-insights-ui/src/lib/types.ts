/* Domain types for the four-plane reference design.
   Mirrors openspec/specs/* + apps/orchestrator/models.py. */

export type Plane = "standards" | "pipeline" | "ledger" | "agenthq";

export type Stage =
  | "ingest"
  | "assessor"
  | "resolver"        // gate stage emitted by orchestrator when /api/runs/<id>/stream fires gate_open
  | "architect"
  | "design_review"   // second gate stage
  | "test_plan"
  | "codegen"
  | "review_scan"
  | "deliver";

export type RunStatus =
  | "queued"
  | "running"
  | "awaiting_gate"
  | "paused"
  | "completed"
  | "failed"
  | "cancelled";

export type RunMode = "auto" | "guided" | "dry_run";

export interface StageEvent {
  stage: Stage;
  status: "started" | "in_progress" | "awaiting_gate" | "completed" | "failed" | "progress" | "gate_open";
  message?: string;
  /** ISO timestamp. Orchestrator emits as `ts` (StageEvent.ts in models.py);
   *  Demo Mode used to emit as `timestamp`. Always read via the
   *  `eventTimestamp()` helper in lib/utils.ts to handle both shapes. */
  timestamp?: string;
  ts?: string;
  payload?: Record<string, unknown>;
}

export interface RunState {
  run_id: string;
  team_id: string;
  mode: RunMode;
  status: RunStatus;
  current_stage?: Stage | string | null;
  created_at: string;
  updated_at: string;
  events: StageEvent[];
  /** @deprecated read total_cost_usd; this alias kept for legacy demo data. */
  cost_usd?: number;
  total_cost_usd?: number;
  total_tokens?: number;
  decisions_count?: number;
  /** Per-stage wall-clock seconds. Populated by the orchestrator + the
   *  experiments harness; absent on legacy in-memory-only runs. */
  stage_durations_seconds?: Record<string, number>;
  /** Total wall clock for the run (from harness summary.json). */
  wall_clock_seconds?: number;
  /** Per-stage provider/model routing snapshot. Useful when an A/B harness
   *  is comparing two models — operator can drill into the run and see
   *  which model produced which artifact. */
  model_routing?: Record<string, { provider?: string; model?: string }>;
  /** Output artifact sizes, keyed by name (architecture_chars, etc.). */
  artifact_sizes?: Record<string, number>;
  /** Experiment-namespace provenance (set by the SBM harness seeder). */
  namespace?: string;
  model?: string;
  model_slug?: string;
  source_run_dir?: string;
  original_team_id?: string;
}

export interface AmbiguityCard {
  ambiguity_class: string;
  prompt: string;
  options: ResolutionOption[];
  recommended?: string;
}

export interface ResolutionOption {
  id: string;
  label: string;
  description: string;
  precedent_count?: number;
}

export interface LedgerEntry {
  id: string;
  entry_type: "runtime" | "meta";
  team_id?: string;
  run_id?: string;
  agent_session_id?: string;
  stage?: Stage;
  actor: { kind: "human" | "agent"; id: string };
  decision: string;
  rationale: string;
  phi_class: "none" | "low" | "high";
  cost_usd: number;
  model_used: string;
  bundle_refs: string[];
  precedent_refs?: string[];
  /**
   * Phase 2.6 chain pinning (2026-06-16): every LedgerEntry written by
   * a stage_decision now carries the full prompt inheritance chain that
   * produced its ambiguity-card recommendation. The orchestrator's
   * stages stash chain on RunState.prompt_chain_by_stage; both ledger
   * writers (autopilot in main.py::_drive, per-card in main.py::approve)
   * copy that chain into LedgerEntry.prompt_resolution_path before write.
   *
   * Shape mirrors PromptCatalog.resolve(...).chain_as_list():
   *   each step has scope + matched + reason + (when matched) the full
   *   matched-prompt frontmatter (prompt_id, version, git_sha, owner_persona).
   *
   * Legacy entries (pre-Phase-2) have null/undefined here — UI renders
   * "chain unavailable (pre-v2)" per openspec spec scenario.
   */
  prompt_resolution_path?: Array<{
    scope: "team" | "persona" | "global";
    matched: boolean;
    reason?: string;
    prompt_id?: string;
    version?: string;
    git_sha?: string;
    owner_persona?: string;
  }> | null;
  /**
   * Discriminator added by the orchestrator. Most card-style renderers
   * don't need this directly, but the economics aggregator uses it to
   * classify autonomy (plan_proposed = human-gated even if actor=agent).
   * Track B: feedback_thumbs, decision_flagged, replay_requested, class_paused.
   */
  runtime_kind?:
    | "stage_decision"
    | "ide_session_summary"
    | "ide_tool_call"
    | "auto_fix"
    | "delivered"
    | "plan_proposed"
    | "phi_block"
    | "feedback_thumbs"
    | "decision_flagged"
    | "replay_requested"
    | "class_paused";
  /** Track B: pointer back to the decision this teaching signal acts on. */
  references_entry_id?: string;
  /** Track B: thumbs subkind, only set when runtime_kind=feedback_thumbs. */
  feedback_kind?: "thumbs_up" | "thumbs_down";
  /** Track B: the ambiguity class paused, only set when runtime_kind=class_paused. */
  paused_class?: string;
  /** Original ambiguity class — set on stage_decision entries by the assessor. */
  ambiguity_class?: string;
  created_at: string;
}

export interface StandardsBundle {
  dept: "security" | "privacy" | "architect" | "finops";
  version: string;
  rules: BundleRule[];
  reviewers: string[];
  pinned: boolean;
}

export interface BundleRule {
  id: string;
  title: string;
  must: string;
  rationale?: string;
  examples?: { good?: string; bad?: string };
}

export interface CustomAgent {
  name: string;
  role: string;
  bundle_subscriptions: string[];
  tools: string[];
  preferred_models: string[];
  ledger_writes: string[];
}

export interface TelemetryCostPoint {
  date: string;
  total_usd: number;
  by_stage?: Record<string, number>;
}

export interface TelemetryClass {
  ambiguity_class: string;
  count: number;
  avg_cost_usd: number;
  resolution_modes: Record<string, number>;
}
