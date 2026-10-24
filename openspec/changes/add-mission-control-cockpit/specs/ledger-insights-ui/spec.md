# Spec delta: add-mission-control-cockpit / ledger-insights-ui

## ADDED Requirements

### Requirement: Mission Control cockpit

The dashboard MUST provide a `/mission` route that renders runs, pipeline stages and
agent personas in one orbital view derived only from existing run and ledger records.

#### Scenario: runs are placed by consequence

- **GIVEN** runs with statuses awaiting_gate, failed, running and completed
- **WHEN** the cockpit renders
- **THEN** blocked runs MUST sit on the innermost ring, then failed, then in flight, then done
- **AND** selecting a run MUST show its evidence and link to `/runs/<id>`

#### Scenario: no fabricated attribution

- **GIVEN** a ledger entry whose stage maps to no agent persona
- **WHEN** agent activity is computed
- **THEN** the entry MUST be counted as unattributed and MUST NOT be credited to any agent

### Requirement: Agent roster telemetry

The Agents page MUST show, for each persona, decision count, autonomous share, flagged
count, spend and last activity derived from the ledger, and MUST show an explicit
"no recorded activity" state when the ledger has none for that persona.

#### Scenario: agent without ledger activity

- **GIVEN** no ledger entries attributable to the review-scan persona
- **WHEN** the roster renders
- **THEN** that card MUST state that no activity is recorded instead of showing zeros as measurements

### Requirement: Decisions command deck

All four Decisions views MUST render the same command deck derived from the entries
that view loaded, and MUST attribute each decision to human or agent using the
producer's `confidence_source` when present.

#### Scenario: live row without an actor object

- **GIVEN** a ledger row with no `actor` object and `confidence_source: "human"`
- **WHEN** the deck computes the autonomy split
- **THEN** the row MUST count as a human decision

### Requirement: Derived precedent reuse respects time order

A derived reuse edge MUST NOT be drawn from a human ruling to an autopilot decision
that was created before that ruling.

#### Scenario: autopilot proposal re-decided by a human

- **GIVEN** an autopilot entry and a later human entry on the same card
- **WHEN** the lineage is built
- **THEN** no reuse edge MUST connect them

### Requirement: Motion is presentation-only

Animated surfaces MUST render their final, data-accurate state when the user prefers
reduced motion, and MUST NOT animate data values into a state that differs from the
loaded record.

#### Scenario: reduced motion

- **GIVEN** the operating system requests reduced motion
- **WHEN** a Decisions view loads
- **THEN** counts, bars and graphs MUST render at their final values without animation

### Requirement: Grounded assistant shows what it injected

Every live assistant reply MUST return the grounding record (sources with provenance,
derived facts, withheld count, warnings) that was injected into the model prompt, and the
panel MUST render it beside the reply.

#### Scenario: run-scoped question

- **GIVEN** the operator is on a run detail view
- **WHEN** they ask a question
- **THEN** ledger retrieval MUST be limited to that run's entries before ranking
- **AND** the run itself MUST be included as a source pinned by the view

### Requirement: PHI guard at the model boundary

Ledger and run excerpts MUST be classified before being sent to the model; high-PHI
excerpts MUST NOT be sent, and their count MUST be shown to the operator with the rule
cited. If classification fails, the excerpt MUST be withheld.

#### Scenario: classifier unavailable

- **GIVEN** the PHI classifier errors
- **WHEN** context is prepared
- **THEN** no ledger or run excerpt MUST be included in the prompt

### Requirement: Assistant does not block the page

The assistant panel MUST NOT render a backdrop or blur, and the page behind it MUST
remain interactive while it is open.

#### Scenario: panel open

- **GIVEN** the assistant panel is open
- **WHEN** the operator clicks a row in the page behind it
- **THEN** the click MUST reach the page

### Requirement: Settings degrades honestly against an older orchestrator

The Settings page MUST compose the posture from individual config endpoints when the orchestrator does not serve `GET /api/config/settings` (404). It MUST compose the posture from the individual config endpoints it does serve
(hard-gate classes, bundle pins, repo autonomy, integrations) and MUST say so. A section
with no available source MUST render as unavailable with the reason, never as an empty
"nothing configured" section. Any failure other than 404 MUST render as an error.

#### Scenario: orchestrator predates the combined endpoint

- **GIVEN** the orchestrator returns 404 for `/api/config/settings`
- **WHEN** the operator opens Settings
- **THEN** governance, bundle pins and repo autonomy MUST render from their own endpoints
- **AND** organization and models MUST show "upgrade the orchestrator"
- **AND** a notice MUST state the view was assembled from individual endpoints

#### Scenario: orchestrator unreachable

- **GIVEN** the orchestrator cannot be reached
- **WHEN** the operator opens Settings
- **THEN** the page MUST show an error, not composed or empty sections

### Requirement: About shows real build and backend identity

The Settings page MUST include a low-prominence About tab showing the UI version, commit, build
time, and demo/sign-in mode, plus live reachability of the orchestrator (API version,
endpoint count, latency, whether it predates this UI), the Ledger MCP, and the assistant
model. Values not available MUST show "unknown" or "not recorded"; none may be invented.
Container builds MUST receive the commit as a build argument because the build context
has no git history.

#### Scenario: built in a container

- **GIVEN** the image is built by `scripts/build-ledger-insights-ui.sh`
- **WHEN** the operator opens Settings → About
- **THEN** the commit shown MUST equal the commit the image was built from

### Requirement: Gate decision links to the Decision Map

Each Resolver gate decision toast MUST offer (single card, custom resolution, bulk approve) a "See on map" action that opens `/decisions/graph?run=<id>&card=<id>`. The map
MUST focus the operator's latest human decision for that card, keep that decision, its
run, and the run's other decisions visible regardless of the node budget, and state how
many agent and human decisions it connects to in that run. If the entry has not landed in
the ledger yet, the map MUST say it is waiting and re-read briefly, then say it is not
found. It MUST NOT focus an agent's decision as the operator's.

#### Scenario: operator clicks Use this, then See on map

- **GIVEN** the operator decided a card on the Resolver gate
- **WHEN** they click "See on map" on the toast
- **THEN** the map MUST select their decision and highlight the agents' decisions in the same run
- **AND** a banner MUST give the agent and human decision counts for that run
