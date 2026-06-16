# SBM Cardiology POC pipeline namespace

This experiment drives the agentic-SDLC pipeline against the cardiology
deterioration alert PRD as a real-world Stony Brook Medicine POC use case.
Goal: empirical evidence about which models can carry which stages, where the
pipeline breaks on healthcare-specific input, and a deployable artifact at
the end.

## Layout

```
experiments/sbm-cardiology/
├── README.md                     (this file)
├── prd.txt                       (the canonical PRD, copy of samples/prds/cardiology-deterioration-alerts.txt)
├── fixtures/
│   └── resolver-decisions.yaml   (deterministic resolver decisions across runs)
├── runs/
│   └── <model-id>-<run-N>/       (one folder per (model, run-index) pair)
│       ├── prd.txt
│       ├── cards.json            (Assessor output)
│       ├── decisions.json        (resolver decisions applied)
│       ├── ledger.jsonl          (LedgerEntry per decision; Track-B-readable)
│       ├── architecture.md       (Architect)
│       ├── test_plan.md          (TestPlan)
│       ├── codegen.py            (CodeGen)
│       ├── decisions.md          (the customer artifact)
│       ├── pr_payload/           (PR-shaped folder: src/, tests/, docs/, decisions.md)
│       ├── events.jsonl          (every StageEvent)
│       └── summary.json          (cost / tokens / durations / model routing)
└── results/
    └── <date>/comparison.md      (run-over-run analysis)
```

## Why a separate namespace

`experiments/results/phase-a` and `phase-b` were the earlier
patient-vitals-streaming A/B (decisions-md format change). Mixing the SBM POC
into those folders would conflate two different experiments. Fresh folder,
fresh team_id, fresh ledger so Track B (class_paused / decision_flagged) can
be observed cleanly on this run.

## Team partitioning

Each run uses team_id `team-sbm-cardiology-{model}-{run}` for the file-shim
ledger and a stable `team-sbm-cardiology` for the Cosmos production ledger
once the run is promoted. Track B's class-pause / flagged-id queries are
partition-keyed by team, so a fresh team_id means a clean slate.
