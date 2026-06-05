# Spec delta — capability: ledger

## Added

### LedgerEntry.entry_type

A discriminator field that classifies the entry as either a `runtime` decision
(made during a pipeline run, IDE session, or coding-agent flow) or a `meta`
decision (a change to the standards rules themselves).

Default value: `"runtime"` (preserves backward compatibility with v0.6
entries that lack this field).

### LedgerEntry.bundle_refs

List of fully-qualified bundle rule references in the form
`<dept>/<version>/<rule-id>`. Required to be populated when an agent invokes a
rule from a bundle. Used by Pipeline Doctor's drift detection to attribute
signal per-bundle.

### LedgerEntry meta-only fields

- `change_ticket_id` (str): identifier of the standards-change ticket
- `bundle_version_from` (str): pre-merge bundle version
- `bundle_version_to` (str): post-merge bundle version
- `blast_class` (LOW | MED | HIGH): committee routing classification
- `reviewers` (List[ReviewerAttribution]): who approved
- `canary_metrics` (CanaryMetrics, optional): metrics observed during canary
- `pr_url` (str): the PR that merged the change

### LedgerEntry.agent_session_id

GitHub Enterprise audit log cross-reference. Set on entries from
Agent-HQ-driven runtimes (coding agent, IDE Copilot, chat bridges). Allows
compliance to join our ledger to GH's `actor:Copilot` audit log.

## Modified

### Cosmos indexing policy

Indexed paths added:
- `/entry_type/?`
- `/bundle_refs/[]/?`
- `/blast_class/?`
- `/agent_session_id/?`

## Validation rules

- A `meta` entry MUST have `change_ticket_id`, `bundle_version_from`,
  `bundle_version_to`, `blast_class`, and at least one entry in `reviewers`.
- A `meta` entry MUST NOT have `run_id` or `stage` set.
- A `runtime` entry MUST have at least one of `run_id` or `agent_session_id`.
- Both entry types MUST have `team_id` set (Cosmos partition key).
