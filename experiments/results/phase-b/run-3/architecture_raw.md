=== PROPOSAL ===
# Secure Real-Time Vitals Ingestion Pipeline with De-Identification and SLA Enforcement

## Why
Clinicians and downstream analytics systems require a reliable, low-latency stream of patient vitals from vendor devices, but raw FHIR payloads containing PHI cannot be forwarded to the clinical event bus without violating HIPAA Safe Harbor requirements. Vendor connectors currently lack standardized authentication, creating uncontrolled ingestion surface area. A governed ingestion pipeline with enforced de-identification, mutual-TLS plus OAuth authentication, and measurable latency SLAs closes these gaps.

## What Changes
- Introduce a WebSocket ingestion gateway that validates short-lived Bearer tokens before upgrading connections and enforces 99.95% monthly uptime with <100ms p95/p99 ingest latency
- Add an egress de-identification stage that HMAC-SHA256 tokenizes FHIR Observation.subject and Observation.encounter and suppresses all 18 HIPAA Safe Harbor identifiers before publishing to the clinical event bus
- Require all vendor connectors to authenticate via mutual TLS (internal PKI, 90-day rotation, OCSP revocation) combined with OAuth 2.0 client_credentials scoped to `vitals:ingest`
- Instrument the full ingest path with OpenTelemetry distributed tracing; breach of the <100ms p99 gateway-to-bus latency triggers a PagerDuty P2 alert

## Capabilities
### New Capabilities
- `phi-safe-vitals-ingestion`: Real-time vitals ingestion pipeline that de-identifies FHIR payloads, enforces mTLS+OAuth vendor authentication, and guarantees sub-100ms p99 latency from WebSocket frame receipt to clinical event bus acknowledgment

## Impact
- Affected components: API Gateway, Vendor Connector adapters, FHIR Egress Processor, Clinical Event Bus publisher, PKI/Certificate Authority, OAuth Authorization Server, Observability/Tracing pipeline, PagerDuty integration
- Migration: Existing vendor connectors must be re-provisioned with mTLS client certificates from internal PKI and issued new OAuth client_credentials; existing WebSocket sessions must be migrated to token-based upgrade flow; downstream consumers of the clinical event bus must update subject/encounter references to accept HMAC tokens instead of raw patient references


=== DESIGN ===
# Design

## Context
The vitals ingestion service receives real-time device telemetry from multiple third-party vendor connectors over WebSocket connections and forwards structured FHIR Observation resources to an internal clinical event bus consumed by analytics and alerting systems. Currently, no standardized authentication exists for vendor connectors, PHI flows unmodified into the event bus, and latency is neither measured nor bounded. This change introduces a layered security and reliability architecture: authenticated ingestion at the WebSocket boundary, deterministic de-identification at egress, and continuous SLA measurement with automated alerting. The design must satisfy HIPAA Safe Harbor (§164.514(b)(2)) for all data reaching the clinical event bus while preserving referential integrity through stable HMAC tokens.

## Goals
- Enforce mutual TLS plus OAuth 2.0 client_credentials authentication for every vendor connector
- Validate short-lived Bearer tokens on every WebSocket upgrade request and close expired sessions with WS code 4401
- Suppress or tokenize all 18 HIPAA Safe Harbor identifiers before any FHIR payload reaches the clinical event bus
- Achieve 99.95% monthly uptime and <100ms p99 latency from WebSocket frame receipt to event bus publish acknowledgment
- Provide continuous latency observability via OpenTelemetry and automated PagerDuty P2 alerting on SLA breach

## Non-Goals
- Re-identification or reverse-lookup of HMAC tokens by downstream consumers
- End-to-end encryption of the clinical event bus itself (addressed by separate data-at-rest policy)
- Modification of vendor device firmware or proprietary telemetry protocols
- Long-term storage or archival of raw PHI payloads at the gateway layer

## Decisions
1. **HMAC-SHA256 de-identification at egress with rotating secret** — Provides deterministic, reversible-only-with-key tokenization of patient and encounter references while enabling correlation across events; rotating secret limits blast radius of key compromise. (card_id=874e3555)
2. **Mutual TLS + OAuth 2.0 client_credentials for vendor connectors, 90-day cert rotation, OCSP revocation** — Dual-layer authentication ensures both transport-level identity (mTLS) and application-level authorization scope (`vitals:ingest`); OCSP mandatory revocation prevents use of compromised certificates between rotation cycles. (card_id=31a265d7)
3. **99.95% monthly uptime; <100ms p95 ingest latency at WebSocket boundary, excluding upstream vendor latency** — Swap decision preserving user-authored SLA wording; p95 at the WebSocket boundary scopes the SLA to controllable infrastructure, excluding uncontrollable vendor network jitter. (card_id=985ed8cd)
4. **Short-lived 15-minute Bearer token on WebSocket Upgrade, introspection validation, refresh_token grant, WS close 4401 on expiry** — Short TTL limits the window of token misuse; introspection at upgrade time ensures revoked tokens are rejected before the long-lived WebSocket session is established. (card_id=3f59750f)
5. **p99 latency SLA from WebSocket frame receipt to event bus publish ack, measured via OpenTelemetry, PagerDuty P2 on breach** — p99 measurement via distributed tracing provides an objective, auditable SLA signal; P2 severity ensures human response before sustained degradation affects clinical workflows. (card_id=530ad826)

## Risks / Trade-offs
- **Risk**: HMAC secret rotation may cause a brief window where in-flight tokens use the old key while downstream consumers have already adopted the new key — **Mitigation**: Implement a two-key overlap window (old key accepted for one rotation period after rollover) with explicit key version embedded in the token prefix.
- **Risk**: OCSP check latency during mTLS handshake may add measurable overhead to connection establishment — **Mitigation**: Deploy an OCSP stapling cache co-located with the gateway; stapled responses are refreshed every 1 hour, eliminating per-handshake round trips.
- **Risk**: 15-minute Bearer token TTL combined with WebSocket long-lived sessions requires reliable client-side refresh logic; failure to refresh before expiry causes abrupt session termination — **Mitigation**: Gateway sends a WebSocket application-level warning frame at T-2 minutes before token expiry; clients that fail to refresh receive WS close 4401 with a machine-readable reason phrase.
- **Risk**: OpenTelemetry span overhead on every ingest frame could itself contribute to latency — **Mitigation**: Use tail-based sampling at 100% for SLA-breach detection spans and 1% for routine traces; span creation is async and off the critical ingest path.


=== SPEC ===
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