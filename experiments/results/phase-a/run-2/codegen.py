
```python
"""
Clinical Vital-Signs Ingestion Platform — Contract Tests

This module implements contract tests for the FHIR Normalization Service API,
covering the five contracts defined in the specification.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from http import HTTPStatus

import pytest
from flask import Flask, jsonify, request, Response


# ---------------------------------------------------------------------------
# Minimal Flask provider application
# ---------------------------------------------------------------------------

def create_app() -> Flask:
    """Create and configure the Flask application for contract testing."""
    app = Flask(__name__)
    app.config["TESTING"] = True

    # In-memory store keyed by resource ID
    _store: dict[str, dict[str, Any]] = {}

    def _build_observation(data: dict[str, Any], resource_id: str) -> dict[str, Any]:
        """Build a FHIR R4 Observation resource from raw input data."""
        return {
            "resourceType": "Observation",
            "id": resource_id,
            "status": data.get("status", "final"),
            "code": data["code"],
            "subject": data["subject"],
            "effectiveDateTime": data.get(
                "effectiveDateTime",
                datetime.now(timezone.utc).isoformat(),
            ),
            "valueQuantity": data.get("valueQuantity"),
            "meta": {
                "versionId": "1",
                "lastUpdated": datetime.now(timezone.utc).isoformat(),
            },
        }

    def _error_body(status_code: int, message: str) -> dict[str, Any]:
        """Build a standardised error response body."""
        return {
            "error": {
                "status": status_code,
                "message": message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        }

    def _validate_auth(req: Any) -> bool:
        """Validate Bearer token presence (simplified for contract testing)."""
        auth_header: Optional[str] = req.headers.get("Authorization", "")
        return bool(auth_header and auth_header.startswith("Bearer "))

    # ------------------------------------------------------------------
    # POST /observations  — Contract Test 1
    # ------------------------------------------------------------------
    @app.route("/observations", methods=["POST"])
    def create_observation() -> tuple[Response, int]:
        """Create a new FHIR R4 Observation resource."""
        if not _validate_auth(request):
            return jsonify(_error_body(401, "Unauthorized")), 401

        body: Optional[dict[str, Any]] = request.get_json(silent=True)
        if body is None:
            return (
                jsonify(_error_body(400, "Request body must be valid JSON")),
                400,
            )

        required_fields = ["code", "subject"]
        missing = [f for f in required_fields if f not in body]
        if missing:
            return (
                jsonify(
                    _error_body(
                        400,
                        f"Missing required fields: {', '.join(missing)}",
                    )
                ),
                400,
            )

        resource_id = str(uuid.uuid4())
        observation = _build_observation(body, resource_id)
        _store[resource_id] = observation

        return jsonify(observation), 201

    # ------------------------------------------------------------------
    # GET /observations/<resource_id>  — Contract Tests 2 & 4
    # ------------------------------------------------------------------
    @app.route("/observations/<string:resource_id>", methods=["GET"])
    def get_observation(resource_id: str) -> tuple[Response, int]:
        """Retrieve a FHIR R4 Observation resource by ID."""
        if not _validate_auth(request):
            return jsonify(_error_body(401, "Unauthorized")), 401

        observation = _store.get(re