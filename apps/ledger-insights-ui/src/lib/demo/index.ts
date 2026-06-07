/* Demo Mode — single feature flag, single subsystem, single rip-out point.
 *
 * Set NEXT_PUBLIC_DEMO_MODE=1 to enable. When enabled:
 *   - "DEMO MODE" pill appears in the topbar
 *   - /runs/new shows "Start Demo Run" buttons that replay pre-canned runs
 *   - Demo runs accumulate in localStorage and appear alongside live runs
 *   - SSE streaming is replaced with a timed replay engine (no LLM calls)
 *
 * Pre-canned data lives in fixtures.ts, generated from real Phase-A-fixed
 * pipeline output by `python experiments/extract_demo_fixture.py`.
 *
 * To rip out for production:
 *   1. Set NEXT_PUBLIC_DEMO_MODE= (empty)
 *   2. Delete src/lib/demo/
 *   3. Remove the four `if (isDemoMode())` guards in:
 *        - src/lib/api/orchestrator.ts (listRuns, getRun)
 *        - src/lib/hooks/use-run-stream.ts
 *        - src/components/layout/topbar.tsx
 *        - src/app/runs/new/page.tsx
 *   4. Verify with `grep -r "demo/" src/` — should return nothing.
 */
import {
  VITALS_PRD,
  VITALS_CARDS,
  VITALS_DECISIONS,
  VITALS_LEDGER,
  VITALS_ARCHITECTURE_MD,
  VITALS_TEST_PLAN_MD,
  VITALS_CODE_PY,
  VITALS_DECISIONS_MD,
  VITALS_SUMMARY,
} from "./fixtures";
import type { RunState, StageEvent, AmbiguityCard } from "@/lib/types";

const DEMO_RUN_PREFIX = "demo-";
const STORAGE_KEY = "agentic-sdlc.demo.runs";

/* ───────────────────────── feature flag ───────────────────────── */

export function isDemoMode(): boolean {
  // Browser: NEXT_PUBLIC_* is inlined at build time.
  if (typeof window === "undefined") {
    return process.env.NEXT_PUBLIC_DEMO_MODE === "1";
  }
  return process.env.NEXT_PUBLIC_DEMO_MODE === "1";
}

export function isDemoRun(runId: string | undefined | null): boolean {
  return !!runId && runId.startsWith(DEMO_RUN_PREFIX);
}

/* ───────────────────────── pre-canned scenarios ───────────────────────── */

export interface DemoScenario {
  id: string;
  /** Short title shown on the launch button. */
  title: string;
  /** One-line subtitle. */
  subtitle: string;
  /** PRD text to display in the Ingest stage. */
  prd: string;
  /** Realtime replay timing per stage (ms). */
  timing: Record<string, number>;
  /** Pre-canned artifacts. */
  cards: AmbiguityCard[];
  decisions: ReadonlyArray<Record<string, unknown>>;
  ledger: ReadonlyArray<Record<string, unknown>>;
  architecture: string;
  test_plan: string;
  code: string;
  decisions_md: string;
  summary: Record<string, unknown>;
  team_id: string;
}

/** Pre-canned scenarios for demo replay. Sourced from real Phase-A-fixed runs. */
export const DEMO_SCENARIOS: DemoScenario[] = [
  {
    id: "vitals",
    title: "Patient Vitals Streaming",
    subtitle:
      "FHIR HL7 streaming, cardiology workload, real PHI surface — full audit-grade pipeline replay",
    prd: VITALS_PRD,
    // Replay timings — fast enough to keep the demo moving (~30s end-to-end)
    // but slow enough that each stage is visibly distinct on the run timeline.
    timing: {
      ingest: 800,
      assessor: 5000, // longest stage in real life — keep proportional
      resolver_open: 200,
      // resolver gate handled by user clicks; not auto-advanced
      architect: 3500,
      test_plan: 2200,
      codegen: 4500,
      review_scan: 800,
      deliver: 1200,
    },
    cards: VITALS_CARDS as unknown as AmbiguityCard[],
    decisions: VITALS_DECISIONS,
    ledger: VITALS_LEDGER,
    architecture: VITALS_ARCHITECTURE_MD,
    test_plan: VITALS_TEST_PLAN_MD,
    code: VITALS_CODE_PY,
    decisions_md: VITALS_DECISIONS_MD,
    summary: VITALS_SUMMARY as unknown as Record<string, unknown>,
    team_id: "cardiology",
  },
];

export function getScenario(id: string): DemoScenario | undefined {
  return DEMO_SCENARIOS.find((s) => s.id === id);
}

/* ───────────────────────── run store (localStorage) ───────────────────────── */

interface StoredDemoRun {
  scenario_id: string;
  run_id: string;
  team_id: string;
  status: RunState["status"];
  current_stage: RunState["current_stage"];
  events: StageEvent[];
  created_at: string;
  updated_at: string;
  cost_usd: number;
  decisions_count: number;
}

function loadStore(): Record<string, StoredDemoRun> {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

function saveStore(store: Record<string, StoredDemoRun>) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
    // Notify same-tab listeners (storage event only fires cross-tab).
    window.dispatchEvent(new CustomEvent("demo-runs-changed"));
  } catch {
    /* quota exceeded — ignore */
  }
}

export function listDemoRuns(): RunState[] {
  const store = loadStore();
  return Object.values(store).map(toRunState);
}

export function getDemoRun(runId: string): RunState | undefined {
  const stored = loadStore()[runId];
  return stored ? toRunState(stored) : undefined;
}

function toRunState(s: StoredDemoRun): RunState {
  return {
    run_id: s.run_id,
    team_id: s.team_id,
    mode: "guided",
    status: s.status,
    current_stage: s.current_stage,
    created_at: s.created_at,
    updated_at: s.updated_at,
    events: s.events,
    cost_usd: s.cost_usd,
    decisions_count: s.decisions_count,
  };
}

function patchStore(runId: string, patch: Partial<StoredDemoRun>) {
  const store = loadStore();
  const existing = store[runId];
  if (!existing) return;
  store[runId] = {
    ...existing,
    ...patch,
    updated_at: new Date().toISOString(),
  };
  saveStore(store);
}

export function clearDemoRuns() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(STORAGE_KEY);
  window.dispatchEvent(new CustomEvent("demo-runs-changed"));
}

/* ───────────────────────── replay engine ───────────────────────── */

type Listener = (events: StageEvent[]) => void;
const subscribers: Map<string, Set<Listener>> = new Map();

function emit(runId: string, events: StageEvent[]) {
  subscribers.get(runId)?.forEach((cb) => cb(events));
}

export function subscribeDemoRun(runId: string, listener: Listener): () => void {
  if (!subscribers.has(runId)) subscribers.set(runId, new Set());
  subscribers.get(runId)!.add(listener);
  // Immediately replay any events already in the store.
  const stored = loadStore()[runId];
  if (stored) listener(stored.events);
  return () => {
    subscribers.get(runId)?.delete(listener);
  };
}

function nowIso(): string {
  return new Date().toISOString();
}

function appendEvent(runId: string, ev: StageEvent) {
  const store = loadStore();
  const stored = store[runId];
  if (!stored) return;
  stored.events = [...stored.events, ev];
  stored.updated_at = nowIso();
  if (ev.stage && ev.status !== "completed") stored.current_stage = ev.stage;
  store[runId] = stored;
  saveStore(store);
  emit(runId, stored.events);
}

/**
 * Start a new demo run. Returns the new run_id; the run accumulates events
 * via setTimeout so the dashboard's existing polling/streaming UI sees a
 * realistic sequence with zero LLM calls.
 */
export function startDemoRun(scenarioId: string): string {
  const scenario = getScenario(scenarioId);
  if (!scenario) throw new Error(`Unknown demo scenario: ${scenarioId}`);

  const runId = `${DEMO_RUN_PREFIX}${scenarioId}-${Date.now()}`;
  const startedAt = nowIso();
  const store = loadStore();
  store[runId] = {
    scenario_id: scenarioId,
    run_id: runId,
    team_id: scenario.team_id,
    status: "running",
    current_stage: "ingest",
    events: [],
    created_at: startedAt,
    updated_at: startedAt,
    cost_usd: 0,
    decisions_count: 0,
  };
  saveStore(store);

  // Schedule the staged-event timeline. We split the resolver gate and
  // post-gate stages: gate opens, then we wait for the user to approve via
  // approveDemoRun(); after approval, we fire architect → deliver.
  const t = scenario.timing;
  let cursor = 0;
  const at = (ms: number) => {
    cursor += ms;
    return cursor;
  };

  setTimeout(() => {
    appendEvent(runId, {
      stage: "ingest",
      status: "started",
      message: `Loading PRD (${scenario.prd.length} chars)`,
      timestamp: nowIso(),
    });
  }, at(0));
  setTimeout(() => {
    appendEvent(runId, {
      stage: "ingest",
      status: "completed",
      message: "PRD normalized into spec-package",
      timestamp: nowIso(),
      payload: { chars: scenario.prd.length },
    });
  }, at(t.ingest ?? 800));
  setTimeout(() => {
    appendEvent(runId, {
      stage: "assessor",
      status: "started",
      message: "Scanning spec for ambiguity",
      timestamp: nowIso(),
    });
  }, at(200));
  setTimeout(() => {
    const gating = scenario.cards.filter((c) => (c as { is_gating?: boolean }).is_gating);
    appendEvent(runId, {
      stage: "assessor",
      status: "completed",
      message: `${scenario.cards.length} cards (${gating.length} gating, ${
        scenario.cards.length - gating.length
      } auto-deferred)`,
      timestamp: nowIso(),
      payload: { card_count: scenario.cards.length },
    });
    appendEvent(runId, {
      stage: "assessor",
      status: "awaiting_gate",
      message: "Resolver gate open — awaiting human decisions",
      timestamp: nowIso(),
      payload: { gating: gating as unknown as Record<string, unknown>[] },
    });
    patchStore(runId, { status: "awaiting_gate", current_stage: "assessor" });
  }, at(t.assessor ?? 5000));
  // The architect/deliver chain is triggered by approveDemoRun() below.
  return runId;
}

/**
 * Resolve the demo run's gate (auto-accept all recommended options) and
 * fire the post-resolver stages. Called by the demo "Approve all" button.
 */
export function approveDemoRun(runId: string) {
  const store = loadStore();
  const stored = store[runId];
  if (!stored || stored.status !== "awaiting_gate") return;
  const scenario = getScenario(stored.scenario_id);
  if (!scenario) return;

  const t = scenario.timing;
  let cursor = 0;
  const at = (ms: number) => {
    cursor += ms;
    return cursor;
  };

  patchStore(runId, {
    status: "running",
    current_stage: "architect",
    decisions_count: scenario.decisions.length,
  });

  setTimeout(() => {
    appendEvent(runId, {
      stage: "architect",
      status: "started",
      message: "Drafting architecture",
      timestamp: nowIso(),
    });
  }, at(0));
  setTimeout(() => {
    appendEvent(runId, {
      stage: "architect",
      status: "completed",
      message: "Architecture drafted",
      timestamp: nowIso(),
      payload: { architecture: scenario.architecture },
    });
  }, at(t.architect ?? 3500));
  setTimeout(() => {
    appendEvent(runId, {
      stage: "test_plan",
      status: "started",
      message: "Writing test plan from decisions",
      timestamp: nowIso(),
    });
  }, at(200));
  setTimeout(() => {
    appendEvent(runId, {
      stage: "test_plan",
      status: "completed",
      message: "Test plan ready",
      timestamp: nowIso(),
      payload: { test_plan: scenario.test_plan },
    });
  }, at(t.test_plan ?? 2200));
  setTimeout(() => {
    appendEvent(runId, {
      stage: "codegen",
      status: "started",
      message: "Generating code",
      timestamp: nowIso(),
    });
  }, at(200));
  setTimeout(() => {
    appendEvent(runId, {
      stage: "codegen",
      status: "completed",
      message: "Code generated",
      timestamp: nowIso(),
      payload: { code: scenario.code },
    });
  }, at(t.codegen ?? 4500));
  setTimeout(() => {
    appendEvent(runId, {
      stage: "review_scan",
      status: "started",
      message: "Running GHAS/CodeQL/secrets/SBOM",
      timestamp: nowIso(),
    });
  }, at(200));
  setTimeout(() => {
    appendEvent(runId, {
      stage: "review_scan",
      status: "completed",
      message: "Policy gate passed (0 findings)",
      timestamp: nowIso(),
      payload: { findings: 0 },
    });
  }, at(t.review_scan ?? 800));
  setTimeout(() => {
    appendEvent(runId, {
      stage: "deliver",
      status: "started",
      message: "Opening pull request",
      timestamp: nowIso(),
    });
  }, at(200));
  setTimeout(() => {
    appendEvent(runId, {
      stage: "deliver",
      status: "completed",
      message: `PR opened: https://github.com/idanshimon/agentic-sdlc-demo/pull/${
        Math.floor(Math.random() * 900) + 100
      }`,
      timestamp: nowIso(),
      payload: {
        pr_url: `https://github.com/idanshimon/agentic-sdlc-demo/pull/${
          Math.floor(Math.random() * 900) + 100
        }`,
      },
    });
    patchStore(runId, {
      status: "completed",
      current_stage: null,
      cost_usd: (scenario.summary as { total_cost_usd?: number }).total_cost_usd ?? 0.21,
    });
  }, at(t.deliver ?? 1200));
}
