# security/v0.1.0

Security bundle — PHI handling, secret management, SBOM, authentication.

## Why empty envelope

By design. **No security rule is ever auto-fixed by Pipeline Doctor.** Every
change goes through committee review. PHI rules carry an additional hard-coded
block in `envelope_validator.py` (defense in depth: even if an envelope is
mis-edited to permit PHI fixes, the validator refuses).

## Rule index

| ID | Title | PHI |
|---|---|---|
| PHI-001 | Patient identifiers may not appear in cleartext logs | true |
| PHI-002 | PHI in transit must be TLS 1.2+ | true |
| PHI-003 | PHI at rest must be encrypted with CMK | true |
| PHI-004 | De-identification before analytics export | true |
| PHI-005 | Audit log retention 7 years for PHI access events | true |
| SECRET-001 | No service-principal secrets in source code | false |
| SECRET-002 | Connection strings must use Managed Identity | false |
| SBOM-001 | All container images must produce an SBOM at build time | false |
| AUTH-001 | Authentication policy must be explicitly resolved before codegen | false |

## Reference path format

`security/v0.1.0/<rule-id>` — used in `bundle_refs` on ledger entries.

Examples:
- `security/v0.1.0/PHI-001`
- `security/v0.1.0/SECRET-001`

## Context-scoped rule matching

Pattern rules support three fields so a rule can express its true intent
declaratively (matched identically by the CI lane `enforce_bundles.scan_file`
and the pipeline `review_verdict._scan_text` — one matcher, no drift):

| Field | Meaning |
|---|---|
| `pattern` | The primary token/shape that must appear on a line (required). |
| `context_pattern` | Optional. The line must ALSO match this for the rule to fire. |
| `safe_wrapper_pattern` | Optional. If the line matches this, it is EXEMPT even when `pattern` + `context_pattern` match. |

A line violates iff: `pattern` **AND** (`context_pattern` absent or matches)
**AND NOT** `safe_wrapper_pattern`.

**PHI-001** uses all three so it flags *cleartext logging* of patient
identifiers — its actual HIPAA intent — without blocking the legitimate use of
those identifiers as domain field/param names (a real eligibility service must
name a `patient_id` field). It fires on `logger.info(f'patient {mrn}')` but
passes `patient_id: str = Field(...)`, `def check(mrn)`, and redacted logging
such as `logger.info(f'{_redact(mrn)}')` / `patient_id_redacted()`. The rule's
own `test_cases` block is enforced as a contract by
`tests/test_phi001_context_scoped.py`.

