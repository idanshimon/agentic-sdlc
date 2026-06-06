import { readFileSync } from "node:fs";
import { join } from "node:path";
import { parse as parseYaml } from "yaml";
import type { BundleResult } from "./schema.js";

const BUNDLES_ROOT = process.env.STANDARDS_BUNDLES_ROOT ?? "/app/standards-bundles";

export function getBundle(dept: string, version: string): BundleResult {
  const base = join(BUNDLES_ROOT, dept, version);
  const rules = parseYaml(readFileSync(join(base, "rules.yaml"), "utf8")) as {
    metadata: Record<string, unknown>;
    rules: Array<Record<string, unknown>>;
  };
  const envelope = parseYaml(readFileSync(join(base, "envelope.yaml"), "utf8")) as Record<string, unknown>;
  return {
    metadata: rules.metadata,
    rules: rules.rules,
    envelope,
  };
}
