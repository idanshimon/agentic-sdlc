/* Domain types for the four-plane reference design.
   Mirrors openspec/specs/* + apps/orchestrator/models.py. */

export type Plane = "standards" | "pipeline" | "ledger" | "agenthq";

export type Stage =
  | "ingest"
  | "assessor"
  | "architect"
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
  status: "started" | "in_progress" | "awaiting_gate" | "completed" | "failed";
  message?: string;
  timestamp: string;
  payload?: Record<string, unknown>;
}

export interface RunState {
  run_id: string;
  team_id: string;
  mode: RunMode;
  status: RunStatus;
  current_stage?: Stage | null;
  created_at: string;
  updated_at: string;
  events: StageEvent[];
  cost_usd?: number;
  decisions_count?: number;
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
