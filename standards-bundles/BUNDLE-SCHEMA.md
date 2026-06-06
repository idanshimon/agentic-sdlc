# Bundle schema reference

This is the canonical schema for each `<dept>/v<version>/` directory. All four
bundle types (architect, security, privacy, finops) share this schema.

## Files in every bundle version

| File | Purpose |
|---|---|
| `rules.yaml` | The rules themselves — what the bundle enforces |
| `envelope.yaml` | What Pipeline Doctor may auto-fix (within bounds, with preconditions) |
| `reviewers.yaml` | Who must approve standards-change PRs (per blast class) |
| `README.md` | Rationale, examples, version history |

## rules.yaml

```yaml
metadata:
  bundle: <dept>            # one of: architect | security | privacy | finops
  version: <semver>         # 0.1.0
  authors: ["@team-handle"] # GitHub handles or M365 UPNs
  date: <YYYY-MM-DD>
  description: <one-line summary of what this bundle does>

rules:
  - id: <RULE-ID>            # uppercase, hyphens, unique within bundle
    title: <short title>
    phi: <bool>              # true = NEVER auto-fixable, ever
    enforcement:
      pipeline_stages:       # which orchestrator stages enforce this rule
        - assessor
        - codegen
        - review-scan
      ide_hooks:             # which Copilot hooks enforce this rule (IDE coverage)
        - pre-tool-use
        - post-tool-use
    pattern: <regex or glob>  # optional; pattern to match against tool input
    severity: BLOCK | WARN | LOG
    rationale: <one-sentence reason; cites regulation/policy/precedent>
    test_cases:              # optional but recommended
      - input: <example input>
        expect: BLOCK | PASS
```

### Required fields

- `id` — globally referenced as `<dept>/v<version>/<id>` in `bundle_refs`
- `title`
- `phi`
- `severity`
- `rationale`

### Optional fields

- `enforcement.pipeline_stages` (default: all stages)
- `enforcement.ide_hooks` (default: all hooks)
- `pattern` (only meaningful if the enforcement surface uses pattern matching)
- `test_cases`

## envelope.yaml

```yaml
allowed_auto_fixes:
  - rule_pattern: "<glob over field paths>"  # e.g. "autopilot.threshold.*"
    bounds:
      min: <number>
      max: <number>
      max_delta_per_run: <number>
    requires:
      - drift_signal_present_for_days: <int>
      - phi_class_not_high: true

forbidden:
  - phi: true             # blanket forbid PHI rules (also hard-coded in validator)
  - rule_pattern: "deny/*"

rate_limits:
  max_per_dept_per_window: <int>      # default 5
  window_days: <int>                  # default 7
```

If `allowed_auto_fixes` is empty or missing, the bundle is fully read-only —
Pipeline Doctor can never apply an auto-fix to it. This is the correct default
for `security` and `privacy` bundles.

## reviewers.yaml

```yaml
blast_classes:
  HIGH:
    required_approvers: 3
    must_include_roles: [security_lead, privacy_dpo]
    can_include_roles: [architect_lead, legal]
  MED:
    required_approvers: 2
    must_include_roles: [bundle_owner]
    can_include_roles: [security_lead, architect_lead]
  LOW:
    required_approvers: 1
    must_include_roles: [bundle_owner]
  AUTO:
    required_approvers: 0      # Pipeline Doctor + envelope = no humans

people:
  bundle_owner:
    - "owner@example.com"
  security_lead:
    - "alice@example.com"
    - "bob@example.com"
  privacy_dpo:
    - "carol@example.com"
  architect_lead:
    - "dave@example.com"
  legal:
    - "eve@example.com"
```

Roster is the canonical source. Deployment scripts (`deploy/scripts/`) sync
the YAML to GitHub Teams + the standards-change-agent's reviewer assignment.

## PINS.yaml

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
    privacy: v0.2.0-canary    # canary period
    finops: v0.1.0
  team-radiology:
    # uses defaults
```

Orchestrator refuses to start if any pin is unresolvable. Canary rollouts
are auto-PR'd by the standards-change-agent.

## Bundle reference format

Every `bundle_refs` entry in the ledger uses this format:

```
<dept>/v<version>/<RULE-ID>
```

Examples:
- `security/v0.1.0/PHI-001`
- `finops/v0.1.0/AUTOPILOT-THRESHOLD-AUTH`
- `architect/v0.2.1/ALLOWED-STACKS`

This is what Pipeline Doctor's drift detection groups by, and what
auditors filter on.
