## Test 1: mTLS + OAuth 2.0 client_credentials Scope Enforcement on Vendor Connector

**Verifies decision:** "Each vendor connector must authenticate via mutual TLS (client certificate issued by internal PKI) combined with OAuth 2.0 client_credentials grant scoped to read:vitals only."

**Given** a Vendor Connector pod is running with a valid internal PKI client certificate and an OAuth 2.0 token issued with the `read:vitals` scope

**When** a vendor monitor attempts to open a connection to the Vendor Connector Layer presenting (a) a valid PKI cert + `read:vitals` token, (b) a valid PKI cert + a token scoped to `write:vitals`, and (c) no client certificate at all

**Then** case (a) is accepted and data flows to the WebSocket Ingest Gateway; case (b) is rejected at the OAuth scope validation step with a logged authorization failure citing scope mismatch; case (c) is rejected at the TLS handshake layer before any OAuth exchange occurs — the connector pod emits a structured log entry with `auth_failure_reason: missing_client_cert` and no FHIR payload reaches the Raw FHIR Observation Buffer

---

## Test 2: 90-Day Credential Rotation Gate Blocks Expired Vendor Credentials

**Verifies decision:** "Credentials must be rotated every 90 days and reviewed by Security Architecture before activation."

**Given** a Vendor Connector pod whose internal PKI client certificate has a `notAfter` timestamp exactly 91 days in the past, and the credential rotation job has not issued a replacement approved by Security Architecture

**When** the vendor monitor attempts to initiate a mutual TLS handshake with the Vendor Connector Layer using the expired certificate

**Then** the TLS handshake is rejected; the credential rotation job emits a metric `vendor_cert_expired_total{vendor=<name>}` incremented by 1; no OAuth token exchange is attempted; and the connector pod logs a `SECURITY_GATE: cert_expired` event traceable to the Security Architecture review queue

---

## Test 3: RS256 JWT Validation and 15-Minute TTL Enforcement at WebSocket Ingest Gateway

**Verifies decision:** "WebSocket connections (both inbound from monitors and outbound to Cardiology consumer) must present a signed JWT (RS256) in the HTTP Upgrade request Authorization header. Tokens have a 15-minute TTL and are issued by the internal identity provider. Connections are terminated on token expiry and must re-authenticate."

**Given** the WebSocket Ingest Gateway is running and the internal identity provider has issued an RS256-signed JWT with a 15-minute TTL

**When** (a) a vendor monitor sends an HTTP Upgrade request with a valid RS256 JWT in the `Authorization` header, (b) a monitor sends an Upgrade request with a token signed using HS256, and (c) an established WebSocket connection's JWT TTL elapses (simulated by advancing clock past `exp` claim)

**Then** case (a) upgrades successfully and data ingestion begins; case (b) is rejected at the Upgrade step — the gateway returns a `401` with body citing `invalid_token_algorithm` and no WebSocket session is created; case (c) results in the gateway tearing down the active WebSocket connection within one TTL-check interval, emitting a `ws_session_terminated_reason: token_expired` log entry, and requiring the client to present a fresh JWT before reconnection is accepted

---

## Test 4: p95 Ingest Latency SLO Measured at WebSocket Ingest Gateway Boundary

**Verifies decision:** "99.95% monthly uptime; <100ms p95 ingest latency measured at the WebSocket boundary, excluding upstream vendor latency."

**Given** the WebSocket Ingest Gateway is instrumented with a latency histogram metric `ingest_latency_ms` timestamped at the moment a FHIR Observation frame is received at the WebSocket boundary (not at the vendor-side origination timestamp)

**When** a sustained load of representative FHIR Observation messages is injected directly into the WebSocket Ingest Gateway at production-representative throughput for a 10-minute window, with upstream vendor jitter stripped from measurement by using gateway-local receipt timestamps

**Then** the p95 value of `ingest_latency_ms` is below 100 ms; any breach causes an alert `slo_ingest_p95_breach` to fire; the measurement explicitly excludes the delta between vendor origination time and gateway receipt time, confirmed by comparing the two timestamp fields in the metric labels

---

## Test 5: HIPAA Safe Harbor PHI Redaction of All 18 Identifiers at Egress

**Verifies decision:** "At egress, strip or tokenize all 18 HIPAA Safe Harbor identifiers present in FHIR Observation resources, including subject.reference (replace with internal pseudonym token), performer, and any contained Patient resource."

**Given** the Raw FHIR Observation Buffer contains a FHIR Observation resource with all 18 Safe Harbor identifiers populated, including `subject.reference` set to a real patient MRN URI, a `performer` array with a named practitioner reference, and a `contained` Patient resource with name, DOB, and address

**When** the PHI Redaction / Tokenization Service consumes the record and produces the egress-safe payload

**Then** `subject.reference` is replaced with an internal pseudonym token matching the format defined in the redaction manifest; `performer` is either stripped or tokenized per the manifest; the `contained` Patient resource is absent from the egress payload; no raw MRN, name, DOB, geographic data, or other Safe Harbor identifier appears in plaintext; and the service emits a `redaction_manifest_version` label on each processed record so auditors can confirm the Privacy Office-approved manifest version was applied

---

## Test 6: Cardiology Event Bus Allowlist Projection Filter Enforced at Egress

**Verifies decision:** "The API enforces this allowlist as a projection filter at egress. The Privacy Office must produce and sign off on a field-level allowlist specifying exactly which FHIR Observation elements (e.g., valueQuantity, effectiveDateTime, code) the Cardiolo