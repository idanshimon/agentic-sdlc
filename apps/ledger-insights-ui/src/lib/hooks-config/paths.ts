import { existsSync } from "node:fs";
import path from "node:path";

/**
 * Resolve the directory containing .github/hooks/ (the canonical hook JSON
 * definitions the Copilot runtime loads).
 *
 * Resolution order:
 *   1. HOOKS_DIR env var (escape hatch — must contain hook *.json files)
 *   2. Production (Container App): /app/.github/hooks/  (cwd is /app)
 *   3. Dev server: ../../.github/hooks/  (cwd is apps/ledger-insights-ui/)
 */
export function resolveHooksDir(): string {
  if (process.env.HOOKS_DIR && existsSync(process.env.HOOKS_DIR)) {
    return process.env.HOOKS_DIR;
  }
  const colocated = path.join(process.cwd(), ".github", "hooks");
  if (existsSync(colocated)) return colocated;
  return path.join(process.cwd(), "..", "..", ".github", "hooks");
}

export const HOOKS_DIR = resolveHooksDir();
