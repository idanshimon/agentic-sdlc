import type { NextConfig } from "next";
import { execSync } from "node:child_process";
import { readFileSync } from "node:fs";

/* Build identity for the About panel. Resolved ONCE at build time.
 * Order: explicit build arg (container builds have no .git) → local git →
 * "unknown". Never invented. */
function git(cmd: string): string | undefined {
  try {
    return execSync(`git ${cmd}`, { stdio: ["ignore", "pipe", "ignore"] }).toString().trim() || undefined;
  } catch {
    return undefined;
  }
}
const pkg = JSON.parse(readFileSync(new URL("./package.json", import.meta.url), "utf-8")) as { version: string };
const sha = process.env.BUILD_GIT_SHA || git("rev-parse --short HEAD") || "unknown";
const dirty = process.env.BUILD_GIT_SHA ? false : Boolean(git("status --porcelain"));

const nextConfig: NextConfig = {
  output: "standalone",
  experimental: {
    optimizePackageImports: ["lucide-react", "recharts"],
  },
  env: {
    NEXT_PUBLIC_APP_VERSION: pkg.version,
    NEXT_PUBLIC_BUILD_SHA: sha,
    NEXT_PUBLIC_BUILD_DIRTY: dirty ? "1" : "0",
    NEXT_PUBLIC_BUILD_TIME: new Date().toISOString(),
  },
};

export default nextConfig;
