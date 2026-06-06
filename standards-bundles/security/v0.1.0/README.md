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
