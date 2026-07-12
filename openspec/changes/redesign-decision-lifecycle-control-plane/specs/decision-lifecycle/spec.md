# Spec delta: enterprise decision lifecycle control plane

## ADDED Requirements

### Requirement: Runtime artifacts MUST derive from live producer evidence

The run UI MUST derive artifact availability from `RunState.events` payloads. It MUST support architecture, test plan, implementation, generated tests, decisions document, and delivery references. The latest non-empty payload for an artifact MUST win.

The UI MUST NOT label an artifact pending when the event stream already contains that artifact.

#### Scenario: live CodeGen output appears without demo fixtures

- **GIVEN** a non-demo run contains a completed CodeGen event with `app_code` and `test_code`
- **WHEN** the operator opens the run artifact panel
- **THEN** the Implementation and Tests artifacts MUST both be available
- **AND** neither artifact MAY be labeled pending

#### Scenario: re-architecture supersedes prior architecture

- **GIVEN** a run contains two completed Architect events with non-empty `architecture` payloads
- **WHEN** the artifacts are projected
- **THEN** the second architecture MUST be displayed
- **AND** the source chronology MUST remain available in diagnostics

### Requirement: Terminal outcomes MUST be actionable

A terminal failed run MUST render a prominent outcome panel before the raw event stream. The panel MUST show the failed stage and reason when available, and MUST offer a recovery action appropriate to the evidence.

Completed stages MUST remain represented as completed, but the stage rail MUST visually identify where execution terminated.

#### Scenario: review policy gate fails

- **GIVEN** Review/Scan emits a failed event with blocker citations
- **AND** the run status becomes failed
- **WHEN** the run page renders
- **THEN** the outcome panel MUST identify Review/Scan as the failed stage
- **AND** MUST surface the blocker evidence or policy references
- **AND** MUST offer inspection/remediation as the next action

#### Scenario: failed status has no failed event

- **GIVEN** a persisted run has status `failed`
- **AND** no event has status `failed`
- **WHEN** the page renders
- **THEN** the UI MUST say failure details are unavailable
- **AND** MUST NOT invent a failed stage or reason

### Requirement: Decisions MUST support URL-addressable run scope

The Decisions registry MUST accept a `run` URL query parameter and pass it to the ledger query. A run page MUST provide a deep link to `/decisions?run=<run_id>`.

URL state MUST only narrow records readable under the authenticated ledger scope. It MUST NOT expand team access.

#### Scenario: operator follows run decision link

- **GIVEN** a run with id `r-123`
- **WHEN** the operator activates `View decisions`
- **THEN** the browser MUST navigate to `/decisions?run=r-123`
- **AND** the ledger query MUST include `run_id=r-123`
- **AND** the UI MUST show the active run scope with a clear action

### Requirement: Delivery MUST write generated tests as executable test artifacts

When CodeGen emits `test_code`, the Deliver stage MUST write that value to `tests/test_main.py`. It MUST NOT write the markdown test plan to that path.

For historical runs without `test_code`, a fallback MAY be used only when it is explicitly identified as a legacy fallback and does not misrepresent markdown as executable Python.

#### Scenario: generated pytest reaches the pull request

- **GIVEN** a CodeGen event with `app_code="APP"` and `test_code="PYTEST"`
- **AND** a Test Plan event with `test_plan="# TEST PLAN"`
- **WHEN** Deliver builds the GitHub file list
- **THEN** `src/main.py` MUST contain `APP`
- **AND** `tests/test_main.py` MUST contain `PYTEST`
- **AND** `# TEST PLAN` MUST NOT be written to `tests/test_main.py`

### Requirement: Decision lifecycle MUST be derived without rewriting audit history

The platform MUST represent each decision through proposed, required, resolved, applied, verified, and learned phases when evidence exists. Missing phases MUST remain absent or unknown. The projection MUST reference source ledger entries, run events, and GitHub records and MUST NOT mutate historical ledger rows.

#### Scenario: decision is resolved but not yet verified

- **GIVEN** a human resolution ledger entry exists
- **AND** no downstream review/check evidence exists
- **WHEN** the lifecycle is projected
- **THEN** `resolved` MUST be present
- **AND** `verified` MUST be absent or unknown
- **AND** the UI MUST NOT imply successful verification

### Requirement: GitHub MUST remain the execution and collaboration backend

The control plane MUST reference GitHub-native agent sessions, branches, commits, pull requests, checks, rulesets, reviews, Actions, and merge outcomes rather than recreating those resources locally.

The differentiated control-plane responsibilities are typed enterprise gates, policy evidence, autonomy envelopes, bounded remediation/escalation, cross-repository posture, and decision-level reporting.

#### Scenario: delivered decision links to GitHub evidence

- **GIVEN** a delivered event contains a real GitHub pull request URL
- **WHEN** the decision lifecycle detail renders
- **THEN** it MUST link to that pull request
- **AND** MUST NOT fabricate a pull request, check, session, or commit reference when one is unavailable

### Requirement: Decisions MUST present a plain-language activity summary for non-specialist leaders

The Decisions registry MUST render a human-readable activity feed above the raw ledger table. Each feed row MUST state, in plain language, what was decided, whether the actor was the agent (autopilot) or a human, and when. The feed MUST distinguish learning events — human teaching signals (feedback, flag, pause) and autopilot reuse of a prior human decision — from ordinary stage decisions, and MUST surface a count of learning events.

The feed MUST NOT require the reader to interpret internal identifiers or state-machine phase codes to understand what happened. Each feed row MUST deep-link to the full decision record, and activating a row MUST expand and reveal that record's rationale, provenance, and evidence.

The feed MUST derive entirely from the same ledger entries shown in the table and MUST NOT invent actors, decisions, or outcomes not present in the ledger.

#### Scenario: leader reads the decision feed without decoding identifiers

- **GIVEN** the ledger contains an agent stage decision and a human teaching signal
- **WHEN** the Decisions page renders the activity feed
- **THEN** the agent decision MUST read as an agent-authored sentence naming the decision
- **AND** the teaching signal MUST be counted as a learning event
- **AND** no row MAY require a raw GUID or phase code to be understood

#### Scenario: feed row drills into the full record

- **GIVEN** an activity feed row for a decision with id `d-1`
- **WHEN** the leader activates that row
- **THEN** the browser location MUST target `#decision-d-1`
- **AND** the corresponding table row MUST expand and scroll into view
- **AND** it MUST reveal that decision's rationale and provenance
