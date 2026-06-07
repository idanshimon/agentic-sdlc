
```python
"""
Contract tests for the Real-Time Vitals Ingestion Platform.

Tests cover:
1. POST /observations -> 201 Created
2. GET /observations/{id} -> 200 OK with schema
3. POST /observations (invalid) -> 400 Bad Request
4. GET /observations/{non-existent-id} -> 404 Not Found
5. DELETE /observations/{id} -> 204 No Content
"""

import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------

class Observation:
    """Represents a de-identified FHIR Observation resource."""

    REQUIRED_FIELDS = {"resourceType", "id", "status", "code", "subject", "effectiveDateTime"}

    def __init__(
        self,
        resource_type: str,
        obs_id: str,
        status: str,
        code: dict,
        subject: str,
        effective_datetime: str,
        encounter: Optional[str] = None,
        value: Optional[dict] = None,
    ) -> None:
        self.resourceType = resource_type
        self.id = obs_id
        self.status = status
        self.code = code
        self.subject = subject
        self.effectiveDateTime = effective_datetime
        self.encounter = encounter
        self.value = value

    def to_dict(self) -> dict:
        """Serialize to dictionary, omitting None values."""
        data: dict[str, Any] = {
            "resourceType": self.resourceType,
            "id": self.id,
            "status": self.status,
            "code": self.code,
            "subject": self.subject,
            "effectiveDateTime": self.effectiveDateTime,
        }
        if self.encounter is not None:
            data["encounter"] = self.encounter
        if self.value is not None:
            data["value"] = self.value
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Observation":
        """Deserialize from dictionary."""
        return cls(
            resource_type=data["resourceType"],
            obs_id=data["id"],
            status=data["status"],
            code=data["code"],
            subject=data["subject"],
            effective_datetime=data["effectiveDateTime"],
            encounter=data.get("encounter"),
            value=data.get("value"),
        )


# ---------------------------------------------------------------------------
# PHI De-identification Sidecar
# ---------------------------------------------------------------------------

class PHIDeidentificationSidecar:
    """
    Replaces PHI identifiers with deterministic HMAC-SHA256 tokens.
    Implements HIPAA Safe Harbor de-identification at connector egress.
    """

    def __init__(self, secret: bytes) -> None:
        self._secret = secret

    def tokenize(self, value: str) -> str:
        """Return a deterministic HMAC-SHA256 hex token for *value*."""
        return hmac.new(self._secret, value.encode(), hashlib.sha256).hexdigest()

    def deidentify(self, observation: dict) -> dict:
        """
        Replace subject and encounter with HMAC tokens and strip remaining
        HIPAA Safe Harbor identifiers.
        """
        result = dict(observation)
        if "subject" in result:
            result["subject"] = self.tokenize(result["subject"])
        if "encounter" in result:
            result["encounter"] = self.tokenize(result["encounter"])
        # Strip any remaining direct identifiers (Safe Harbor fields)
        phi_fields = {
            "patientName", "birthDate", "address", "phone", "fax",
            "email", "ssn", "mrn", "accountNumber", "certificateNumber",
            "vehicleId", "deviceId", "url", "ip", "biometric", "photo",
            "geolocation", "dateOfDeath",
        }
        for field in phi_fields:
            result.pop(field, None)
        return result


# -----------------------------