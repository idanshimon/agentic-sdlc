import { NextResponse } from "next/server";
import { readFile, readdir, stat } from "node:fs/promises";
import path from "node:path";
import { CHANGES_DIR } from "@/lib/openspec/paths";

/* GET /api/openspec/changes
 * Returns the list of OpenSpec change proposals on disk.
 *
 * Each change is a directory under <openspec-root>/openspec/changes/ containing:
 *   - proposal.md   (mandatory; first H1 is the title)
 *   - tasks.md      (optional; counts checkbox lines)
 *   - specs/        (optional; per-capability spec deltas)
 *
 * Path resolution: see src/lib/openspec/paths.ts
 *
 * Spec ref: openspec/changes/add-ledger-insights-ui-deploy/specs/ledger-insights-ui-deploy/spec.md REQ-2
 */

interface ChangeMeta {
  id: string;
  title: string;
  status: "draft" | "in-review" | "merged";
  authors: string[];
  date?: string;
  capabilities_touched: string[];
  why_excerpt: string;
  task_total: number;
  task_done: number;
  spec_count: number;
  proposal_path: string;
}

const STATUS_RX = /^>\s*\*\*Status:\*\*\s*([A-Z][A-Za-z\s\-/]+)/m;
const AUTHORS_RX = /^>\s*\*\*Authors?:\*\*\s*(.+)$/m;
const DATE_RX = /^>\s*\*\*Date:\*\*\s*(\d{4}-\d{2}-\d{2})/m;
const CAPS_RX = /^>\s*\*\*Capabilities touched:\*\*\s*(.+)$/m;
const TITLE_RX = /^#\s+(.+)$/m;
const WHY_RX = /^##\s+Why\s*\n+([\s\S]*?)(?=\n##\s)/m;

function normalizeStatus(raw: string): ChangeMeta["status"] {
  const lower = raw.trim().toLowerCase();
  if (lower.includes("merged") || lower.includes("shipped")) return "merged";
  if (lower.includes("review") || lower.includes("approved")) return "in-review";
  return "draft";
}

async function exists(p: string): Promise<boolean> {
  try {
    await stat(p);
    return true;
  } catch {
    return false;
  }
}

async function readChange(id: string): Promise<ChangeMeta | null> {
  const dir = path.join(CHANGES_DIR, id);
  const proposalPath = path.join(dir, "proposal.md");
  if (!(await exists(proposalPath))) return null;

  const proposal = await readFile(proposalPath, "utf-8");
  const titleMatch = proposal.match(TITLE_RX);
  const statusMatch = proposal.match(STATUS_RX);
  const authorsMatch = proposal.match(AUTHORS_RX);
  const dateMatch = proposal.match(DATE_RX);
  const capsMatch = proposal.match(CAPS_RX);
  const whyMatch = proposal.match(WHY_RX);

  let task_total = 0;
  let task_done = 0;
  const tasksPath = path.join(dir, "tasks.md");
  if (await exists(tasksPath)) {
    const tasks = await readFile(tasksPath, "utf-8");
    const checkboxes = tasks.match(/^\s*-\s+\[([ x])\]/gm) ?? [];
    task_total = checkboxes.length;
    task_done = checkboxes.filter((c) => c.includes("[x]")).length;
  }

  let spec_count = 0;
  const specsDir = path.join(dir, "specs");
  if (await exists(specsDir)) {
    const entries = await readdir(specsDir);
    spec_count = entries.length;
  }

  return {
    id,
    title: titleMatch?.[1]?.trim() ?? id,
    status: normalizeStatus(statusMatch?.[1] ?? "draft"),
    authors: (authorsMatch?.[1] ?? "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean),
    date: dateMatch?.[1],
    capabilities_touched: (capsMatch?.[1] ?? "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean),
    why_excerpt: (whyMatch?.[1] ?? "").trim().slice(0, 380),
    task_total,
    task_done,
    spec_count,
    proposal_path: `openspec/changes/${id}/proposal.md`,
  };
}

export async function GET() {
  if (!(await exists(CHANGES_DIR))) {
    return NextResponse.json({ changes: [] });
  }
  const ids = (await readdir(CHANGES_DIR)).filter(
    (n) => !n.startsWith("."),
  );
  const changes = (
    await Promise.all(ids.map(readChange))
  ).filter((c): c is ChangeMeta => c !== null);
  // Sort: drafts first, then alphabetical
  changes.sort((a, b) => {
    if (a.status !== b.status) return a.status.localeCompare(b.status);
    return a.id.localeCompare(b.id);
  });
  return NextResponse.json({ changes });
}
