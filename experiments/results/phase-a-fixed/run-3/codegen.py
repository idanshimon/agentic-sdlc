
```python
"""
Clinical Vitals Ingest & Distribution Platform — Contract Tests

Covers:
  Test 1 — Canonical Redaction Manifest Enforced at All Egress Points
  Test 2 — Vendor Connector mTLS Handshake Rejected Without Valid Internal PKI Certificate
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import ipaddress
import json
import os
import re
import socket
import ssl
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# PKI helpers — generate self-signed CA + leaf certs using only stdlib
# ---------------------------------------------------------------------------

try:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

    _CRYPTO_AVAILABLE = True
except ImportError:  # pragma: no cover
    _CRYPTO_AVAILABLE = False


def _require_crypto() -> None:
    if not _CRYPTO_AVAILABLE:
        pytest.skip("cryptography package not available")


def _generate_rsa_key() -> "rsa.RSAPrivateKey":
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _key_pem(key: "rsa.RSAPrivateKey") -> bytes:
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )


def _cert_pem(cert: "x509.Certificate") -> bytes:
    return cert.public_bytes(serialization.Encoding.PEM)


def _build_ca_cert(
    key: "rsa.RSAPrivateKey", cn: str = "Internal-PKI-CA"
) -> "x509.Certificate":
    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    now = datetime.datetime.utcnow()
    return (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(seconds=1))
        .not_valid_after(now + datetime.timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )


def _build_leaf_cert(
    leaf_key: "rsa.RSAPrivateKey",
    ca_key: "rsa.RSAPrivateKey",
    ca_cert: "x509.Certificate",
    cn: str = "vendor-connector",
) -> "x509.Certificate":
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    now = datetime.datetime.utcnow()
    return (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_cert.subject)
        .public_key(leaf_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(seconds=1))
        .not_valid_after(now + datetime.timedelta(days=90))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False
        )
        .sign(ca_key, hashes.SHA256())
    )


@dataclass
class PKIBundle:
    """Holds PEM bytes for a CA + leaf cert/key pair written to temp files."""

    ca_cert_pem: bytes
    leaf_cert_pem: bytes
    leaf_key_pem: bytes
    _tmpdir: tempfile.TemporaryDirectory = field(
        default_factory=tempfile.TemporaryDirectory, repr=False
    )

    # Paths (populated by __post_init__)
    ca_cert_path: str = field(init=False)
    leaf_cert_path: str = field(init=False)
    leaf_key_path: str = field(init=False)

    def __post_init__(self) -> None:
        d = self._tmpdir.name
        self.ca_cert_path = os.path.join(d, "ca.pem")
   