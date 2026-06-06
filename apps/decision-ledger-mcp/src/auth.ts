/**
 * Per-team bearer token authentication.
 *
 * Tokens are stored as Container App secrets. The token-to-team mapping is
 * loaded at startup from env: LEDGER_MCP_TOKENS = JSON.stringify({
 *   "<token-1>": "team-cardiology",
 *   "<token-2>": "team-radiology",
 * }).
 *
 * In production, replace with per-call Key Vault lookup or Entra App auth.
 */

let tokenToTeam: Record<string, string> | null = null;

export function loadTokenMap(env: NodeJS.ProcessEnv = process.env): void {
  const raw = env.LEDGER_MCP_TOKENS;
  if (!raw) {
    tokenToTeam = {};
    return;
  }
  try {
    tokenToTeam = JSON.parse(raw);
  } catch (e) {
    throw new Error(`LEDGER_MCP_TOKENS must be valid JSON: ${(e as Error).message}`);
  }
}

export function authenticate(authHeader: string | undefined): string {
  if (tokenToTeam == null) loadTokenMap();
  if (!authHeader || !authHeader.startsWith("Bearer ")) {
    throw new Error("Missing or malformed Authorization header");
  }
  const token = authHeader.slice("Bearer ".length).trim();
  const teamId = (tokenToTeam ?? {})[token];
  if (!teamId) {
    throw new Error("Invalid bearer token");
  }
  return teamId;
}

export function authenticateForTeam(authHeader: string | undefined, requestedTeamId: string): void {
  const authedTeam = authenticate(authHeader);
  if (authedTeam !== requestedTeamId) {
    throw new Error(
      `Token is scoped to team '${authedTeam}'; request targeted team '${requestedTeamId}'`
    );
  }
}
