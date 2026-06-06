# Orchestrator tests

Unit + integration tests for the orchestrator.

## Run

```bash
cd ~/projects/msft/cust/hca/agentic-sdlc
pip install pytest httpx
PYTHONPATH=. pytest apps/orchestrator/tests/ -v
```

## Coverage

| File | What it tests |
|---|---|
| `test_models.py` | ResolutionOption shape, AmbiguityCard option fields, GateDecision variants, LedgerEntry defaults |
| `test_approve_endpoint.py` | /approve resolution-text logic: option_index → recommended fallback → swap verbatim → 404 |

## What's NOT tested here (call-out)

- Stages (`stages.py`) — depends on live APIM + Databricks calls. Tested via end-to-end Manthan PRD runs in production.
- Ledger write-block invariants — depends on live Cosmos. Smoke-tested via the live demo.
- SSE streaming — depends on real run state machine.

Those are integration concerns and live in `scripts/smoke-test.sh`.
