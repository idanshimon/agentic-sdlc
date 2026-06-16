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
  approve(runId: string, body: { decision: string; rationale: string }) {
    if (isDemoRun(runId)) {
      // Demo gate approval triggers the local replay engine to fire the
      // architect → deliver chain. The body is accepted for API parity but
      // ignored — the demo replays a fixed pre-canned decision set.
      approveDemoRun(runId);
      const r = getDemoRun(runId);
      if (!r) throw new ApiError(404, `Demo run ${runId} not found`);
      return Promise.resolve(r);
    }
    return req<RunState>(`/api/runs/${runId}/approve`, {
      method: "POST",
      body: JSON.stringify(body),
    });
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
};

/** Browser-fetch a same-origin sample PRD file (lives under public/samples). */
export async function fetchSample(url: string): Promise<string> {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to load sample (${res.status})`);
  return res.text();
}
