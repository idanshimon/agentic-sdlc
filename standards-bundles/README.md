# Standards Bundles

Per-department versioned policy bundles. The Architect, Security, Privacy, and FinOps
teams each own a bundle. Pipeline reads the pinned bundle version at runtime
(see `PINS.yaml`); changes go through PR + committee review + canary rollout.

See:
- `BUNDLE-SCHEMA.md` for the full schema reference
- `openspec/changes/add-standards-bundles/` for the spec proposal
- `<dept>/v<version>/README.md` for per-bundle rationale

## Layout

```
standards-bundles/
├── BUNDLE-SCHEMA.md       # the schema documentation
├── PINS.yaml              # team_id → bundle_version mapping
├── architect/
│   └── v0.1.0/{rules,envelope,reviewers}.yaml + README.md
├── security/v0.1.0/...
├── privacy/v0.1.0/...
└── finops/v0.1.0/...
```

## Lifecycle

1. **Author:** dept lead opens PR on `<dept>/v<new-version>/` with new rules
2. **Triage:** `standards-change-agent` (`.github/agents/standards-change.agent.md`)
   reads the diff, classifies blast class, drafts ADR, assigns reviewers
3. **Review:** committee approves per `reviewers.yaml` quorum
4. **Merge:** GitHub Actions writes `meta` ledger entry, opens canary PINS PR
5. **Canary:** 5% of teams pinned for 7 days; Pipeline Doctor watches metrics
6. **Promote / Revert:** auto-PR opens to either fully promote or revert

## Hard rules (cannot be overridden by any envelope)

- **PHI rules** (`phi: true`) are NEVER auto-fixed by Pipeline Doctor
- **Deny rules** (`severity: BLOCK` or `rule_pattern: "deny/*"`) are NEVER loosened
- Auto-fix is rate-limited to 5 / department / 7-day window
