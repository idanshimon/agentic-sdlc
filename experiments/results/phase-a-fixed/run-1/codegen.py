
```python
"""
vendor_vitals_ingest.py

Contract tests for Vendor Vitals Ingest & Cardiology Event Bus.
Covers:
  - Test 1: mTLS + OAuth 2.0 client_credentials scope enforcement
  - Test 2: 90-day credential rotation gate
  - Test 3: RS256 JWT validation (WebSocket Ingest Gateway)
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import pytest

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("vendor_vitals_ingest")


# ---------------------------------------------------------------------------
# Minimal RSA / JWT helpers (pure-Python, no external crypto deps required
# for the contract test harness — uses stdlib hmac/hashlib stubs so the
# tests can run without cryptography installed; real production code would
# use `cryptography` or `PyJWT`).
# ---------------------------------------------------------------------------

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


class _FakeRSA256Signer:
    """
    Deterministic fake RS256 signer for testing.
    Signs with HMAC-SHA256 keyed on a secret so tests can verify
    without a real RSA key pair.
    """

    def __init__(self, secret: str = "test-rsa-secret") -> None:
        self._secret = secret.encode()

    def sign(self, message: bytes) -> bytes:
        import hmac
        return hmac.new(self._secret, message, hashlib.sha256).digest()

    def verify(self, message: bytes, signature: bytes) -> bool:
        import hmac
        expected = self.sign(message)
        return hmac.compare_digest(expected, signature)


_DEFAULT_SIGNER = _FakeRSA256Signer()


def create_jwt(
    payload: Dict[str, Any],
    signer: _FakeRSA256Signer = _DEFAULT_SIGNER,
    algorithm: str = "RS256",
) -> str:
    header = {"alg": algorithm, "typ": "JWT"}
    header_b64 = _b64url_encode(json.dumps(header).encode())
    payload_b64 = _b64url_encode(json.dumps(payload).encode())
    signing_input = f"{header_b64}.{payload_b64}".encode()
    signature = signer.sign(signing_input)
    return f"{header_b64}.{payload_b64}.{_b64url_encode(signature)}"


def decode_jwt(
    token: str,
    signer: _FakeRSA256Signer = _DEFAULT_SIGNER,
    verify_signature: bool = True,
) -> Dict[str, Any]:
    """
    Decode and optionally verify a JWT.

    Raises:
        ValueError: on malformed token, bad signature, or expiry.
    """
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Malformed JWT: expected 3 parts")

    header_b64, payload_b64, sig_b64 = parts
    header = json.loads(_b64url_decode(header_b64))
    payload = json.loads(_b64url_decode(payload_b64))

    if verify_signature:
        signing_input = f"{header_b64}.{payload_b64}".encode()
        signature = _b64url_decode(sig_b64)
        if not signer.verify(signing_input, signature):
            raise ValueError("JWT signature verification failed")

    now = time.time()
    if "exp" in payload and payload["exp"] < now:
        raise ValueError(f"JWT expired at {payload['exp']}")
    if "nbf" in payload and payload["nbf"] > now:
        raise ValueError(f"JWT not yet valid (nbf={payload['nbf']})")

    return payload


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------

@dataclass
class ClientCertificate:
    """Represents an internal PKI client certificate."""
    vendor_name: str
    not_before: datetime.datetime
    not_after: datetime.datetime