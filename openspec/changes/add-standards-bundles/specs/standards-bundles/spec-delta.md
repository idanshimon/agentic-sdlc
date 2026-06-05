# Spec delta — capability: standards-bundles

## Added (NEW capability)

### Standards-bundles directory structure

A new top-level directory `standards-bundles/` carrying per-department,
versioned policy bundles.

```
standards-bundles/
├── BUNDLE-SCHEMA.md
├── PINS.yaml
└── <dept>/<version>/
    ├── rules.yaml
    ├── envelope.yaml
    ├── reviewers.yaml
    └── README.md
```

Departments at v0.1.0: `architect`, `security`, `privacy`, `finops`.

### rules.yaml

Carries the rules themselves. Each rule has: `id`, `title`, `phi` (bool),
`enforcement` (which surfaces enforce it), `pattern`, `severity`
(BLOCK | WARN | LOG), `rationale`, `test_cases`.

### envelope.yaml

Declares what Pipeline Doctor may auto-fix (within bounds, with preconditions)
and what is forbidden (PHI rules, deny rules).

### reviewers.yaml

Declares the reviewer roster per blast class (HIGH/MED/LOW/AUTO):
`required_approvers`, `must_include_roles`, `can_include_roles`, plus a
people→email map.

### PINS.yaml

Maps `team_id → bundle_version` per department. Allows different teams
to be on different bundle versions during canary rollouts.

### Standards-change agent

A custom agent at `.github/agents/standards-change.agent.md` triggered
on PR open against `standards-bundles/`. Classifies blast class, drafts
ADR, assigns reviewers, blocks merge until quorum.

### Meta ledger entries on bundle merge

When a standards-change PR merges, a `meta` ledger entry is automatically
written. `meta` entries carry the change ticket ID, blast class, reviewers,
bundle version transition, and PR URL.

### Canary rollout

New bundle versions roll out to 5% of teams for 7 days before full rollout.
Pipeline Doctor watches metrics; auto-revert PR opens if regression detected.

## Validation

- Every rule MUST have a unique `id` within its bundle.
- Every rule with `phi: true` is auto-excluded from envelope `allowed_auto_fixes`.
- PINS.yaml entries MUST resolve to an existing `<dept>/<version>/` directory;
  orchestrator refuses startup on unresolvable pin.
- Reviewer roster MUST cover all `must_include_roles` for HIGH blast class
  (validation script `scripts/validate-reviewer-roster.py`).
