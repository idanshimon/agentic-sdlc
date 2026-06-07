import pytest
import json
import time
import hmac
import hashlib
import re
import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Helpers & Fakes
# ---------------------------------------------------------------------------

ISO8601_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)


def _is_iso8601(value: str) -> bool:
    """Return True if *value* is a valid ISO 8601 timestamp string."""
    return bool(ISO8601_RE.match(value))


def _hmac_sha256(key: bytes, data: str) -> str:
    """Return hex-encoded HMAC-SHA256 of *data* using *key*."""
    return hmac.new(key, data.encode(), hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# Fake implementations that satisfy the contracts
# ---------------------------------------------------------------------------

class FakeUserService:
    """Minimal in-memory User Service used by contract tests."""

    _USERS: dict[str, dict[str, Any]] = {
        "user-001": {
            "id": "user-001",
            "email": "alice@example.com",
            "name": "Alice Example",
            "createdAt": "2024-01-15T08:30:00Z",
        }
    }

    def get_user(self, user_id: str, token: str) -> dict[str, Any]:
        """
        Simulate GET /users/{id}.

        Returns a response dict with ``status`` and ``body`` keys.
        """
        if not token or not token.startswith("Bearer "):
            return {"status": 401, "body": {"error": "Unauthorized", "message": "Missing or invalid token"}}

        user = self._USERS.get(user_id)
        if user is None:
            return {
                "status": 404,
                "body": {"error": "NotFound", "message": f"User '{user_id}' does not exist"},
            }
        return {"status": 200, "body": dict(user)}


class FakeOrderDatabase:
    """Minimal in-memory Orders database used by contract tests."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    def write_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Persist *payload* and return the stored record with a ``createdAt`` timestamp.

        Raises ``ValueError`` for incomplete payloads.
        """
        required = {"orderId", "userId", "items", "totalAmount"}
        missing = required - payload.keys()
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        record = dict(payload)
        record["createdAt"] = datetime.now(timezone.utc).isoformat()
        self._store[record["orderId"]] = record
        return dict(record)

    def read_order(self, order_id: str) -> dict[str, Any] | None:
        """Return the stored order or *None* if absent."""
        stored = self._store.get(order_id)
        return dict(stored) if stored else None


class FakeEventBus:
    """Minimal in-memory event bus for service-to-service contract tests."""

    def __init__(self) -> None:
        self._published: list[dict[str, Any]] = []
        self._subscribers: dict[str, list] = {}

    def publish(self, topic: str, event: dict[str, Any]) -> None:
        """Publish *event* to *topic*."""
        self._published.append({"topic": topic, "event": event})
        for handler in self._subscribers.get(topic, []):
            handler(event)

    def subscribe(self, topic: str, handler) -> None:
        """Register *handler* for *topic*."""
        self._subscribers.setdefault(topic, []).append(handler)

    @property
    def published(self) -> list[dict[str, Any]]:
        return list(self._published)


class FakePHIRedactionPipeline:
    """
    Inline PHI redaction pipeline.

    Applies HMAC-SHA256 pseudonymisation to the four designated fields and
    runs a Safe Harbor 18-identifier scan on every remaining field.
    """

    _SAFE_HARBOR_PAT