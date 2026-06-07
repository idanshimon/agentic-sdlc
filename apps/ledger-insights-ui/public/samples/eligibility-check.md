# Patient Eligibility Check Service

## Goal
Build a service that checks insurance eligibility for incoming patients before they are scheduled.

## Requirements

1. The system must look up patient access using their MRN. Patient access means the level of clinical data the requesting user is permitted to view.
2. When a patient arrives, the service contacts the payer to verify coverage. Use the standard 270/271 EDI flow. Cache responses for 24 hours.
3. If the patient has multiple insurance plans, query primary first, then secondary. Use BizTalk or Logic Apps for orchestration depending on cost.
4. Log all eligibility responses for audit. Include the patient MRN, payer ID, and response code. Retain for 7 years per HIPAA.
5. High priority bugs must be addressed quickly. PHI must never appear in error logs.
6. The endpoint must be available 24/7. Acceptable response time is under 2 seconds.
