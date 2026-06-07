import hmac
import hashlib
import pytest
from typing import Any
import re


# ---------------------------------------------------------------------------
# Domain constants
# ---------------------------------------------------------------------------

SAFE_HARBOR_FIELDS = {
    "name",
    "birthDate",
    "date_of_birth",
    "dob",
    "address",
    "city",
    "zip",
    "zipCode",
    "postalCode",
    "county",
    "precinct",
    "phone",
    "phoneNumber",
    "fax",
    "faxNumber",
    "email",
    "emailAddress",
    "ssn",
    "socialSecurityNumber",
    "mrn",
    "medicalRecordNumber",
    "healthPlanBeneficiaryNumber",
    "accountNumber",
    "certificateLicenseNumber",
    "vehicleIdentifier",
    "deviceIdentifier",
    "webUrl",
    "url",
    "ipAddress",
    "biometricIdentifier",
    "fullFacePhoto",
    "uniqueIdentifyingNumber",
    "geographic_data",
    "geographicData",
}

_HMAC_SECRET = b"phi-safe-vitals-secret-key-do-not-expose"

_PHI_MAPPING_STORE: dict[str, str] = {}

_AUTHORIZED_REIDENTIFICATION_ROLES = {"reidentification_service", "phi_admin"}


# ---------------------------------------------------------------------------
# Core de-identification helpers
# ---------------------------------------------------------------------------


def _hmac_token(value: str) -> str:
    """Return a deterministic HMAC-SHA256 hex token for *value*."""
    return hmac.new(_HMAC_SECRET, value.encode("utf-8"), hashlib.sha256).hexdigest()


def _store_mapping(token: str, original: str) -> None:
    """Persist *original* → *token* mapping in the PHI-classified store."""
    _PHI_MAPPING_STORE[token] = original


def tokenize_reference(reference: str) -> str:
    """Replace a FHIR reference string with its HMAC-SHA256 token.

    The original value is stored in the PHI mapping store and is NOT
    included in the returned token.
    """
    token = _hmac_token(reference)
    _store_mapping(token, reference)
    return token


def strip_safe_harbor_fields(resource: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow-copied resource with all Safe Harbor fields removed.

    Operates recursively on nested dicts.
    """
    if not isinstance(resource, dict):
        return resource
    cleaned: dict[str, Any] = {}
    for key, value in resource.items():
        if key in SAFE_HARBOR_FIELDS:
            continue
        if isinstance(value, dict):
            cleaned[key] = strip_safe_harbor_fields(value)
        elif isinstance(value, list):
            cleaned[key] = [
                strip_safe_harbor_fields(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            cleaned[key] = value
    return cleaned


def process_fhir_observation_egress(
    observation: dict[str, Any],
) -> dict[str, Any]:
    """Apply full egress de-identification to a FHIR Observation resource.

    Steps:
    1. Tokenize ``subject.reference`` and ``encounter.reference`` if present.
    2. Strip all 18 HIPAA Safe Harbor identifiers from the resource tree.

    Returns the de-identified resource suitable for event bus publication.
    The original PHI values are stored only in the PHI-classified mapping
    store and are absent from the returned dict.
    """
    result = {k: (dict(v) if isinstance(v, dict) else v) for k, v in observation.items()}

    # Step 1 – tokenize FHIR references
    if "subject" in result and isinstance(result["subject"], dict):
        subject = dict(result["subject"])
        if "reference" in subject:
            subject["reference"] = tokenize_reference(subject["reference"])
        result["subject"] = subject

    if "encounter" in result and isinstance(result["encounter"], dict):
        encounter = dict(result["encounter"])
        if "reference" in encounter:
            encounter["reference"] = tokenize_reference(encounter["reference"])
        result["encounter"] = encounter

    # Step 2 – strip Safe Harbor fields
    result = strip_safe_harbor