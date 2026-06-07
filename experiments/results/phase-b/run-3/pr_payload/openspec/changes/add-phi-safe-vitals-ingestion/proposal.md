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