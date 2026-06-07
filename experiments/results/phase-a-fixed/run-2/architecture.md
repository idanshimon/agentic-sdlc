# Solution Architecture: Clinical Device Event Ingestion & Distribution Platform

---

## Components & Data Flow

- **1. Vendor Gateway (mTLS + OAuth 2.0 Termination Point)**
Validates every inbound connector against an internal PKI-issued client certificate AND verifies an OAuth 2.0 `client_credentials` token scoped to the specific device fleet before any data enters the pipeline. Unapproved connectors receive HTTP 403 immediately; the rejection event is forwarded synchronously to the SIEM. *(Decision: vendor authentication + SIEM logging)*

- **2. WebSocket Ingest Layer (JWT-Authenticated, Latency-Bounded)**
Accepts device telemetry over persistent WebSocket connections. Each connection must present a signed RS256 JWT in the `Authorization` header of the HTTP Upgrade request. A session watchdog enforces the 15-minute re-authentication window: at T−30s before expiry the client is challenged for a refresh token; failure triggers graceful close with WebSocket status 1008 (Policy Violation). This layer is horizontally scaled to sustain <100ms p95 ingest latency at the WebSocket boundary under peak fleet load. *(Decisions: WebSocket JWT auth + 99.95% uptime / <100ms p95 SLA)*

- **3. 