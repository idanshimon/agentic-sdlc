
```python
"""
Clinical Device Event Ingestion & Distribution Platform
Contract Tests Module

Implements contract tests for:
1. HIPAA §164.514(b)(2) Egress Redaction
2. Vendor Connector mTLS + OAuth 2.0 client_credentials Enforcement
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ===========================================================================
# Domain models
# ===========================================================================

@dataclass
class DeviceTelemetryEvent:
    """Raw device telemetry event containing all 18 HIPAA identifiers."""

    event_id: str
    # 1. Names
    patient_name: str
    # 2. Geographic data finer than state
    address: str
    city: str
    county: str
    zip_code: str
    state: str
    # 3. Dates (other than year)
    date_of_birth: str          # e.g. "1985-04-12"
    admission_date: str
    discharge_date: str
    date_of_death: str
    # 4. Phone numbers
    phone_number: str
    # 5. Fax numbers
    fax_number: str
    # 6. Email addresses
    email: str
    # 7. Social Security numbers
    ssn: str
    # 8. Medical record numbers
    mrn: str
    # 9. Health plan beneficiary numbers
    health_plan_beneficiary: str
    # 10. Account numbers
    account_number: str
    # 11. Certificate/license numbers
    certificate_number: str
    # 12. Vehicle identifiers / serial numbers
    vehicle_serial: str
    # 13. Device identifiers and serial numbers
    device_serial: str
    # 14. Web URLs
    url: str
    # 15. IP addresses
    ip_address: str
    # 16. Biometric identifiers
    biometric_id: str
    # 17. Full-face photographs (represented as reference)
    photo_reference: str
    # 18. Any other unique identifying number
    unique_id: str
    # Payload
    telemetry_payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class RedactedEvent:
    """Event after HIPAA egress redaction — safe for clinical event bus."""

    event_id: str
    state: str                  # coarsened to state only
    year_of_birth: Optional[str]
    tokenized_fields: Dict[str, str]   # identifier_name -> surrogate token
    telemetry_payload: Dict[str, Any]
    timestamp: str
    redaction_audit_ref: str    # reference to audit log entry


@dataclass
class AuditLogEntry:
    """Structured audit log entry for a redaction action."""

    audit_id: str
    originating_event_id: str
    action: str
    redacted_fields: List[str]
    timestamp: str
    performed_by: str = "EgressRedactionService"


@dataclass
class ConnectorConfig:
    """Vendor connector authentication configuration."""

    connector_id: str
    certificate_pem: str        # PEM-encoded certificate (simulated)
    issued_by_internal_pki: bool
    oauth_token: str
    token_fleet_scope: str
    target_fleet: str


@dataclass
class GatewayResponse:
    """Response from the Vendor Gateway."""

    status_code: int
    accepted: bool
    rejection_reason: Optional[str]
    siem_event_logged: bool


# ===========================================================================
# HIPAA §164.514(b)(2) — 18 Identifier definitions
# ===========================================================================

HIPAA_18_IDENTIFIER_FIELDS: List[str] = [
    "patient_name",
    "address",
    "city",
    "county",
    "zip_code",
    "date_of_birth",
    "admission_date",
    "discharge_date",
    "date_of_death",
    "phone_number",
    "fax_number",
    "email",
    "ssn",
    "mrn",
    "health_p