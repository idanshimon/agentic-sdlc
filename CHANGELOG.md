# Changelog

All notable changes to the v0.7 reference design.

## [0.7.0-rc1] — 2026-06-05 — initial v0.7 scaffold

The four-plane architecture cut from v0.6 lessons.

### Added
- Repo skeleton at `~/projects/msft/agentic-sdlc/` (clean break from `cust/hca/agentic-sdlc`)
- `AGENTS.md` repo-wide guardrails
- `.github/copilot-instructions.md`
- OpenSpec config with strict-validation rules
- Master proposal `openspec/changes/master-v07-four-plane-architecture/`
- README.md with audience callout, four-plane diagram, layout map, honest disclaimers
- MIT LICENSE

### Background
v0.6 (HCA Nashville workshop reference, line `0.6.7` `bfae9d9`) proved that
**governance is the differentiator**: Decision Ledger as audit spine, HITL
gates at ambiguity classes, cost-per-decision dashboards. The two limits that
drove v0.7:

1. Ledger only saw orchestrator pipeline runs (~20% of agentic activity).
2. Department standards lived as scattered prompts and APIM policies; rule
   changes meant code changes; no committee process.

v0.7 closes both via Agent HQ ledger coverage + standards-bundles plane +
Pipeline Doctor.

### Ported from v0.6 (selectively)
- Orchestrator app (FastAPI, 9 stages, providers, prompt library)
- Ledger module (extracted to `packages/ledger-core/`, schema extended)
- Resolver UI → renamed `ledger-insights-ui` (HITL gate panel removed)
- OpenSpec proposals: prompt-library, telemetry-dashboard, vnet-private-endpoints

### Discarded from v0.6
- ADO-only deliver path (GH default; ADO opt-in via `deliver_provider` flag)
- Standalone HITL gate UI (Plan Mode + chat bridges replace it)
