# Spec delta: harden-codegen-governance-quality / review-scan

## ADDED Requirements

### Requirement: PHI cleartext-logging rules MUST be context-scoped
A PHI identifier rule (e.g. security/v0.1.0/PHI-001) MUST flag only cleartext
logging of patient identifiers, not their legitimate use as domain field or
parameter names. Rules MAY declare an optional `context_pattern` (the line must
also match for the rule to fire) and an optional `safe_wrapper_pattern` (the line
is exempt when the identifier is wrapped in a redaction/hash/mask helper). A
violation requires `pattern` AND (`context_pattern` absent or matches) AND NOT
`safe_wrapper_pattern`. The CI enforcement lane and the pipeline review MUST use
one shared matcher so they never disagree.

#### Scenario: cleartext PHI in a log is blocked
- **GIVEN** a bundle with PHI-001 context-scoped to logging sinks
- **WHEN** generated code contains `logger.info(f"patient {mrn} checked")`
- **THEN** review-scan MUST record a PHI-001 blocker on that line
- **AND** delivery MUST be blocked

#### Scenario: legitimate domain field is not blocked
- **GIVEN** the same PHI-001 rule
- **WHEN** generated code declares `patient_id: str = Field(...)` and logs only `logger.info("done", extra={"request_id": rid})`
- **THEN** review-scan MUST produce zero PHI-001 blockers

#### Scenario: redacted logging is exempt
- **GIVEN** the same PHI-001 rule
- **WHEN** generated code logs `logger.info(f"patient {_redact(mrn)} checked")`
- **THEN** the `safe_wrapper_pattern` MUST exempt the line and produce no blocker

### Requirement: Review MUST block generated code that cannot run
Review-scan MUST statically verify that every generated Python file parses and
that every referenced name resolves — at module scope (import-time NameError) and
inside functions (call-time NameError). An undefined name (third party, stdlib,
or typo) that is not a builtin, comprehension local, parameter, or forward
reference to a module-level definition MUST be a BLOCK-severity finding. Delivery
MUST be blocked while any runnability finding exists.

#### Scenario: missing third-party import at module scope
- **GIVEN** a delivered test file using `TestClient(app)` with no `from fastapi.testclient import TestClient`
- **WHEN** review-scan runs
- **THEN** it MUST record a `runnability/v0.1.0/IMPORT-001` blocker at the use site
- **AND** delivery MUST be blocked

#### Scenario: missing stdlib import used at startup
- **GIVEN** a delivered `src/main.py` referencing `os.environ` with no `import os`
- **WHEN** review-scan runs
- **THEN** it MUST record a runnability blocker for `os`

#### Scenario: correct code with all imports passes
- **GIVEN** a file that imports every name it uses and only uses builtins otherwise
- **WHEN** review-scan runs
- **THEN** it MUST produce zero runnability blockers
- **AND** forward references between module-level functions MUST NOT be flagged

### Requirement: Delivered code and tests MUST use the delivered module layout
The codegen prompts MUST target the layout the deliver stage writes: the
implementation delivered as `src/main.py` and tests importing it as
`from main import app`. Generated tests MUST NOT import from a non-existent `app`
module.

#### Scenario: delivered tests import the implementation module
- **GIVEN** the deliver stage writes the implementation to `src/main.py`
- **WHEN** codegen produces the test module
- **THEN** the test module MUST import `from main import app`
- **AND** the delivered suite MUST be collectable with `PYTHONPATH=src pytest tests/`
