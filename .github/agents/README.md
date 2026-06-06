# Custom Agents

GitHub Copilot Custom Agents that mirror the Foundry pipeline agents. Same
personas, different runtime: Foundry agents run in the orchestrator pipeline;
these run in VS Code, Copilot CLI, or coding-agent flows.

## Agent inventory

| Agent | Persona | Bundles | Where it runs |
|---|---|---|---|
| [assessor](assessor.agent.md) | Classify PRD ambiguities into typed cards | security, privacy | orchestrator stage 2 |
| [architect](architect.agent.md) | Propose architecture given resolved decisions | architect, security | orchestrator stage 4 + IDE |
| [codegen](codegen.agent.md) | Generate code aligned to architecture | architect, security | orchestrator stage 7 + IDE + coding-agent |
| [review-scan](review-scan.agent.md) | Pre-merge gate (SBOM + SAST + secret + PHI) | security, privacy | orchestrator stage 8 + Copilot Code Review |
| [pipeline-doctor](pipeline-doctor.agent.md) | Drift detection + bounded auto-fix + change-proposal authoring | finops (envelope), all (read) | Container Job (cron) |
| [standards-change](standards-change.agent.md) | Triage standards-bundles PRs, draft ADR, assign reviewers | all (read) | GitHub Actions workflow |

## A365 registration

Each agent is registered as an A365 tenant agent identity at deploy time
(see `deploy/scripts/register-a365-agents.sh`). Each gets a stable
`agent_principal_id` that becomes `actor.id` on every ledger entry the
agent writes.

## How agents are loaded

GitHub Copilot reads `.github/agents/*.agent.md` automatically when running
in this repo. The `tools:` allow-list is honored by Copilot's tool gating.
The `bundle_subscriptions:` list is read by our hooks at SessionStart to
inject the relevant rules into the agent's context.

## Why these mirror Foundry agents

The Foundry agents (running inside the orchestrator pipeline) and the
Custom Agents (running in IDE / coding-agent flows) share:

- The same prompt library (served via `ledger.get_prompt(stage, model)` MCP tool)
- The same bundle subscriptions
- The same `actor.id` namespace (so a ledger query for "what did the
  architect agent decide last week" returns BOTH pipeline-stage decisions
  AND IDE-session decisions)

Different runtime, same governance substrate.
