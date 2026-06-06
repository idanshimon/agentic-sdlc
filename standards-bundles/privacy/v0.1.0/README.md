# privacy/v0.1.0

Privacy bundle — HIPAA minimum-necessary, retention windows, consent surfaces,
breach notification, de-identification.

## Why empty envelope

Privacy rules govern legally-binding obligations (HIPAA, state law).
**Pipeline Doctor cannot auto-tune them.** Every change requires the privacy
DPO + legal as required reviewers (HIGH blast class quorum).

## Rule index

| ID | Title | PHI | Severity |
|---|---|---|---|
| HIPAA-MIN-NEC-001 | Minimum-necessary scope on PHI queries | true | BLOCK |
| RETENTION-CLINICAL-001 | Clinical record retention 7y | true | BLOCK |
| RETENTION-OPS-001 | Ops logs 3y; pruned after | false | BLOCK |
| CONSENT-DISPLAY-001 | Consent surface before non-treatment data use | true | BLOCK |
| BREACH-NOTIFY-001 | Breach notification path documented | true | BLOCK |
| DEIDENT-EXPERT-001 | Expert-determination de-id citation | true | WARN |

## Reference path format

`privacy/v0.1.0/<rule-id>`
