# Design: decision lifecycle control plane

## Context

The system already records stage events, gate decisions, ledger entries, prompt chains, bundle citations, review-loop hops, and GitHub delivery results. The missing piece is not another store. It is a coherent read model and operator interaction model over those existing facts.

The implementation starts by repairing producer/consumer contracts before introducing the full lifecycle projection.

## Architecture

### Source evidence

- `RunState.events`: stage chronology and live payloads
- Decision Ledger: immutable runtime/meta decisions and teaching signals
- GitHub: agent session, branch, commit, pull request, check, ruleset, review, merge
- Git repository: agent profiles, prompts, bundles, workflows, instructions, skills, hooks

### Derived lifecycle read model

A lifecycle projection groups source evidence by stable decision identity and derives:

- `proposed`
- `required`
- `resolved`
- `applied`
- `verified`
- `learned`

The projection stores source references, never copied mutable truth. It can be rebuilt from the ledger, run events, and GitHub references.

### Runtime workspace

The run page is organized in priority order:

1. Terminal outcome or attention queue
2. Stage rail and current state
3. Decision workbench
4. Artifacts and GitHub evidence
5. Raw event diagnostics
6. Cost/model/provenance summary

A failed run must identify the failed stage, reason, governing policy/check where available, and recovery action. Completed prior stages remain completed, but the rail visually terminates at the failed stage.

### Artifact projection

A pure event projector reads the latest non-empty payload for each canonical artifact:

| Artifact | Event payload key |
|---|---|
| Architecture | `architecture` |
| Test plan | `test_plan` |
| Implementation | `app_code`, fallback `code` |
| Generated tests | `test_code` |
| Decisions document | `decisions_md`, `decisions_md_url` |
| Delivery | `pr_url`, `delivery_status`, `delivery_reason`, `artifact_files` |

Demo fixtures may enrich a demo run but may not override fresher live evidence. Availability is derived from projected content, never from run status.

### Terminal outcome projection

A pure classifier selects the latest terminal evidence:

- Latest `failed` event → failed stage, message, payload evidence
- `run.status=failed` without failed event → unknown failure with diagnostic guidance
- Delivery `not_delivered` on an otherwise completed pipeline → completed with delivery action required, not a fabricated success
- Review verdict FAIL → policy verification failure with blocker references

### URL-backed Decisions registry

Supported query parameters begin with `run`, `team`, `stage`, `actor`, `phi`, `kind`, `lineage`, and `q`. Parsing and serialization are pure functions. The backend remains authoritative for readable team scope.

A run detail link uses `/decisions?run=<run_id>`. The page passes this scope to the ledger query rather than fetching all readable rows and filtering afterward.

### GitHub boundary

GitHub owns agent sessions, execution environments, branches, commits, PRs, reviews, checks, Actions, rulesets, CODEOWNERS, merge queue, repository settings, and native agent configuration. This system stores references and governance overlays; it does not clone those products.

GitHub-native user-private automations are unsuitable as canonical organization workflow definitions. Shared deterministic automation remains Actions. Shared agentic workflow definitions remain version-controlled governed configuration.

## First implementation slice

1. Event-to-artifact projector and tests.
2. Run artifact panel consumes projected live architecture/test plan/app/tests/delivery.
3. Terminal outcome classifier and prominent failed-run panel.
4. URL-backed `run` scope on Decisions plus run-page deep link.
5. Delivery routes generated `test_code` to `tests/test_main.py`.

## Security and governance

- No source ledger entry is mutated.
- Cross-team access is not expanded by URL state.
- Free text remains subject to existing PHI controls.
- GitHub links are rendered only when backed by an actual URL/ID.
- No standards bundle changes are included.

## Rollback

Remove the new pure projections/components and restore prior renderers. The orchestrator delivery mapping can be reverted independently. No data migration is required.
