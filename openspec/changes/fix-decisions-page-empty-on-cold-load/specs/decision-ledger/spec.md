## MODIFIED Requirements

### Requirement: ledger.query input schema

The `ledger.query` MCP tool MUST accept requests where `team_id` is omitted; the schema validator MUST NOT reject the request on the basis of `team_id` alone. When `team_id` is omitted, the handler defaults it to the authed team. When `team_id` is provided explicitly, the handler MUST reject the request with HTTP 400 if it does not match the bearer token's bound team.

#### Scenario: caller omits team_id, request succeeds

- **GIVEN** a bearer token bound to `team-cardiology`
- **WHEN** the caller invokes `POST /tools/ledger.query` with body `{}`
- **THEN** the request MUST succeed with HTTP 200
- **AND** `queryEntries` MUST be invoked with `team_id: "team-cardiology"` (the authed team)

#### Scenario: caller passes matching team_id, request succeeds

- **GIVEN** a bearer token bound to `team-cardiology`
- **WHEN** the caller invokes `POST /tools/ledger.query` with body `{"team_id":"team-cardiology"}`
- **THEN** the request MUST succeed with HTTP 200

#### Scenario: caller passes mismatched team_id, request rejected

- **GIVEN** a bearer token bound to `team-cardiology`
- **WHEN** the caller invokes `POST /tools/ledger.query` with body `{"team_id":"team-radiology"}`
- **THEN** the request MUST fail with HTTP 400
- **AND** the error message MUST identify both the authed team and the requested team

#### Scenario: caller passes invalid limit, request rejected

- **WHEN** the caller invokes `ledger.query` with `limit: 500`
- **THEN** the request MUST fail at schema validation (`limit` exceeds max 200)

### Requirement: ledger.query MCP tool descriptor

The `ledger.query` tool descriptor exposed via `GET /tools` MUST declare `inputSchema.required = []` (no required fields). MCP clients (Copilot CLI, VS Code MCP) discover tool surfaces via this descriptor; declaring `team_id` as required would force every client to know the team, defeating the per-token tenancy model.

#### Scenario: tool descriptor reflects optional team_id

- **WHEN** a client invokes `GET /tools`
- **THEN** the entry for `ledger.query` MUST have `inputSchema.required` equal to the empty array `[]`
- **AND** the entry's `description` MUST mention that `team_id` defaults to the authed team when omitted
