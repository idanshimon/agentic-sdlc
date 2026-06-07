import { existsSync } from "node:fs";
import path from "node:path";

/**
 * Resolve the directory containing openspec/changes/.
 *
 * Resolution order:
 *   1. OPENSPEC_DIR env var (escape hatch — must contain a `changes` subdir)
 *   2. Production (Container App): /app/openspec/  (cwd is /app, COPY'd by Dockerfile)
 *   3. Dev server: ../../openspec/  (cwd is apps/ledger-insights-ui/)
 *
 * Spec ref:
 * openspec/changes/add-ledger-insights-ui-deploy/specs/ledger-insights-ui-deploy/spec.md REQ-2
 */
export function resolveOpenspecRoot(): string {
  if (
    process.env.OPENSPEC_DIR &&
    existsSync(path.join(process.env.OPENSPEC_DIR, "changes"))
  ) {
    return process.env.OPENSPEC_DIR;
  }
  const colocated = path.join(process.cwd(), "openspec");
  if (existsSync(path.join(colocated, "changes"))) {
    return colocated;
  }
  return path.join(process.cwd(), "..", "..", "openspec");
}

export const OPENSPEC_ROOT = resolveOpenspecRoot();
export const CHANGES_DIR = path.join(OPENSPEC_ROOT, "changes");
