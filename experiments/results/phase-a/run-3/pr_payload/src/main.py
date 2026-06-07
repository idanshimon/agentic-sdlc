
```python
"""
Contract tests for the Clinical Vitals Ingest Platform.

Tests cover:
1. Vendor WebSocket Gateway dual-factor auth enforcement
2. Internal Authorization Server token issuance
3. PHI Tokenization Service HIPAA Safe Harbor identifier replacement
4. FHIR Observation resource schema validation
5. End-to-end ingest pipeline latency SLA
"""

import json
import time
import uuid
import hashlib
import unittest
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch, PropertyMock


# ---------------------------------------------------------------------------
# Domain models / stubs used across tests
# ---------------------------------------------------------------------------

@dataclass
class VendorCertificate:
    """Represents an mTLS client certificate presented by a vendor."""
    cn: str
    san: List[str]
    is_valid: bool = True


@dataclass
class OAuthToken:
    """Represents an OAuth 2.0 bearer token."""
    access_token: str
    scope: str
    expires_in: int
    token_type: str = "Bearer"

    def is_expired(self) -> bool:
        return self.expires_in <= 0


@dataclass
class FHIRObservation:
    """Minimal FHIR R4 Observation resource."""
    resource_type: str
    id: str
    status: str
    code: Dict[str, Any]
    subject: Dict[str, str]
    effective_date_time: str
    value_quantity: Dict[str, Any]
    device: Optional[Dict[str, str]] = None
    performer: Optional[List[Dict[str, str]]] = None
    # Raw PHI fields (pre-tokenization)
    patient_name: Optional[str] = None
    mrn: Optional[str] = None
    device_id: Optional[str] = None
    geographic_data: Optional[str] = None


@dataclass
class TokenizedObservation:
    """FHIR Observation with PHI replaced by reversible tokens."""
    resource_type: str
    id: str
    status: str
    code: Dict[str, Any]
    subject: Dict[str, str]          # subject.reference is now a token
    effective_date_time: str          # year-only or tokenized
    value_quantity: Dict[str, Any]
    patient_name_token: Optional[str] = None
    mrn_token: Optional[str] = None
    device_id_token: Optional[str] = None
    geographic_data_token: Optional[str] = None
    phi_fields_present: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Service stubs
# ---------------------------------------------------------------------------

class ConnectorRegistry:
    """Registry of approved vendor connector certificates."""

    _approved: Dict[str, List[str]] = {
        "vendor-acme": ["acme.vitals.example.com"],
        "vendor-beta": ["beta.vitals.example.com"],
    }

    def is_approved(self, cn: str, san: List[str]) -> bool:
        if cn not in self._approved:
            return False
        approved_sans = self._approved[cn]
        return any(s in approved_sans for s in san)


class InternalAuthorizationServer:
    """
    Issues short-lived OAuth 2.0 client-credentials tokens scoped to
    `vitals:ingest` after validating the vendor certificate against the
    connector registry.
    """

    REQUIRED_SCOPE = "vitals:ingest"
    TOKEN_TTL_SECONDS = 300

    def __init__(self, registry: ConnectorRegistry) -> None:
        self._registry = registry

    def issue_token(self, certificate: VendorCertificate) -> Optional[OAuthToken]:
        """
        Returns an OAuthToken if the certificate is valid and registered,
        otherwise returns None.
        """
        if not certificate.is_valid:
            return None
        if not self._registry.is_approved(certificate.cn, certificate.san):
            return None
        raw = f"{certificate.cn}:{uuid.uuid4()}"
        token_value = hashlib.sha256(raw.encode()).hexdigest()
        return OAuthToken(
            access_token=token_value,
            scope=self.REQUIRED_SCOPE,
            expires_in=self.TOKEN_TTL_SECONDS,
        )

    def intro