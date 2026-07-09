# AGENTS.md — repository-wide agent guardrails

This file is read by every Copilot agent (cloud agent, CLI, VS Code) and every
custom agent invoked from `.github/agents/`. It is the entrypoint to the
standards hierarchy for THIS repository — not the law. Bundles are the law.

## Standards hierarchy (precedence)

Earlier layers establish defaults; later layers refine. On direct conflict
the **lower-numbered** layer wins **except where a bundle is pinned** —
bundles always win.

| # | File / Glob | Always loaded? | Loaded by |
|---|---|---|---|
| 1 | `AGENTS.md` (this file) | yes | every Copilot runtime; Custom Agents |
| 2 | `.github/copilot-instructions.md` | yes for Copilot runtimes | VS Code Copilot, Copilot CLI, cloud agent |
| 3 | `.github/instructions/*.instructions.md` | only when `applyTo:` glob matches the touched file | VS Code Copilot Chat, cloud agent |
| 4 | `.github/agents/<name>.agent.md` | only when that custom agent is invoked | Custom Agents (VS Code, CLI, cloud) |
| 5 | `standards-bundles/<dept>/v<n.n.n>/rules.yaml` | injected by SessionStart hook based on the agent's `bundle_subscriptions:` | hook script via `ledger.get_bundle` MCP tool |

Bundle pins live at `standards-bundles/PINS.yaml`. The normative spec for this
hierarchy is `openspec/changes/add-agent-instructions-hierarchy/`.

### Worked example — Architect agent editing `apps/orchestrator/main.py`

When a contributor opens `apps/orchestrator/main.py` in VS Code and invokes
the `architect` custom agent, the session loads, in order:

1. `AGENTS.md` (this file) — repo-wide hard rules
2. `.github/copilot-instructions.md` — commit-message format, Plan Mode trigger
3. `.github/instructions/python.instructions.md` — Python conventions (matches `**/*.py`)
4. `.github/agents/architect.agent.md` — persona, allowed tools, declared ledger writes
5. `standards-bundles/architect/v0.1.0/rules.yaml` + `standards-bundles/security/v0.1.0/rules.yaml` — injected by SessionStart hook from `architect.agent.md`'s `bundle_subscriptions:`

If a bundle rule (layer 5) and a `copilot-instructions` rule (layer 2)
contradict, the bundle wins. If the architect agent file (layer 4) and
the python instructions (layer 3) contradict, the python instructions win
(per precedence) — but if you find yourself fighting the precedence, that
is a signal to open a standards-change PR rather than work around it.

## Repository purpose (one sentence)

Reference design for a governed agentic SDLC: a four-plane architecture
(Standards / Pipeline / Ledger+Doctor / Agent HQ runtime) where every AI-agent
decision is auditable and every standards change is committee-approved.

**This is a real, customer-neutral production system.** It is not tied to any
one customer, engagement, or account. Nothing in this repo — code, specs,
proposals, docs, comments, commit messages — may frame a change around a named
engagement, deal, or customer contact. (Public company names as generic
example/sample data are fine — see the NEVER rule below.)

## Hard rules — NEVER

- **Never tie the repo to a named engagement, deal, or customer contact.** No
  "motivating engagement," no "so-and-so asked for," no
  meeting/deal/account references, no sales framing ("sellable," "on the call")
  — in code, specs, OpenSpec proposals/design, docs, comments, or commit
  messages. This is a customer-neutral production system: motivate every change
  by the *architectural* need (e.g. "un-orchestrated agent PRs bypass both
  enforcement surfaces"), never by who asked. **Public company names (payers,
  providers, vendors — Humana, Aetna, HCA, etc.) as generic example/sample data
  are FINE** — that is public knowledge and reveals no engagement. The line is
  named-live-engagement vs. public-example, not "no company names."
- **Never write raw PHI** (MRN, full DOB, SSN, full name + DOB, biometric IDs, treatment notes)
  to logs, telemetry, ledger, prompts, or sample data. PHI in samples must be obviously
  synthetic (Patient ID `PT-DEMO-0001`, DOB `1900-01-01`).
- **Never bypass the Decision Ledger.** Every meaningful agent action writes a ledger entry.
  No silent edits, no untracked tool calls.
- **Never commit account keys, connection strings with embedded keys, or service-principal
  secrets.** Managed Identity only for data-plane auth.
- **Never modify `standards-bundles/**/*.yaml` without an OpenSpec change proposal**
  and reviewer approval per the bundle's declared roster.

## Hard rules — ALWAYS

- **Always classify before acting.** Pipeline stages classify ambiguity at the Assessor stage;
  IDE Copilot sessions classify at the `PreToolUse` hook.
- **Always cite the bundle version** when applying a standards rule. Format:
  `[<dept>/<version>/<rule-id>]` (e.g. `[security/v0.1.0/PHI-001]`).
- **Always write a `runtime` ledger entry per stage decision** and a `meta` ledger entry
  per standards change merge.
- **Always run tests before declaring a task complete.** Targets: `apps/orchestrator/tests/`,
  `apps/pipeline-doctor/tests/`, `apps/decision-ledger-mcp/tests/`.

## Personas (custom agents in `.github/agents/`)

| Agent file | Role | Bundle subscriptions |
|---|---|---|
| `assessor.agent.md` | Classify PRD ambiguities into typed cards | security, privacy |
| `architect.agent.md` | Propose architecture given resolved decisions | architect, security |
| `codegen.agent.md` | Generate code aligned to architecture decisions | architect, security |
| `review-scan.agent.md` | Pre-merge review, SBOM + SAST + secret scan | security |
| `pipeline-doctor.agent.md` | Drift detection + bounded auto-fix + change-proposal author | finops, all (read-only) |
| `standards-change.agent.md` | Triage standards-change PRs, draft ADRs, route reviewers | (all, meta) |

Each agent file declares the bundles it reads and the ledger entry types it
can write. Frontmatter MUST validate against
`.github/agents/agent-frontmatter.schema.json`; CI rejects PRs that introduce
malformed agent files.

## In-UI AgentAssistant (reading layer, NOT a ledger writer)

The `ledger-insights-ui` dashboard ships an in-UI conversational assistant
(floating Sparkles button + ⌘K slide-over) that answers operator questions
grounded in the live ledger + run + portfolio state. It is a **reading layer**
over what already exists, NOT a custom agent that participates in the
pipeline.

Hard boundaries (enforced by the openspec change `add-context-aware-agent-assistant`):

- The AgentAssistant **MUST NOT** write to the Decision Ledger.
- The AgentAssistant **MUST NOT** modify standards bundles, agent files, or
  prompt-library entries directly. Apply-back actions on agent / prompt
  edits write to a local versioned store (rollback-friendly), not to the
  canonical bundles.
- Demo mode runs a deterministic composer (no LLM call). Live mode would
  send the same `gatherContext()` snapshot as the system prompt to the
  orchestrator chat agent, with PHI classification at the LLM boundary
  before any rationale text is forwarded.
- Suggestions and replies MUST be re-derived on every turn from
  `gatherContext()`. No reply caching, no per-kind pre-canned text, no
  invented citations.

The reply engine lives at `apps/ledger-insights-ui/src/lib/assist/`.
Capability spec: `openspec/changes/add-context-aware-agent-assistant/specs/agent-assistant/spec.md`.

## Plan Mode by default for non-trivial changes

If a task touches >3 files, modifies a stage definition, edits a standards bundle, or
changes the ledger schema, use Plan Mode. Capture the plan to the ledger as a
`runtime` entry of type `plan_proposed` before any code lands.

## Ledger contract (every agent writes)

```yaml
entry_type: runtime | meta
run_id: <uuid>             # or change_ticket_id for meta
agent_session_id: <gh id>  # null for orchestrator-internal stages
stage: <stage_name>        # null for IDE / coding-agent sessions
actor:
  kind: human | agent
  id: <m365_upn or agent_principal_id>
decision: <one-line summary>
rationale: <full reasoning>
phi_class: none | low | high
cost_usd: <float>
model_used: <model_id>
bundle_refs: [security/v0.1.0/PHI-001, ...]
precedent_refs: [<ledger_entry_id>, ...]
gh_audit_xref: <agent_session_id from GH audit log>
```

## When in doubt

Stop. Open a Plan Mode session. Ask the user. The cost of pausing is small;
the cost of writing a `meta` ledger entry that quietly changes a PHI rule is large.
