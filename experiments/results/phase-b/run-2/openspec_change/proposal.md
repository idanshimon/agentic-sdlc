# Secure Real-Time Vitals Ingestion with PHI De-identification and Vendor Authentication

## Why
The PRD requires a compliant, high-availability pipeline for ingesting patient vitals from third-party vendor connectors while protecting PHI at every boundary. Current architecture lacks standardized de-identification at egress, vendor authentication controls, and formally specified latency and uptime commitments. These gaps create regulatory exposure and operational risk.

## What Changes
- Introduce a deterministic HMAC-SHA256 de-identification layer at egress that replaces FHIR patient/encounter references and removes all 18 HIPAA Safe Harbor identifiers, with a PHI-classified re-identification mapping store
- Mandate mutual TLS plus OAuth 2.0 client_credentials (read:vitals scope) for all vendor connectors, with 90-day certificate rotation and BAA/approval gate
- Enforce WebSocket session termination at 15 minutes of inactivity with short-lived JWT re-authentication and TLS-session-bound tokens
- Adopt 99.95% monthly uptime and <100ms p95 ingest latency SLA measured at the WebSocket boundary, excluding upstream vendor latency
- Define p99 ingest latency as the interval from first TCP/WebSocket data frame at the API gateway NIC to event bus publish acknowledgment, tracked via distributed tracing

## Capabilities
### New Capabilities
- `phi-safe-vitals-ingestion`: End-to-end compliant vitals ingestion pipeline with egress de-identification, vendor mTLS+OAuth authentication, session lifecycle enforcement, and formally bounded latency SLAs

## Impact
- Affected components: API Gateway, Vendor Connector Service, FHIR Egress Processor, Event Bus, PHI Mapping Store, Internal PKI, Session Manager, Distributed Tracing Layer
- Migration: Existing vendor connectors must be re-provisioned with mTLS client certificates and OAuth client_credentials; existing WebSocket sessions must be drained and re-established under new session lifecycle policy; BAA and vendor management approval tickets required before any connector re-activation