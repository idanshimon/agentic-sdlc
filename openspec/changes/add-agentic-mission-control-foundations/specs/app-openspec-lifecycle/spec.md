## ADDED Requirements

### Requirement: SL-01 Application owned OpenSpec bootstrap
Enabled agent-driven application development MUST initialize or preserve an app-owned OpenSpec workspace using a pinned supported toolchain, install matching workflow instructions and record the app repo/spec root/version separately from the foundation own specifications.

#### Scenario: SL-01-01
- **WHEN** A new app is bootstrapped
- **THEN** its repository contains its own specs/change workflow and agents are instructed to use them before consequential feature work

#### Scenario: SL-01-02
- **WHEN** An existing app already owns an OpenSpec workspace and instructions
- **THEN** bootstrap reuses it through a reviewed compatible diff rather than overwriting it or writing app requirements into the foundation repo

### Requirement: SL-02 Spec task test traceability
Every agent-driven feature or material behavior change MUST bind the approved change/spec revision and requirement/scenario identifiers to eligible tasks, acceptance/test references, agent attempts, PR/commit/build and decision records.

#### Scenario: SL-02-01
- **WHEN** A backlog item lacks an approved change or allowed bug-fix classification and acceptance linkage
- **THEN** unattended implementation remains blocked with the missing linkage identified

#### Scenario: SL-02-02
- **WHEN** A user opens a task in Mission Control
- **THEN** the user can follow its exact app change, scenario, tests, decisions and GitHub implementation evidence

### Requirement: SL-03 Executable application change workflow
The application workflow MUST require the applicable proposal/design/spec/task artifacts and structural validation before material implementation, tests before implementation for new behavior/regressions, and independent verification before task/change completion; no profile may treat green parsing as semantic approval.

#### Scenario: SL-03-01
- **WHEN** A new feature proposal is structurally valid but product acceptance is unapproved
- **THEN** the feature is not eligible for unattended implementation

#### Scenario: SL-03-02
- **WHEN** Implementation exists but required linked tests have not executed successfully
- **THEN** the task and change remain unverified rather than complete

#### Scenario: SL-03-03
- **WHEN** An app selects Simple with agent-driven development
- **THEN** the lightweight OpenSpec/test contract remains active without requiring committee review or enterprise hosting

### Requirement: SL-04 Version invalidation and task completion
The controller MUST revalidate work when app specifications, acceptance or target policy change and must not mark tasks complete from PR creation, model assertions or unrelated CI success.

#### Scenario: SL-04-01
- **WHEN** Acceptance changes while an implementation run is active
- **THEN** affected prior approval/test evidence is invalidated according to compatibility and the task is rechecked before completion

#### Scenario: SL-04-02
- **WHEN** The PR is merged but an app acceptance criterion still fails
- **THEN** implementation/admission may be recorded while acceptance and any claimed resolution remain incomplete

### Requirement: SL-05 Repair classification without process bypass
Incident and bug-fix workflows MUST classify whether the fix restores existing specified behavior or changes the contract, link a regression and decision evidence in either case, and require an app OpenSpec delta for material behavior/policy changes rather than forcing every typo through a heavyweight feature proposal.

#### Scenario: SL-05-01
- **WHEN** A repair restores an already specified attachment-upload behavior
- **THEN** it links the existing scenario and a defect regression using the recorded lightweight fix path

#### Scenario: SL-05-02
- **WHEN** A proposed repair changes who may access attachments or the retention behavior
- **THEN** it requires the relevant app spec/acceptance approval and applicable sensitive-change gate before release

### Requirement: SL-06 Verified spec sync and archive
The application workflow MUST synchronize accepted deltas into canonical app specs and archive completed changes through its supported pinned OpenSpec process only after applicable implementation/acceptance evidence is complete; spec acceptance, merge, deployment and operational recovery must retain distinct statuses.

#### Scenario: SL-06-01
- **WHEN** A completed accepted app change is synchronized and archived
- **THEN** readback confirms canonical app specs reflect the accepted revision and evidence/task links survive archive path changes

#### Scenario: SL-06-02
- **WHEN** A change is incomplete or accepted only by model prose
- **THEN** it is not archived as complete

#### Scenario: SL-06-03
- **WHEN** The app specification is accepted but production rollout has not occurred
- **THEN** spec/implementation acceptance may be shown but production deployment and recovery remain explicitly unverified

