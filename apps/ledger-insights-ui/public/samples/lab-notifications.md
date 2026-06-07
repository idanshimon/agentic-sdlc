# Lab Result Notification Service

## Goal
Build a service that pushes new lab results to ordering clinicians within
5 minutes of result availability, using HL7 v2 ORU messages as the inbound
trigger.

## Requirements

1. Subscribe to the EHR's HL7 v2 ORU^R01 outbound feed via MLLP over TLS.
   Acknowledge receipt with ACK^R01 within 250ms.
2. Parse the OBR-7 (observation date), PID-3 (patient identifier), and OBX-5
   (result value) segments. Reject messages with malformed required segments
   and forward the raw payload to a dead-letter Service Bus topic for human
   triage.
3. Match the ordering clinician using OBR-16 (ordering provider ID). Resolve
   the provider's notification preference (Teams, secure SMS, in-EHR inbox)
   from the provider directory.
4. Critical-value results (flagged with OBX-8 in {AA, HH, LL}) must trigger
   an additional escalation: page the on-call clinician for the patient's
   primary service line if the ordering clinician does not acknowledge
   within 10 minutes.
5. Every notification attempt — success, failure, retry — must write an audit
   row to the message ledger. PHI (patient name, MRN, result value) must
   remain in the audit row for HIPAA traceability but MUST be encrypted at
   rest with the cardiology-specific KEK.
6. Service must process 1000 ORU/sec at peak (Mondays 06:00-09:00).
   p99 end-to-end latency under 5s including notification delivery.
7. Multi-region active-active across East US 2 and West US 3. Cross-region
   replication of the notification ledger is required for audit continuity
   during a regional failover.

## Out of scope
- Notifying patients directly (clinician-facing only).
- Result interpretation or clinical-decision-support recommendations.
- Order entry (we only react to results, never create orders).
