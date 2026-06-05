# AGENTS.md — repository-wide agent guardrails

This file is read by every Copilot agent (cloud agent, CLI, VS Code) and every
custom agent invoked from `.github/agents/`. It is the top of the standards
hierarchy for THIS repository.

The standards hierarchy:

1. `AGENTS.md` (this file) — repo-wide, always loaded
2. `.github/copilot-instructions.md` — Copilot-specific, always loaded
3. `.github/instructions/*.instructions.md` — path-scoped via `applyTo`
4. `standards-bundles/<dept>/v<n.n.n>/` — versioned per-department policies (the canonical source)

Bundle pins are stored in `standards-bundles/PINS.yaml`. When this file conflicts
with a pinned bundle rule, the bundle wins. This file is the entrypoint, not the law.

## Repository purpose (one sentence)

Reference design for a governed agentic SDLC: a four-plane architecture
(Standards / Pipeline / Ledger+Doctor / Agent HQ runtime) where every AI-agent
decision is auditable and every standards change is committee-approved.

## Hard rules — NEVER

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

Each agent file declares the bundles it reads and the ledger entry types it can write.

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
