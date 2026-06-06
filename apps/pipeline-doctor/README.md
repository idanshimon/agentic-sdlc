# pipeline-doctor

Reads the Decision Ledger continuously, surfaces drift signals, and produces:

- **AUTO-FIX** within bounded envelopes (writes a runtime ledger entry)
- **CHANGE-PROPOSAL** for everything else (opens a PR on `standards-bundles/<dept>` with ADR)

Hard rules (override any envelope.yaml):

- PHI rules (`phi: true`) are NEVER auto-fixed
- Deny rules (`severity: BLOCK` or `rule_pattern: "deny/*"`) are NEVER loosened
- Auto-fix is rate-limited to 5 / department / 7-day window

See `openspec/changes/add-pipeline-doctor/` for full spec.

## Install (dev)

```bash
cd apps/pipeline-doctor
pip install -e ../../packages/ledger-core
pip install -e .[test]
```

## Test

```bash
pytest
```

## Run (one-shot)

```bash
python -m pipeline_doctor --mode dry-run
```
