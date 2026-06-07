import { NextResponse, type NextRequest } from "next/server";
import { readFile, stat, readdir } from "node:fs/promises";
import path from "node:path";
import { CHANGES_DIR } from "@/lib/openspec/paths";

/* GET /api/openspec/changes/[id]
 * Returns the full proposal.md, tasks.md, and any spec deltas for a single
 * OpenSpec change. ID is folder name under openspec/changes/.
 *
 * Path resolution: see src/lib/openspec/paths.ts
 * Spec ref: openspec/changes/add-ledger-insights-ui-deploy/specs/ledger-insights-ui-deploy/spec.md REQ-2
 */

async function exists(p: string): Promise<boolean> {
  try {
    await stat(p);
    return true;
  } catch {
    return false;
  }
}

async function readSpecDeltas(specsDir: string) {
  if (!(await exists(specsDir))) return [];
  const caps = await readdir(specsDir);
  const out: { capability: string; spec_md: string }[] = [];
  for (const cap of caps) {
    const specPath = path.join(specsDir, cap, "spec.md");
    if (await exists(specPath)) {
      out.push({
        capability: cap,
        spec_md: await readFile(specPath, "utf-8"),
      });
    }
  }
  return out;
}

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  // Defensive: refuse path traversal.
  if (id.includes("..") || id.includes("/") || id.includes("\\")) {
    return NextResponse.json({ error: "invalid change id" }, { status: 400 });
  }
  const dir = path.join(CHANGES_DIR, id);
  if (!(await exists(dir))) {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }
  const proposalPath = path.join(dir, "proposal.md");
  const tasksPath = path.join(dir, "tasks.md");
  const proposal = (await exists(proposalPath))
    ? await readFile(proposalPath, "utf-8")
    : "";
  const tasks = (await exists(tasksPath))
    ? await readFile(tasksPath, "utf-8")
    : "";
  const specs = await readSpecDeltas(path.join(dir, "specs"));

  return NextResponse.json({
    id,
    proposal,
    tasks,
    specs,
  });
}
