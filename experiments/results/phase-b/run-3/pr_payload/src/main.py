
```python
"""
phi_safe_vitals_ingestion.py

Secure Real-Time Vitals Ingestion Pipeline with De-Identification and SLA Enforcement.

This module implements the FHIR egress de-identification stage that:
- HMAC-SHA256 tokenizes FHIR Observation.subject and Observation.encounter
- Suppresses all 18 HIPAA Safe Harbor identifiers
- Blocks payloads when de-identification fails
"""

import hashlib
import hmac
import copy
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# HIPAA Safe Harbor – 18 identifier field names (FHIR-mapped where applicable)
# ---------------------------------------------------------------------------
SAFE_HARBOR_FIELDS: frozenset[str] = frozenset(
    [
        # 1. Names
        "name",
        # 2. Geographic data (smaller than state)
        "address",
        "city",
        "zip",
        "postalCode",
        # 3. Dates (except year) – represented as specific date fields
        "birthDate",
        "deceasedDateTime",
        "deceasedDate",
        "date",
        "effectiveDateTime",
        "effectivePeriod",
        "issued",
        # 4. Phone numbers
        "phone",
        "telecom",
        # 5. Fax numbers
        "fax",
        # 6. Email addresses
        "email",
        # 7. Social security numbers
        "ssn",
        "socialSecurityNumber",
        # 8. Medical record numbers
        "mrn",
        "medicalRecordNumber",
        # 9. Health plan beneficiary numbers
        "healthPlanBeneficiaryNumber",
        "insuranceId",
        # 10. Account numbers
        "accountNumber",
        # 11. Certificate/license numbers
        "licenseNumber",
        "certificateNumber",
        # 12. Vehicle identifiers and serial numbers
        "vehicleId",
        "vehicleSerialNumber",
        "licensePlate",
        # 13. Device identifiers and serial numbers
        "deviceId",
        "deviceIdentifier",
        "serialNumber",
        # 14. Web URLs
        "url",
        "website",
        # 15. IP addresses
        "ipAddress",
        "ip",
        # 16. Biometric identifiers
        "biometric",
        "fingerprint",
        "voicePrint",
        # 17. Full-face photographs and comparable images
        "photo",
        "image",
        "photograph",
        # 18. Any other unique identifying number, characteristic, or code
        "uniqueId",
        "identifier",
        "id",
    ]
)

# Fields that must be HMAC-tokenized rather than simply removed
TOKENIZE_FIELDS: frozenset[str] = frozenset(["subject", "encounter"])

# Fields that are suppressed (removed) rather than tokenized
SUPPRESS_FIELDS: frozenset[str] = SAFE_HARBOR_FIELDS - TOKENIZE_FIELDS


class DeIdentificationError(Exception):
    """Raised when de-identification cannot be completed safely."""


def _hmac_token(value: str, secret: bytes) -> str:
    """
    Compute an HMAC-SHA256 token for *value* using *secret*.

    Parameters
    ----------
    value:
        The raw string to tokenize (e.g., a patient reference).
    secret:
        The current rotating HMAC secret as bytes.

    Returns
    -------
    str
        Hex-encoded HMAC-SHA256 digest.
    """
    return hmac.new(secret, value.encode("utf-8"), hashlib.sha256).hexdigest()


def _serialize_value(value: Any) -> str:
    """
    Serialize an arbitrary FHIR field value to a stable string for HMAC input.

    Parameters
    ----------
    value:
        The field value (str, dict, list, etc.).

    Returns
    -------
    str
        A deterministic string representation.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        # Use reference if present (FHIR pattern), else repr
        return value.get("reference", repr(value))
    return repr(value)


def _suppress_phi_recursive(payload: dict[str, Any], secret: bytes) -> dict[str, Any]:
    """
    Recursively walk *payload* and apply de-identification ru