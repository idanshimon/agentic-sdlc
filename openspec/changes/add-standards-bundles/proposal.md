# Proposal: add Standards Bundles plane

> **Status:** DRAFT
> **Capability:** standards-bundles
> **Related:** master-v07-four-plane-architecture, add-pipeline-doctor

## Why

In v0.6, department standards (Architect, Security, Privacy, FinOps) lived as
scattered prompts inside individual stage agents and APIM policies. There
was no:

- **Versioning** — a rule change was a code edit, not a Policy PR.
- **Authorship** — no clear "Privacy owns PHI rules; Architect can't unilaterally change them."
- **Committee review** — no blast-radius routing, no required reviewer roster.
- **Canary rollout** — a rule change went live for everyone the moment it shipped.
- **Rollback** — no way to pin "team X uses bundle v2.4.0 while team Y stays on v2.3.5."

The v0.7 standards-bundles plane fixes all five.

## What changes

A new top-level directory `standards-bundles/` with the following structure:

```
standards-bundles/
├── BUNDLE-SCHEMA.md           # the schema documentation
├── PINS.yaml                  # team_id → bundle_version pinning
├── architect/
│   └── v0.1.0/
│       ├── rules.yaml         # the rules themselves
│       ├── envelope.yaml      # what Pipeline Doctor may auto-fix
│       ├── reviewers.yaml     # blast-class → reviewer roster
│       └── README.md          # rationale, examples
├── security/v0.1.0/...
├── privacy/v0.1.0/...
└── finops/v0.1.0/...
```

### rules.yaml schema

```yaml
metadata:
  bundle: security
  version: 0.1.0
  authors: ["@security-leadership"]
  date: 2026-06-05

rules:
  - id: PHI-001
    title: Patient identifiers may not be logged in cleartext
    phi: true                         # marks rule as PHI-class
    enforcement:
      pipeline_stages: [codegen, review-scan]
      ide_hooks: [pre-tool-use]
    pattern: "MRN|DOB|SSN|patient_id"
    severity: BLOCK                   # BLOCK | WARN | LOG
    rationale: HIPAA Safe Harbor; logs are persistent and accessible to ops.
    test_cases:
      - input: "logger.info(f'patient {mrn} updated')"
        expect: BLOCK
      - input: "logger.info(f'patient {patient_id_redacted()} updated')"
        expect: PASS
```

### envelope.yaml schema

See `add-pipeline-doctor/proposal.md` — declares what the Doctor may auto-fix.
Critical: `phi: true` rules can NEVER be in `allowed_auto_fixes` (validator
hard-blocks even if accidentally configured).

### reviewers.yaml schema

```yaml
blast_classes:
  HIGH:                 # PHI / privacy / security-critical
    required_approvers: 3
    must_include_roles: [security_lead, privacy_dpo]
    can_include_roles: [architect_lead, legal]
  MED:
    required_approvers: 2
    must_include_roles: [security_lead]
    can_include_roles: [architect_lead, finops_lead]
  LOW:                  # style, heuristic tuning
    required_approvers: 1
    must_include_roles: [bundle_owner]
  AUTO:                 # within envelope, no human approval
    required_approvers: 0

people:
  security_lead:
    - "alice@example.com"
    - "bob@example.com"
  privacy_dpo:
    - "carol@example.com"
  # ... etc
```

### PINS.yaml schema

```yaml
defaults:
  architect: v0.1.0
  security: v0.1.0
  privacy: v0.1.0
  finops: v0.1.0

teams:
  team-cardiology:
    architect: v0.1.0
    security: v0.1.0
    privacy: v0.1.0  # canary: v0.2.0-beta1 (5%)
    finops: v0.1.0
  team-radiology:
    # uses defaults
```

### Standards-change agent

A new custom agent at `.github/agents/standards-change.agent.md`. Triggered
on PR-open against `standards-bundles/`. Responsibilities:

1. **Classify blast class.** Read the diff, check rule properties.
   PHI rule changes → HIGH. Threshold tuning → LOW. Pattern changes → MED.
2. **Draft an ADR.** Template at `.github/agents/templates/adr.md.j2`.
3. **Assign reviewers.** Read `reviewers.yaml`, assign N approvers per blast class.
4. **Block merge** until required approvers + role-coverage met. Implementation:
   GitHub branch protection rule with custom check.
5. **On merge:** write a `meta` ledger entry. Bump bundle version (semver auto-incremented
   per blast class: HIGH → minor, MED/LOW → patch). Trigger canary rollout via PINS.yaml PR.

### Canary rollout

When a new bundle version merges:

1. PINS.yaml is auto-PR'd to set 5% of teams to the new version.
2. After 7 days, if Pipeline Doctor reports no regression spikes, full rollout PR is opened.
3. If regression: auto-revert PR opens, original version restored.

## Why this design

**Per-department repos** are the production target, but v0.7 demo ships
bundles in-repo for ergonomics. `docs/STANDARDS-BUNDLES-DEPLOYMENT.md`
documents the per-repo split for production.

**Versions are immutable directories**, not git tags. Reason: PINS.yaml
references must be unambiguous. `v0.1.0` always means the file tree under
`standards-bundles/security/v0.1.0/`. A new version is a new directory,
not a tag move.

**Reviewer roster is in YAML, not GitHub team.** Reason: cross-tenant
deployments may have different identity providers. The YAML is the canonical
roster; deployment scripts sync it to GitHub Teams on bootstrap.

## Migration

v0.6 had no bundle plane. Initial v0.7 ships with reference bundles for
all four departments at v0.1.0. Pipeline reads from PINS.yaml; if a team
isn't pinned, it falls back to `defaults`.

## Risks and rollback

| Risk | Mitigation | Rollback |
|---|---|---|
| Bundle version mismatch crashes pipeline | Strict version validation at orchestrator startup; pipeline refuses to start with unresolved pins | Pin all teams back to last-known-good version |
| Canary rollout regresses prod team | Pipeline Doctor watches metrics during 7d canary period; auto-revert PR opens at threshold | Revert PINS.yaml change manually |
| Committee dispute deadlocks PR | `required_approvers` are minimums, not requirements that all named reviewers approve; doc'd escalation path | Escalation to bundle owner via standards-change-agent's escalation hook |

## Test targets

- Unit: schema validation for rules/envelope/reviewers/PINS YAMLs
- Integration: standards-change-agent on synthetic PR → correct blast classification + reviewer assignment
- E2E: PR opens → agent comments + assigns → simulate approvals → merge → meta ledger entry written + version bump + canary PR opened
