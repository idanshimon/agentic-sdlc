# ledger-core

Shared library for the Decision Ledger schema and Cosmos client. Used by:

- `apps/orchestrator` — writes runtime entries from pipeline stages
- `apps/pipeline-doctor` — reads ledger, writes auto-fix runtime entries
- `apps/decision-ledger-mcp` — exposes ledger via MCP tools to GH runtimes

## Schema highlights

- `entry_type: runtime | meta` discriminator
- `bundle_refs` for per-bundle attribution (drives Pipeline Doctor signal)
- `agent_session_id` cross-references GitHub audit log entries
- Meta-only fields validate via `model_validator` (committee approvals,
  bundle version transition, blast class)

See `openspec/changes/extend-ledger-runtime-meta-entries/` for the full spec.

## Install (dev)

```bash
cd packages/ledger-core
pip install -e .[test]
```

## Test

```bash
pytest
```
