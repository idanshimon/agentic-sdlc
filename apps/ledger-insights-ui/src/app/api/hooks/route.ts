import { NextResponse } from "next/server";
import { readFile, readdir, stat } from "node:fs/promises";
import path from "node:path";
import { HOOKS_DIR } from "@/lib/hooks-config/paths";
import { deriveHookTarget } from "@/lib/hooks-config/target";

/* GET /api/hooks
 * Returns the REAL lifecycle hooks defined on disk under .github/hooks/*.json —
 * not a hardcoded list. Each hook reports the lifecycle event it binds, the
 * downstream service it controls (derived, or from an explicit `controls`
 * field), its timeout + fail-open posture, and whether its scripts exist.
 */

interface HookScript {
  shell: "bash" | "powershell";
  path: string;
  exists: boolean;
}

interface HookMeta {
  file: string;
  name: string;
  description: string;
  events: string[];
  timeout_seconds?: number;
  fail_open?: boolean;
  controls: { service: string; href?: string; mode: string };
  scripts: HookScript[];
}

async function exists(p: string): Promise<boolean> {
  try {
    await stat(p);
    return true;
  } catch {
    return false;
  }
}

/** Resolve a `${GITHUB_REPOSITORY_DIR:-.}/…` script ref to a real repo path so
 *  we can check the script actually exists on disk. */
function resolveScriptPath(raw: string): string {
  // Strip the env-var prefix; the tail is relative to the repo root.
  const tail = raw.replace(/^\$\{GITHUB_REPOSITORY_DIR:-\.\}\/?/, "");
  // HOOKS_DIR is <repo>/.github/hooks; repo root is two levels up.
  const repoRoot = path.join(HOOKS_DIR, "..", "..");
  return path.join(repoRoot, tail);
}

async function readHook(file: string): Promise<HookMeta | null> {
  const full = path.join(HOOKS_DIR, file);
  let raw: string;
  try {
    raw = await readFile(full, "utf-8");
  } catch {
    return null;
  }
  let json: Record<string, unknown>;
  try {
    json = JSON.parse(raw);
  } catch {
    return null;
  }

  const events = Array.isArray(json.events) ? (json.events as string[]) : [];
  const primaryEvent = events[0] ?? "";
  const target = deriveHookTarget(primaryEvent, {
    explicitControls: typeof json.controls === "string" ? json.controls : undefined,
    name: typeof json.name === "string" ? json.name : undefined,
  });

  const scripts: HookScript[] = [];
  for (const shell of ["bash", "powershell"] as const) {
    const ref = json[shell];
    if (typeof ref === "string") {
      const resolved = resolveScriptPath(ref);
      scripts.push({ shell, path: ref, exists: await exists(resolved) });
    }
  }

  return {
    file,
    name: typeof json.name === "string" ? json.name : file.replace(/\.json$/, ""),
    description: typeof json.description === "string" ? json.description : "",
    events,
    timeout_seconds: typeof json.timeout_seconds === "number" ? json.timeout_seconds : undefined,
    fail_open: typeof json.fail_open === "boolean" ? json.fail_open : undefined,
    controls: { service: target.service, href: target.href, mode: target.mode },
    scripts,
  };
}

export async function GET() {
  if (!(await exists(HOOKS_DIR))) {
    return NextResponse.json({ hooks: [], hooks_dir: HOOKS_DIR, note: "hooks dir not found" });
  }
  const files = (await readdir(HOOKS_DIR)).filter((f) => f.endsWith(".json"));
  const hooks = (await Promise.all(files.map(readHook))).filter(
    (h): h is HookMeta => h !== null,
  );
  // Stable order: by first lifecycle event in the natural session sequence.
  const order = ["SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "SessionEnd"];
  hooks.sort((a, b) => {
    const ai = order.indexOf(a.events[0] ?? "");
    const bi = order.indexOf(b.events[0] ?? "");
    return (ai < 0 ? 99 : ai) - (bi < 0 ? 99 : bi);
  });
  return NextResponse.json({ hooks, hooks_dir: HOOKS_DIR });
}
