/* Assistant grounding engine — server-side, Atlas `prepare_context` pattern.
 *
 * Pure assembly over INJECTED sources, so every rule is unit-testable with no
 * network:
 *   - Scope BEFORE top-k: a run-scoped question only ranks that run's ledger.
 *   - Every injected fact carries provenance (kind + ref + optional href).
 *   - Derived facts are labelled "computed from the record" so the model does
 *     not try to "verify" them against raw rows and conclude they are wrong.
 *   - Nothing is fabricated: an unavailable source is an empty section plus a
 *     warning, never invented content.
 *   - PHI guard at the LLM boundary: every excerpt is classified by the
 *     ledger's own classifier; high-PHI excerpts are WITHHELD from the prompt
 *     and counted, citing the rule that requires it.
 *   - Read-only. Nothing here writes to the ledger (AGENTS.md: the in-UI
 *     assistant is a reading layer, not a ledger writer).
 */

export type SourceKind = "view" | "ledger" | "run" | "rule" | "openspec" | "github" | "derived";

export interface GroundingSource {
  kind: SourceKind;
  /** Stable reference: entry id, run id, rule id, PR number, change id. */
  ref: string;
  title: string;
  excerpt: string;
  href?: string;
  /** Why this was selected — retrieval score, scope, or "pinned by view". */
  matched?: string;
}

export interface Grounding {
  view: { kind: string; id?: string; label?: string };
  scope: { run?: string; team?: string };
  sources: GroundingSource[];
  derived: string[];
  withheld: { count: number; rule: string } | null;
  warnings: string[];
  degraded: boolean;
  built_at: string;
}

export interface RawLedgerEntry {
  id: string;
  run_id?: string;
  team_id?: string;
  ambiguity_class?: string | null;
  resolution_text?: string | null;
  decision?: string | null;
  rationale?: string | null;
  confidence_source?: string | null;
  actor_kind?: string | null;
  runtime_kind?: string | null;
  bundle_refs?: string[] | null;
  created_at?: string;
}

export interface RawRun {
  run_id: string;
  team_id?: string;
  status?: string;
  current_stage?: string | null;
  failure_kind?: string | null;
  failure_reason?: string | null;
  blocking_rules?: string[] | null;
  total_cost_usd?: number | null;
  updated_at?: string;
  created_at?: string;
  pending_gate?: { stage?: string } | null;
}

export interface RuleDoc { id: string; dept: string; version: string; title: string; text: string }
export interface ChangeDoc { id: string; title: string; why: string }
export interface GithubItem { kind: "pr" | "commit" | "issue"; ref: string; title: string; state?: string; href: string; at?: string }

export interface ContextSources {
  ledger: () => Promise<RawLedgerEntry[]>;
  runs: () => Promise<RawRun[]>;
  rules: () => Promise<RuleDoc[]>;
  changes: () => Promise<ChangeDoc[]>;
  github: () => Promise<GithubItem[]>;
  /** Returns true when the text is high-PHI per the ledger classifier. */
  isHighPhi: (text: string) => Promise<boolean>;
}

export interface PrepareInput {
  message: string;
  view: { kind: string; id?: string; label?: string; payload?: Record<string, unknown> };
  ground?: boolean;
  limit?: number;
  now?: Date;
}

const PHI_RULE = "security/v0.1.0/PHI-001";
const STOP = new Set(["many", "much", "some", "any", "all", "most", "more", "get", "got", "there", "here", "about", "from", "have", "has", "was", "were", "been", "being", "will", "would", "could", "rule", "rules", "run", "runs", "decision", "decisions", "the", "a", "an", "is", "are", "of", "to", "in", "on", "and", "or", "for", "what", "why", "how", "this", "that", "me", "my", "do", "does", "it", "with", "be", "should", "i", "we", "can", "which", "show"]);

export function tokens(text: string): string[] {
  return (text.toLowerCase().match(/[a-z0-9][a-z0-9_-]{1,}/g) ?? []).filter((t) => !STOP.has(t));
}

/** Simple BM25-ish keyword score: matched distinct terms, weighted by rarity
 *  across the candidate set. Deterministic, explainable, no embeddings. */
export function rank<T>(query: string, items: T[], text: (t: T) => string, limit: number): Array<{ item: T; score: number; terms: string[] }> {
  const q = Array.from(new Set(tokens(query)));
  if (!q.length || !items.length) return [];
  const docs = items.map((it) => new Set(tokens(text(it))));
  const df = new Map(q.map((t) => [t, docs.filter((d) => d.has(t)).length]));
  const scored = items.map((item, i) => {
    const hit = q.filter((t) => docs[i].has(t));
    const score = hit.reduce((s, t) => s + Math.log(1 + items.length / (df.get(t) || 1)), 0);
    return { item, score, terms: hit };
  });
  const ranked = scored.filter((s) => s.score > 0).sort((a, b) => b.score - a.score);
  // Drop weak tail matches: a single-term hit far below the best is noise
  // (e.g. "many" matching a retention rule).
  const best = ranked[0]?.score ?? 0;
  return ranked.filter((s) => s.terms.length > 1 || s.score >= best * 0.6).slice(0, limit);
}

const clip = (s: string | null | undefined, n = 320) => {
  const t = (s ?? "").replace(/\s+/g, " ").trim();
  return t.length > n ? `${t.slice(0, n - 1)}…` : t;
};

function decidedBy(e: RawLedgerEntry): "human" | "agent" {
  if (e.confidence_source === "autopilot") return "agent";
  if (e.confidence_source === "human") return "human";
  return e.actor_kind === "human" ? "human" : "agent";
}

async function safe<T>(label: string, fn: () => Promise<T>, fallback: T, warnings: string[]): Promise<[T, boolean]> {
  try {
    return [await fn(), true];
  } catch (e) {
    warnings.push(`${label} unavailable (${e instanceof Error ? e.message : String(e)}); answered without it.`);
    return [fallback, false];
  }
}

export async function prepareContext(src: ContextSources, input: PrepareInput): Promise<{ prompt: string; grounding: Grounding }> {
  const now = input.now ?? new Date();
  const view = { kind: input.view.kind, id: input.view.id, label: input.view.label };
  const runScope = /^run/.test(input.view.kind) && input.view.id ? input.view.id : undefined;
  const g: Grounding = {
    view, scope: { run: runScope }, sources: [], derived: [], withheld: null,
    warnings: [], degraded: false, built_at: now.toISOString(),
  };
  if (input.ground === false) return { prompt: input.message, grounding: g };

  const limit = Math.max(1, Math.min(10, input.limit ?? 6));
  const w = g.warnings;
  const [[ledger, okL], [runs, okR], [rules, okRu], [changes], [gh, okG]] = await Promise.all([
    safe("Ledger", src.ledger, [] as RawLedgerEntry[], w),
    safe("Runs", src.runs, [] as RawRun[], w),
    safe("Standards bundles", src.rules, [] as RuleDoc[], w),
    safe("OpenSpec changes", src.changes, [] as ChangeDoc[], w),
    safe("GitHub", src.github, [] as GithubItem[], w),
  ]);
  g.degraded = !(okL && okR && okRu && okG);

  // ---- derived facts (computed from the record, not quoted) ----
  const decisions = ledger.filter((e) => !e.runtime_kind || e.runtime_kind === "stage_decision");
  const scoped = runScope ? decisions.filter((e) => e.run_id === runScope) : decisions;
  if (scoped.length) {
    const agent = scoped.filter((e) => decidedBy(e) === "agent").length;
    g.derived.push(`${scoped.length} decisions in scope: ${agent} by agents (${Math.round((agent / scoped.length) * 100)}%), ${scoped.length - agent} by humans.`);
    const byClass = new Map<string, number>();
    scoped.forEach((e) => e.ambiguity_class && byClass.set(e.ambiguity_class, (byClass.get(e.ambiguity_class) ?? 0) + 1));
    const top = [...byClass.entries()].sort((a, b) => b[1] - a[1]).slice(0, 5);
    if (top.length) g.derived.push(`Most frequent ambiguity classes: ${top.map(([k, n]) => `${k} (${n})`).join(", ")}.`);
  }
  if (runs.length) {
    const gate = runs.filter((r) => r.status === "awaiting_gate" || r.status === "paused");
    const failed = runs.filter((r) => r.status === "failed");
    const policy = failed.filter((r) => r.failure_kind === "policy_block").length;
    g.derived.push(`${runs.length} runs loaded: ${gate.length} waiting on a human gate, ${failed.length} failed (${policy} blocked by policy).`);
    const byStage = new Map<string, number>();
    gate.forEach((r) => {
      const s = r.pending_gate?.stage || r.current_stage || "unknown";
      byStage.set(s, (byStage.get(s) ?? 0) + 1);
    });
    if (byStage.size) g.derived.push(`Gates held at: ${[...byStage.entries()].map(([s, n]) => `${s} (${n})`).join(", ")}.`);
    const ruleCount = new Map<string, number>();
    failed.forEach((r) => (r.blocking_rules ?? []).forEach((id) => ruleCount.set(id, (ruleCount.get(id) ?? 0) + 1)));
    if (ruleCount.size) {
      g.derived.push(`Rules cited by failed runs: ${[...ruleCount.entries()].sort((a, b) => b[1] - a[1]).map(([id, n]) => `${id} (${n} run${n === 1 ? "" : "s"})`).join(", ")}.`);
    }
    const reasons = new Map<string, number>();
    failed.forEach((r) => {
      const k = clip(r.failure_reason, 90);
      if (k) reasons.set(k, (reasons.get(k) ?? 0) + 1);
    });
    if (reasons.size) {
      g.derived.push(`Most common failure reasons: ${[...reasons.entries()].sort((a, b) => b[1] - a[1]).slice(0, 3).map(([k, n]) => `"${k}" (${n})`).join("; ")}.`);
    }
  }

  // ---- pinned by view ----
  if (runScope) {
    const run = runs.find((r) => r.run_id === runScope);
    if (run) {
      g.sources.push({
        kind: "run", ref: run.run_id, title: `Run ${run.run_id.slice(0, 8)} — ${run.status}`,
        excerpt: clip(`team ${run.team_id}; stage ${run.pending_gate?.stage || run.current_stage}; ${run.failure_reason ? `failure: ${run.failure_reason}` : ""} ${run.blocking_rules?.length ? `blocking rules: ${run.blocking_rules.join(", ")}` : ""}`),
        href: `/runs/${run.run_id}`, matched: "pinned by view",
      });
    } else {
      w.push(`Run ${runScope} not found in the loaded runs.`);
    }
  }

  // ---- retrieval, scoped BEFORE top-k ----
  const q = `${input.message} ${input.view.label ?? ""}`;
  const ledgerHits = rank(q, scoped, (e) => `${e.ambiguity_class} ${e.resolution_text ?? e.decision} ${e.rationale ?? ""}`, limit);
  const runHits = runScope ? [] : rank(q, runs, (r) => `${r.run_id} ${r.status} ${r.current_stage} ${r.pending_gate?.stage ?? ""} ${r.failure_reason ?? ""} ${(r.blocking_rules ?? []).join(" ")} ${r.team_id}`, 3);
  // Rules: those the hits/runs cite, then any that match the question.
  const cited = new Set<string>([
    ...ledgerHits.flatMap((h) => h.item.bundle_refs ?? []),
    ...runs.flatMap((r) => (runScope ? (r.run_id === runScope ? r.blocking_rules ?? [] : []) : [])),
    // Portfolio views: the rules failed runs actually cite are always relevant.
    ...(runScope ? [] : runs.filter((r) => r.status === "failed").flatMap((r) => r.blocking_rules ?? [])),
  ]);
  const ruleKey = (r: RuleDoc) => `${r.dept}/${r.version}/${r.id}`;
  const citedRules = rules.filter((r) => cited.has(ruleKey(r)));
  const ruleHits = rank(q, rules.filter((r) => !cited.has(ruleKey(r))), (r) => `${r.id} ${r.title} ${r.text}`, 3);
  const changeHits = rank(q, changes, (c) => `${c.id} ${c.title} ${c.why}`, 2);
  const ghHits = rank(q, gh, (i) => `${i.kind} ${i.ref} ${i.title}`, 3);
  // Always give the model the newest repo activity, even with no keyword hit.
  const ghSel = ghHits.length ? ghHits.map((h) => h.item) : gh.slice(0, 3);

  const candidates: GroundingSource[] = [
    ...ledgerHits.map(({ item: e, terms }) => ({
      kind: "ledger" as const, ref: e.id,
      title: `${decidedBy(e) === "agent" ? "Agent" : "Human"} decision · ${e.ambiguity_class ?? "unclassified"}`,
      excerpt: clip(`${e.resolution_text ?? e.decision ?? ""}${e.rationale ? ` — ${e.rationale}` : ""}`),
      href: `/decisions#decision-${e.id}`, matched: `terms: ${terms.join(", ")}`,
    })),
    ...runHits.map(({ item: r, terms }) => ({
      kind: "run" as const, ref: r.run_id, title: `Run ${r.run_id.slice(0, 8)} — ${r.status}`,
      excerpt: clip(`stage ${r.pending_gate?.stage || r.current_stage}; ${r.failure_reason ?? ""}`),
      href: `/runs/${r.run_id}`, matched: `terms: ${terms.join(", ")}`,
    })),
    ...citedRules.map((r) => ({
      kind: "rule" as const, ref: ruleKey(r), title: `[${ruleKey(r)}] ${r.title}`, excerpt: clip(r.text, 260),
      href: `/bundles`, matched: "cited by a selected decision or run",
    })),
    ...ruleHits.map(({ item: r, terms }) => ({
      kind: "rule" as const, ref: ruleKey(r), title: `[${ruleKey(r)}] ${r.title}`, excerpt: clip(r.text, 260),
      href: `/bundles`, matched: `terms: ${terms.join(", ")}`,
    })),
    ...changeHits.map(({ item: c, terms }) => ({
      kind: "openspec" as const, ref: c.id, title: c.title, excerpt: clip(c.why, 260),
      href: `/changes`, matched: `terms: ${terms.join(", ")}`,
    })),
    ...ghSel.map((i) => ({
      kind: "github" as const, ref: i.ref, title: `${i.kind === "pr" ? "PR" : i.kind === "issue" ? "Issue" : "Commit"} ${i.ref} · ${i.title}`,
      excerpt: clip(`${i.state ?? ""} ${i.at ? `· ${i.at.slice(0, 10)}` : ""}`), href: i.href,
      matched: ghHits.length ? "keyword match" : "latest repository activity",
    })),
  ];

  // ---- PHI guard at the LLM boundary ----
  let withheld = 0;
  const phiChecked = await Promise.all(
    candidates.map(async (s) => {
      if (s.kind !== "ledger" && s.kind !== "run") return { s, high: false };
      try {
        return { s, high: await src.isHighPhi(`${s.title} ${s.excerpt}`) };
      } catch {
        // Fail closed: if we cannot classify, we do not forward.
        return { s, high: true };
      }
    }),
  );
  for (const { s, high } of phiChecked) {
    if (high) withheld += 1;
    else g.sources.push(s);
  }
  if (withheld) g.withheld = { count: withheld, rule: PHI_RULE };

  // ---- prompt assembly ----
  const blocks: string[] = [];
  blocks.push(`The operator is on the "${input.view.label ?? input.view.kind}" view${runScope ? ` for run ${runScope}` : ""}.`);
  if (g.derived.length) blocks.push(`Facts computed from the record (exact; do not re-derive):\n${g.derived.map((d) => `- ${d}`).join("\n")}`);
  if (g.sources.length) {
    blocks.push(`Retrieved sources (cite them by [n]):\n${g.sources.map((s, i) => `[${i + 1}] (${s.kind} ${s.ref}) ${s.title}\n    ${s.excerpt}`).join("\n")}`);
  } else {
    blocks.push("No sources matched this question.");
  }
  if (g.withheld) blocks.push(`${g.withheld.count} matching excerpt(s) were withheld by the PHI guard [${g.withheld.rule}]. Say so if they would have mattered.`);
  if (w.length) blocks.push(`Warnings: ${w.join(" ")}`);
  const prompt = `${blocks.join("\n\n")}\n\n---\n\nQuestion: ${input.message}`;
  return { prompt, grounding: g };
}

export const SYSTEM_PROMPT = `You are the read-only operator assistant for a governed agentic SDLC dashboard.
Answer ONLY from the provided context. Cite sources inline as [n]. When a rule is relevant, cite it in the form [dept/version/RULE-ID].
If the context does not contain the answer, say what is missing and which view would show it — never invent runs, decisions, rules, PRs or numbers.
You cannot write to the Decision Ledger, approve gates, or change standards; when an action is needed, tell the operator exactly where to do it.
Be concise: lead with the answer in 1-2 sentences, then at most 5 bullets. Plain language, no marketing tone.`;
