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
/** Hard cap on number of demo runs kept in localStorage. Older runs are LRU-
 * evicted on save. Each run can hold ~30 KB of events + ledger entries +
 * payloads, so an uncapped store can quickly grow to multi-MB and trigger
 * O(N) JSON.parse on every gatherContext() call — eventually OOMing the
 * renderer. 10 is plenty for a demo and well under the 5MB localStorage cap. */
const MAX_DEMO_RUNS = 10;

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
  /** Ledger entries written for this run (post-resolver-gate). */
  ledger_entries: Record<string, unknown>[];
}

/* Memoized loadStore: parses localStorage once per raw-string identity.
 *
 * Background: gatherContext() (called from every page's getSuggestions on
 * every render) calls listDemoRuns() + listDemoLedgerEntries(), which means
 * 2 full JSON.parse calls per render. Multiply by N pages × M renders per
 * second from React Query refetch + the AssistantPanel context-publish chain
 * + the demo replay engine's setTimeout cascade, and the main thread chokes
 * on parse work. The renderer eventually OOMs and Chrome SIGKILLs the tab.
 *
 * The cache is keyed on the raw localStorage string, so any write (which
 * happens via saveStore) instantly invalidates the cached parse the next
 * time loadStore() reads. SSR-safe: returns fresh on server.
 */
let _cachedRaw: string | null = null;
let _cachedStore: Record<string, StoredDemoRun> = {};

function loadStore(): Record<string, StoredDemoRun> {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      _cachedRaw = null;
      _cachedStore = {};
      return _cachedStore;
    }
    if (raw === _cachedRaw) return _cachedStore;
    _cachedRaw = raw;
    _cachedStore = JSON.parse(raw);
    return _cachedStore;
  } catch {
    _cachedRaw = null;
    _cachedStore = {};
    return _cachedStore;
  }
}

/* LRU-evict to MAX_DEMO_RUNS by updated_at, keeping the most recent. */
function enforceCap(
  store: Record<string, StoredDemoRun>,
): Record<string, StoredDemoRun> {
  const ids = Object.keys(store);
  if (ids.length <= MAX_DEMO_RUNS) return store;
  const sorted = ids.sort((a, b) => {
    const at = store[a].updated_at ?? "";
    const bt = store[b].updated_at ?? "";
    return bt.localeCompare(at); // newest first
  });
  const keep = sorted.slice(0, MAX_DEMO_RUNS);
  const out: Record<string, StoredDemoRun> = {};
  for (const id of keep) out[id] = store[id];
  return out;
}

function saveStore(store: Record<string, StoredDemoRun>) {
  if (typeof window === "undefined") return;
  try {
    const capped = enforceCap(store);
    const raw = JSON.stringify(capped);
    window.localStorage.setItem(STORAGE_KEY, raw);
    // Refresh memoization cache in-process so the next loadStore() call
    // doesn't re-parse what we just serialized.
    _cachedRaw = raw;
    _cachedStore = capped;
  } catch {
    /* quota exceeded — drop oldest half and retry once before giving up. */
    try {
      const ids = Object.keys(store).sort((a, b) => {
        const at = store[a].updated_at ?? "";
        const bt = store[b].updated_at ?? "";
        return bt.localeCompare(at);
      });
      const trimmed: Record<string, StoredDemoRun> = {};
      for (const id of ids.slice(0, Math.max(1, Math.floor(ids.length / 2)))) {
        trimmed[id] = store[id];
      }
      const raw = JSON.stringify(trimmed);
      window.localStorage.setItem(STORAGE_KEY, raw);
      _cachedRaw = raw;
      _cachedStore = trimmed;
    } catch {
      /* still over quota — give up; user can hit Reset demo */
    }
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

/**
 * Return all ledger entries across all demo runs, optionally filtered.
 * Mirrors the shape of the live `ledgerMcp.query()` response.
 */
export function listDemoLedgerEntries(filter?: {
  team_id?: string;
  run_id?: string;
  entry_type?: string;
  limit?: number;
}): Record<string, unknown>[] {
  const store = loadStore();
  let all: Record<string, unknown>[] = [];
  for (const r of Object.values(store)) {
    all = all.concat(r.ledger_entries ?? []);
  }
  if (filter?.team_id) {
    all = all.filter((e) => e.team_id === filter.team_id);
  }
  if (filter?.run_id) {
    all = all.filter((e) => e.run_id === filter.run_id);
  }
  if (filter?.entry_type) {
    all = all.filter((e) => e.entry_type === filter.entry_type);
  }
  // Newest first.
  all.sort((a, b) => {
    const at = String(a.created_at ?? "");
    const bt = String(b.created_at ?? "");
    return bt.localeCompare(at);
  });
  if (filter?.limit) all = all.slice(0, filter.limit);
  return all;
}

/**
 * Return the artifact bundle (architecture / test_plan / code / decisions_md)
 * for a specific demo run, sourced from its scenario fixture.
 * Returns null if the run is not a demo run, the scenario is unknown, or
 * the run hasn't yet hit the post-resolver stages.
 */
export interface DemoArtifacts {
  architecture: string;
  test_plan: string;
  code: string;
  decisions_md: string;
  summary: Record<string, unknown>;
  pr_url?: string;
}

export function getDemoArtifacts(runId: string): DemoArtifacts | null {
  const stored = loadStore()[runId];
  if (!stored) return null;
  const scenario = getScenario(stored.scenario_id);
  if (!scenario) return null;

  // Only expose artifacts once the relevant stage has completed.
  const has = (stage: string) =>
    stored.events.some(
      (e) => e.stage === stage && e.status === "completed",
    );

  // Find PR url from deliver event payload.
  const deliverDone = stored.events.find(
    (e) => e.stage === "deliver" && e.status === "completed",
  );
  const prUrl =
    (deliverDone?.payload as { pr_url?: string } | undefined)?.pr_url ??
    undefined;

  return {
    architecture: has("architect") ? scenario.architecture : "",
    test_plan: has("test_plan") ? scenario.test_plan : "",
    code: has("codegen") ? scenario.code : "",
    decisions_md: has("deliver") ? scenario.decisions_md : "",
    summary: scenario.summary,
    pr_url: prUrl,
  };
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
  // Wipe the in-process cache too so any subsequent loadStore() call sees
  // the empty state immediately rather than serving stale data.
  _cachedRaw = null;
  _cachedStore = {};
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
    ledger_entries: [],
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
    ledger_entries: scenario.ledger.map((e) => ({
      ...e,
      run_id: runId,
      team_id: scenario.team_id,
      created_at: nowIso(),
    })),
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
