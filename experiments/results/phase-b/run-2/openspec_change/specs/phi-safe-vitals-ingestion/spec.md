## ADDED Requirements

### Requirement: FHIR Egress PHI De-identification
The system MUST replace FHIR Observation.subject.reference and Observation.encounter.reference with a deterministic HMAC-SHA256 token keyed per-deployment, and MUST remove all 18 HIPAA Safe Harbor identifiers from the resource before any egress event is published. [decision: 0be92de1]

#### Scenario: Patient and encounter references are tokenized at egress
- **WHEN** a FHIR Observation resource containing Observation.subject.reference and Observation.encounter.reference is processed by the egress layer
- **THEN** both references are replaced with deterministic HMAC-SHA256 tokens and the original values are stored only in the PHI-classified mapping store, not in the published event

#### Scenario: Safe Harbor identifiers are stripped before publish
- **WHEN** a FHIR Observation resource containing any of the 18 HIPAA Safe Harbor identifiers (e.g., patient name, date of birth, geographic data below state level) reaches the egress processor
- **THEN** all such identifiers are removed from the resource prior to event bus publication and the published event contains no Safe Harbor PHI fields

### Requirement: PHI Mapping Store Access Control
The system MUST restrict read and write access to the re-identification mapping table to authorized re-identification workflows only, enforced by PHI-classified store access policy. [decision: 0be92de1]

#### Scenario: Unauthorized service attempts to read mapping table
- **WHEN** a service without an authorized re-identification role attempts to query the PHI mapping store
- **THEN** the request is denied with an authorization error and an audit log entry is created

#### Scenario: Authorized re-identification workflow reads mapping table
- **WHEN** a service holding a valid authorized re-identification credential queries the PHI mapping store for a token
- **THEN** the original PHI reference is returned and the access event is recorded in the audit log

### Requirement: Vendor Connector Mutual TLS and OAuth Authentication
The system MUST require all vendor connectors to authenticate using mutual TLS with a client certificate issued by the internal PKI combined with an OAuth 2.0 client_credentials grant scoped to read:vitals before any data connection is accepted. [decision: 8035279b]

#### Scenario: Connector presents valid mTLS certificate and OAuth token
- **WHEN** a vendor connector presents a valid internal-PKI-issued client certificate and a valid OAuth 2.0 client_credentials token scoped to read:vitals
- **THEN** the connection is accepted and data ingestion is permitted

#### Scenario: Connector presents expired or missing client certificate
- **WHEN** a vendor connector attempts to connect with an expired, revoked, or absent client certificate
- **THEN** the TLS handshake is terminated, the connection is rejected, and the failure is logged with the connector identity

### Requirement: Vendor Connector Certificate Rotation
The system MUST enforce rotation of vendor connector client certificates every 90 days, and MUST prevent any connector from operating beyond its certificate validity period. [decision: 8035279b]

#### Scenario: Certificate approaches 90-day expiry
- **WHEN** a vendor connector's client certificate is within 30 days of its 90-day expiry
- **THEN** the system emits a rotation alert to the connector operator and the internal PKI initiates issuance of a replacement certificate

#### Scenario: Certificate validity period is exceeded
- **WHEN** a vendor connector presents a client certificate whose validity period has elapsed
- **THEN** the connection is rejected and the connector is marked inactive until a new certificate is provisioned

### Requirement: Vendor Connector BAA and Approval Gate
The system MUST prevent activation of any vendor connector unless a signed Business Associate Agreement and a vendor management approval ticket are on record for that connector. [decision: 8035279b]

#### Scenario: Connector activation attempted without signed BAA
- **WHEN** an operator attempts to activate a vendor connector that has no signed BAA on record
- **THEN** the activation is blocked, an error referencing the missing BAA is returned, and no data connection is permitted

#### Scenario: Connector activation with all prerequisites satisfied
- **WHEN** a vendor connector has a signed BAA and a vendor management approval ticket on record and presents valid mTLS and OAuth credentials
- **THEN** the connector is activated and data ingestion is permitted

### Requirement: WebSocket Session Inactivity Timeout
The system MUST terminate any WebSocket session carrying PHI after 15 minutes of no data frames, and MUST require client re-authentication via a short-lived JWT with a maximum 15-minute expiry before a new session is established. [decision: 36cffec4]

#### Scenario: Session reaches 15-minute inactivity threshold
- **WHEN** a WebSocket session carrying PHI has received no data frames for 15 consecutive minutes
- **THEN** the server closes the WebSocket connection and the session token is invalidated

#### Scenario: Client reconnects after session termination
- **WHEN** a client attempts to re-establish a WebSocket session after inactivity-based termination
- **THEN** the client must present a valid short-lived JWT with an expiry of no more than 15 minutes, and the new session token is bound to the new TLS session ID before data frames are accepted

### Requirement: WebSocket Session Token TLS Binding
The system MUST bind each WebSocket session token to the originating TLS session ID, and MUST reject any session token presented over a TLS session with a non-matching session ID. [decision: 36cffec4]

#### Scenario: Session token presented on correct TLS session
- **WHEN** a client presents a WebSocket session token over the same TLS session to which it was bound
- **THEN** the session is accepted and data frames are processed normally

#### Scenario: Session token presented on mismatched TLS session
- **WHEN** a client presents a WebSocket session token over a TLS session whose ID does not match the token's bound session ID
- **THEN** the session is rejected, the token is invalidated, and the event is recorded in the security audit log

### Requirement: Ingest Latency and Uptime SLA
The system MUST achieve 99.95% monthly uptime and a p95 ingest latency of less than 100ms measured at the WebSocket boundary, excluding upstream vendor latency. [decision: c48f7fbe]

#### Scenario: Monthly uptime is calculated
- **WHEN** the monthly uptime of the WebSocket ingest endpoint is computed
- **THEN** the result must be greater than or equal to 99.95%, with vendor-caused outages excluded from the calculation

#### Scenario: p95 ingest latency is measured under normal load
- **WHEN** ingest latency is sampled continuously at the WebSocket boundary under normal operating conditions
- **THEN** the 95th percentile latency must be less than 100ms, with upstream vendor network transit time excluded from the measurement

### Requirement: P99 Ingest Latency Measurement via Distributed Tracing
The system MUST measure p99 ingest latency as the interval from the timestamp of the first TCP/WebSocket data frame received at the API gateway's network interface to the event bus publish acknowledgment, continuously via distributed tracing, and MUST track vendor network transit time separately as a vendor SLA metric. [decision: 68b81a47]

#### Scenario: Distributed trace captures full ingest span
- **WHEN** a data frame is received at the API gateway's network interface
- **THEN** a distributed trace span is opened at that instant and closed upon event bus publish acknowledgment, with the resulting latency recorded against the p99 SLA bucket

#### Scenario: Vendor network transit time is attributed separately
- **WHEN** a distributed trace includes timing data for vendor network transit (time from vendor send to API gateway NIC receipt)
- **THEN** that duration is recorded as a vendor SLA metric in a separate telemetry stream and is not included in the internal p99 ingest latency calculation