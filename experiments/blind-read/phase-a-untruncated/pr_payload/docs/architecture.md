# Solution Architecture: Vendor Vitals Ingest Platform

## Components & Data Flow

- **Vendor Connector Gateway (VCG):** Terminates all inbound vendor connections. Enforces dual-layer auth — mTLS certificate validation (vendor-issued, 90-day rotation, catalog-checked) AND OAuth 2.0 client-credentials token scoped to `vitals:ingest` before any data is accepted. *(Decision: mTLS + OAuth dual-auth)*

- **WebSocket Ingest Layer:** Accepts FHIR Observation streams over WebSocket. Validates RS256 JWT (15-min expiry) on HTTP Upgrade; enforces sub-protocol token refresh heartbeat; hard-terminates connections where token has been expired >30 seconds without refresh. Latency SLO of <100ms p95 is measured at this boundary via embedded timing middleware. *(Decisions: WebSocket JWT auth; p95 latency SLO)*

- **Service Catalog & Certificate Registry:** Authoritative store of registered vendor certificates and OAuth client IDs. VCG performs a synchronous catalog lookup at connection establishment; unregistered certificates are rejected before TLS handshake completes. Rotation expiry triggers automated alerts at T-14 days. *(Decision: mTLS + catalog registration)*

- **PHI Redaction Pipeline:** Inline, pre-egress tokenization service. Applies HMAC-SHA256 pseudonymization to `subject.reference`, `performer`, `encounter.reference`, and `device.identifier`. Runs a full 18-identifier Safe Harbor scan across every FHIR Observation field using a policy engine backed by the canonical data dictionary. Redaction is synchronous and blocking — no data exits without a redaction receipt. *(Decision: canonical redaction manifest)*

- **Canonical Data Dictionary Service:** Versioned registry documenting every FHIR Observation field, its Safe Harbor evaluation result, and tokenization disposition. Updated on schema change via CI gate; serves as the compliance audit artifact. *(Decision: redaction manifest / HIPAA §164.514(b)(2))*

- **Downstream FHIR Store / Event Bus:** Receives only post-redaction, tokenized Observations. Separated from the ingest path by the redaction pipeline to enforce a hard PHI boundary. Internal consumers subscribe via the event bus; no raw PHI traverses this segment. *(Decision: redaction manifest egress rule)*

## Security & PHI Handling

- **Zero-Trust Auth Chain:** Every inbound connection must satisfy mTLS + OAuth token + JWT in strict sequence. Failure at any layer drops the connection with a structured error log (no PHI in error payloads). HMAC keys for pseudonymization are stored in a dedicated HSM-backed secrets manager, rotated independently of certificates. *(Decisions: mTLS/OAuth; WebSocket JWT)*

- **Token Refresh Enforcement:** Server-side refresh watchdog runs per-connection; emits a `token_expiry_warning` sub-protocol message at T-60 seconds; escalates to connection termination at T+30 seconds post-expiry. State is tracked in an in-memory session store (Redis with TTL) co-located with the WebSocket layer to avoid cross-service latency. *(Decision: WebSocket JWT refresh)*

## Scale Assumptions

- **Ingest Layer Sizing:** Horizontally scaled WebSocket pods behind a Layer-4 load balancer (sticky sessions per vendor connection). Autoscaling triggered at 70% CPU/connection saturation. Redaction pipeline scales independently as a sidecar-adjacent service to keep the ingest-to-redaction hop sub-millisecond and protect the p95 budget. *(Decision: <100ms p95 at WebSocket boundary)*

## Observability & SLO Enforcement

- **SLO Instrumentation:** Rolling 30-day uptime window tracked via synthetic probes (1-minute interval) and real-user WebSocket connection success rates. Prometheus + Grafana dashboards surface error budget burn rate in real time. Planned maintenance is flagged in a maintenance calendar API; probe results during pre-announced windows (≥72h notice, ≤60 min/month) are excluded from SLO calculation automatically. *(Decision: 99.95% uptime definition)*

- **Automated Incident Response:** A burn-rate alert fires at 2× budget consumption rate (fast-burn) and 5% budget consumed in 1 hour (slow-burn), both routing to PagerDuty as P1. Runbooks are linked directly in the alert payload. Certificate expiry, failed catalog lookups, and redaction pipeline failures each have dedicated alert channels to prevent P1 noise conflation. *(Decision: 99.95% uptime; PagerDuty P1 trigger)*