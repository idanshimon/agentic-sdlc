"""Shared pytest config for orchestrator tests.

We disable Cosmos / blob / APIM init at import-time so tests can run
without Azure credentials. The ledger is set to None which the /approve
endpoint handles gracefully (writes are skipped, decisions still persist
on the in-memory run state).
"""
from __future__ import annotations

import os
import sys
import pathlib

# Make the repo root importable so `from apps.orchestrator import ...` works.
REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

# Disable real Azure clients before main.py is imported.
os.environ.setdefault("DISABLE_TELEMETRY", "1")
os.environ.setdefault("LEDGER_DISABLED", "1")
