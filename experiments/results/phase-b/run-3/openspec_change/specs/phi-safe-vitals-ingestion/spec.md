## ADDED Requirements

### Requirement: FHIR Egress De-Identification
The system MUST suppress or tokenize all 18 HIPAA Safe Harbor identifiers (§164.514(b)(2)) present in any FHIR Observation payload, replacing Observation.subject and Observation.encounter with a deterministic HMAC-SHA256 token keyed by a rotating secret, before forwarding any payload to the clinical event bus. [decision: 874e3555]

#### Scenario: Patient reference tokenized at egress
- **WHEN** a FHIR Observation containing a populated Observation.subject patient reference arrives at the egress processor
- **THEN** the egress processor replaces Observation.subject with an HMAC-SHA256 token derived from the patient reference and the current rotating secret, and the raw patient reference does not appear in the published event bus message

#### Scenario: All 18 Safe Harbor identifiers suppressed
- **WHEN** a FHIR Observation payload contains one or more of the 18 HIPAA Safe Harbor identifiers (e.g., name, geographic data, dates, phone numbers, device identifiers)
- **THEN** each such identifier is either removed from the payload or replaced with its HMAC-SHA256 token before the message is published to the clinical event bus, and no raw PHI field is present in the forwarded message

#### Scenario: Payload blocked on de-identification failure
- **WHEN** the egress processor encounters an error during HMAC tokenization or identifier suppression (e.g., missing rotating secret, processing exception)
- **THEN** the payload is not forwarded to the clinical event bus, an error is logged with a non-PHI correlation identifier, and an alert is raised for operator investigation


### Requirement: Vendor Connector Mutual TLS and OAuth Authentication
The system MUST require every vendor connector to authenticate using mutual TLS with a client certificate issued by the internal PKI combined with a valid OAuth 2.0 client_credentials grant scoped to `vitals:ingest`; certificates MUST rotate every 90 days and revocation MUST be enforced via OCSP before any ingest connection is accepted. [decision: 31a265d7]

#### Scenario: Valid mTLS certificate and OAuth token accepted
- **WHEN** a vendor connector presents a current, non-revoked internal-PKI-issued client certificate and a valid OAuth 2.0 access token with scope `vitals:ingest` during connection establishment
- **THEN** the gateway accepts the connection and permits the connector to submit vitals data

#### Scenario: Revoked certificate rejected via OCSP
- **WHEN** a vendor connector presents a client certificate that has been revoked and the OCSP responder returns a revoked status
- **THEN** the gateway terminates the TLS handshake immediately, logs the revocation event with the certificate serial number, and does not permit any data ingestion

#### Scenario: Missing or incorrect OAuth scope rejected
- **WHEN** a vendor connector presents a valid mTLS certificate but an OAuth 2.0 access token that does not include the `vitals:ingest` scope
- **THEN** the gateway rejects the connection with HTTP 403 Forbidden and does not upgrade to an ingest session


### Requirement: WebSocket Ingestion Uptime and Latency SLA
The system MUST achieve 99.95% monthly uptime and maintain p95 ingest latency of less than 100 milliseconds measured at the WebSocket boundary, excluding upstream vendor latency. [decision: 985ed8cd]

#### Scenario: p95 latency within SLA under normal load
- **WHEN** the ingestion gateway is processing vitals frames under normal operating load
- **THEN** the p95 latency from WebSocket frame receipt at the API gateway to confirmed publish acknowledgment from the clinical event bus is less than 100 milliseconds, as measured by the continuous monitoring system

#### Scenario: Monthly uptime target met
- **WHEN** uptime is calculated for any calendar month
- **THEN** the total available time for the WebSocket ingestion service is at or above 99.95% of the total minutes in that month, excluding any pre-approved maintenance windows documented in the change management system


### Requirement: WebSocket Bearer Token Validation and Session Lifecycle
The system MUST validate a short-lived OAuth 2.0 Bearer token with a maximum TTL of 15 minutes presented in the HTTP Upgrade request Authorization header via token introspection before upgrading any WebSocket connection, and MUST close sessions with WebSocket close code 4401 when the token expires without a successful refresh_token grant. [decision: 3f59750f]

#### Scenario: Valid Bearer token accepted and connection upgraded
- **WHEN** a client presents a non-expired OAuth 2.0 Bearer token with a TTL of 15 minutes or less in the Authorization header of an HTTP Upgrade request
- **THEN** the gateway performs token introspection, confirms the token is active, and upgrades the connection to a WebSocket session

#### Scenario: Expired token causes session closure with code 4401
- **WHEN** a WebSocket session's associated Bearer token reaches its expiry time and no successful refresh_token grant has been completed to provide a replacement token
- **THEN** the gateway closes the WebSocket connection with close code 4401 and a machine-readable reason phrase indicating token expiry

#### Scenario: Revoked or invalid token rejected at upgrade
- **WHEN** a client presents a Bearer token that introspection identifies as inactive, revoked, or malformed in the HTTP Upgrade Authorization header
- **THEN** the gateway returns HTTP 401 Unauthorized and does not upgrade the connection to a WebSocket session


### Requirement: Distributed Tracing SLA Measurement and Alerting
The system MUST measure p99 latency continuously from WebSocket frame receipt at the API gateway to confirmed publish acknowledgment from the clinical event bus using OpenTelemetry distributed tracing spans, and MUST trigger a PagerDuty P2 alert when this p99 latency exceeds 100 milliseconds. [decision: 530ad826]

#### Scenario: OpenTelemetry span created for every ingest frame
- **WHEN** the API gateway receives a WebSocket frame containing a vitals payload
- **THEN** an OpenTelemetry trace span is initiated at frame receipt and a child span is closed upon receipt of the publish acknowledgment from the clinical event bus, recording the end-to-end latency for that frame

#### Scenario: PagerDuty P2 alert triggered on p99 breach
- **WHEN** the continuously computed p99 latency from WebSocket frame receipt to event bus publish acknowledgment exceeds 100 milliseconds within any measurement window
- **THEN** the observability system automatically triggers a PagerDuty P2 alert containing the measured p99 value, the measurement window, and a link to the relevant trace data

#### Scenario: Latency within threshold produces no alert
- **WHEN** the p99 latency from WebSocket frame receipt to event bus publish acknowledgment remains at or below 100 milliseconds across all frames in the measurement window
- **THEN** no PagerDuty alert is triggered and the measurement is recorded in the observability dashboard as within SLA