/* Live source adapters for the assistant grounding engine.
 *
 * Each adapter is bounded (timeout + cache) and read-only. GitHub uses the
 * public REST API; a token (GITHUB_TOKEN, server-side only) is optional and
 * just raises the rate limit. Nothing here ever reaches the browser except
 * the grounding record the route chooses to return.
 */
import { readFile, readdir } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
import { callLedgerMcp } from "@/lib/server/mcp-proxy";
import { CHANGES_DIR, OPENSPEC_ROOT } from "@/lib/openspec/paths";
import type { ChangeDoc, ContextSources, GithubItem, RawLedgerEntry, RawRun, RuleDoc } from "@/lib/server/assist-context";

const env = process.env;
const TTL_MS = 60_000;
const cache = new Map<string, { at: number; value: unknown }>();

async function cached<T>(key: string, fn: () => Promise<T>): Promise<T> {
  const hit = cache.get(key);
  if (hit && Date.now() - hit.at < TTL_MS) return hit.value as T;
  const value = await fn();
  cache.set(key, { at: Date.now(), value });
  return value;
}

async function fetchJson(url: string, init: RequestInit = {}, timeoutMs = 8000): Promise<unknown> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(url, { ...init, signal: ctrl.signal, cache: "no-store" });
    if (!res.ok) throw new Error(`${new URL(url).host} ${res.status}`);
    return await res.json();
  } catch (e) {
    if (e instanceof Error && e.name === "AbortError") throw new Error(`${new URL(url).host} timed out`);
    throw e;
  } finally {
    clearTimeout(t);
  }
}

function orchestratorUrl() {
  return (
    env.ORCHESTRATOR_URL ??
    env.NEXT_PUBLIC_ORCHESTRATOR_URL ??
    "https://ca-orchestrator-vnet.thankfulflower-0a94d0d3.eastus2.azurecontainerapps.io"
  );
}

export function githubRepo(): string {
  return env.ASSIST_GITHUB_REPO ?? "idanshimon/agentic-sdlc";
}

/** Bundles live next to openspec/ (repo root in dev, /app in the container). */
function bundlesRoot(): string {
  const sibling = path.join(path.dirname(OPENSPEC_ROOT), "standards-bundles");
  return existsSync(sibling) ? sibling : path.join(process.cwd(), "standards-bundles");
}

/** Minimal extraction of `- id:` / `title:` / `description:` from rules.yaml.
 *  The text is only used for keyword retrieval + a short excerpt. */
export function parseRules(yaml: string, dept: string, version: string): RuleDoc[] {
  const out: RuleDoc[] = [];
  const blocks = yaml.split(/\n\s{2}- id:\s*/).slice(1);
  for (const b of blocks) {
    const id = b.split("\n")[0].trim();
    const title = b.match(/\n\s+title:\s*(.+)/)?.[1]?.trim().replace(/^["']|["']$/g, "") ?? id;
    const desc = b.match(/\n\s+(?:description|rationale):\s*[|>]?\s*\n?([\s\S]*?)(?=\n\s{4}\w+:|$)/)?.[1] ?? "";
    out.push({ id, dept, version, title, text: `${title} ${desc.replace(/\s+/g, " ").slice(0, 600)}` });
  }
  return out;
}

export function liveSources(): ContextSources {
  return {
    ledger: () =>
      cached("ledger", async () => {
        const { status, data } = await callLedgerMcp("/tools/ledger.query", { limit: 1000 });
        if (status >= 400) throw new Error(`ledger ${status}`);
        return ((data as { entries?: RawLedgerEntry[] }).entries ?? []) as RawLedgerEntry[];
      }),
    runs: () =>
      cached("runs", async () => {
        const data = (await fetchJson(`${orchestratorUrl()}/api/runs?limit=200`)) as { items?: RawRun[] };
        return data.items ?? [];
      }),
    rules: () =>
      cached("rules", async () => {
        const root = bundlesRoot();
        const pins = await readFile(path.join(root, "PINS.yaml"), "utf-8");
        const defaults = pins.split(/\nteams:/)[0];
        const pinned = [...defaults.matchAll(/^\s{2}(\w+):\s*(v[\d.]+)/gm)].map((m) => [m[1], m[2]] as const);
        const all: RuleDoc[] = [];
        for (const [dept, ver] of pinned) {
          const f = path.join(root, dept, ver, "rules.yaml");
          if (existsSync(f)) all.push(...parseRules(await readFile(f, "utf-8"), dept, ver));
        }
        return all;
      }),
    changes: () =>
      cached("changes", async () => {
        const ids = (await readdir(CHANGES_DIR, { withFileTypes: true }))
          .filter((d) => d.isDirectory() && d.name !== "archive")
          .map((d) => d.name);
        const out: ChangeDoc[] = [];
        for (const id of ids) {
          const p = path.join(CHANGES_DIR, id, "proposal.md");
          if (!existsSync(p)) continue;
          const md = await readFile(p, "utf-8");
          out.push({
            id,
            title: md.match(/^#\s+(.+)$/m)?.[1] ?? id,
            why: md.match(/^##\s+Why\s*\n+([\s\S]*?)(?=\n##\s|$)/m)?.[1]?.trim() ?? "",
          });
        }
        return out;
      }),
    github: () =>
      cached("github", async () => {
        const headers: Record<string, string> = { Accept: "application/vnd.github+json", "User-Agent": "ledger-insights-ui" };
        if (env.GITHUB_TOKEN) headers.Authorization = `Bearer ${env.GITHUB_TOKEN}`;
        const repo = githubRepo();
        const [prs, commits] = await Promise.all([
          fetchJson(`https://api.github.com/repos/${repo}/pulls?state=all&per_page=15&sort=updated&direction=desc`, { headers }),
          fetchJson(`https://api.github.com/repos/${repo}/commits?per_page=10`, { headers }),
        ]);
        const items: GithubItem[] = [];
        for (const p of prs as Array<{ number: number; title: string; state: string; merged_at: string | null; html_url: string; updated_at: string }>) {
          items.push({ kind: "pr", ref: `#${p.number}`, title: p.title, state: p.merged_at ? "merged" : p.state, href: p.html_url, at: p.updated_at });
        }
        for (const c of commits as Array<{ sha: string; html_url: string; commit: { message: string; author?: { date?: string } } }>) {
          items.push({ kind: "commit", ref: c.sha.slice(0, 7), title: c.commit.message.split("\n")[0], href: c.html_url, at: c.commit.author?.date });
        }
        return items.sort((a, b) => (b.at ?? "").localeCompare(a.at ?? ""));
      }),
    isHighPhi: async (text: string) => {
      const { status, data } = await callLedgerMcp("/tools/ledger.classify_phi", { text });
      if (status >= 400) throw new Error(`classifier ${status}`);
      return (data as { phi_class?: string }).phi_class === "high";
    },
  };
}
