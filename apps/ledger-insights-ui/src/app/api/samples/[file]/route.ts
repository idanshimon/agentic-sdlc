/**
 * /api/samples/[file]/route.ts
 *
 * Direct read of sample PRDs from disk. We had been serving these as static
 * files from public/samples/ — that worked for two of the four samples and
 * 500'd on the other two with no useful error in the Next.js standalone
 * runtime. Same bytes, same encoding, no middleware, no shadowing route.
 * Could not root-cause; the time-to-fix on a route handler is shorter than
 * the time-to-debug Next's static-file machinery.
 *
 * This handler reads the file directly with fs.readFile. Same files, just
 * served through a route instead of through Next's static-cache pipeline.
 * Allowlisted filenames only — no path traversal allowed.
 */
import { NextRequest, NextResponse } from "next/server";
import { readFile } from "fs/promises";
import path from "path";

export const runtime = "nodejs";

// Allowlist — synced with src/app/runs/new/page.tsx SAMPLES.
// Anything not on this list returns 404 (defense against path traversal).
const ALLOWED = new Set([
  "eligibility-check.md",
  "patient-vitals-streaming.md",
  "lab-notifications.md",
  "pci-clean.md",
]);

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ file: string }> },
) {
  const { file } = await params;
  if (!ALLOWED.has(file)) {
    return new NextResponse("Not Found", { status: 404 });
  }
  try {
    // Next.js standalone runs from /app; samples ship at /app/public/samples.
    const abs = path.join(process.cwd(), "public", "samples", file);
    const buf = await readFile(abs);
    return new NextResponse(buf, {
      status: 200,
      headers: {
        "content-type": "text/markdown; charset=utf-8",
        "cache-control": "private, max-age=300",
      },
    });
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return NextResponse.json(
      { error: `sample read failed: ${msg}` },
      { status: 500 },
    );
  }
}
