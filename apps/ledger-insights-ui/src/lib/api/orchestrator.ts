import { apiConfig } from "./config";
import {
  isDemoMode,
  isDemoRun,
  listDemoRuns,
  getDemoRun,
  approveDemoRun,
} from "@/lib/demo";
import type { RunState, RunMode, Stage } from "../types";

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${apiConfig.orchestratorUrl}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new ApiError(res.status, `${path} -> HTTP ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

/* Real orchestrator response shapes (verified against deployed API on 2026-06-06).
   Do NOT change these without re-checking the OpenAPI at /openapi.json. */

/**
 * Phase 3.2 — payload shape for per-card resolver gate approval.
 * Matches the orchestrator's GateDecision pydantic model in
 * apps/orchestrator/models.py. The previous bulk shape
 *   { decision: "approve_all_recommended", rationale: "..." }
 * triggered HTTP 422 because the backend has no such fields.
 */
export interface ApproveBody {
  card_id: string;
  decision_kind: "accept" | "swap" | "reject";
  option_index?: number;
  resolution_text?: string;
  actor: string;
  confidence_source?: "human" | "autopilot";
  gate?: string;
  // Tier-2 governance: "bulk" = swept in by "Approve all recommended";
  // "individual" = explicit per-card decision. The server rejects "bulk" on
  // hard-gated classes (PHI/auth) with 409. Defaults to "individual" server-side.
  approval_path?: "bulk" | "individual";
}

/**
 * Phase 3 — prompt catalog (YAML-backed, persona-owned, versioned).
 *
 * Shape verified against deployed orchestrator's GET /api/prompts/catalog
 * on 2026-06-16. Templates intentionally NOT included on list responses to
 * keep payload small; fetch via promptDetail() for the full body.
 */
export interface PromptCatalogEntry {
  prompt_id: string;
  version: string;
  stage: string;
  scope: "global" | "persona" | "team";
  owner_persona: string;
  status: "draft" | "published" | "superseded";
  git_sha: string;
  authored_by: string;
  reason: string;
  effective_from: string;
  superseded_by: string | null;
  model_compat_notes: string;
  template_chars: number;
  template_first_line: string;
}

export interface PromptCatalogV2Response {
  loaded_from: string;
  count: number;
  by_persona: Record<string, PromptCatalogEntry[]>;
  by_stage: Record<string, PromptCatalogEntry[]>;
  prompts: PromptCatalogEntry[];
}

export interface PromptDetailResponse {
  prompt_id: string;
  version: string;
  stage: string;
  scope: "global" | "persona" | "team";
  owner_persona: string;
  status: "draft" | "published" | "superseded";
  git_sha: string;
  authored_by: string;
  reason: string;
  effective_from: string;
  superseded_by: string | null;
  model_compat_notes: string;
  template: string;
  versions: Array<{ version: string; status: string; effective_from: string }>;
}

export interface RunsListResponse {
  items: RunState[];
  count: number;
}

export interface TelemetryCostResponse {
  window: string;
  since: string;
  total_runs: number;
  total_decisions: number;
  human_decisions: number;
  autopilot_decisions: number;
  total_cost_usd: number;
  total_tokens: number;
  cost_per_decision_usd: number;
  mean_gate_wall_clock_seconds: number;
  mean_tokens_per_run: number;
  cost_by_stage: Record<string, number>;
  cost_per_run_timeseries: Array<{ run_id: string; cost_usd: number; created_at?: string }>;
}

export interface TelemetryClassesResponse {
  window: string;
  since: string;
  total_decisions: number;
  classes: Array<{
    ambiguity_class: string;
    count: number;
    human_count?: number;
    autopilot_count?: number;
    avg_cost_usd?: number;
  }>;
}

export interface PromptCatalogResponse {
  stages: Array<{
    stage_name: string;
    providers: Array<{
      provider: string;
      model: string;
      prompt_version: string;
      template_preview: string;
      model_compat_notes?: string;
    }>;
  }>;
}

export interface PromptLookupResponse {
  stage: string;
  model: string;
  template: string;
  version: string;
  model_compat_notes?: string;
  fallback?: boolean;
}

export interface CreateRunInput {
  prd_text: string;
  filename: string;
  team_id?: string;
  mode?: "manual" | "autopilot" | "hybrid";
  stage_providers?: Record<string, { provider: string; model: string; via_apim?: boolean }>;
}

export const orchestrator = {
  health() {
    return req<{ status: string; runs_in_memory: number }>("/healthz");
  },
  async listRuns() {
    if (isDemoMode()) {
      // Merge live runs with demo runs from localStorage. If the live API
      // is unreachable in demo mode (offline demos), return demo runs only.
      const demoRuns = listDemoRuns();
      try {
        const live = await req<RunsListResponse>("/api/runs");
        return {
          items: [...demoRuns, ...live.items],
          count: demoRuns.length + live.count,
        };
      } catch {
        return { items: demoRuns, count: demoRuns.length };
      }
    }
    return req<RunsListResponse>("/api/runs");
  },
  async getRun(runId: string) {
    if (isDemoMode() && isDemoRun(runId)) {
      const r = getDemoRun(runId);
      if (!r) throw new ApiError(404, `Demo run ${runId} not found`);
      return r;
    }
    return req<RunState>(`/api/runs/${runId}`);
  },
  /** Submit a PRD as multipart/form-data. Real orchestrator accepts UploadFile. */
  async createRun(input: CreateRunInput): Promise<{ run_id: string; stream_url: string }> {
    const fd = new FormData();
    fd.append(
      "prd",
      new Blob([input.prd_text], { type: "text/markdown" }),
      input.filename,
    );
    fd.append("team_id", input.team_id ?? "cardiology");
    fd.append("mode", input.mode ?? "manual");
    if (input.stage_providers && Object.keys(input.stage_providers).length > 0) {
      fd.append("stage_providers", JSON.stringify(input.stage_providers));
    }
    const res = await fetch(`${apiConfig.orchestratorUrl}/api/run`, {
      method: "POST",
      body: fd,
      cache: "no-store",
    });
    if (!res.ok) {
      const detail = await res.text().catch(() => "");
      throw new ApiError(res.status, `POST /api/run -> HTTP ${res.status}${detail ? `: ${detail.slice(0, 300)}` : ""}`);
    }
    return res.json();
  },
  rerun(runId: string, body?: { mode?: "manual" | "autopilot" | "hybrid" }) {
    return req<{ run_id: string }>(`/api/runs/${runId}/rerun`, {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    });
  },
  pause(runId: string) {
    if (isDemoRun(runId)) {
      // Demo runs cannot be paused — replay is deterministic.
      const r = getDemoRun(runId);
      if (!r) throw new ApiError(404, `Demo run ${runId} not found`);
      return Promise.resolve(r);
    }
    return req<RunState>(`/api/runs/${runId}/pause`, { method: "POST" });
  },
  resume(runId: string) {
    if (isDemoRun(runId)) {
      const r = getDemoRun(runId);
      if (!r) throw new ApiError(404, `Demo run ${runId} not found`);
      return Promise.resolve(r);
    }
    return req<RunState>(`/api/runs/${runId}/resume`, { method: "POST" });
  },
  // Phase 3.2 wiring (2026-06-16): orchestrator expects per-card
  // GateDecision payload — NOT a bulk { decision, rationale } shape.
  // The previous approveAll body returned HTTP 422 (Unprocessable
  // Entity) on every click — confirmed on run 66ce4cb5.
  //
  // Per-card: POST /api/runs/<id>/approve with
  //   { card_id, decision_kind, option_index, actor, confidence_source }
  // Then close the gate: POST /api/runs/<id>/finalize
  //
  // We loop the approves so each one writes its own LedgerEntry with
  // the prompt_resolution_path pinned (Phase 2.6 work). Operator sees
  // per-card progress via the submitting flag + toast.
  approve(runId: string, body: ApproveBody) {
    if (isDemoRun(runId)) {
      // Demo gate approval triggers the local replay engine to fire the
      // architect → deliver chain. The body is accepted for API parity but
      // ignored — the demo replays a fixed pre-canned decision set.
      approveDemoRun(runId);
      const r = getDemoRun(runId);
      if (!r) throw new ApiError(404, `Demo run ${runId} not found`);
      return Promise.resolve(r);
    }
    return req<{ ok: boolean; decisions_count: number; resolution_text: string }>(
      `/api/runs/${runId}/approve`,
      { method: "POST", body: JSON.stringify(body) },
    );
  },
  finalizeGate(runId: string) {
    if (isDemoRun(runId)) {
      // Demo runs auto-close gates inside approveDemoRun; finalize is a no-op.
      return Promise.resolve({ ok: true });
    }
    return req<{ ok: boolean; gate_closed: boolean; decisions_count: number; next_stage: string }>(
      `/api/runs/${runId}/finalize`,
      { method: "POST", body: JSON.stringify({}) },
    );
  },
  reject(runId: string, body: { reason: string }) {
    if (isDemoRun(runId)) {
      // Reject is a no-op for demo runs — they always run to completion.
      const r = getDemoRun(runId);
      if (!r) throw new ApiError(404, `Demo run ${runId} not found`);
      return Promise.resolve(r);
    }
    return req<RunState>(`/api/runs/${runId}/reject`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },
  telemetryCost() {
    return req<TelemetryCostResponse>("/api/telemetry/cost");
  },
  telemetryClasses() {
    return req<TelemetryClassesResponse>("/api/telemetry/classes");
  },
  telemetryDecisions() {
    return req<{ entries: Array<Record<string, unknown>> }>("/api/telemetry/decisions");
  },
  promptLibrary() {
    return req<PromptCatalogResponse>("/api/prompt-library");
  },
  promptForStage(stage: string) {
    return req<PromptLookupResponse>(`/api/prompt-library/${stage}`);
  },
  // Phase 3 — new prompt catalog backed by YAML files under prompts/global/<stage>/v*.yaml
  // and resolved through the Phase 2 inheritance walker on every pipeline stage.
  promptCatalog() {
    return req<PromptCatalogV2Response>("/api/prompts/catalog");
  },
  promptDetail(promptId: string, version?: string) {
    const q = version ? `?version=${encodeURIComponent(version)}` : "";
    return req<PromptDetailResponse>(`/api/prompts/${encodeURIComponent(promptId)}${q}`);
  },
  streamUrl(runId: string) {
    return `${apiConfig.orchestratorUrl}/api/runs/${runId}/stream`;
  },

  // ── Editing plane (#3): governed PR write-back ──────────────────────────
  // Each save opens a PR on the config file the pipeline reads (CODEOWNERS
  // review), returning the PR URL. Bundles are PR-only by governance design.
  saveAgentConfig(body: {
    name: string; content: string; commit_message: string;
    pr_title?: string; pr_body?: string;
  }) {
    return req<ConfigSaveResponse>("/api/config/agents/save", {
      method: "POST", body: JSON.stringify(body),
    });
  },
  saveBundleConfig(body: {
    dept: string; version: string; file?: string; content: string;
    commit_message: string; pr_title?: string; pr_body?: string;
  }) {
    return req<ConfigSaveResponse>("/api/config/bundles/save", {
      method: "POST", body: JSON.stringify(body),
    });
  },
  savePromptConfig(body: {
    scope: string; stage: string; version: string; persona?: string;
    content: string; commit_message: string; pr_title?: string; pr_body?: string;
  }) {
    return req<ConfigSaveResponse>("/api/config/prompts/save", {
      method: "POST", body: JSON.stringify(body),
    });
  },
  reloadConfig() {
    return req<{ ok: boolean; reloaded: string[] }>("/api/config/reload", {
      method: "POST",
    });
  },
  repoAutonomy() {
    return req<import("../types").RepoAutonomyPosture>("/api/config/repo-autonomy");
  },
};

export interface ConfigSaveResponse {
  ok: boolean;
  pr_url: string | null;
  branch: string;
  path: string;
  dry_run: boolean;
  message: string;
}

/** Browser-fetch a same-origin sample PRD file (lives under public/samples). */
export async function fetchSample(url: string): Promise<string> {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to load sample (${res.status})`);
  return res.text();
}
