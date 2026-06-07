/* Pre-canned agent replies for Demo Mode.
 *
 * Each reply is keyed by `AssistContextKind` and a fuzzy-matched user prompt
 * keyword. Returns narrative text + ApplyAction[] the user can click to apply
 * back to the live state.
 *
 * In production these come from the orchestrator's chat endpoint; in demo
 * mode they're hand-authored to look reasonable for a customer audience.
 */
import type { AssistContext, ApplyAction } from "./context";

export interface AgentReply {
  text: string;
  reasoning?: string;
  /** Optional patch the user can click "Apply" on. */
  actions: ApplyAction[];
  /** Cited bundle rules / decisions / runs for this reply. */
  citations?: { label: string; ref: string }[];
}

interface ReplyMatcher {
  /** All keywords (lowercased) must appear in the user prompt for this match. */
  keywords: string[];
  reply: (ctx: AssistContext) => AgentReply;
}

/* ─────────────── per-context demo replies ─────────────── */

const DASHBOARD_REPLIES: ReplyMatcher[] = [
  {
    keywords: ["health", "status"],
    reply: () => ({
      text: "All four planes report healthy. Standards bundles are pinned at v0.1.0 (security/privacy/architect/finops). Pipeline is processing 1 active demo run. Ledger is recording 5 decisions with full bundle citations. Agent HQ runtime registered 4 active personas. Combined posture score: **92/100** — only deduction is the 1 stale prompt version on `test_plan.derive` (v0.1.0 → v0.2.0 available).",
      actions: [
        { kind: "navigate", description: "Update test_plan prompt to v0.2.0", href: "/prompts" },
        { kind: "navigate", description: "View governance reports", href: "/reports" },
      ],
      citations: [
        { label: "Stale prompt", ref: "prompt:test_plan.derive@v0.1.0" },
      ],
    }),
  },
  {
    keywords: ["report", "exec", "summary"],
    reply: () => ({
      text: "I drafted an executive summary for the last 24h: **8 runs · 5 decisions · $0.62 spend · 0 PHI violations · 0 secret-scan blockers · 12% autopilot rate**. The autopilot rate trend is rising +4pp week-over-week — your team's precedent ledger is paying off. Want me to open the full Reports page or send this to your CFO format?",
      actions: [
        { kind: "navigate", description: "Open governance reports", href: "/reports" },
      ],
    }),
  },
];

const RUN_RESOLVER_REPLIES: ReplyMatcher[] = [
  {
    keywords: ["recommend"],
    reply: (ctx) => ({
      text: `Based on your **security/v0.1.0** and **privacy/v0.1.0** bundle rules, the Architect+Privacy precedent ledger, and HIPAA §164.312(d) entity-authentication requirements, I recommend approving all 5 cards as the Assessor classified them. The recommendations form a coherent posture: mTLS+OAuth for vendor connectors, Safe Harbor 18-identifier redaction at egress, 6-year retention with archival, field-level allowlist for the consumer, and RS256 JWT 15min TTL on WebSocket. Combined risk surface: $1,750 blast-radius averted.`,
      reasoning: "All 5 cards have a 'recommended' option backed by at least one bundle rule citation. No card has a precedent-mismatch score above 0.2. Auto-resolve confidence: high.",
      actions: [],
      citations: [
        { label: "HIPAA §164.312(d)", ref: "security/v0.1.0/AUTH-001" },
        { label: "HIPAA §164.514(b) Safe Harbor", ref: "privacy/v0.1.0/PHI-REDACT-001" },
        { label: "HIPAA §164.530(j)", ref: "privacy/v0.1.0/RETENTION-001" },
      ],
    }),
  },
  {
    keywords: ["override", "different"],
    reply: () => ({
      text: "If you override the recommended option on Card 1 (`auth-policy`) to API-key-with-IP-allowlist, you'll trip `security/v0.1.0/AUTH-001` which requires entity authentication for HIPAA. The pipeline will block at review-scan unless you also stage a standards-change PR to relax that rule. Cost of override: $450 incremental blast radius + ~2 days delay for the standards-change committee. Want me to draft the OpenSpec change proposal?",
      actions: [
        {
          kind: "create_bundle_change",
          description: "Draft openspec change: relax AUTH-001 to allow API-key for legacy connectors",
          dept: "security",
          new_version: "v0.2.0",
          reasoning: "Some legacy Philips IntelliVue firmware versions don't support OAuth flows natively — relaxation needed for vendor compatibility.",
        },
      ],
      citations: [
        { label: "Blocking rule", ref: "security/v0.1.0/AUTH-001" },
      ],
    }),
  },
];

const PROMPT_EDIT_REPLIES: ReplyMatcher[] = [
  {
    keywords: ["test", "decision"],
    reply: () => ({
      text: "I see you're on the test_plan prompt. The current v0.1.0 doesn't bind decisions into the prompt context — that's the bug we caught in the Phase A vs Phase B experiment (it produced generic CRUD tests for streaming WebSocket APIs). I drafted a v0.2.0 that consumes both `prd_text` AND `decisions` AND requires verbatim decision citations in each test entry. Want me to apply this draft? It will create a new version in your local edit history and you can roll back any time.",
      actions: [
        {
          kind: "apply_text_edit",
          description: "Apply test_plan.derive v0.2.0 (decision-grounded)",
          new_content: `# Test Plan stage prompt v0.2.0 (decision-grounded)

You are the Test Plan generator. Produce a test plan that verifies the
PRD requirements AND every resolved decision.

## Inputs
- PRD body: {prd_text}
- Resolved decisions: {decisions}
- Architecture proposal: {architecture}

## Required output
Markdown test plan with:
1. **Decision-coverage tests** — for each resolved decision, ≥1 test that
   verifies the system enforces that decision. Quote each decision verbatim
   in the test description.
2. **PRD-requirement tests** — happy path, error path, contract test per
   stated requirement.
3. **Bundle-rule tests** — for every cited bundle rule, ≥1 test that
   verifies the rule is enforced.
4. **PHI guard tests** — verify no raw PHI in logs, prompts, telemetry.
5. **Performance tests** — verify SLAs from PRD/decisions.

Each test entry: {name, type, description, decision_ref|bundle_ref,
fixture, asserts}.

## Hard rules
- Quote each decision verbatim in the relevant test description.
- Cite the bundle rule in the test's tag/category.
- Synthetic PHI only.
- Generic CRUD tests are NOT acceptable for streaming/auth/PHI requirements.
`,
        },
      ],
      citations: [
        { label: "Phase A vs B finding", ref: "experiments/COMPARISON.md#test-spec" },
      ],
    }),
  },
  {
    keywords: ["why", "explain"],
    reply: (ctx) => ({
      text: `This prompt is the template the orchestrator binds at the **${ctx.id ?? "current"}** stage. The variables in curly braces (\`{prd_text}\`, \`{decisions}\`, etc.) are populated at runtime from the run state. Each version you save here becomes a new prompt-library variant — but to actually ship it to production runs, you'll need an OpenSpec change PR for the orchestrator's prompt registry. Want me to walk you through the deployment flow?`,
      actions: [
        { kind: "navigate", description: "View OpenSpec methodology", href: "/changes" },
      ],
    }),
  },
];

const AGENT_EDIT_REPLIES: ReplyMatcher[] = [
  {
    keywords: ["tighten", "phi"],
    reply: (ctx) => ({
      text: `I can tighten this agent's PHI rule. Currently it cites \`security/v0.1.0/PHI-001\` once. I propose adding three concrete don'ts: never include raw MRN/SSN/DOB even in code comments, always use \`redacted_id()\` for log lines, and never write to \`Observation.subject.reference\` without first running it through the tokenization service. This is a cumulative tightening — no relaxation, so it won't trigger a standards-change committee review.`,
      actions: [
        {
          kind: "apply_text_edit",
          description: `Add three concrete PHI don'ts to ${ctx.id} agent`,
          new_content: "(full agent.md content with appended hard rules — handler will compose)",
        },
      ],
      citations: [
        { label: "PHI rule", ref: "security/v0.1.0/PHI-001" },
      ],
    }),
  },
  {
    keywords: ["add", "model"],
    reply: () => ({
      text: "If you add `gpt-5` to preferred_models, I should warn: GPT-5 is not currently routed via APIM in your tenant. The orchestrator will fall back to the next model in the list. To actually use GPT-5 you need (a) APIM route for it, (b) APIM rate-limit policy, (c) prompt-library entry for `<stage>:openai-apim:gpt-5`. Want me to draft an OpenSpec change covering all three?",
      actions: [
        {
          kind: "create_bundle_change",
          description: "Draft openspec change: register gpt-5 via APIM with prompt-library variant",
          dept: "architect",
          new_version: "v0.2.0",
          reasoning: "Add GPT-5 routing for stages that benefit from longer-context reasoning.",
        },
      ],
    }),
  },
];

const DECISIONS_REPLIES: ReplyMatcher[] = [
  {
    keywords: ["why", "phi"],
    reply: () => ({
      text: "The 5 decisions for this run all classified `phi_class: high` because the Patient Vitals Streaming PRD explicitly mentions FHIR Observation resources with patient identifiers in `subject.reference` fields. The Assessor's PHI classifier matched 3 patterns: MRN-like identifier reference, FHIR resource subject pointer, and HIPAA Safe Harbor identifier category. All 5 decisions cite at least one PHI bundle rule. This is the expected posture for any run touching FHIR + PHI.",
      actions: [],
      citations: [
        { label: "PHI classifier", ref: "security/v0.1.0/PHI-001" },
        { label: "Safe Harbor", ref: "privacy/v0.1.0/PHI-REDACT-001" },
      ],
    }),
  },
  {
    keywords: ["amend", "rationale"],
    reply: () => ({
      text: "I can amend the rationale on a decision, but be aware: the original rationale stays in the audit trail. Every amend creates a new ledger entry of type `meta:rationale_amendment` with a pointer to the original. This preserves the integrity of the audit log while allowing post-hoc clarification. Which decision id do you want to amend?",
      actions: [],
    }),
  },
];

const TELEMETRY_REPLIES: ReplyMatcher[] = [
  {
    keywords: ["spend", "cost"],
    reply: () => ({
      text: "Your last 24h spend is $0.62 across 8 runs. Codegen accounts for 32% (largest), then Architect at 30%, Assessor 18%, TestPlan 12%. The TestPlan share rose from 4% to 12% this week — that's the v0.2.0 prompt fix doing real work (decision-grounded tests cost more than CRUD generics). Cost-per-decision is $0.124. If you want hard savings, the next lever is shifting Codegen from sonnet-4-6 to haiku-4-5 for runs without security/architect bundle citations — saves ~40% on that stage with ~5% quality loss in our eval.",
      actions: [
        { kind: "navigate", description: "Open governance reports", href: "/reports" },
      ],
    }),
  },
  {
    keywords: ["drift", "trend"],
    reply: () => ({
      text: "Class drift over the last 7 days: `phi-classification` flat, `auth-policy` -8% (good — fewer ambiguous auth specs reaching the pipeline), `data-retention` +14% (this is new — investigate which team is filing PRDs without retention windows). Mean gate-wall-clock time is 47s, down from 2m12s last week — your humans are getting faster at the resolver gate.",
      actions: [],
      citations: [
        { label: "Class window", ref: "telemetry/classes?window=7d" },
      ],
    }),
  },
];

const BUNDLES_REPLIES: ReplyMatcher[] = [
  {
    keywords: ["change", "edit", "rule"],
    reply: () => ({
      text: "Bundles can't be edited directly — that's by design. To change a rule, I need to draft an OpenSpec change PR that creates `standards-bundles/<dept>/v<n.n.n>/rules.yaml` (next minor version), reviewed by the bundle's pinned reviewer roster. Tell me which rule you want to change and I'll draft the proposal + tasks + spec delta.",
      actions: [
        {
          kind: "create_bundle_change",
          description: "Draft openspec change for next bundle version",
          dept: "(unspecified)",
          new_version: "v0.2.0",
          reasoning: "Specify the rule and direction (tighten/relax) to fill in.",
        },
      ],
    }),
  },
];

const RUNS_LIST_REPLIES: ReplyMatcher[] = [
  {
    keywords: ["latest", "recent"],
    reply: () => ({
      text: "Showing the most recent 6 runs. The vitals-streaming demo run is currently `awaiting_gate` with 5 decisions pending human resolution. Eligibility-check ran clean (no gates triggered). The PCI-clean run is at the architect stage. Mean wall-clock for runs that completed: 4m12s. Want me to drill into a specific one?",
      actions: [
        { kind: "navigate", description: "Start a fresh run", href: "/runs/new" },
      ],
    }),
  },
];

const REPORTS_REPLIES: ReplyMatcher[] = [
  {
    keywords: ["explain", "score"],
    reply: () => ({
      text: "Governance posture score is computed as: 0.4 × bundle-rule-coverage + 0.3 × decision-citation-completeness + 0.2 × prompt-version-currency + 0.1 × autopilot-precedent-confidence. Your current 92/100 breakdown: bundle coverage 100%, citation completeness 95%, prompt currency 75% (one stale), autopilot confidence 80%. Updating that one stale prompt would lift you to ~96/100.",
      actions: [
        { kind: "navigate", description: "Update stale prompt", href: "/prompts" },
      ],
    }),
  },
];

/* ─────────────── master matcher ─────────────── */

const MATCHERS: Record<string, ReplyMatcher[]> = {
  dashboard: DASHBOARD_REPLIES,
  "runs-list": RUNS_LIST_REPLIES,
  "run-detail": RUN_RESOLVER_REPLIES,
  "run-resolver-gate": RUN_RESOLVER_REPLIES,
  decisions: DECISIONS_REPLIES,
  telemetry: TELEMETRY_REPLIES,
  bundles: BUNDLES_REPLIES,
  "agents-list": AGENT_EDIT_REPLIES,
  "agent-edit": AGENT_EDIT_REPLIES,
  "prompts-list": PROMPT_EDIT_REPLIES,
  "prompt-edit": PROMPT_EDIT_REPLIES,
  reports: REPORTS_REPLIES,
};

/** Generic fallback for any context. */
const FALLBACK_REPLY: AgentReply = {
  text: "I can read the current view's context but I don't have a pre-canned answer for that exact question. In production I'd route this through the orchestrator's chat agent with the bundle rules + recent decisions + active prompt as system context. Try one of these prompts: \"why\" / \"recommend\" / \"explain score\" / \"trend\" / \"add rule\" / \"override\".",
  actions: [],
};

/**
 * Pick the best pre-canned reply for the user's prompt within the current
 * context. Falls back to a generic explanation when no keyword matches.
 */
export function pickReply(
  context: AssistContext | null,
  userPrompt: string,
): AgentReply {
  if (!context) return FALLBACK_REPLY;
  const lower = userPrompt.toLowerCase();
  const matchers = MATCHERS[context.kind] ?? [];
  for (const m of matchers) {
    if (m.keywords.every((kw) => lower.includes(kw))) {
      return m.reply(context);
    }
  }
  // First reply for the context as a soft default.
  if (matchers.length > 0) return matchers[0].reply(context);
  return FALLBACK_REPLY;
}

/**
 * Suggested prompts shown as chips before the user types anything.
 * Context-specific so the user can see what's possible at a glance.
 */
export function getSuggestions(context: AssistContext | null): string[] {
  if (!context) return [];
  switch (context.kind) {
    case "dashboard":
    case "reports":
      return [
        "How is the system health right now?",
        "Show me an exec summary",
        "What's the trend on autopilot rate?",
      ];
    case "runs-list":
      return [
        "What's the latest run state?",
        "Which runs need my attention?",
      ];
    case "run-detail":
    case "run-resolver-gate":
      return [
        "What do you recommend?",
        "What if I override card 1?",
        "Why is this gating?",
      ];
    case "decisions":
      return [
        "Why are these classified PHI high?",
        "How do I amend a rationale?",
      ];
    case "telemetry":
      return [
        "Where is my spend going?",
        "What's the drift trend?",
      ];
    case "bundles":
      return [
        "How do I change a rule?",
        "What does each bundle govern?",
      ];
    case "agents-list":
    case "agent-edit":
      return [
        "Tighten the PHI rule",
        "Add gpt-5 to preferred models",
        "What does this agent write to ledger?",
      ];
    case "prompts-list":
    case "prompt-edit":
      return [
        "Why this prompt? Explain it.",
        "Update test_plan to bind decisions",
      ];
    case "phi-classifier":
      return [
        "How does the classifier work?",
        "What patterns trigger high PHI class?",
      ];
  }
}
