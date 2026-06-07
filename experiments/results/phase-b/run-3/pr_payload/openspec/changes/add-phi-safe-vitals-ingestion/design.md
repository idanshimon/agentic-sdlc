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