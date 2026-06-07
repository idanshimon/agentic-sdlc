## Test 1: Canonical Redaction Manifest Enforced at All Egress Points Including Vendor Connectors

**Verifies decision:** "patient MRN, name, DOB, and device serial number are masked before publishing to the clinical event bus. Cardiology consumers receive a pseudonymous encounter token instead. Redaction applies to ALL egress points including vendor connectors."

**Given** a vendor connector has successfully authenticated via mTLS + OAuth 2.0 `client_credentials` and is publishing a vitals frame containing a real patient MRN, patient name, DOB, and device serial number to the API Gateway WebSocket endpoint

**When** the Redaction & Pseudonymization Service processes the inbound frame and the resulting event is delivered to the clinical event bus and subsequently consumed by a Cardiology consumer subscription

**Then** the event payload received by the Cardiology consumer MUST contain no raw MRN, patient name, DOB, or device serial number fields; a pseudonymous encounter token MUST be present in place of patient identity; and a parallel assertion against the vendor connector egress path MUST confirm those same four fields are absent — any test probe that retrieves the raw values from any egress point constitutes a test failure

---

## Test 2: Vendor Connector mTLS Handshake Rejected Without Valid Internal PKI Certificate

**Verifies decision:** "Each vendor connector must authenticate via mutual TLS (client certificate issued by internal PKI) combined with OAuth 2.0 client_credentials grant scoped to 'vitals:ingest'."

**Given** a simulated vendor connector presents a client certificate issued by an external or self-signed CA (not the internal PKI) during the WebSocket TLS handshake to the API Gateway

**When** the connector attempts to establish the WebSocket connection and subsequently submit a valid OAuth 2.0 `client_credentials` bearer token scoped to `vitals:ingest`

**Then** the API Gateway MUST terminate the TLS handshake before the OAuth token is evaluated; the connection MUST be refused at the mTLS layer; no frame MUST reach the Redaction & Pseudonymization Service; and the API Gateway access log MUST record a certificate validation failure citing the untrusted issuer, with no `vitals:ingest` scope grant recorded

---

## Test 3: OAuth Scope Enforcement — Connector With Valid mTLS But Wrong Scope Is Rejected

**Verifies decision:** "OAuth 2.0 client_credentials grant scoped to 'vitals:ingest'. Certificates rotate every 90 days; revocation via OCSP is mandatory."

**Given** a vendor connector presents a valid internal PKI client certificate (not revoked, within 90-day window) and successfully completes the mTLS handshake, but presents an OAuth 2.0 bearer token whose scope is `vitals:read` rather than `vitals:ingest`

**When** the connector sends a WebSocket frame containing a well-formed vitals payload to the API Gateway

**Then** the API Gateway MUST reject the frame with an OAuth authorization failure; no event MUST be published to the clinical event bus; the OpenTelemetry trace for this request MUST record an authorization error span on the API Gateway component; and no SLA clock timestamp MUST be emitted for the rejected frame

---

## Test 4: OCSP Revocation Check Blocks Connector With Revoked Certificate on Every Handshake

**Verifies decision:** "Certificates rotate every 90 days; revocation via OCSP is mandatory."

**Given** a vendor connector holds an internal PKI client certificate that has been explicitly revoked via OCSP (revocation recorded in the OCSP responder) prior to the connection attempt

**When** the connector initiates a new WebSocket connection to the API Gateway, triggering an OCSP revocation check on the handshake

**Then** the API Gateway MUST consult the OCSP responder during the handshake, receive a `revoked` status, and refuse the connection; the API Gateway MUST NOT cache a prior `good` OCSP response to allow the connection; the access log MUST contain an entry referencing OCSP revocation status `revoked` for the connector's certificate serial number; and no vitals frame MUST reach the clinical event bus

---

## Test 5: p99 Ingest Latency SLA Measured From WebSocket Frame Receipt to Event Bus Publish Acknowledgment

**Verifies decision:** "The <100ms SLA is defined as the p99 latency from the timestamp of WebSocket frame receipt at the API gateway to the event bus publish acknowledgment. Measured via distributed tracing (OpenTelemetry) and reported in 1-minute rolling windows."

**Given** 500 concurrent vendor connectors authenticated via mTLS + `vitals:ingest` scope are streaming vitals frames at a representative production load rate, with the API Gateway stamping each frame with a monotonic receipt timestamp per the SLA clock definition

**When** the load is sustained for 10 minutes and OpenTelemetry distributed traces are collected across the API Gateway → Redaction & Pseudonymization Service → clinical event bus publish path

**Then** the p99 latency computed from the API Gateway WebSocket frame receipt timestamp to the event bus publish acknowledgment span MUST be below 100ms in every 1-minute rolling window reported by OpenTelemetry; the p95 of the same metric MUST also be below 100ms; any 1-minute window breaching the 100ms p99 threshold MUST emit an alert; and vendor-side network latency MUST be excluded from all reported trace spans per the SLA definition

---

## Test 6: Data Access Matrix Filter Enforced in Cardiology Consumer Event Bus Subscription

**Verifies decision:** "The Privacy Office must approve a documented Data Access Matrix specifying exactly which FHIR Observation fields, patient identifiers, and vital sign types the Cardiology consumer may receive. This matrix is enforced as a filter in the event bus subscription configuration."

**Given** the clinical event bus subscription for the Cardiology consumer is configured with the approved Data Access Matrix filter, and an inbound vitals event contains a mix of FHIR Observation 