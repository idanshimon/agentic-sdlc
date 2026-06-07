## Test 1: HIPAA §164.514(b)(2) Egress Redaction — All 18 Identifiers Removed Before Clinical Event Bus Publication

**Verifies decision:** "Egress redaction must remove or tokenize all 18 identifiers defined in HIPAA §164.514(b)(2), including patient name, MRN, device serial number, and geographic data finer than state, before events are published to the clinical event bus consumer."

**Given** a synthetic device telemetry event is constructed containing all 18 HIPAA §164.514(b)(2) identifiers, including patient name, MRN, device serial number, ZIP code (5-digit), and date of birth, and the Vendor Gateway and WebSocket Ingest Layer have accepted the event into the pipeline

**When** the event is published to the clinical event bus and a subscribed consumer reads the delivered message payload

**Then** the consumed event must contain zero occurrences of patient name, MRN, or device serial number in any field; geographic data must be coarsened to state-level only (no ZIP, city, or county); all remaining direct identifiers must be replaced with tokenized surrogates; a structured audit log entry must record the redaction action referencing the originating event ID — any event that carries a raw identifier value must cause the test to fail

---

## Test 2: Vendor Connector mTLS + OAuth 2.0 client_credentials Enforcement at the Vendor Gateway

**Verifies decision:** "Each approved vendor connector must authenticate via mTLS (client certificate issued by internal PKI) combined with OAuth 2.0 client_credentials grant scoped to the specific device fleet. Unapproved connectors are rejected at the gateway with HTTP 403 and logged to SIEM."

**Given** three connector configurations are prepared: (A) a valid internal PKI client certificate paired with a valid `client_credentials` token scoped to the correct device fleet, (B) a valid PKI certificate paired with a token scoped to a *different* device fleet, and (C) a self-signed certificate not issued by the internal PKI

**When** each connector attempts to establish a connection through the Vendor Gateway

**Then** connector A is admitted and data flows into the WebSocket Ingest Layer; connectors B and C each receive HTTP 403 from the Vendor Gateway within 500ms; within 5 seconds of each rejection the SIEM receives a structured log entry containing the connector identity, rejection reason, and timestamp — absence of the SIEM entry for either rejected connector constitutes a test failure

---

## Test 3: WebSocket JWT RS256 Authentication on HTTP Upgrade Request

**Verifies decision:** "WebSocket connections must present a signed JWT (RS256, issued by the internal IdP) in the HTTP Upgrade request Authorization header."

**Given** the WebSocket Ingest Layer is running and three upgrade requests are prepared: (A) a valid RS256 JWT issued by the internal IdP in the `Authorization` header, (B) an HS256-signed token in the `Authorization` header, and (C) an HTTP Upgrade request with no `Authorization` header

**When** each upgrade request is submitted to the WebSocket Ingest Layer

**Then** request A completes the WebSocket handshake successfully; requests B and C are rejected before the handshake completes — the Ingest Layer must not emit a WebSocket 101 response for B or C, and the connection must not enter an open state; the rejection for B and C must be observable in the Ingest Layer access log with a distinct authentication-failure reason code

---

## Test 4: WebSocket Session Re-Authentication and 1008 Termination on Refresh Failure

**Verifies decision:** "Sessions exceeding 15 minutes must re-authenticate using a short-lived refresh token; failure to re-authenticate within 30 seconds of expiry results in connection termination and event 1008 (Policy Violation)."

**Given** a WebSocket connection is established with a valid RS256 JWT whose expiry is set to T+15 minutes, and the session watchdog in the WebSocket Ingest Layer is active

**When** the JWT approaches expiry and the client deliberately does not respond to the refresh token challenge within the 30-second re-authentication window

**Then** the WebSocket Ingest Layer must close the connection with WebSocket close code 1008 (Policy Violation) no later than T+15m+30s; the close frame must carry the code 1008 and not any other close code; a session-termination event must appear in the Ingest Layer audit log referencing the session ID and the reason "re-authentication timeout"; no further events from that session must be delivered to the clinical event bus after the close frame is sent

---

## Test 5: Cardiology Subscription Filter — Encounter.serviceType and Field Restriction

**Verifies decision:** "The event bus subscription for Cardiology must be filtered to FHIR Observations linked to patients with an active Cardiology encounter (Encounter.serviceType = cardiology). Delivered fields are limited to: Observation.code, Observation.value, Observation.effectiveDateTime, and a pseudonymized subject token. Subject demographics are excluded."

**Given** the clinical event bus has an active Cardiology subscription, and three FHIR Observation events are published: (A) an Observation linked to a patient with `Encounter.serviceType = cardiology` (active encounter), (B) an Observation linked to a patient with `Encounter.serviceType = orthopedics` (active encounter), and (C) an Observation linked to a patient with `Encounter.serviceType = cardiology` but a *discharged* (inactive) encounter

**When** the Cardiology subscription consumer reads all delivered messages

**Then** only event A is delivered to the Cardiology consumer; events B and C must not appear in the Cardiology consumer's message queue; the delivered payload for event A must contain exactly the fields `Observation.code`, `Observation.value`, `Observation.effectiveDateTime`, and a pseudonymized subject token — any presence of subject name, date of birth, MRN, or any other demographic field in the delivered payload constitutes a test failur