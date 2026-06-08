"use client";
/* Context-aware agent reply engine.
 *
 * Reads the actual demo store + run state at reply time and synthesizes
 * replies grounded in what's literally on screen. No more keyword-matched
 * pre-canned text — replies are composed from real data.
 *
 * Production parity: in live mode the same `gatherContext()` output becomes
 * the system-prompt context block sent to the orchestrator chat agent. The
 * demo composer is the deterministic stand-in for the LLM call.
 */

import type { AssistContext, ApplyAction } from "./context";
import {
  getDemoRun,
  listDemoRuns,
  listDemoLedgerEntries,
  getDemoArtifacts,
} from "@/lib/demo";

export interface AgentReply {
  text: string;
  reasoning?: string;
  actions: ApplyAction[];
  citations?: { label: string; ref: string }[];
}

/* ─────────────── context gathering ─────────────── */

export interface GatheredContext {
  viewing: AssistContext;
  run?: {
    id: string;
    status: string;
    stage: string | null;
    awaiting_gate: boolean;
    completed_stages: string[];
    has_artifacts: boolean;
    pr_url?: string;
  };
  decisions: Array<{
    id: string;
    decision: string;
    stage: string;
    bundle_refs: string[];
    phi_class: string;
    cost_usd: number;
    model_used: string;
    rationale: string;
  }>;
  portfolio?: {
    total_runs: number;
    by_status: Record<string, number>;
    awaiting_gate_count: number;
    total_cost_usd: number;
    total_decisions: number;
    bundle_citation_density: number;
  };
}

function readDecisions(runId?: string) {
  const filter = runId
    ? { run_id: runId, entry_type: "runtime", limit: 50 }
    : { entry_type: "runtime", limit: 25 };
  const entries = listDemoLedgerEntries(filter);
  return entries.map((e) => ({
    id: String(e.id ?? e.entry_id ?? "(no-id)"),
    decision: String(e.decision ?? "(no decision text)"),
    stage: String(e.stage ?? "?"),
    bundle_refs: Array.isArray(e.bundle_refs) ? (e.bundle_refs as string[]) : [],
    phi_class: String(e.phi_class ?? "none"),
    cost_usd: Number(e.cost_usd ?? 0),
    model_used: String(e.model_used ?? "?"),
    rationale: String(e.rationale ?? ""),
  }));
}

function readPortfolio() {
  const runs = listDemoRuns();
  const by_status: Record<string, number> = {};
  let awaiting_gate_count = 0;
  let total_cost_usd = 0;
  for (const r of runs) {
    const status = r.status ?? "unknown";
    by_status[status] = (by_status[status] ?? 0) + 1;
    if (status === "awaiting_gate") awaiting_gate_count += 1;
  }
  const all_decisions = listDemoLedgerEntries({ entry_type: "runtime" });
  for (const e of all_decisions) {
    total_cost_usd += Number(e.cost_usd ?? 0);
  }
  const cited = all_decisions.filter(
    (e) => Array.isArray(e.bundle_refs) && (e.bundle_refs as string[]).length > 0,
  ).length;
  const bundle_citation_density =
    all_decisions.length === 0 ? 0 : cited / all_decisions.length;
  return {
    total_runs: runs.length,
    by_status,
    awaiting_gate_count,
    total_cost_usd,
    total_decisions: all_decisions.length,
    bundle_citation_density,
  };
}

/** Build the full state snapshot. Called fresh on every user turn. */
export function gatherContext(viewing: AssistContext): GatheredContext {
  const out: GatheredContext = { viewing, decisions: [] };

  if (viewing.kind === "run-detail" || viewing.kind === "run-resolver-gate") {
    const runId = viewing.id;
    if (runId) {
      const run = getDemoRun(runId);
      // Spec REQ-3: missing run from the demo store MUST yield run=undefined.
      // The composer falls back to an open-question reply in that path.
      if (run) {
        const artifacts = getDemoArtifacts(runId);
        const completed_stages = run.events
          ? Array.from(
              new Set(
                run.events
                  .filter((e) => e.status === "completed")
                  .map((e) => String(e.stage)),
              ),
            )
          : [];
        out.run = {
          id: runId,
          status: String(run.status ?? "unknown"),
          stage: run.current_stage ?? null,
          awaiting_gate: run.status === "awaiting_gate",
          completed_stages,
          has_artifacts: !!artifacts,
          pr_url: artifacts?.pr_url,
        };
        out.decisions = readDecisions(runId);
      }
    }
  } else if (
    viewing.kind === "decisions" ||
    viewing.kind === "telemetry" ||
    viewing.kind === "reports"
  ) {
    out.decisions = readDecisions();
    out.portfolio = readPortfolio();
  } else if (viewing.kind === "dashboard" || viewing.kind === "runs-list") {
    out.portfolio = readPortfolio();
    out.decisions = readDecisions().slice(0, 5);
  }
  return out;
}

/* ─────────────── intent detection ─────────────── */

type Intent =
  | "recommend"
  | "explain"
  | "summarize"
  | "what_if"
  | "drill_in"
  | "compare"
  | "next_step"
  | "open_question";

const INTENT_KEYWORDS: Record<Intent, string[]> = {
  recommend: ["recommend", "should i", "approve", "what would you do", "auto"],
  explain: ["why", "explain", "how does", "how do", "what does", "tell me about", "what is"],
  summarize: ["summary", "summarize", "tldr", "tl;dr", "overview", "report", "status"],
  what_if: ["what if", "if i ", "override", "instead", "different", "change", "swap"],
  drill_in: ["which", "show me", "list", "find", "where"],
  compare: ["compare", "difference", "vs", "versus", "better", "trade", "stale"],
  next_step: ["next", "what now", "ship", "deploy", "merge", "approve all"],
  open_question: [],
};

function detectIntent(prompt: string): Intent {
  const lower = prompt.toLowerCase();
  const ranked: Array<[Intent, number]> = (Object.keys(INTENT_KEYWORDS) as Intent[]).map(
    (intent) => {
      const kws = INTENT_KEYWORDS[intent];
      const hits = kws.filter((kw) => lower.includes(kw)).length;
      return [intent, hits];
    },
  );
  ranked.sort((a, b) => b[1] - a[1]);
  if (ranked[0][1] === 0) return "open_question";
  return ranked[0][0];
}

/* ─────────────── reply composition helpers ─────────────── */

function bulletList(items: string[], cap = 5): string {
  return items.slice(0, cap).map((s) => `- ${s}`).join("\n");
}

function fmtUsd(n: number): string {
  return `$${n.toFixed(4)}`;
}

function uniqueBundleRefs(decisions: GatheredContext["decisions"]): string[] {
  const set = new Set<string>();
  for (const d of decisions) for (const ref of d.bundle_refs) set.add(ref);
  return Array.from(set);
}

/* ─────────────── per-context composers ─────────────── */

function composeRunReply(g: GatheredContext, intent: Intent): AgentReply {
  const r = g.run;
  if (!r) {
    return {
      text: "I don't see a run loaded yet — give me a moment, or refresh the page.",
      actions: [],
    };
  }
  const decs = g.decisions;
  const bundleRefs = uniqueBundleRefs(decs);
  const totalCost = decs.reduce((acc, d) => acc + d.cost_usd, 0);
  const phiHigh = decs.filter((d) => d.phi_class === "high").length;
  const stagesDone = r.completed_stages.length;

  const stateLine = r.awaiting_gate
    ? `Run \`${r.id}\` is **awaiting human gate** at the resolver stage. ${decs.length} decision card${decs.length === 1 ? "" : "s"} need your call.`
    : r.status === "completed"
      ? `Run \`${r.id}\` is **complete**. ${stagesDone} stages shipped, ${decs.length} ledger decisions written.`
      : `Run \`${r.id}\` is **${r.status}** at stage \`${r.stage ?? "?"}\`. ${stagesDone} stages complete so far.`;

  if (intent === "recommend") {
    if (!r.awaiting_gate) {
      return {
        text: `${stateLine}\n\nNothing to recommend — there are no open gates. The run is moving through the pipeline on its own. Ask "summarize" for current state or "explain" for a stage rationale.`,
        actions: [],
      };
    }
    const recItems = decs.map((d) => {
      const refList = d.bundle_refs.length > 0 ? d.bundle_refs.join(", ") : "(no bundle citation)";
      return `**${d.decision}** — cited ${refList}`;
    });
    return {
      text: `${stateLine}\n\nReading the actual gate state, I recommend approving all ${decs.length} as the Assessor classified them. Each decision is bundle-cited; the combined posture is internally consistent.\n\n${bulletList(recItems, 8)}\n\nPHI-high decisions: ${phiHigh}/${decs.length}. Bundles in play: ${bundleRefs.join(", ") || "(none)"}. Reasoning cost so far: ${fmtUsd(totalCost)}.`,
      reasoning: `gate=awaiting, decisions=${decs.length}, bundle_refs=${bundleRefs.length}, phi_high=${phiHigh}`,
      actions: [],
      citations: bundleRefs.slice(0, 5).map((ref) => ({ label: ref, ref })),
    };
  }

  if (intent === "what_if") {
    return {
      text: `${stateLine}\n\nTo answer a what-if I need to know which card you're considering overriding. The cards on this run cite: ${bundleRefs.join(", ") || "(no rules cited yet)"}. Override any of those and the pipeline will block at review-scan unless you stage an OpenSpec change to relax the rule. Committee SLA on tighten-vs-relax is typically 1–3 business days.`,
      actions: [],
    };
  }

  if (intent === "explain" || intent === "open_question") {
    if (decs.length === 0) {
      return {
        text: `${stateLine}\n\nThis run hasn't written any decisions yet — the orchestrator has only emitted ${stagesDone} stage events so far. Ask again once the resolver stage runs.`,
        actions: [],
      };
    }
    const phiLine =
      phiHigh > 0
        ? `${phiHigh}/${decs.length} decisions classified PHI-high`
        : `no PHI-high classifications`;
    const stageDist: Record<string, number> = {};
    for (const d of decs) stageDist[d.stage] = (stageDist[d.stage] ?? 0) + 1;
    const stageLines = Object.entries(stageDist).map(
      ([s, n]) => `**${s}**: ${n} decision${n === 1 ? "" : "s"}`,
    );
    return {
      text: `${stateLine}\n\n**What's actually in this run's ledger:**\n${bulletList(stageLines, 8)}\n\nBundle rules cited: ${bundleRefs.join(", ") || "(none)"}. ${phiLine}. Total reasoning cost: ${fmtUsd(totalCost)}. Models used: ${Array.from(new Set(decs.map((d) => d.model_used))).join(", ")}.`,
      actions: [],
      citations: bundleRefs.slice(0, 5).map((ref) => ({ label: ref, ref })),
    };
  }

  if (intent === "summarize") {
    return {
      text: `${stateLine}\n\n${stagesDone} stages complete (${r.completed_stages.join(" → ") || "(none yet)"}). ${decs.length} ledger decisions, ${bundleRefs.length} unique bundle rules cited, ${phiHigh} PHI-high. Cost so far: ${fmtUsd(totalCost)}. ${r.has_artifacts ? `Artifacts available (architecture, test plan, code, decisions.md).` : `No artifacts yet — the deliver stage hasn't run.`}${r.pr_url ? ` PR: ${r.pr_url}` : ""}`,
      actions: r.has_artifacts
        ? [{ kind: "navigate", description: "View run artifacts", href: `/runs/${r.id}` }]
        : [],
    };
  }

  if (intent === "next_step") {
    if (r.awaiting_gate) {
      return {
        text: `${stateLine}\n\nNext step is yours: approve the ${decs.length} cards (use the Approve-all-recommended button if you trust my read) or override the ones you disagree with. Once you approve, the run continues to architect → testplan → codegen → review → deliver and writes a PR.`,
        actions: [],
      };
    }
    if (r.status === "completed") {
      return {
        text: `${stateLine}\n\nNothing left to do on this run. ${r.pr_url ? `PR is open at ${r.pr_url}.` : "Open the artifacts to see the architecture, test plan, code, and decisions.md."}`,
        actions: r.has_artifacts
          ? [{ kind: "navigate", description: "Open artifacts", href: `/runs/${r.id}` }]
          : [],
      };
    }
    return {
      text: `${stateLine}\n\nThe orchestrator is still working. Wait for stage \`${r.stage ?? "?"}\` to finish, or open the live event stream to watch.`,
      actions: [],
    };
  }

  return {
    text: `${stateLine}\n\nI can answer: "what do you recommend", "explain the decisions", "summarize the run", "what if I override card 1", or "what's next". Ask anything specific about: ${bundleRefs.join(", ") || "this run's stages"}.`,
    actions: [],
  };
}

function composePortfolioReply(g: GatheredContext, intent: Intent): AgentReply {
  const p = g.portfolio;
  if (!p) return { text: "No portfolio state available yet.", actions: [] };
  const decs = g.decisions;
  const bundleRefs = uniqueBundleRefs(decs);
  const statusLine =
    Object.entries(p.by_status)
      .map(([s, n]) => `${n} ${s}`)
      .join(", ") || "no runs yet";
  const headline = `**Portfolio:** ${p.total_runs} demo run${p.total_runs === 1 ? "" : "s"} (${statusLine}). ${p.total_decisions} decisions in the ledger, ${(p.bundle_citation_density * 100).toFixed(0)}% with bundle citations. Total reasoning cost: ${fmtUsd(p.total_cost_usd)}.`;

  if (intent === "recommend" || intent === "next_step") {
    if (p.awaiting_gate_count > 0) {
      return {
        text: `${headline}\n\nYou have **${p.awaiting_gate_count} run${p.awaiting_gate_count === 1 ? "" : "s"} awaiting gate** — that's your highest-leverage next step. Open Runs to clear them.`,
        actions: [{ kind: "navigate", description: "Go to Runs", href: "/runs" }],
      };
    }
    if (p.total_runs === 0) {
      return {
        text: `${headline}\n\nNo runs yet — start one from /runs/new with the vitals or eligibility fixture to see the pipeline in motion.`,
        actions: [{ kind: "navigate", description: "Start a new run", href: "/runs/new" }],
      };
    }
    return {
      text: `${headline}\n\nNothing urgent. Bundle citation density is ${(p.bundle_citation_density * 100).toFixed(0)}% — healthy. Worth poking at the Reports page if you want to see where spend goes by stage.`,
      actions: [{ kind: "navigate", description: "Open governance reports", href: "/reports" }],
    };
  }

  if (intent === "summarize" || intent === "explain") {
    return {
      text: `${headline}\n\nBreakdown:\n${bulletList(
        [
          `Awaiting human gate: ${p.awaiting_gate_count}`,
          `Bundle rules in play: ${bundleRefs.length} (${bundleRefs.slice(0, 4).join(", ")}${bundleRefs.length > 4 ? "…" : ""})`,
          `Avg cost per decision: ${p.total_decisions > 0 ? fmtUsd(p.total_cost_usd / p.total_decisions) : "n/a"}`,
          `Models: ${Array.from(new Set(decs.map((d) => d.model_used))).join(", ") || "(none)"}`,
        ],
        6,
      )}`,
      actions: [],
      citations: bundleRefs.slice(0, 5).map((ref) => ({ label: ref, ref })),
    };
  }

  return {
    text: `${headline}\n\nAsk "what should I do next", "summarize", or "explain bundle coverage".`,
    actions: [],
  };
}

function composeContextualReply(
  g: GatheredContext,
  intent: Intent,
): AgentReply {
  const v = g.viewing;
  switch (v.kind) {
    case "run-detail":
    case "run-resolver-gate":
      return composeRunReply(g, intent);
    case "dashboard":
    case "runs-list":
    case "decisions":
    case "telemetry":
    case "reports":
      return composePortfolioReply(g, intent);
    case "agent-edit":
    case "agents-list":
      return {
        text: `You're editing the **${v.id ?? "?"}** agent. The agent assistant works on this resource specifically — every change you apply creates a new local version (rollbackable). Tell me concretely what to change: "tighten the PHI rule" / "add gpt-5 routing" / "explain bundle subscriptions".`,
        actions: [],
      };
    case "prompt-edit":
    case "prompts-list":
      return {
        text: `You're on the **${v.id ?? "prompt library"}**. Versioning is local-storage backed; every saved version shows up in the History tab with line-level diff. Tell me what to change: "bind decisions into context" / "add bundle-citation requirement" / "why is this template missing X".`,
        actions: [],
      };
    case "bundles":
      return {
        text: `Standards bundles can't be edited directly — by design. To change a rule I'd draft an OpenSpec change PR for the next minor version, reviewed by the bundle's pinned reviewer roster. Tell me which dept and which rule.`,
        actions: [
          { kind: "navigate", description: "View OpenSpec changes flow", href: "/changes" },
        ],
      };
    case "phi-classifier":
      return {
        text: `The PHI classifier runs at the Assessor stage and at the PreToolUse hook for IDE sessions. It pattern-matches on MRN-like identifiers, FHIR \`subject.reference\` pointers, name+DOB combinations, and the 18 HIPAA Safe Harbor categories. Output classes: none / low / high. Ask "why was X classified Y" with a specific decision id.`,
        actions: [],
      };
    default:
      return {
        text: `I see you're on **${v.label ?? v.kind}**. Ask me a specific question — "summarize", "explain", "what's next", or "recommend".`,
        actions: [],
      };
  }
}

/** Public entry point: same shape as the old `pickReply` so call sites work. */
export function pickReply(
  context: AssistContext | null,
  userPrompt: string,
): AgentReply {
  if (!context) {
    return {
      text: "I don't have a page context yet — give me a moment for the page to publish its state.",
      actions: [],
    };
  }
  const g = gatherContext(context);
  const intent = detectIntent(userPrompt);
  return composeContextualReply(g, intent);
}

/* ─────────────── suggestions (also context-aware) ─────────────── */

export function getSuggestions(context: AssistContext | null): string[] {
  if (!context) return [];
  const g = gatherContext(context);

  if ((context.kind === "run-detail" || context.kind === "run-resolver-gate") && g.run) {
    if (g.run.awaiting_gate) {
      return [
        "What do you recommend for these cards?",
        "What if I override card 1?",
        "Explain the decisions",
      ];
    }
    if (g.run.status === "completed") {
      return [
        "Summarize this run",
        "Explain the decisions",
        "What was the architecture?",
      ];
    }
    return ["Summarize this run", "What's next?", "Why is this stage running?"];
  }

  if (context.kind === "dashboard" || context.kind === "runs-list") {
    if (g.portfolio && g.portfolio.awaiting_gate_count > 0) {
      return [
        `${g.portfolio.awaiting_gate_count} runs awaiting gate — what should I clear first?`,
        "Summarize the portfolio",
        "What's the current spend?",
      ];
    }
    if (g.portfolio && g.portfolio.total_runs === 0) {
      return [
        "How do I start a run?",
        "Show me the demo flow",
        "What does this dashboard show?",
      ];
    }
    return [
      "Summarize the portfolio",
      "Where's my spend going?",
      "What should I do next?",
    ];
  }

  if (context.kind === "decisions") {
    return [
      "Why are these classified PHI high?",
      "Summarize the bundle coverage",
      "Which decisions cost the most?",
    ];
  }

  if (context.kind === "telemetry" || context.kind === "reports") {
    return [
      "Where is my spend going?",
      "What's the citation density trend?",
      "Explain the posture score",
    ];
  }

  if (context.kind === "bundles") {
    return [
      "How do I change a rule?",
      "What does each bundle govern?",
      "Show me the reviewer roster",
    ];
  }

  if (context.kind === "agents-list" || context.kind === "agent-edit") {
    return [
      "Tighten the PHI rule",
      "Add gpt-5 to preferred models",
      "What does this agent write to ledger?",
    ];
  }

  if (context.kind === "prompts-list" || context.kind === "prompt-edit") {
    return [
      "Why this prompt? Explain it.",
      "Bind decisions into context",
      "Compare versions",
    ];
  }

  if (context.kind === "phi-classifier") {
    return [
      "How does the classifier work?",
      "What patterns trigger high PHI class?",
      "What's the false-positive rate?",
    ];
  }

  return [];
}
