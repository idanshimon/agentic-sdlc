
```python
"""
hipaa_safe_harbor_pseudonymization.py

Implementation of HIPAA Safe Harbor pseudonymization transform and vendor
connector authentication for the Real-Time Vitals Ingest Pipeline.
"""

import hashlib
import hmac
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)

# The 18 HIPAA Safe Harbor identifier field names (canonical mapping)
HIPAA_SAFE_HARBOR_FIELDS = [
    "name",
    "geographic_subdivisions",
    "dates",
    "phone_number",
    "fax_number",
    "email",
    "ssn",
    "medical_record_number",
    "health_plan_beneficiary_number",
    "account_number",
    "certificate_license_number",
    "vehicle_identifier",
    "device_identifier",
    "web_url",
    "ip_address",
    "biometric_identifier",
    "full_face_photo",
    "unique_identifying_number",
]

# Aliases used in FHIR / test payloads mapped to canonical categories
HIPAA_FIELD_ALIASES: dict[str, str] = {
    "name": "name",
    "address": "geographic_subdivisions",
    "date_of_birth": "dates",
    "birth_date": "dates",
    "birthDate": "dates",
    "phone": "phone_number",
    "phone_number": "phone_number",
    "fax": "fax_number",
    "email": "email",
    "ssn": "ssn",
    "mrn": "medical_record_number",
    "medical_record_number": "medical_record_number",
    "health_plan_id": "health_plan_beneficiary_number",
    "account_number": "account_number",
    "license_number": "certificate_license_number",
    "vehicle_id": "vehicle_identifier",
    "device_id": "device_identifier",
    "url": "web_url",
    "ip_address": "ip_address",
    "biometric": "biometric_identifier",
    "photo": "full_face_photo",
    "unique_id": "unique_identifying_number",
}


@dataclass
class AuditLogEntry:
    """Records which HIPAA field categories were acted upon during transform."""

    timestamp: str
    resource_id: Optional[str]
    categories_acted_upon: list[str]
    subject_pseudonymized: bool
    encounter_pseudonymized: bool


@dataclass
class EgressTransformResult:
    """Result of applying the egress pseudonymization transform."""

    published_payload: dict[str, Any]
    audit_log: AuditLogEntry


class HIPAASafeHarborEgressTransform:
    """
    Deterministic HMAC-SHA256 pseudonymization transform applied at egress.

    Replaces FHIR Observation subject and encounter references with HMAC-SHA256
    pseudonyms and removes all 18 HIPAA Safe Harbor identifiers.
    """

    def __init__(self, secret_key: bytes) -> None:
        """
        Initialise the transform with a Privacy-office-managed secret key.

        Args:
            secret_key: HMAC secret key bytes managed by the Privacy Office.
        """
        if not secret_key:
            raise ValueError("secret_key must be non-empty bytes")
        self._secret_key = secret_key

    def _pseudonymize(self, value: str) -> str:
        """
        Produce a deterministic HMAC-SHA256 pseudonym for *value*.

        Args:
            value: The raw identifier string to pseudonymize.

        Returns:
            Hex-encoded HMAC-SHA256 digest.
        """
        return hmac.new(
            self._secret_key,
            value.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def transform(self, fhir_observation: dict[str, Any]) -> EgressTransformResult:
        """
        Apply the HIPAA Safe Harbor egress transform to a FHIR Observation.

        Steps:
        1. Deep-copy the payload.
        2. Pseudonymize ``subject.reference`` and ``encounter.reference``.
        3. Remove / pseudonymize all 18 HIPAA Safe Harbor identifier fields.
        4. Emit an audit log entry.

        Args:
            fhir_observation: Raw FHIR Observation dict from the ingest pipeline.

        Returns:
            EgressTransformResult containing the sanitised payload and audit log.
        """
        payload: dict[str, Any] = json.loads(json.dumps(fhir_observation))

 