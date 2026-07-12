export interface DecisionQueryState {
  run?: string;
  team?: string;
  stage?: string;
  actor?: string;
  phi?: string;
  kind?: string;
  lineage?: string;
  q?: string;
}

const KEYS = ["run", "team", "stage", "actor", "phi", "kind", "lineage", "q"] as const;

export function parseDecisionQuery(params: URLSearchParams): DecisionQueryState {
  const state: DecisionQueryState = {};
  for (const key of KEYS) {
    const value = params.get(key)?.trim();
    if (value) state[key] = value;
  }
  return state;
}

export function serializeDecisionQuery(state: DecisionQueryState): URLSearchParams {
  const params = new URLSearchParams();
  for (const key of KEYS) {
    const value = state[key]?.trim();
    if (value) params.set(key, value);
  }
  return params;
}
